import os

# ================= 1. 运行模式控制 (核心逻辑) =================
# 优先读取环境变量，默认为 'DAILY'
# 可选值: 'DAILY' (1天), 'WEEKLY' (7天), 'MONTHLY' (30天)
REPORT_MODE = os.environ.get("REPORT_MODE", "DAILY")

# 根据模式定义抓取范围和标题前缀
if REPORT_MODE == "MONTHLY":
    TIME_RANGE = "30d"
    REPORT_TITLE_PREFIX = "【电信月报】"
    REPORT_TYPE_EN = "MONTHLY REPORT"
elif REPORT_MODE == "WEEKLY":
    TIME_RANGE = "7d"
    REPORT_TITLE_PREFIX = "【电信周报】"
    REPORT_TYPE_EN = "WEEKLY REPORT"
else:
    TIME_RANGE = "1d"
    REPORT_TITLE_PREFIX = "【电信日报】"
    REPORT_TYPE_EN = "DAILY REPORT"

# ================= 2. API 与 邮箱配置 =================
# 大模型配置
LLM_API_KEY = os.environ.get("LLM_API_KEY") 
LLM_BASE_URL = "https://api.deepseek.com"
LLM_MODEL = "deepseek-chat"

# 邮箱配置
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")       
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD") 
# 接收人配置 (使用了 OR 逻辑防止空值报错)
RECEIVER_EMAIL = os.environ.get("RECEIVER_EMAIL") or "zhuchuandong@gmail.com"

# ================= 3. 路径配置 =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
RAW_NEWS_FILE = os.path.join(DATA_DIR, "raw_news.json")
REPORT_FILE = os.path.join(DATA_DIR, "report.html")

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)
