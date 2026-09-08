import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
import json
import config
from datetime import datetime, timedelta
import email.utils
import trafilatura
from concurrent.futures import ThreadPoolExecutor, as_completed

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

# =====================================================================
# 全文抓取：自己下载 HTML -> 传给 trafilatura 解析（不让它自己发请求）
# 关键修复：
#   1. 用 session.head() 解析 Google News 跳转链接，得到真实 URL
#   2. 用 session.get() 下载 HTML
#   3. 把 HTML 文本传给 trafilatura.extract()，trafilatura 只做解析
#      => 彻底避免 trafilatura 自己建连接池 => 消除 "Connection pool is full"
# =====================================================================
def resolve_redirect(url, session):
    """解析重定向，获取真实文章 URL（主要处理 Google News 跳转链接）"""
    try:
        resp = session.head(url, allow_redirects=True, timeout=8)
        return resp.url
    except Exception:
        return url

def fetch_full_content(article, session, max_chars=1500):
    """抓取单篇文章全文，在线程池中调用"""
    url = article.get("link", "")
    if not url:
        article["full_content"] = ""
        return article

    full_content = ""
    try:
        # ① 解析真实 URL（处理 Google News 跳转）
        real_url = resolve_redirect(url, session)

        # ② 用统一 session 下载 HTML
        resp = session.get(real_url, timeout=10, allow_redirects=True)
        if resp.status_code != 200:
            raise ValueError(f"HTTP {resp.status_code}")

        html = resp.text

        # ③ trafilatura 只做解析，传入已下载的 HTML，不让它自己发请求
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

        # ④ trafilatura 没提取到时，BS4 段落兜底
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

    article["full_content"] = full_content
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
                results[idx] = articles[idx]
            done += 1
            if done % 10 == 0 or done == total:
                ok = sum(1 for r in results if r and r.get("full_content"))
                print(f"  进度 {done}/{total}，成功提取全文: {ok} 篇")

    session.close()
    return [r for r in results if r is not None]

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
                                  "link": link, "description": desc, "full_content": ""})
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
                articles.append({"source": source_name, "title": title,
                                  "link": link, "description": desc, "full_content": ""})
                valid += 1

        total_items = len(soup.find_all("item"))
        print(f"✅ {source_name} (Direct): 过滤后 {valid} 条 (共 {total_items} 条)")
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

        if not news_items:  # 修复原 Bug：空列表 [] 也触发 Fallback
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
    ok = sum(1 for a in data if a.get("full_content"))
    print(f"\n🎉 完成！共 {len(data)} 条，全文成功 {ok} 篇 ({ok/max(len(data),1)*100:.0f}%)。")
