import requests
from bs4 import BeautifulSoup
import json
import config
from datetime import datetime, timedelta
import email.utils

def get_headers():
    return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Accept': 'application/rss+xml, application/xml, text/xml, */*',
    }

def scrape_google_rss(source_name, query, days="1d"):
    """
    通用函数：通过 Google News RSS 抓取 (适合周报/月报，有历史数据)
    """
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
                # 清理 Google RSS 标题中自带的 " - Source Name" 后缀
                title = title.rsplit(' - ', 1)[0]
                link = item.link.get_text(strip=True)
                
                # 🔥 新增：提取摘要 (Google RSS 的 description 通常包含 HTML，get_text 会自动清理标签)
                description = item.description.get_text(strip=True) if item.description else ""
                
                articles.append({
                    "source": source_name, 
                    "title": title, 
                    "link": link,
                    "description": description  # 保存摘要
                })
            print(f"✅ {source_name} (Google): 获取 {len(items)} 条")
        else:
            print(f"❌ {source_name} (Google): 请求失败 Code {resp.status_code}")
            
    except Exception as e:
        print(f"❌ {source_name} (Google) Error: {e}")
        
    return articles

def scrape_direct_rss(source_name, rss_url, days="1d"):
    """
    专用函数：直接抓取官方 RSS (适合日报，无延迟)
    包含严格的时间过滤逻辑
    """
    articles = []
    print(f"--- [Direct RSS] 正在抓取 {source_name} (官方直连 / 过去 {days}) ---")
    
    # 1. 解析时间范围
    try:
        days_int = int(days.replace("d", ""))
    except ValueError:
        days_int = 1

    # 2. 计算截止时间 (当前时间 - 天数)
    cutoff_date = datetime.now().astimezone() - timedelta(days=days_int)
    
    try:
        resp = requests.get(rss_url, headers=get_headers(), timeout=15)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.content, 'xml')
            items = soup.find_all('item')
            
            valid_count = 0
            for item in items: 
                # 解析发布时间
                pub_date_str = item.pubDate.get_text(strip=True) if item.pubDate else None
                
                is_within_range = False
                if pub_date_str:
                    try:
                        # 解析 RSS 时间 (RFC 822)
                        article_date = email.utils.parsedate_to_datetime(pub_date_str)
                        # 处理时区问题
                        if article_date.tzinfo is None:
                             article_date = article_date.astimezone()
                             
                        # 核心过滤逻辑：只有晚于截止时间的才保留
                        if article_date >= cutoff_date:
                            is_within_range = True
                    except Exception as e:
                        print(f"⚠️ 日期解析警告: {e}")
                        is_within_range = True 
                
                if is_within_range:
                    title = item.title.get_text(strip=True)
                    link = item.link.get_text(strip=True)
                    
                    # 🔥 新增：提取摘要
                    description = item.description.get_text(strip=True) if item.description else ""
                    
                    articles.append({
                        "source": source_name, 
                        "title": title, 
                        "link": link,
                        "description": description # 保存摘要
                    })
                    valid_count += 1
            
            print(f"✅ {source_name} (Direct): 过滤后剩余 {valid_count} 条 (共 {len(items)} 条)")
        else:
            print(f"❌ {source_name} (Direct): 请求失败 Code {resp.status_code}")
            return None # 返回 None 表示失败，触发 Fallback
            
    except Exception as e:
        print(f"❌ {source_name} (Direct) Error: {e}")
        return None
        
    return articles

def scrape_all():
    all_articles = []
    
    current_days = config.TIME_RANGE  
    mode = config.REPORT_MODE
    print(f"🚀 启动爬虫 | 模式: {mode} | 时间范围: {current_days}")

    # 定义所有源及其配置
    sources = [
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
        }
    ]

    for src in sources:
        news_items = []
        
        # === 智能策略选择 ===
        if mode == "DAILY":
            news_items = scrape_direct_rss(src["name"], src["rss"], days=current_days)
        
        if news_items is None or (mode != "DAILY"):
            reason = "周/月报模式" if mode != "DAILY" else "Direct RSS 失败或为空"
            print(f"🔄 切换到 Google 源 ({reason})...")
            news_items = scrape_google_rss(src["name"], src["google_query"], days=current_days)

        if news_items:
            all_articles.extend(news_items)

    # 去重逻辑 (以链接为准)
    unique_articles = []
    seen_links = set()
    for article in all_articles:
        if article['link'] not in seen_links:
            unique_articles.append(article)
            seen_links.add(article['link'])

    return unique_articles

if __name__ == "__main__":
    data = scrape_all()
    # 写入文件
    with open(config.RAW_NEWS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n🎉 爬虫结束，共保存 {len(data)} 条。")
