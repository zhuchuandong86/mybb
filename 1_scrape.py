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
    通用函数：通过 Google News RSS 抓取指定网站
    """
    articles = []
    print(f"--- 正在抓取 {source_name} (Google渠道 / 过去 {days}) ---")
    
    rss_url = f"https://news.google.com/rss/search?q={query}+when:{days}&hl=en-ZA&gl=ZA&ceid=ZA:en"
    
    try:
        resp = requests.get(rss_url, headers=get_headers(), timeout=20)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.content, 'xml')
            items = soup.find_all('item')
            
            for item in items:
                title = item.title.get_text(strip=True)
                title = title.replace(f" - {source_name}", "").replace(" - MyBroadband", "")
                link = item.link.get_text(strip=True)
                
                articles.append({
                    "source": source_name, 
                    "title": title, 
                    "link": link
                })
            print(f"✅ {source_name}: 成功获取 {len(items)} 条")
        else:
            print(f"❌ {source_name}: 请求失败 Code {resp.status_code}")
            
    except Exception as e:
        print(f"❌ {source_name} Error: {e}")
        
    return articles

def scrape_direct_rss(source_name, rss_url, days="1d"):
    """
    专用函数：直接抓取网站官方 RSS (解决 TechCentral Google 抓取不到的问题)
    🔥 修改：增加时间过滤逻辑，精准控制时间范围
    """
    articles = []
    print(f"--- 正在抓取 {source_name} (官方直连 / 过去 {days}) ---")
    
    # 1. 解析时间范围 (例如 "1d" -> 1, "7d" -> 7)
    try:
        days_int = int(days.replace("d", ""))
    except ValueError:
        days_int = 1

    # 2. 计算截止时间 (使用当前时区时间)
    cutoff_date = datetime.now().astimezone() - timedelta(days=days_int)
    
    try:
        resp = requests.get(rss_url, headers=get_headers(), timeout=20)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.content, 'xml')
            items = soup.find_all('item')
            
            # 不再硬性截取前15条，而是遍历所有条目进行时间判断
            count = 0
            for item in items: 
                # 解析发布时间
                pub_date_str = item.pubDate.get_text(strip=True) if item.pubDate else None
                
                is_within_range = False
                if pub_date_str:
                    try:
                        # 解析 RSS 时间 (RFC 822)
                        article_date = email.utils.parsedate_to_datetime(pub_date_str)
                        
                        # 如果 article_date 没带时区，假定为当前时区（防止报错）
                        if article_date.tzinfo is None:
                             article_date = article_date.astimezone()
                             
                        # 比较时间
                        if article_date >= cutoff_date:
                            is_within_range = True
                    except Exception as e:
                        print(f"⚠️ 日期解析错误: {pub_date_str} - {e}")
                
                # 如果在时间范围内，则加入
                if is_within_range:
                    title = item.title.get_text(strip=True)
                    link = item.link.get_text(strip=True)
                    
                    articles.append({
                        "source": source_name, 
                        "title": title, 
                        "link": link
                    })
                    count += 1
            
            print(f"✅ {source_name}: 成功获取 {count} 条 (过滤后)")
        else:
            print(f"❌ {source_name}: 请求失败 Code {resp.status_code}")
    except Exception as e:
        print(f"❌ {source_name} Error: {e}")
        
    return articles

def scrape_all():
    all_articles = []
    
    # 从 config 读取时间范围
    current_days = config.TIME_RANGE  
    print(f"当前运行模式: {config.REPORT_MODE}, 抓取范围: {current_days}")

    # === 1. Google News 源 ===
    google_sources = [
        {"name": "MyBroadband", "query": "site:mybroadband.co.za"},
        {"name": "ITWeb",       "query": "site:itweb.co.za"}
    ]

    for src in google_sources:
        news = scrape_google_rss(src["name"], src["query"], days=current_days)
        all_articles.extend(news)

    # === 2. 官方源 TechCentral ===
    # 🔥 修改点：传入 days=current_days 参数
    tc_news = scrape_direct_rss("TechCentral", "https://techcentral.co.za/feed/", days=current_days)
  
    all_articles.extend(tc_news)

    # 去重逻辑
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
