import os

# ================= 用户配置区 (修改这里) =================

# 1. 大模型配置 (建议使用 DeepSeek)
LLM_API_KEY = "sk-dadd54e10368479087e11eeb5f7522ef"  # 您的真实 Key
LLM_BASE_URL = "https://api.deepseek.com"    # API 地址
LLM_MODEL = "deepseek-chat"                  # 模型名称

# 2. 邮箱配置
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "zhuchuandong@gmail.com"        # 发件账号
SENDER_PASSWORD = "eupksymngvybzuac"        # 应用专用密码
# 接收人列表 (用英文逗号隔开)
RECEIVER_EMAIL = "zhuchuandong@huawei.com,yt.tangyong@huawei.com"

# ================= 系统配置区 (不要动) =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
RAW_NEWS_FILE = os.path.join(DATA_DIR, "raw_news.json")
REPORT_FILE = os.path.join(DATA_DIR, "report.html")

if not os.path.exists(DATA_DIR):

    os.makedirs(DATA_DIR)
