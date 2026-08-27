"""
2_analyze.py — 重构版

与原版的核心区别：
  原版：一次 LLM 调用直接生成整段 HTML（模型自己拼 CSS/标签，脆弱、不可复用、无法积累历史）。
  新版：
    Step 1  结构化抽取   —— LLM 以 JSON 模式对每条新闻打标签（是否相关/分级/运营商/摘要/建议/情绪/置信度）
    Step 2  历史归档     —— 把结构化结果按日期存到 data/history/，供趋势分析和未来复用
    Step 3  趋势计算     —— 读取历史归档，算出运营商声量环比变化等统计量（纯 Python，不靠模型）
    Step 4  叙事生成     —— 第二次、更小的 LLM 调用，只负责写"AI Market Pulse"这段综述，
                            输入是结构化数据 + 趋势统计，而不是原始新闻全文，模型不用做分级判断了
    Step 5  模板渲染     —— HTML 由 Python 代码拼装，LLM 只提供文本内容，不负责生成标签/CSS
                            → 报告格式 100% 可控，不会被截断或跑偏破坏邮件排版

同时保留原有接口：仍然读 config.RAW_NEWS_FILE，仍然写 config.REPORT_FILE，
所以 1_scrape.py 和 3_email.py 不需要改动。
"""

import json
import os
import re
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta

import config
from openai import OpenAI

OPERATORS = ["Vodacom", "MTN", "Telkom", "Openserve", "Rain", "Cell C",
             "Vumatel", "Frogfoot", "MetroFibre", "Starlink", "ICASA"]

HISTORY_DIR = os.path.join(config.DATA_DIR, "history")
os.makedirs(HISTORY_DIR, exist_ok=True)


def get_client():
    return OpenAI(api_key=config.LLM_API_KEY, base_url=config.LLM_BASE_URL)


# =====================================================================
# Step 1：结构化抽取 —— 让模型只做"打标签"这一件事，不再自己写 HTML
# =====================================================================
EXTRACT_SYSTEM_PROMPT = """你是南非电信行业分析师。你会收到一批新闻，请逐条判断并只输出 JSON，不要任何多余文字。

【必须排除】体育、娱乐、生活方式内容 —— include 设为 false。

【核心关注范围】运营商动态(Vodacom/MTN/Telkom/Openserve/Rain/Cell C)、网络基础设施(5G/4G/光纤FNO/FWA/Starlink)、
监管政策(ICASA/DCDT/频谱)、市场竞争(并购/MVNO/企业ICT大单)。不在此范围的 include 设为 false。

【分级】
T0 = 重大战略/财务/网络决策，或将改变竞争格局的政策/资费变化
T1 = T0 周边事件、区域性部署、尚不确定影响的监管动向
T2 = 与南非电信间接相关的科技动态（如 AI 网络优化、半导体供应）

对每条输出以下字段：
{
  "id": 输入中的编号,
  "include": true/false,
  "tier": "T0"|"T1"|"T2"|null,
  "operator": "涉及的运营商名称，没有则 null",
  "summary_cn": "事件概述，≤120字，必须基于正文而非标题推测",
  "strategic_advice_cn": "仅 T0 需要：对南非电信市场/具体运营商的可操作建议，≤100字，其余留空字符串",
  "sentiment": "positive"|"neutral"|"negative",
  "confidence": 0到1之间的浮点数，表示你对这条判断的把握
}

输出格式：{"items": [ {...}, {...}, ... ]}"""


def call_llm_json(client, system_prompt, user_content, max_tokens, label):
    """统一封装：调用 LLM 并要求 JSON 输出，带重试和容错解析。"""
    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model=config.LLM_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.3,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
            raw = resp.choices[0].message.content
            return json.loads(raw)
        except json.JSONDecodeError:
            # 兜底：某些模型在 json_object 模式下仍可能夹带 ```json 代码块
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass
            print(f"⚠️ [{label}] 第 {attempt+1}/3 次 JSON 解析失败")
        except Exception as e:
            print(f"⚠️ [{label}] 第 {attempt+1}/3 次调用失败: {e}")
        if attempt < 2:
            time.sleep((attempt + 1) * 5)
    print(f"❌ [{label}] 三次重试均失败")
    return None


