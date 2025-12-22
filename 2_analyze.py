import json
import config
from openai import OpenAI
from datetime import datetime


def analyze():
    try:
        with open(config.RAW_NEWS_FILE, 'r', encoding='utf-8') as f:
            news_items = json.load(f)
    except:
        print("无数据文件。")
        return

    if not news_items:
        print("数据为空。")
        return

    print(f"待分析新闻数量: {len(news_items)} 条 (正在截取前80条以防Token溢出)")

    # 构造输入文本，格式：ID. [来源] 标题 (链接)
    # 限制前80条，防止超过大模型处理上限
    input_text = "\n".join(
        [f"{i + 1}. [{x['source']}] {x['title']} (URL: {x['link']})" for i, x in enumerate(news_items[:80])])

    prompt = f"""
    【角色设定】
    你是一名南非国电信行业的市场分析师和咨询师，专注于南非电信市场。

    【输入数据】
    {input_text}

    【任务要求】
    请用**中文**撰写《南非电信行业市场日报》。

    ⚠️⚠️ **严格格式要求 (Strict Format Rules)** ⚠️⚠️
    1. **所有引用的新闻，必须在文字后附带原文链接！**
    2. 链接格式统一为：`<a href="URL_HERE" target="_blank" style="color:#c0392b;text-decoration:none;">[原文]</a>`
    3. 如果没有提到具体新闻，不要编造链接。

    【报告结构】
    1. **今日头条深度解读 (Top Story)**：
       - 挑选对南非电信行业(5G/光纤/家宽/资费/运营商等、MTN/Vodacom/Telkom/Rain/Vuma等)影响最大的三件事。
       - 深度分析背景、竞对影响(MTN/Vodacom/Telkom/Rain/Vuma等)和用户影响。
       - **不要只是复述新闻，同时需要用你的能力进行洞察和分析**
       - **必须附带该新闻的原文链接**。

    2. **关键动态 (Key Updates)**：
       - 筛选 3-5 条移动网络、光纤、家宽、FWA、频谱等动态。
       - 每条一句话摘要 + **[原文]链接**。

    3. **其他科技速览 (Tech Briefs)**：
       - 3-5 条值得关注的通用科技/政策新闻。
       - 每条一句话摘要 + **[原文]链接**。

    4. **分析师辣评 (Analyst Take)**：
       - 两到三句对市场趋势的犀利总结。

    【输出HTML示例】
    (直接输出HTML代码，不要Markdown)
    <div class="top-story">
        <h3>新闻标题 <a href="...">[原文]</a></h3>
        <p><strong>背景：</strong>...</p>
    </div>
    <div class="section">
        <h4>📡 关键动态</h4>
        <ul>
            <li><strong>标题</strong>: 摘要内容 <a href="链接地址" target="_blank">[原文]</a></li>
            <li><strong>标题</strong>: 摘要内容 <a href="链接地址" target="_blank">[原文]</a></li>
        </ul>
    </div>
    ...
    """

    print("正在进行深度分析与链接匹配...")
    try:
        client = OpenAI(api_key=config.LLM_API_KEY, base_url=config.LLM_BASE_URL)
        resp = client.chat.completions.create(
            model=config.LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=2500  # 增加输出长度
        )
        content = resp.choices[0].message.content.replace("```html", "").replace("```", "")

        # 注入 CSS 样式
        html = f"""
        <!DOCTYPE html>
        <html><head><meta charset="utf-8"><style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f4f4f4; padding: 20px; color: #333; }}
        .container {{ max-width: 700px; margin: auto; background: #fff; padding: 30px; border-radius: 8px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }}
        h1 {{ color: #b71c1c; border-bottom: 2px solid #eee; padding-bottom: 10px; text-align:center; }}
        .meta {{ text-align: center; color: #888; font-size: 12px; margin-bottom: 20px; }}
        .top-story {{ background: #fff8e1; padding: 20px; border-left: 5px solid #ffc107; margin-bottom: 25px; border-radius: 4px; }}
        .top-story h3 {{ margin-top: 0; color: #e65100; }}
        .section h4 {{ color: #2c3e50; border-bottom: 1px dashed #ddd; padding-bottom: 8px; margin-top: 30px; font-size: 18px; }}
        ul {{ padding-left: 20px; line-height: 1.6; }}
        li {{ margin-bottom: 12px; }}
        a {{ font-weight: bold; }}
        a:hover {{ text-decoration: underline; }}
        .analyst-take {{ margin-top: 40px; background: #e8f5e9; padding: 20px; border-radius: 8px; color: #2e7d32; font-weight: bold; text-align: center; font-size: 16px; border: 1px solid #c8e6c9; }}
        .footer {{ margin-top: 30px; font-size: 12px; color: #aaa; text-align: center; border-top: 1px solid #eee; padding-top: 10px; }}
        </style></head><body>
        <div class="container">
            <h1>🇿🇦 南非电信市场日报</h1>
            <div class="meta">📅 {datetime.now().strftime('%Y-%m-%d')} | 📍 Johannesburg | 🤖 AI Analysis</div>

            {content}

            <div class="footer">
                Powered by Huawei Cloud ECS & DeepSeek<br>
                Based on: MyBroadband, TechCentral, ITWeb
            </div>
        </div></body></html>
        """

        with open(config.REPORT_FILE, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"分析完成。HTML报告大小: {len(html)} 字符")
    except Exception as e:
        print(f"分析失败: {e}")


if __name__ == "__main__":
    analyze()