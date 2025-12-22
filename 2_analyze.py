import json
import config
from openai import OpenAI
from datetime import datetime

def analyze():
    # --- 1. 读取数据 ---
    try:
        with open(config.RAW_NEWS_FILE, 'r', encoding='utf-8') as f:
            news_items = json.load(f)
    except:
        print("错误：无法读取数据文件，请先运行爬虫。")
        return

    if not news_items:
        print("错误：数据为空，请先运行爬虫。")
        return

    print(f"待分析新闻数量: {len(news_items)} 条 (正在截取前80条以防Token溢出)")

    # --- 2. 构造 Prompt 输入 ---
    input_text = "\n".join(
        [f"{i + 1}. [{x['source']}] {x['title']} (URL: {x['link']})" for i, x in enumerate(news_items[:80])])

    # --- 3. 定义 Prompt (保留核心逻辑 + 钛合金实验室风格) ---
    prompt = f"""
    【角色设定】南非电信行业的资深市场分析师和战略顾问。
    【风格】：**专业**，像一位精通南非市场的电信分析咨询师在做分享。

    【输入数据】
    {input_text}

    【任务要求】
    用**中文**撰写《南非电信行业市场日报》。先概括新闻，再**深度分析**、**趋势判断**以及**对运营商的思考和建议**。

    ⚠️⚠️ **严格格式要求 (邮件安全版)** ⚠️⚠️
    1. **所有引用的新闻，必须在文字后附带原文链接！**
    2. 链接格式：`<a href="URL" style="color: #2563eb; text-decoration: none; font-weight: 600;">[原文]</a>`
    3. **直接输出 HTML 代码**，使用内联 CSS (Inline CSS)，因为邮件不支持外部样式表。
    4. 严格按照下方的【HTML 模板】结构填充内容。

【报告结构与内容指南】

    1. **AI 市场洞察 (Market Pulse)**
       - 对今日新闻进行全局化的汇总理解。
       - 输出两到三句市场动态的专业总结。
       - **重点**：结合今日新闻，给出对运营商（如 MTN/Vodacom/Rain/Telkom）的一句话战略思考或建议。

    2. **今日头条深度解读 (Top Stories)**
       - 挑选影响最大的 **3件事**，优先聚焦南非电信行业。
       - **解读要求**：
         - **背景**：简述发生了什么。
         - **影响分析**：这对行业意味着什么？
         - **一句话建议**：(例如：Vodacom 应如何应对？Rain 需要注意什么？)
       - **必须附带原文链接**。

    3. **关键动态 (Key Updates)**
       - **电信行业新闻逐条列出**，如45G，家宽，光纤、FWA、频谱、资费、ICASA等。
       - 每条一句话摘要 + **[原文]链接**。

    4. **科技速览 (Tech Briefs)**
       - 3-5 条值得关注的通用科技/政策新闻。
       - 每条一句话摘要 + **[原文]链接**。

    【HTML 输出模板 (请复刻此结构和Style)】
    
    <div style="background-color: #f1f5f9; border-left: 4px solid #0ea5e9; padding: 15px 20px; margin-bottom: 30px; border-radius: 4px;">
        <h3 style="margin-top: 0; color: #0f172a; font-family: 'Segoe UI', sans-serif; font-size: 16px; text-transform: uppercase; letter-spacing: 1px;">
            🤖 AI Market Pulse
        </h3>
        <p style="font-family: 'Consolas', 'Monaco', monospace; font-size: 14px; color: #334155; line-height: 1.6; margin-bottom: 0;">
            这里填写你的市场洞察和犀利点评...
        </p>
    </div>

    <div style="margin-bottom: 30px; border: 1px solid #e2e8f0; border-radius: 8px; padding: 20px; background-color: #ffffff;">
        <div style="display: inline-block; background-color: #ef4444; color: white; font-size: 11px; font-weight: bold; padding: 2px 8px; border-radius: 3px; margin-bottom: 10px;">TOP STORY</div>
        <h3 style="margin: 0 0 10px 0; color: #1e293b; font-size: 20px; font-family: 'Segoe UI', sans-serif;">
            新闻标题 <a href="..." style="color: #2563eb; text-decoration: none; font-size: 16px;">[原文]</a>
        </h3>
        <p style="color: #475569; font-size: 15px; line-height: 1.6; margin-bottom: 8px;">
            <strong>📊 背景与影响：</strong> 这里写深度分析...
        </p>
        <div style="background-color: #eff6ff; padding: 10px; border-radius: 4px; color: #1e40af; font-size: 14px; margin-top: 10px;">
            💡 <strong>战略建议：</strong> 这里写给运营商的具体行动建议...
        </div>
    </div>

    <h3 style="border-bottom: 2px solid #334155; padding-bottom: 8px; margin-top: 40px; color: #334155; font-size: 18px;">
        📡 关键动态 (Key Updates)
    </h3>
    <ul style="padding-left: 20px; color: #334155; line-height: 1.8;">
        <li style="margin-bottom: 8px;">
            <strong>[分类]</strong> 新闻摘要... <a href="..." style="color: #2563eb; text-decoration: none;">[原文]</a>
        </li>
    </ul>

    <h3 style="border-bottom: 2px solid #334155; padding-bottom: 8px; margin-top: 40px; color: #334155; font-size: 18px;">
        🚀 科技速览 (Tech Briefs)
    </h3>
    <ul style="padding-left: 20px; color: #334155; line-height: 1.8;">
        <li style="margin-bottom: 8px;">
            新闻摘要... <a href="..." style="color: #2563eb; text-decoration: none;">[原文]</a>
        </li>
    </ul>
    """

    print("正在进行深度分析与链接匹配 (AI Mode)...")
    try:
        client = OpenAI(api_key=config.LLM_API_KEY, base_url=config.LLM_BASE_URL)
        resp = client.chat.completions.create(
            model=config.LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=3500 
        )
        content = resp.choices[0].message.content.replace("```html", "").replace("```", "")

        # ================= 邮件包装壳 (Email Wrapper - 修复了这里的断裂) =================
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="margin: 0; padding: 0; background-color: #ffffff; font-family: 'Segoe UI', Helvetica, Arial, sans-serif; color: #334155;">
            
            <div style="max-width: 650px; margin: 0 auto; padding: 40px 20px;">
                
                <div style="text-align: center; border-bottom: 1px solid #e2e8f0; padding-bottom: 30px; margin-bottom: 30px;">
                    <h1 style="margin: 0; color: #0f172a; font-size: 26px; font-weight: 800; letter-spacing: -0.5px;">
                        🇿🇦 SOUTH AFRICA TELECOM DAILY
                    </h1>
                    <p style="margin-top: 8px; color: #64748b; font-family: 'Consolas', monospace; font-size: 12px; letter-spacing: 1px;">
                        DATE: {datetime.now().strftime('%Y-%m-%d')} | INTELLIGENCE REPORT
                    </p>
                </div>

                {content}

                <div style="margin-top: 50px; border-top: 1px solid #f1f5f9; padding-top: 20px; text-align: center; color: #94a3b8; font-size: 11px; font-family: 'Consolas', monospace;">
                    Powered by AI Agent (DeepSeek) | Confidential
                </div>
            </div>
            
        </body>
        </html>
        """

        with open(config.REPORT_FILE, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"分析完成。HTML报告大小: {len(html)} 字符")
    except Exception as e:
        print(f"分析失败: {e}")

if __name__ == "__main__":
    analyze()
