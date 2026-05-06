import requests
from bs4 import BeautifulSoup
import json
import config
from datetime import datetime, timedelta
import email.utils
import time
import trafilatura
from concurrent.futures import ThreadPoolExecutor, as_completed

def get_headers():
    return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Accept': 'application/rss+xml, application/xml, text/xml, */*',
    }

# =====================================================================
# 【新增】全文抓取函数
# 使用 trafilatura 库（专为文章正文提取设计，效果远好于 BeautifulSoup）
# 失败时 fallback 到 BS4 段落提取
# =====================================================================
def fetch_full_content(article, max_chars=1500):
    """
    抓取单篇文章全文，返回更新后的 article 字典。
    设计为在线程池中调用。
    """
    url = article.get('link', '')
    if not url:
        return article

    full_content = ""
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            text = trafilatura.extract(
                downloaded,
                include_comments=False,
                include_tables=False,
                no_fallback=False
            )
            if text:
                full_content = text.replace('\n', ' ').strip()[:max_chars]

        # Fallback: 如果 trafilatura 没提取到内容，用 BS4 兜底
        if not full_content:
            resp = requests.get(url, headers=get_headers(), timeout=8)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.content, 'html.parser')
                for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe']):
                    tag.decompose()
                container = soup.find('article') or soup.find('main') or soup.body
                if container:
                    paragraphs = container.find_all('p')
                    full_content = ' '.join(
                        p.get_text(strip=True) for p in paragraphs
                        if len(p.get_text(strip=True)) > 30
                    )[:max_chars]

    except Exception:
        pass  # 静默失败，保留 description 兜底

    article['full_content'] = full_content
    return article


def fetch_all_full_contents(articles, max_workers=5):
    """
    并发抓取所有文章全文（5线程），并打印进度。
    """
    print(f"\n📖 开始全文抓取，共 {len(articles)} 篇，并发数={max_workers}...")
    results = [None] * len(articles)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_idx = {
            executor.submit(fetch_full_content, articles[i]): i
            for i in range(len(articles))
        }
        done_count = 0
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                results[idx] = future.result()
            except Exception:
                results[idx] = articles[idx]  # 原样保留
            done_count += 1
            # 每完成 10 篇打印一次进度
            if done_count % 10 == 0 or done_count == len(articles):
                success = sum(1 for r in results if r and r.get('full_content'))
                print(f"  进度: {done_count}/{len(articles)}，成功提取全文: {success} 篇")

    # 过滤掉 None（理论上不会有）
    return [r for r in results if r is not None]


# =====================================================================
# 抓取函数（与原版相同，保持不变）
# =====================================================================
def scrape_google_rss(source_name, query, days="1d"):
    """通用函数：通过 Google News RSS 抓取"""
    articles = []
    print(f"--- [Google RSS] 正在抓取 {source_name} (过去 {days}) ---")
    rss_url = f"https://news.google.com/rss/search?q={query}+when:{days}&hl=en-ZA&gl=ZA&ceid=ZA:en"
    try:
        resp = requests.get(rss_url, headers=get_headers(), timeout=20)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.content, 'xml')
            items = soup.find_all('item')
            for item in items:
                title = item.title.get_text(strip=True)
                title = title.rsplit(' - ', 1)[0]
                link = item.link.get_text(strip=True)
                description = item.description.get_text(strip=True) if item.description else ""
                articles.append({
                    "source": source_name,
                    "title": title,
                    "link": link,
                    "description": description,
                    "full_content": ""   # 占位，后续填充
                })
            print(f"✅ {source_name} (Google): 获取 {len(items)} 条")
        else:
            print(f"❌ {source_name} (Google): 请求失败 Code {resp.status_code}")
    except Exception as e:
        print(f"❌ {source_name} (Google) Error: {e}")
    return articles


def scrape_direct_rss(source_name, rss_url, days="1d"):
    """专用函数：直接抓取官方 RSS，含严格时间过滤"""
    articles = []
    print(f"--- [Direct RSS] 正在抓取 {source_name} (官方直连 / 过去 {days}) ---")
    try:
        days_int = int(days.replace("d", ""))
    except ValueError:
        days_int = 1
    cutoff_date = datetime.now().astimezone() - timedelta(days=days_int)

    try:
        resp = requests.get(rss_url, headers=get_headers(), timeout=15)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.content, 'xml')
            items = soup.find_all('item')
            valid_count = 0
            for item in items:
                pub_date_str = item.pubDate.get_text(strip=True) if item.pubDate else None
                is_within_range = False
                if pub_date_str:
                    try:
                        article_date = email.utils.parsedate_to_datetime(pub_date_str)
                        if article_date.tzinfo is None:
                            article_date = article_date.astimezone()
                        if article_date >= cutoff_date:
                            is_within_range = True
                    except Exception:
                        is_within_range = True
                else:
                    is_within_range = True  # 无日期字段则默认保留

                if is_within_range:
                    title = item.title.get_text(strip=True)
                    link = item.link.get_text(strip=True)
                    description = item.description.get_text(strip=True) if item.description else ""
                    articles.append({
                        "source": source_name,
                        "title": title,
                        "link": link,
                        "description": description,
                        "full_content": ""   # 占位，后续填充
                    })
                    valid_count += 1
            print(f"✅ {source_name} (Direct): 过滤后剩余 {valid_count} 条 (共 {len(items)} 条)")
        else:
            print(f"❌ {source_name} (Direct): 请求失败 Code {resp.status_code}")
            return None
    except Exception as e:
        print(f"❌ {source_name} (Direct) Error: {e}")
        return None
    return articles


# =====================================================================
# 数据源配置
# 新增：IT News Africa、Connecting Africa、Vodacom、MTN、ICASA
# =====================================================================
SOURCES = [
    # ——— 原有 3 个通用科技媒体 ———
    {
        "name": "TechCentral",
        "rss": "https://techcentral.co.za/feed/",
        "google_query": "site:techcentral.co.za"
    },
    {
        "name": "MyBroadband",
        "rss": "https://mybroadband.co.za/news/feed/",
        "google_query": "site:mybroadband.co.za"
    },
    {
        "name": "ITWeb",
        "rss": "https://www.itweb.co.za/rss",
        "google_query": "site:itweb.co.za"
    },

    # ——— 新增：电信垂类媒体 ———
    {
        # 专注非洲电信/科技，内容质量高
        "name": "IT News Africa",
        "rss": "https://www.itnewsafrica.com/feed/",
        "google_query": "South Africa telecom site:itnewsafrica.com"
    },
    {
        # Light Reading 旗下非洲电信专栏
        "name": "Connecting Africa",
        "rss": None,   # 无稳定直连 RSS，走 Google
        "google_query": "South Africa telecom site:connectingafrica.com"
    },

    # ——— 新增：运营商官方新闻（通过 Google RSS 监控） ———
    {
        # Vodacom 官网新闻中心
        "name": "Vodacom News",
        "rss": None,
        "google_query": "Vodacom South Africa news announcement"
    },
    {
        # MTN 集团南非业务新闻
        "name": "MTN Group News",
        "rss": None,
        "google_query": "MTN South Africa news announcement"
    },

    # ——— 新增：监管机构 ———
    {
        # ICASA = Independent Communications Authority of South Africa
        # 频谱、牌照、政策的第一手来源
        "name": "ICASA / 监管政策",
        "rss": None,
        "google_query": "ICASA South Africa spectrum telecom regulation"
    },
]


def scrape_all():
    all_articles = []
    current_days = config.TIME_RANGE
    mode = config.REPORT_MODE

    print(f"🚀 启动爬虫 | 模式: {mode} | 时间范围: {current_days}")
    print(f"📡 数据源数量: {len(SOURCES)} 个\n")

    for src in SOURCES:
        news_items = []

        if mode == "DAILY" and src.get("rss"):
            # 日报：优先直连 RSS（实时性最好）
            news_items = scrape_direct_rss(src["name"], src["rss"], days=current_days)

        # 【修复原有 Bug】: 原来是 `if news_items is None`，
        # 空列表 [] 也应该触发 Fallback，改为 `if not news_items`
        if not news_items:
            reason = "无直连RSS / 周月报模式" if not src.get("rss") or mode != "DAILY" else "Direct RSS 失败或返回空"
            print(f"🔄 [{src['name']}] 切换到 Google 源 ({reason})...")
            news_items = scrape_google_rss(src["name"], src["google_query"], days=current_days)

        if news_items:
            all_articles.extend(news_items)

    # ——— 去重（以链接为准）———
    unique_articles = []
    seen_links = set()
    for article in all_articles:
        if article['link'] not in seen_links:
            unique_articles.append(article)
            seen_links.add(article['link'])

    print(f"\n📊 去重后共 {len(unique_articles)} 条新闻，开始抓取全文...")

    # ——— 【核心新增】并发全文抓取 ———
    # 对所有文章并发抓取正文，失败时保留 description 作为兜底
    unique_articles = fetch_all_full_contents(unique_articles, max_workers=5)

    return unique_articles


if __name__ == "__main__":
    data = scrape_all()
    with open(config.RAW_NEWS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    full_count = sum(1 for a in data if a.get('full_content'))
    print(f"\n🎉 爬虫结束，共保存 {len(data)} 条（其中 {full_count} 条已抓取全文）。")