def extract_structured(client, articles, batch_size=25):
    """分批抽取，避免单次输入过长导致模型漏判或截断。"""
    all_items = []
    for start in range(0, len(articles), batch_size):
        batch = articles[start:start + batch_size]
        lines = []
        for i, x in enumerate(batch):
            gid = start + i  # 全局编号，回填时用
            body = (x.get("full_content") or x.get("description") or "").strip()
            body = body[:1200] if x.get("full_content") else body[:300]
            lines.append(f"{gid}. [{x['source']}] {x['title']}\n   正文/摘要: {body or '（无内容）'}")
        user_content = "\n\n".join(lines)

        print(f"  抽取批次 {start}-{start+len(batch)-1} ...")
        result = call_llm_json(
            client, EXTRACT_SYSTEM_PROMPT, user_content,
            max_tokens=4000, label=f"extract-batch-{start}"
        )
        if result and isinstance(result.get("items"), list):
            all_items.extend(result["items"])
        else:
            print(f"  ⚠️ 批次 {start} 抽取失败，跳过（不阻塞整体流程）")

    # 把结构化判断与原始文章字段（title/link/source）合并
    merged = []
    for item in all_items:
        idx = item.get("id")
        if idx is None or not (0 <= idx < len(articles)) or not item.get("include"):
            continue
        src = articles[idx]
        merged.append({
            "title": src["title"],
            "link": src["link"],
            "source": src["source"],
            "tier": item.get("tier"),
            "operator": item.get("operator"),
            "summary_cn": item.get("summary_cn", ""),
            "strategic_advice_cn": item.get("strategic_advice_cn", ""),
            "sentiment": item.get("sentiment", "neutral"),
            "confidence": item.get("confidence", 0.5),
        })

    # 按置信度过滤明显不靠谱的判断，而不是全盘相信模型
    merged = [m for m in merged if m["confidence"] >= 0.4]
    return merged


# =====================================================================
# Step 2：历史归档 —— 之前抓的数据从"用完即弃"变成"持续积累"
# =====================================================================
def archive_today(structured_items):
    today = datetime.now().strftime("%Y-%m-%d")
    path = os.path.join(HISTORY_DIR, f"{today}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "date": today,
            "mode": config.REPORT_MODE,
            "items": structured_items,
        }, f, ensure_ascii=False, indent=2)
    print(f"📦 已归档 {len(structured_items)} 条结构化数据 → {path}")


def load_history(days):
    """读取过去 N 天的归档，用于趋势对比。"""
    cutoff = datetime.now() - timedelta(days=days)
    records = []
    if not os.path.isdir(HISTORY_DIR):
        return records
    for fname in os.listdir(HISTORY_DIR):
        if not fname.endswith(".json"):
            continue
        try:
            fdate = datetime.strptime(fname[:-5], "%Y-%m-%d")
        except ValueError:
            continue
        if fdate >= cutoff:
            with open(os.path.join(HISTORY_DIR, fname), "r", encoding="utf-8") as f:
                records.append(json.load(f))
    return records


# =====================================================================
# Step 3：趋势计算 —— 纯 Python 统计，不消耗 LLM token，结果可靠
# =====================================================================
def compute_trend(structured_items):
    window_days = {"DAILY": 1, "WEEKLY": 7, "MONTHLY": 30}.get(config.REPORT_MODE, 1)

    current_counts = Counter(x["operator"] for x in structured_items if x.get("operator"))

    # 上一个等长周期（用于计算环比），排除今天已归档的这份数据本身
    prev_records = load_history(days=window_days * 2)
    prev_counts = Counter()
    today_str = datetime.now().strftime("%Y-%m-%d")
    for rec in prev_records:
        if rec["date"] == today_str:
            continue
        for it in rec.get("items", []):
            if it.get("operator"):
                prev_counts[it["operator"]] += 1

    trend_lines = []
    for op in OPERATORS:
        cur, prev = current_counts.get(op, 0), prev_counts.get(op, 0)
        if cur == 0 and prev == 0:
            continue
        if prev == 0:
            trend_lines.append(f"{op}: 本期 {cur} 条（此前无提及）")
        else:
            delta = round((cur - prev) / prev * 100)
            sign = "+" if delta >= 0 else ""
            trend_lines.append(f"{op}: 本期 {cur} 条，环比 {sign}{delta}%")

    return {
        "current_counts": dict(current_counts),
        "summary_text": "；".join(trend_lines) if trend_lines else "历史数据不足，暂无环比趋势",
    }


