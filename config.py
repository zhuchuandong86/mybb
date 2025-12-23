import os

# ================= 用户配置区 (从环境变量读取) =================

# 1. 大模型配置
# os.environ.get("变量名") 会去读取系统里的变量，而不是写死在文件里
LLM_API_KEY = os.environ.get("LLM_API_KEY") 
LLM_BASE_URL = "https://api.deepseek.com"    # 这个地址是非敏感信息，可以直接写
LLM_MODEL = "deepseek-chat"                  # 模型名也可以直接写

# 2. 邮箱配置
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
# 邮箱和密码都要隐藏
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")       
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD") 

# 接收人也可以放入变量，或者如果固定的话写死也行（邮箱地址通常不算最高机密，但隐藏更好）
RECEIVER_EMAIL = os.environ.get("RECEIVER_EMAIL") or "zhuchuandong@gmail.com"

# ================= 系统配置区 =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
RAW_NEWS_FILE = os.path.join(DATA_DIR, "raw_news.json")
REPORT_FILE = os.path.join(DATA_DIR, "report.html")

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)


