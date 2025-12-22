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

def scrape_direct_rss(source_name, rss_url):
    """
    专用函数：直接抓取网站官方 RSS (解决 TechCentral Google 抓取不到的问题)
    """
    articles = []
    print(f"--- 正在抓取 {source_name} (官方直连) ---")
    
    try:
        resp = requests.get(rss_url, headers=get_headers(), timeout=20)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.content, 'xml')
            items = soup.find_all('item')
            
            # 简单的日期过滤：只取前 15 条（通常包含最近3-5天的新闻）
            # 这里的目的是防止抓取到太旧的新闻
            for item in items[:15]: 
                title = item.title.get_text(strip=True)
                link = item.link.get_text(strip=True)
                
                articles.append({
                    "source": source_name, 
                    "title": title, 
                    "link": link
                })
            print(f"✅ {source_name}: 成功获取 {len(articles)} 条")
        else:
            print(f"❌ {source_name}: 请求失败 Code {resp.status_code}")
    except Exception as e:
        print(f"❌ {source_name} Error: {e}")
        
    return articles

def scrape_all():
    all_articles = []
    
    # === 1. 使用 Google News 抓取的源 (MyBB 和 ITWeb 目前正常) ===
    google_sources = [
        {"name": "MyBroadband", "query": "site:mybroadband.co.za"},
        {"name": "ITWeb",       "query": "site:itweb.co.za"}
    ]

    for src in google_sources:
        news = scrape_google_rss(src["name"], src["query"], days="1d")
        all_articles.extend(news)

    # === 2. 使用 官方直连 RSS 抓取的源 (TechCentral) ===
    # TechCentral 的官方 RSS 地址: https://techcentral.co.za/feed/
    tc_news = scrape_direct_rss("TechCentral", "https://techcentral.co.za/feed/")
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
