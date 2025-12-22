import requests
from bs4 import BeautifulSoup
import json
import config


def get_headers():
    return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }


def scrape_all():
    articles = []

    # --- 1. MyBroadband (Google News RSS - 放松限制) ---
    print("--- 正在抓取 MyBroadband (全量模式) ---")
    try:
        # 修改说明：
        # 1. 移除了 "South Africa" 关键词，防止漏掉本地默认新闻 (如 Eskom, MTN 相关)。
        # 2. 保留了 site:mybroadband.co.za (限定源)。
        # 3. 保留了 gl=ZA (限定谷歌新闻区域为南非)。
        # 4. when:1d 抓取过去24小时。
        rss_url = "https://news.google.com/rss/search?q=site:mybroadband.co.za+when:1d&hl=en-ZA&gl=ZA&ceid=ZA:en"

        resp = requests.get(rss_url, headers=get_headers(), timeout=20)

        if resp.status_code == 200:
            soup = BeautifulSoup(resp.content, 'xml')
            items = soup.find_all('item')

            # 不设数量上限，全量抓取
            for item in items:
                title = item.title.get_text(strip=True).replace(" - MyBroadband", "")
                link = item.link.get_text(strip=True)
                articles.append({"source": "MyBroadband", "title": title, "link": link})
            print(f"MyBroadband: 抓取到 {len(items)} 条")
    except Exception as e:
        print(f"MyBroadband Error: {e}")

    # --- 2. TechCentral (直连 - 保持不变) ---
    print("--- 正在抓取 TechCentral ---")
    try:
        resp = requests.get("https://techcentral.co.za/", headers=get_headers(), timeout=20)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            tc_count = 0
            for item in soup.select('article h3 a, article h2 a, .entry-title a'):
                title = item.get_text(strip=True)
                link = item.get('href')
                if title and link:
                    if not any(d['link'] == link for d in articles):
                        articles.append({"source": "TechCentral", "title": title, "link": link})
                        tc_count += 1
            print(f"TechCentral: 抓取到 {tc_count} 条")
    except Exception as e:
        print(f"TechCentral Error: {e}")

    # --- 3. ITWeb (直连 - 保持不变) ---
    print("--- 正在抓取 ITWeb ---")
    try:
        resp = requests.get("https://www.itweb.co.za/", headers=get_headers(), timeout=20)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            itweb_count = 0
            # 抓取主要标题链接
            links = soup.select('h1 a, h2 a, h3 a, h4 a, .title a, .news_container a')
            if not links: links = soup.select('a')

            for item in links:
                title = item.get_text(strip=True)
                link = item.get('href')
                # 简单过滤：标题长度>20，且看起来像新闻链接
                if title and link and len(title) > 20:
                    if not link.startswith('http'): link = "https://www.itweb.co.za" + link

                    # 路径过滤，避免抓到 footer 里的隐私政策等
                    if any(x in link for x in ['/content/', '/news/']) or link.endswith('.html'):
                        if not any(d['link'] == link for d in articles):
                            articles.append({"source": "ITWeb", "title": title, "link": link})
                            itweb_count += 1
            print(f"ITWeb: 抓取到 {itweb_count} 条")
    except Exception as e:
        print(f"ITWeb Error: {e}")

    return articles


if __name__ == "__main__":
    data = scrape_all()
    # 写入文件
    with open(config.RAW_NEWS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"爬虫结束，共保存 {len(data)} 条。")