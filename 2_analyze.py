import json
import config
from openai import OpenAI
from datetime import datetime

def analyze():
    # ================= 1. 读取数据 (此前丢失的部分) =================
    try:
        with open(config.RAW_NEWS_FILE, 'r', encoding='utf-8') as f:
            news_items = json.load(f)
    except FileNotFoundError:
        print("错误：无法读取数据文件，请先运行爬虫 (1_scrape.py)。")
        return
    except Exception as e:
        print(f"读取数据出错: {e}")
        return

    if not news_items:
        print("错误：数据为空，请先运行爬虫。")
        return

    print(f"待分析新闻数量: {len(news_items)} 条 (正在截取前80条以防Token溢出)")

    # 构造 Prompt 输入变量 (修复 NameError 的关键)
    input_text = "\n".join(
        [f"{i + 1}. [{x['source']}] {x['title']} (URL: {x['link']})" for i, x in enumerate(news_items[:80])]
    )

    # ================= 2. 动态 Prompt 定义 =================
    
    report_type_cn = "日报"
    focus_point = "结合今日新闻"
    
    # 根据 config 判断是周报还是月报
    if config.REPORT_MODE == "WEEKLY":
        report_type_cn = "周报"
        focus_point = "回顾过去一周"
    elif config.REPORT_MODE == "MONTHLY":
        report_type_cn = "月度深度报告"
        focus_point = "复盘上个月"

    prompt = f"""
    【角色设定】南非电信行业的资深战略顾问。
    【当前任务】撰写《南非电信行业市场{report_type_cn}》。
    
    【输入数据】
    {input_text}

    【任务要求】
    请根据{focus_point}的数据进行分析。如果是日报，重点在**总结新闻和思考**；如果是周报或月报，要**识别长期趋势**、**总结重大事件的影响**。

    ⚠️⚠️ **严格格式要求** ⚠️⚠️
    1. **所有引用的新闻，必须在文字后附带原文链接！**
    2. 链接格式：`<a href="URL" style="color: #2563eb; text-decoration: none; font-weight: 600;">[原文]</a>`
    3. **直接输出 HTML 代码**，使用内联 CSS (Inline CSS)，因为邮件不支持外部样式表。
    4. 严格按照下方的【HTML 模板】结构填充内容。

    【报告结构指南】
    1. **AI 市场洞察 ({config.REPORT_MODE} Pulse)**
       - {focus_point}，输出宏观总结2-3句。
       - 给出对运营商的阶段性战略思考和建议。

    2. **核心事件解读 (Top Stories)**
       - 挑选影响最大的 3 件事。优先聚焦南非电信行业。
       - (如果是月报，请侧重于政策变化、财报、并购等大事件)。
       - **解读要求**：
         - **背景**：简述发生了什么。
         - **影响分析**：这对行业意味着什么？
         - **一句话建议**：(例如：Vodacom/MTN/Telkom/Rain，谁需要关注，如何应对，需要注意什么？)
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
            这里填写你的市场洞察总结...同时给与运营商的思考和建议...
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
            💡 <strong>Deepseek思考和建议：</strong> 这里写给运营商的思考和建议...
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

    # ================= 3. 调用 AI 分析 =================
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

# ================= 4. 生成 HTML 报告 (修复排版版) =================
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
                        🇿🇦 SOUTH AFRICA TELECOM {config.REPORT_TYPE_EN}
                    </h1>
                    <p style="margin-top: 8px; color: #64748b; font-family: 'Consolas', monospace; font-size: 12px; letter-spacing: 1px;">
                        DATE: {datetime.now().strftime('%Y-%m-%d')} | INTELLIGENCE REPORT
                    </p>
                </div>

                <div style="line-height: 1.6;">
                    {content}
                </div>

                <br style="clear: both;" />
                <div style="height: 30px; width: 100%; clear: both;"></div>

                <div style="border-top: 1px solid #f1f5f9; padding-top: 20px; text-align: center; color: #94a3b8; font-size: 11px; font-family: 'Consolas', monospace;">
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


