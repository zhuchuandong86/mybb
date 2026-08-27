import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
import json
import config
import time
from datetime import datetime, timedelta
from urllib.parse import urlparse
import email.utils
import trafilatura
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
from googlenewsdecoder import gnewsdecoder

# =====================================================================
# 已知会拦爬虫的域名 —— 与其反复请求换来 403/验证页污染正文，不如直接跳过，
# 只用 RSS 自带的 description 兜底。省时间，也降低整个 IP 被拉黑的风险。
# 后续如果发现其他域名同样被拦，往这个集合里加就行。
# =====================================================================
ANTI_BOT_DOMAINS = {
    "mybroadband.co.za",
}

MIN_CONTENT_CHARS = 200  # 低于这个长度不算"抓到全文"，只是噪音（如 Cookie 提示、验证页残留文字）


# =====================================================================
# Session 工厂：连接池开大，避免 "Connection pool is full" 告警
# =====================================================================
def make_session():
    session = requests.Session()
    adapter = HTTPAdapter(
        pool_connections=20,
        pool_maxsize=40,
        max_retries=Retry(total=2, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503])
    )
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,*/*",
        "Accept-Language": "en-US,en;q=0.9",
    })
    return session

def get_rss_headers():
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
    }


def is_anti_bot_domain(url):
    try:
        host = urlparse(url).netloc.lower()
        return any(host == d or host.endswith("." + d) for d in ANTI_BOT_DOMAINS)
    except Exception:
        return False


# =====================================================================
# 新增：优先从 RSS 的 <content:encoded> 里拿全文
# 很多 WordPress 站点（这几个南非科技媒体大概率是）在 RSS 里就直接带了完整正文，
# 根本不需要再去请求文章页面 —— 从源头绕开反爬/跳转问题，这是最治本的改法。
# =====================================================================
def extract_content_encoded(item):
    """兼容 BS4 不同解析器对 content:encoded 命名空间标签的处理方式"""
    tag = item.find("content:encoded") or item.find("encoded")
    if not tag or not tag.get_text(strip=True):
        return ""
    soup = BeautifulSoup(tag.get_text(), "html.parser")
    text = soup.get_text(" ", strip=True)
    return text


# =====================================================================
# 全文抓取：自己下载 HTML -> 传给 trafilatura 解析（不让它自己发请求）
# =====================================================================
def is_google_news_link(url):
    try:
        return urlparse(url).hostname == "news.google.com"
    except Exception:
        return False


def decode_google_news_link(url):
    """
    Google News 的 /rss/articles/... 链接不是普通跳转，而是加密过的 token：
    真实地址需要 ①从 https://news.google.com/articles/{token} 页面里取出签名+时间戳，
    ②拿这两个参数去调 Google 内部的 batchexecute 接口才能换出真实 URL。
    这里复用社区维护的 googlenewsdecoder 库实现这套流程，普通 HEAD 请求是解不出来的。
    失败返回 None（调用方会退回 description，不会再尝试拿 Google 的壳页面当正文）。
    """
    try:
        result = gnewsdecoder(url, interval=1)
        if result.get("status"):
            return result["decoded_url"]
    except Exception:
        pass
    return None


def resolve_redirect(url, session):
    """解析普通跳转（非 Google News 链接走这里，比如某些站点自己的短链）"""
    try:
        resp = session.head(url, allow_redirects=True, timeout=8)
        return resp.url
    except Exception:
        return url

def fetch_full_content(article, session, max_chars=1500):
    """
    抓取单篇文章全文，在线程池中调用。
    返回时额外记录 content_source 字段，标明正文到底是怎么来的：
      "feed"        —— RSS 的 content:encoded 直接给了全文，没发起页面请求
      "scrape"      —— 请求了文章页并成功提取到足够长度的正文
      "description" —— 全文抓取失败/被跳过，退回 RSS 摘要
      "none"        —— 什么都没拿到
    这样最后能按来源拆分统计，而不是一个笼统的成功率。
    """
    url = article.get("link", "")

    # ① 如果 RSS 里已经带了 content:encoded 全文，直接用，不发页面请求
    feed_text = article.pop("_feed_full_content", "")
    if len(feed_text) >= MIN_CONTENT_CHARS:
        article["full_content"] = feed_text[:max_chars]
        article["content_source"] = "feed"
        return article

    if not url:
        article["full_content"] = ""
        article["content_source"] = "none"
        return article

    # ② 已知反爬域名：不浪费请求，直接退回 description
    if is_anti_bot_domain(url):
        article["full_content"] = ""
        article["content_source"] = "description" if article.get("description") else "none"
        return article

    full_content = ""
    try:
        # ③ Google News 链接需要专门解密，不能用普通 HEAD 跳转解析
        if is_google_news_link(url):
            real_url = decode_google_news_link(url)
            if not real_url:
                # 解码失败：原始链接指向的是 Google 的壳页面，硬抓只会拿到无关内容，不如直接放弃
                article["full_content"] = ""
                article["content_source"] = "description" if article.get("description") else "none"
                return article
            if is_anti_bot_domain(real_url):
                # 解码后发现真实来源正好是反爬域名（如周报模式下 MyBroadband 走了 Google News fallback）
                article["full_content"] = ""
                article["content_source"] = "description" if article.get("description") else "none"
                return article
        else:
            real_url = resolve_redirect(url, session)

        resp = session.get(real_url, timeout=10, allow_redirects=True)
        if resp.status_code != 200:
            raise ValueError(f"HTTP {resp.status_code}")

        html = resp.text

        text = trafilatura.extract(
            html,
            url=real_url,
            include_comments=False,
            include_tables=False,
            no_fallback=False,
            favor_precision=False,
        )
        if text:
            full_content = text.replace("\n", " ").strip()[:max_chars]

        if not full_content:
            soup = BeautifulSoup(html, "html.parser")
            for tag in soup(["script", "style", "nav", "header", "footer", "aside", "iframe"]):
                tag.decompose()
            container = soup.find("article") or soup.find("main") or soup.body
            if container:
                paras = [p.get_text(" ", strip=True) for p in container.find_all("p")]
                full_content = " ".join(p for p in paras if len(p) > 30)[:max_chars]

    except Exception:
        pass  # 静默失败，保留 description 兜底

    # ③ 应用最低长度门槛：太短的"正文"（验证页残留文字/Cookie提示）不算数
    if len(full_content) >= MIN_CONTENT_CHARS:
        article["full_content"] = full_content
        article["content_source"] = "scrape"
    else:
        article["full_content"] = ""
        article["content_source"] = "description" if article.get("description") else "none"

    return article

def fetch_all_full_contents(articles, max_workers=5):
    """并发全文抓取，所有线程共享同一个 Session（连接池复用）"""
    session = make_session()
    total = len(articles)
    print(f"\n📖 开始全文抓取，共 {total} 篇，并发={max_workers}...")

    results = [None] * total
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_idx = {
            executor.submit(fetch_full_content, articles[i], session): i
            for i in range(total)
        }
        done = 0
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                results[idx] = future.result()
            except Exception:
                articles[idx]["full_content"] = ""
                articles[idx]["content_source"] = "none"
                results[idx] = articles[idx]
            done += 1
            if done % 10 == 0 or done == total:
                ok = sum(1 for r in results if r and r.get("content_source") in ("feed", "scrape"))
                print(f"  进度 {done}/{total}，成功提取全文: {ok} 篇")

    session.close()
    return [r for r in results if r is not None]


# =====================================================================
# 按来源统计成功率 —— 取代原来笼统的一个百分比
# =====================================================================
def print_source_stats(articles):
    stats = defaultdict(lambda: defaultdict(int))
    for a in articles:
        src = a["source"]
        stats[src][a.get("content_source", "none")] += 1
        stats[src]["_total"] += 1

    print("\n📊 按来源抓取成功率：")
    print(f"  {'来源':<20}{'总数':>6}{'feed全文':>10}{'页面抓取':>10}{'仅摘要':>8}{'无内容':>8}")
    for src, s in stats.items():
        print(f"  {src:<20}{s['_total']:>6}{s['feed']:>10}{s['scrape']:>10}{s['description']:>8}{s['none']:>8}")

    total = len(articles)
    full_text_ok = sum(1 for a in articles if a.get("content_source") in ("feed", "scrape"))
    print(f"\n  全文获取成功率: {full_text_ok}/{total} ({full_text_ok/max(total,1)*100:.0f}%) "
          f"[不含仅有摘要的条目]")


# =====================================================================
# RSS 抓取
# =====================================================================
def scrape_google_rss(source_name, query, days="1d"):
    articles = []
    print(f"--- [Google RSS] 抓取 {source_name} (过去 {days}) ---")
    url = (f"https://news.google.com/rss/search"
           f"?q={query}+when:{days}&hl=en-ZA&gl=ZA&ceid=ZA:en")
    try:
        resp = requests.get(url, headers=get_rss_headers(), timeout=20)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.content, "xml")
            for item in soup.find_all("item"):
                title = item.title.get_text(strip=True).rsplit(" - ", 1)[0]
                link  = item.link.get_text(strip=True)
                desc  = item.description.get_text(strip=True) if item.description else ""
                articles.append({"source": source_name, "title": title,
                                  "link": link, "description": desc, "full_content": "",
                                  "_feed_full_content": ""})  # Google News 聚合feed没有全文
            print(f"✅ {source_name} (Google): {len(articles)} 条")
        else:
            print(f"❌ {source_name} (Google): HTTP {resp.status_code}")
    except Exception as e:
        print(f"❌ {source_name} (Google) Error: {e}")
    return articles

def scrape_direct_rss(source_name, rss_url, days="1d"):
    articles = []
    print(f"--- [Direct RSS] 抓取 {source_name} (官方 / 过去 {days}) ---")
    try:
        days_int = int(days.replace("d", ""))
    except ValueError:
        days_int = 1
    cutoff = datetime.now().astimezone() - timedelta(days=days_int)

    try:
        resp = requests.get(rss_url, headers=get_rss_headers(), timeout=15)
        if resp.status_code != 200:
            print(f"❌ {source_name} (Direct): HTTP {resp.status_code}")
            return None

        soup = BeautifulSoup(resp.content, "xml")
        valid = 0
        feed_full_count = 0
        for item in soup.find_all("item"):
            pub_str = item.pubDate.get_text(strip=True) if item.pubDate else None
            in_range = True
            if pub_str:
                try:
                    art_date = email.utils.parsedate_to_datetime(pub_str)
                    if art_date.tzinfo is None:
                        art_date = art_date.astimezone()
                    in_range = art_date >= cutoff
                except Exception:
                    pass
            if in_range:
                title = item.title.get_text(strip=True)
                link  = item.link.get_text(strip=True)
                desc  = item.description.get_text(strip=True) if item.description else ""
                feed_full = extract_content_encoded(item)
                if feed_full:
                    feed_full_count += 1
                articles.append({"source": source_name, "title": title,
                                  "link": link, "description": desc, "full_content": "",
                                  "_feed_full_content": feed_full})
                valid += 1

        total_items = len(soup.find_all("item"))
        print(f"✅ {source_name} (Direct): 过滤后 {valid} 条 (共 {total_items} 条)，"
              f"其中 {feed_full_count} 条 RSS 自带全文")
    except Exception as e:
        print(f"❌ {source_name} (Direct) Error: {e}")
        return None

    return articles

# =====================================================================
# 数据源配置
# =====================================================================
SOURCES = [
    {"name": "TechCentral",      "rss": "https://techcentral.co.za/feed/",        "google_query": "site:techcentral.co.za"},
    {"name": "MyBroadband",      "rss": "https://mybroadband.co.za/news/feed/",    "google_query": "site:mybroadband.co.za"},
    {"name": "ITWeb",            "rss": "https://www.itweb.co.za/rss",             "google_query": "site:itweb.co.za"},
    {"name": "IT News Africa",   "rss": "https://www.itnewsafrica.com/feed/",      "google_query": "South Africa telecom site:itnewsafrica.com"},
    {"name": "Connecting Africa","rss": None,                                       "google_query": "South Africa telecom site:connectingafrica.com"},
    {"name": "Vodacom News",     "rss": None,                                       "google_query": "Vodacom South Africa news announcement"},
    {"name": "MTN Group News",   "rss": None,                                       "google_query": "MTN South Africa news announcement"},
    {"name": "ICASA / 监管政策", "rss": None,                                       "google_query": "ICASA South Africa spectrum telecom regulation"},
]

def scrape_all():
    all_articles = []
    current_days = config.TIME_RANGE
    mode = config.REPORT_MODE
    print(f"🚀 启动爬虫 | 模式: {mode} | 时间范围: {current_days} | 数据源: {len(SOURCES)} 个\n")

    for src in SOURCES:
        news_items = []
        if mode == "DAILY" and src.get("rss"):
            news_items = scrape_direct_rss(src["name"], src["rss"], days=current_days)

        if not news_items:  # 空列表 [] 也触发 Fallback
            reason = "无直连RSS" if not src.get("rss") else ("周/月报模式" if mode != "DAILY" else "Direct RSS 空/失败")
            print(f"🔄 [{src['name']}] 切换 Google 源 ({reason})...")
            news_items = scrape_google_rss(src["name"], src["google_query"], days=current_days)

        if news_items:
            all_articles.extend(news_items)

    # 去重
    unique, seen = [], set()
    for a in all_articles:
        if a["link"] not in seen:
            unique.append(a)
            seen.add(a["link"])
    print(f"\n📊 去重后共 {len(unique)} 条，开始全文抓取...")

    unique = fetch_all_full_contents(unique, max_workers=5)
    return unique

if __name__ == "__main__":
    data = scrape_all()
    with open(config.RAW_NEWS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print_source_stats(data)

    full_text_ok = sum(1 for a in data if a.get("content_source") in ("feed", "scrape"))
    print(f"\n🎉 完成！共 {len(data)} 条，全文成功 {full_text_ok} 篇 ({full_text_ok/max(len(data),1)*100:.0f}%)。")