# =====================================================================
# Step 4：叙事生成 —— 第二次、更聚焦的 LLM 调用
#   只喂结构化结果 + 趋势统计，不再喂原始新闻全文，模型不用重新做分级判断
# =====================================================================
def generate_market_pulse(client, structured_items, trend):
    mode_cn = {"DAILY": "今日", "WEEKLY": "本周", "MONTHLY": "本月"}.get(config.REPORT_MODE, "今日")
    t0_titles = [x["title"] for x in structured_items if x["tier"] == "T0"]

    prompt = f"""基于以下{mode_cn}南非电信市场的结构化情报和趋势统计，写一段"AI Market Pulse"综述（3-8句，
必须点名具体运营商，结合环比数据），只输出这段文字本身，不要标题、不要 markdown。

T0 核心事件标题：
{chr(10).join('- ' + t for t in t0_titles) or '（本期无 T0 级事件）'}

运营商声量趋势：
{trend['summary_text']}
"""
    try:
        resp = client.chat.completions.create(
            model=config.LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
            max_tokens=500,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"⚠️ Market Pulse 生成失败: {e}")
        return "（本期市场综述生成失败，请查看下方具体事件）"


# =====================================================================
# Step 5：模板渲染 —— HTML 完全由 Python 拼装，LLM 只提供文本内容
#   好处：报告格式 100% 可控，不会因模型输出被截断/跑偏而破坏邮件排版
# =====================================================================
def esc(text):
    """极简 HTML 转义，防止摘要文本里出现的 <, > 破坏结构。"""
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_t0(item):
    return f"""
  <div style="border:1px solid #fecaca;border-radius:8px;padding:18px 20px;margin-bottom:14px;background:#fff;">
    <div style="display:inline-block;background:#dc2626;color:#fff;font-size:11px;font-weight:700;padding:2px 8px;border-radius:3px;margin-bottom:10px;letter-spacing:0.5px;">T0 · 核心事件</div>
    <h3 style="margin:0 0 10px 0;font-family:'Segoe UI',sans-serif;font-size:17px;color:#1e293b;line-height:1.4;">
      {esc(item['title'])} <a href="{item['link']}" style="color:#2563eb;font-size:13px;font-weight:600;text-decoration:none;">[原文]</a>
    </h3>
    <p style="font-family:'Segoe UI',sans-serif;font-size:14px;color:#475569;line-height:1.65;margin:0 0 12px 0;">
      <strong>📋 事件：</strong>{esc(item['summary_cn'])}
    </p>
    <div style="background:#eff6ff;border-left:3px solid #3b82f6;padding:10px 14px;border-radius:4px;font-family:'Segoe UI',sans-serif;font-size:14px;color:#1d4ed8;line-height:1.6;">
      💡 <strong>📊 分析建议：</strong>{esc(item['strategic_advice_cn'])}
    </div>
  </div>"""


def render_t1_li(item):
    return (f'    <li style="margin-bottom:10px;">{esc(item["summary_cn"])} '
            f'<a href="{item["link"]}" style="color:#2563eb;text-decoration:none;font-weight:600;">[原文]</a></li>')


def render_t2_li(item):
    return (f'    <li style="margin-bottom:8px;">{esc(item["summary_cn"])} '
            f'<a href="{item["link"]}" style="color:#2563eb;text-decoration:none;">[原文]</a></li>')


