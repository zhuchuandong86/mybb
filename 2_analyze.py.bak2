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
        print("错误：找不到数据文件，请先运行 1_scrape.py")
        return
    except Exception as e:
        print(f"读取数据出错: {e}")
        return

    if not news_items:
        print("错误：数据为空")
        return

    limit = 60 if config.REPORT_MODE == "DAILY" else 80
    sample = news_items[:limit]
    full_count = sum(1 for x in sample if x.get('full_content'))
    print(f"待分析: {len(news_items)} 条 → 送入AI: {limit} 条（含全文: {full_count} 篇）")

    # ================= 2. 构造 Input Text =================
    formatted_lines = []
    for i, x in enumerate(sample):
        full_content = x.get('full_content', '').strip()
        description  = x.get('description', '').strip()

        if full_content:
            body_text  = full_content[:1200]
            body_label = "全文摘录"
        elif description:
            body_text  = description.replace('\n', ' ')[:300]
            body_label = "RSS摘要"
        else:
            body_text  = "（无内容）"
            body_label = "无"

        entry = (
            f"{i+1}. [{x['source']}] {x['title']}\n"
            f"   {body_label}: {body_text}\n"
            f"   URL: {x['link']}"
        )
        formatted_lines.append(entry)

    input_text = "\n\n".join(formatted_lines)

    # ================= 3. Prompt =================
    mode_cn   = {"DAILY": "日报", "WEEKLY": "周报", "MONTHLY": "月度深度报告"}.get(config.REPORT_MODE, "日报")
    focus_str = {"DAILY": "今日", "WEEKLY": "过去一周", "MONTHLY": "上个月"}.get(config.REPORT_MODE, "今日")

    prompt = f"""
# Role & Mission
你是一位深耕南非电信市场 15 年的**行业战略分析师**，服务对象是电信公司的高管团队。
你的任务是从大量混杂新闻中**精准提炼南非电信行业情报**，生成《南非电信行业{mode_cn}》。

---

# ⚠️ 内容纪律（必须严格遵守，违反则报告失败）

## 【必须排除】以下内容禁止进入报告任何板块：
- 体育、娱乐、生活方式内容
- 重复新闻（同一事件只取信息最完整的一条）

## 【核心关注范围】只有以下内容才进入 T0/T1：
**运营商动态**
- Vodacom、MTN South Africa、Telkom（含 Openserve）、Rain、Cell C
- 资费调整、套餐变化、用户数/ARPU 披露、网络质量投诉或表彰

**网络基础设施**
- 5G 建设进展、4G 覆盖扩展、频谱拍卖/分配/ICASA 决定
- 光纤 FNO（Vumatel、Openserve、Frogfoot、MetroFibre）建设、家宽竞争、WISP
- FWA（Fixed Wireless Access）、Starlink 在南非的进展

**监管与政策**
- ICASA、DCDT（数字通信部）、Competition Commission 的决定或咨询文件
- 频谱、互联互通、漫游、OTT 监管

**市场竞争与商业**
- 运营商并购、战略合作、基站共享协议
- MVNO 动态
- 企业客户 ICT/云服务大单（需明确说明是哪家运营商）

---

# 新闻分级标准（三级制）

**T0 — 核心事件**（进入"核心事件解读"板块）
满足以下任一条件：
- 南非主要运营商的重大战略/财务/网络决策
- ICASA 或政府出台影响行业格局的政策
- 将改变用户感知或竞争态势的重大产品/资费变化

**T1 — 关键动态**（进入"关键动态"板块）
- T0 的周边事件、背景补充
- 规模较小的运营商动态、区域性部署
- 值得关注但尚未确定影响的监管动向

**T2 — 科技速览**（进入"科技速览"板块，严格限制 ≤8 条）
- 如 AI 在网络优化的应用、影响运营商成本的半导体供应

---

# Input Data
<input_data>
{input_text}
</input_data>

---

# Output Requirements

## 格式
- 直接输出**纯 HTML**，不含任何 markdown 代码块标记（禁止出现 ```html）
- 全部使用**内联 CSS**（邮件客户端兼容性要求）
- 严格复刻后文 `<html_template>` 的样式

## 内容完整性要求
| 板块 | 日报 | 周报 | 月报 |
|------|------|------|------|
| AI Market Pulse | 3句 | 5句 | 5-8句 |
| 核心事件解读 T0 | 2-4条 | 4-6条 | 6-10条 |
| 关键动态 T1 | 5-8条 | 8-12条 | 10-15条 |
| 科技速览 T2 | ≤3条 | ≤5条 | ≤8条 |

## 每条 T0 必须包含：
1. **标题** + `<a href="...">[原文]</a>` 链接（链接必须真实，来自输入数据）
2. **事件概述**（≤120字）：发生了什么？基于全文内容，非标题推测
3. **深度分析和战略建议**（≤100字）：对南非电信竞争格局/用户/监管意味着什么？针对具体运营商的可操作建议

## 每条 T1 格式：
一句话摘要（含关键数字/事实）+ `<a href="...">[原文]</a>`

---

# HTML Template
<html_template>

<!-- ① AI Market Pulse -->
<div style="background:#f0f9ff;border-left:4px solid #0ea5e9;padding:16px 20px;margin-bottom:28px;border-radius:4px;">
  <h3 style="margin:0 0 10px 0;color:#0c4a6e;font-family:'Segoe UI',sans-serif;font-size:14px;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;">
    🤖 AI Market Pulse · {focus_str}南非电信市场
  </h3>
  <p style="font-family:'Segoe UI',sans-serif;font-size:15px;color:#1e3a5f;line-height:1.75;margin:0;">
    {{市场总结与战略洞察，须点名具体运营商}}
  </p>
</div>

<!-- ② 核心事件解读 T0（每条一个 div） -->
<div style="margin-bottom:30px;">
  <h2 style="font-family:'Segoe UI',sans-serif;font-size:17px;font-weight:700;color:#0f172a;border-bottom:2px solid #e2e8f0;padding-bottom:8px;margin-bottom:16px;">
    🔥 核心事件解读
  </h2>

  <div style="border:1px solid #fecaca;border-radius:8px;padding:18px 20px;margin-bottom:14px;background:#fff;">
    <div style="display:inline-block;background:#dc2626;color:#fff;font-size:11px;font-weight:700;padding:2px 8px;border-radius:3px;margin-bottom:10px;letter-spacing:0.5px;">T0 · 核心事件</div>
    <h3 style="margin:0 0 10px 0;font-family:'Segoe UI',sans-serif;font-size:17px;color:#1e293b;line-height:1.4;">
      {{标题}} <a href="{{URL}}" style="color:#2563eb;font-size:13px;font-weight:600;text-decoration:none;">[原文]</a>
    </h3>
    <p style="font-family:'Segoe UI',sans-serif;font-size:14px;color:#475569;line-height:1.65;margin:0 0 12px 0;">
      <strong>📋 事件：</strong>{{事件概述，基于全文}}
    </p>
    <div style="background:#eff6ff;border-left:3px solid #3b82f6;padding:10px 14px;border-radius:4px;font-family:'Segoe UI',sans-serif;font-size:14px;color:#1d4ed8;line-height:1.6;">
      💡 <strong>📊 分析建议：</strong>{{对南非电信市场的影响}}{{针对具体运营商的可操作建议}}
    </div>
  </div>

</div>

<!-- ③ 关键动态 T1 -->
<div style="margin-bottom:28px;">
  <h2 style="font-family:'Segoe UI',sans-serif;font-size:17px;font-weight:700;color:#0f172a;border-bottom:2px solid #e2e8f0;padding-bottom:8px;margin-bottom:14px;">
    ⚡ 关键动态
  </h2>
  <ul style="margin:0;padding-left:18px;font-family:'Segoe UI',sans-serif;font-size:14px;color:#334155;line-height:1.7;">
    <li style="margin-bottom:10px;">{{一句话摘要，含关键数字}} <a href="{{URL}}" style="color:#2563eb;text-decoration:none;font-weight:600;">[原文]</a></li>
  </ul>
</div>

<!-- ④ 科技速览 T2（≤3条，必须与SA电信直接相关） -->
<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:16px 18px;margin-bottom:10px;">
  <h2 style="margin:0 0 12px 0;font-family:'Segoe UI',sans-serif;font-size:15px;font-weight:700;color:#64748b;">
    🌐 科技速览 <span style="font-size:12px;font-weight:400;">（与SA电信相关）</span>
  </h2>
  <ul style="margin:0;padding-left:18px;font-family:'Segoe UI',sans-serif;font-size:14px;color:#64748b;line-height:1.7;">
    <li style="margin-bottom:8px;">{{摘要}} <a href="{{URL}}" style="color:#2563eb;text-decoration:none;">[原文]</a></li>
  </ul>
</div>

</html_template>
"""

    # ================= 4. 调用 AI（含重试） =================
    max_tok = {"DAILY": 8192, "WEEKLY": 12000, "MONTHLY": 16000}.get(config.REPORT_MODE, 8192)
    print(f"调用 AI 分析（模式={config.REPORT_MODE}, max_tokens={max_tok}）...")

    content = None
    for attempt in range(3):
        try:
            client = OpenAI(api_key=config.LLM_API_KEY, base_url=config.LLM_BASE_URL)
            resp = client.chat.completions.create(
                model=config.LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.6,
                max_tokens=max_tok
            )
            content = resp.choices[0].message.content.replace("```html", "").replace("```", "")
            print("✅ AI 分析完成")
            break
        except Exception as e:
            print(f"⚠️ 第 {attempt+1}/3 次失败: {e}")
            if attempt < 2:
                time.sleep((attempt + 1) * 5)
            else:
                print("❌ 三次重试均失败")
                return

    # ================= 5. 生成 HTML =================
    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:#fff;font-family:'Segoe UI',Helvetica,Arial,sans-serif;color:#334155;">
  <div style="max-width:660px;margin:0 auto;padding:40px 20px;">

    <!-- 报告头部 -->
    <div style="text-align:center;border-bottom:1px solid #e2e8f0;padding-bottom:24px;margin-bottom:28px;">
      <div style="display:inline-block;background:#0ea5e9;color:#fff;font-size:11px;font-weight:700;padding:3px 10px;border-radius:12px;letter-spacing:1px;margin-bottom:10px;">
        SOUTH AFRICA · TELECOM INTELLIGENCE
      </div>
      <h1 style="margin:0;color:#0f172a;font-size:24px;font-weight:800;letter-spacing:-0.5px;">
        🇿🇦 南非电信行业{mode_cn}
      </h1>
      <p style="margin:8px 0 0 0;color:#94a3b8;font-size:12px;letter-spacing:0.5px;">
        {datetime.now().strftime('%Y年%m月%d日')} &nbsp;|&nbsp; Powered by AI Agent
      </p>
    </div>

    {content}

    <div style="border-top:1px solid #f1f5f9;padding-top:16px;text-align:center;color:#cbd5e1;font-size:11px;margin-top:20px;">
      本报告由 AI 自动生成，仅供内部参考，不构成投资建议
    </div>
  </div>
</body>
</html>"""

    with open(config.REPORT_FILE, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"📄 报告已保存，大小: {len(html):,} 字符")


if __name__ == "__main__":
    analyze()
