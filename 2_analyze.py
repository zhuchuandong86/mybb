import json
import config
from openai import OpenAI
from datetime import datetime
import time

def analyze():
    # ================= 1. 读取数据 =================
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

    # 截取条数：日报 60 条，周/月报 80 条（全文更长，日报略少以控制 Token）
    limit = 60 if config.REPORT_MODE == "DAILY" else 80
    sample = news_items[:limit]
    print(f"待分析新闻: 共 {len(news_items)} 条，本次送入 AI: {limit} 条")

    full_count = sum(1 for x in sample if x.get('full_content'))
    print(f"  其中已抓取全文: {full_count} 条，仅有摘要: {limit - full_count} 条")

    # ================= 2. 构造 Input Text =================
    # 【核心改动】优先使用 full_content，无全文时降级到 description
    formatted_lines = []
    for i, x in enumerate(sample):
        full_content = x.get('full_content', '').strip()
        description  = x.get('description', '').strip()

        if full_content:
            # 有全文：截取前 1200 字，AI 可深度理解文章
            body_text = full_content[:1200]
            body_label = "全文摘录"
        elif description:
            # 无全文：用 RSS 摘要兜底
            body_text = description.replace('\n', ' ')[:300]
            body_label = "RSS摘要(未抓到全文)"
        else:
            body_text = "（无内容）"
            body_label = "无"

        entry = (
            f"{i + 1}. [{x['source']}] {x['title']}\n"
            f"   {body_label}: {body_text}\n"
            f"   (URL: {x['link']})"
        )
        formatted_lines.append(entry)

    input_text = "\n\n".join(formatted_lines)

    # ================= 3. 动态 Prompt 定义 =================
    report_type_cn = "日报"
    focus_point    = "结合今日新闻"

    if config.REPORT_MODE == "WEEKLY":
        report_type_cn = "周报"
        focus_point    = "回顾过去一周"
    elif config.REPORT_MODE == "MONTHLY":
        report_type_cn = "月度深度报告"
        focus_point    = "复盘上个月"

    prompt = f"""
# Role
你是一位拥有 20 年经验的**南非电信/通信行业资深战略顾问**。你需要为企业高管撰写一份名为《南非电信行业市场{report_type_cn}》的简报。

# Input Data
请仔细阅读以下 `<input_data>` 中的文本，每条新闻包含了**标题**和**全文摘录（或RSS摘要）**：

<input_data>
{input_text}
</input_data>

# Task Overview
你的核心任务是：基于输入数据，按照 `<report_mode>` ({focus_point}) 的要求，生成一份**HTML 格式**的专业报告。

# Critical Constraints (⚠️必须严格遵守)
<rules>
1. **真实性验证**：所有引用的新闻，**必须**在新闻标题或摘要后附带 `<a href="...">[原文]</a>` 链接。严禁编造链接。
2. **格式强制**：**直接输出纯 HTML 代码**，不要包含 markdown 代码块标记（如 ```html）。
3. **样式要求**：必须使用**内联 CSS (Inline CSS)**，确保邮件客户端兼容性。请严格复刻后文提供的 `<html_template>`。
4. **完整性优先**：必须确保输出完整的 HTML 闭合标签。如果内容过长，优先精简"深度解读"的字数，**严禁**砍掉"关键动态"或"科技速览"板块。
5. **深度利用全文**：对于提供了"全文摘录"的文章，你的分析必须基于全文内容，不能只看标题。若全文与标题有出入，以全文为准。
</rules>

# Analysis Workflow (思维链)
在生成 HTML 之前，请按以下逻辑处理数据（不要输出此思考过程）：

1. **清洗**：剔除重复、无实质内容的广告或纯促销信息。
2. **分级**：根据影响力将新闻分为 T0 (核心事件)、T1 (关键动态)、T2 (科技速览)。
   - *T0 标准*：南非运营商（Vodacom, MTN, Telkom，Rain，Openserve，Vumatel等）相关，
     譬如战略、财报、业务发展、CXO发言、创新，资费、套餐、促销，
     5G、网络体验、网络投诉，ICASA、通信部、频谱、政策，光纤 FNO、家宽、FWA、Starlink。
3. **分析**：针对 T0 事件，结合**全文内容**，思考其对竞争格局(Market Share)和ARPU值的潜在影响。

# Output Structure & Content Guide

### 1. 🤖 AI Market Pulse
- **内容**：针对 {focus_point} 的宏观总结。
- **风格**：高屋建瓴，给出对部分运营商的阶段性战略建议（2-3句）。

### 2. 🔥 核心事件解读 (Top Stories)
- **数量**：日报选 3-5 条，周报选 5-8 条，月报选8-12条。
- **筛选**：从T0级新闻提取，优先聚焦南非本地电信；宁缺毋滥。
- **字段要求**：
  - **标题**：加上原文链接。
  - **背景**：发生了什么（<150字，必须结合全文，而非仅凭标题推测）。
  - **深度分析**：对行业意味着什么？（<100字）。
  - **建议**：用"💡"标识，针对特定运营商的思考和建议。

### 3. ⚡ 关键动态 (Key Updates)
- **数量**：**务必列出 5-10 条**，不可遗漏。
- **内容**：覆盖 4G/5G、家宽、光纤、FWA、频谱、资费调整等。
- **格式**：每条一句话摘要 + [原文]链接。

### 4. 🌐 科技速览 (Tech Briefs)
- **数量**：3-5 条。
- **内容**：通用科技、AI 进展或周边政策。
- **格式**：每条一句话摘要 + [原文]链接。

# HTML Template Reference
<html_template>
<div style="background-color: #f8fafc; border-left: 4px solid #0ea5e9; padding: 16px 20px; margin-bottom: 30px; border-radius: 4px;">
  <h3 style="margin-top: 0; color: #0f172a; font-family: 'Segoe UI', sans-serif; font-size: 16px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;">
    🤖 AI Market Pulse
  </h3>
  <p style="font-family: 'Segoe UI', sans-serif; font-size: 15px; color: #334155; line-height: 1.7; margin-bottom: 0;">
    {{这里填充市场洞察内容}}
  </p>
</div>

<div style="margin-bottom: 15px; border: 1px solid #e2e8f0; border-radius: 8px; padding: 20px; background-color: #ffffff; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
  <div style="display: inline-block; background-color: #ef4444; color: white; font-size: 11px; font-weight: bold; padding: 2px 8px; border-radius: 3px; margin-bottom: 10px;">TOP STORY</div>
  <h3 style="margin: 0 0 10px 0; color: #1e293b; font-size: 20px; font-family: 'Segoe UI', sans-serif; line-height: 1.4; font-weight: 600;">
    {{新闻标题}} <a href="{{URL}}" style="color: #2563eb; text-decoration: none; font-size: 14px; font-weight: 600;">[原文]</a>
  </h3>
  <p style="color: #475569; font-size: 15px; line-height: 1.6; margin-bottom: 12px;">
    <strong>📊 背景与影响：</strong> {{这里写深度分析，必须基于全文内容}}
  </p>
  <div style="background-color: #eff6ff; padding: 12px; border-radius: 6px; color: #1e40af; font-size: 14px; border-left: 3px solid #3b82f6; line-height: 1.5;">
    💡 <strong>思考和建议：</strong> {{这里写战略建议}}
  </div>
</div>

<div style="margin-bottom: 30px;">
  <h3 style="border-bottom: 2px solid #e2e8f0; padding-bottom: 10px; color: #334155; font-family: 'Segoe UI', sans-serif; font-size: 18px; font-weight: 600;">⚡ 关键动态</h3>
  <ul style="padding-left: 20px; color: #475569; font-family: 'Segoe UI', sans-serif; font-size: 15px; line-height: 1.6;">
    <li style="margin-bottom: 10px;">
      {{动态摘要}} <a href="{{URL}}" style="color: #2563eb; text-decoration: none; font-weight: 600;">[原文]</a>
    </li>
  </ul>
</div>

<div style="margin-bottom: 30px; background-color: #f8fafc; padding: 15px; border-radius: 6px; border: 1px solid #f1f5f9;">
  <h3 style="margin-top:0; color: #64748b; font-size: 16px; font-family: 'Segoe UI', sans-serif; font-weight: 600;">🌐 科技速览</h3>
  <ul style="padding-left: 20px; color: #64748b; font-family: 'Segoe UI', sans-serif; font-size: 15px; line-height: 1.6;">
    <li style="margin-bottom: 6px;">
      {{科技摘要}} <a href="{{URL}}" style="color: #2563eb; text-decoration: none;">[原文]</a>
    </li>
  </ul>
</div>
</html_template>
"""

    # ================= 4. 调用 AI 分析（含重试） =================
    # 【新增】根据模式动态调整 max_tokens（月报内容更多，需要更大空间）
    max_tok = {
        "DAILY":   8192,
        "WEEKLY":  12000,
        "MONTHLY": 16000,
    }.get(config.REPORT_MODE, 8192)

    print(f"正在进行深度分析 (模式={config.REPORT_MODE}, max_tokens={max_tok})...")

    content = None
    for attempt in range(3):
        try:
            client = OpenAI(api_key=config.LLM_API_KEY, base_url=config.LLM_BASE_URL)
            resp = client.chat.completions.create(
                model=config.LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=max_tok
            )
            content = resp.choices[0].message.content.replace("```html", "").replace("```", "")
            print("✅ AI 分析完成。")
            break
        except Exception as e:
            print(f"⚠️ AI 调用失败 (第 {attempt + 1}/3 次): {e}")
            if attempt < 2:
                wait = (attempt + 1) * 5
                print(f"   等待 {wait}s 后重试...")
                time.sleep(wait)
            else:
                print("❌ 三次重试均失败，退出。")
                return

    # ================= 5. 生成 HTML 报告 =================
    html = f"""<!DOCTYPE html>
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
      <p style="margin-top: 8px; color: #64748b; font-family: 'Segoe UI', monospace; font-size: 12px; letter-spacing: 1px; font-weight: 500;">
        DATE: {datetime.now().strftime('%Y-%m-%d')} | INTELLIGENCE REPORT By deepseek-v4-flash
      </p>
    </div>

    <div style="line-height: 1.6;">
      {content}
    </div>

    <br style="clear: both;" />
    <div style="height: 30px; width: 100%; clear: both;"></div>
    <div style="border-top: 1px solid #f1f5f9; padding-top: 20px; text-align: center; color: #94a3b8; font-size: 12px; font-family: 'Segoe UI', sans-serif;">
      Powered by AI Agent (DeepSeek) | Confidential
    </div>
  </div>
</body>
</html>"""

    with open(config.REPORT_FILE, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"📄 HTML 报告已保存，大小: {len(html):,} 字符")


if __name__ == "__main__":
    analyze()