def render_report(structured_items, market_pulse, trend, mode_cn, focus_str):
    t0_items = [x for x in structured_items if x["tier"] == "T0"]
    t1_items = [x for x in structured_items if x["tier"] == "T1"]
    t2_items = [x for x in structured_items if x["tier"] == "T2"][:8]

    t0_html = "\n".join(render_t0(x) for x in t0_items) or "  <p style=\"color:#94a3b8;font-size:14px;\">本期无 T0 级事件</p>"
    t1_html = "\n".join(render_t1_li(x) for x in t1_items) or '    <li style="color:#94a3b8;">本期无关键动态</li>'
    t2_html = "\n".join(render_t2_li(x) for x in t2_items) or '    <li style="color:#94a3b8;">本期无相关科技动态</li>'

    body = f"""
<div style="background:#f0f9ff;border-left:4px solid #0ea5e9;padding:16px 20px;margin-bottom:28px;border-radius:4px;">
  <h3 style="margin:0 0 10px 0;color:#0c4a6e;font-family:'Segoe UI',sans-serif;font-size:14px;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;">
    🤖 AI Market Pulse · {focus_str}南非电信市场
  </h3>
  <p style="font-family:'Segoe UI',sans-serif;font-size:15px;color:#1e3a5f;line-height:1.75;margin:0;">
    {esc(market_pulse)}
  </p>
</div>

<div style="margin-bottom:30px;">
  <h2 style="font-family:'Segoe UI',sans-serif;font-size:17px;font-weight:700;color:#0f172a;border-bottom:2px solid #e2e8f0;padding-bottom:8px;margin-bottom:16px;">
    🔥 核心事件解读
  </h2>
{t0_html}
</div>

<div style="margin-bottom:28px;">
  <h2 style="font-family:'Segoe UI',sans-serif;font-size:17px;font-weight:700;color:#0f172a;border-bottom:2px solid #e2e8f0;padding-bottom:8px;margin-bottom:14px;">
    ⚡ 关键动态
  </h2>
  <ul style="margin:0;padding-left:18px;font-family:'Segoe UI',sans-serif;font-size:14px;color:#334155;line-height:1.7;">
{t1_html}
  </ul>
</div>

<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:16px 18px;margin-bottom:10px;">
  <h2 style="margin:0 0 12px 0;font-family:'Segoe UI',sans-serif;font-size:15px;font-weight:700;color:#64748b;">
    🌐 科技速览 <span style="font-size:12px;font-weight:400;">（与SA电信相关）</span>
  </h2>
  <ul style="margin:0;padding-left:18px;font-family:'Segoe UI',sans-serif;font-size:14px;color:#64748b;line-height:1.7;">
{t2_html}
  </ul>
</div>
"""

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:#fff;font-family:'Segoe UI',Helvetica,Arial,sans-serif;color:#334155;">
  <div style="max-width:660px;margin:0 auto;padding:40px 20px;">

    <div style="text-align:center;border-bottom:1px solid #e2e8f0;padding-bottom:24px;margin-bottom:28px;">
      <div style="display:inline-block;background:#0ea5e9;color:#fff;font-size:11px;font-weight:700;padding:3px 10px;border-radius:12px;letter-spacing:1px;margin-bottom:10px;">
        SOUTH AFRICA · TELECOM INTELLIGENCE
      </div>
      <h1 style="margin:0;color:#0f172a;font-size:24px;font-weight:800;letter-spacing:-0.5px;">
        🇿🇦 南非电信行业{mode_cn}
      </h1>
      <p style="margin:8px 0 0 0;color:#94a3b8;font-size:12px;letter-spacing:0.5px;">
        {datetime.now().strftime('%Y年%m月%d日')} &nbsp;|&nbsp; Powered by AI Agent · T0 {len(t0_items)} · T1 {len(t1_items)} · T2 {len(t2_items)}
      </p>
    </div>

    {body}

    <div style="border-top:1px solid #f1f5f9;padding-top:16px;text-align:center;color:#cbd5e1;font-size:11px;margin-top:20px;">
      本报告由 AI 自动生成，仅供内部参考，不构成投资建议
    </div>
  </div>
</body>
</html>"""
    return html


# =====================================================================
# 主流程
# =====================================================================
def analyze():
    try:
        with open(config.RAW_NEWS_FILE, "r", encoding="utf-8") as f:
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

    limit = 60 if config.REPORT_MODE == "DAILY" else 100
    sample = news_items[:limit]
    print(f"待分析: {len(news_items)} 条 → 送入AI: {len(sample)} 条")

    client = get_client()

    print("Step 1/4 结构化抽取 ...")
    structured = extract_structured(client, sample)
    if not structured:
        print("❌ 抽取结果为空，终止（不生成空报告，避免发出无意义邮件）")
        return
    print(f"  → 抽取到 {len(structured)} 条有效事件 "
          f"(T0={sum(1 for x in structured if x['tier']=='T0')}, "
          f"T1={sum(1 for x in structured if x['tier']=='T1')}, "
          f"T2={sum(1 for x in structured if x['tier']=='T2')})")

    print("Step 2/4 归档历史数据 ...")
    archive_today(structured)

    print("Step 3/4 计算趋势 ...")
    trend = compute_trend(structured)
    print(f"  → {trend['summary_text']}")

    print("Step 4/4 生成市场综述 + 渲染报告 ...")
    market_pulse = generate_market_pulse(client, structured, trend)

    mode_cn = {"DAILY": "日报", "WEEKLY": "周报", "MONTHLY": "月度深度报告"}.get(config.REPORT_MODE, "日报")
    focus_str = {"DAILY": "今日", "WEEKLY": "过去一周", "MONTHLY": "上个月"}.get(config.REPORT_MODE, "今日")
    html = render_report(structured, market_pulse, trend, mode_cn, focus_str)

    with open(config.REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"📄 报告已保存，大小: {len(html):,} 字符")


if __name__ == "__main__":
    analyze()
