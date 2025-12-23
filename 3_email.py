import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import config
import traceback # 需要在文件顶部导入

def send():
    try:
        with open(config.REPORT_FILE, 'r', encoding='utf-8') as f:
            html = f.read()
    except:
        return

    # 处理多收件人
    receivers = [x.strip() for x in config.RECEIVER_EMAIL.split(',') if x.strip()]

    msg = MIMEMultipart()
    msg['From'] = config.SENDER_EMAIL
    msg['To'] = ",".join(receivers)
    
    # 🔥 修改点：使用 config 中定义的动态前缀
    # 例如：【电信月报】南非电信市场新闻分析 (2025-05-01)
    msg['Subject'] = f"{config.REPORT_TITLE_PREFIX} 南非电信市场分析 ({datetime.now().strftime('%Y-%m-%d')})"
    
    msg.attach(MIMEText(html, 'html'))

    try:
        s = smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT)
        s.starttls()
        s.login(config.SENDER_EMAIL, config.SENDER_PASSWORD)
        s.sendmail(config.SENDER_EMAIL, receivers, msg.as_string())
        s.quit()
        print(f"邮件已发送给: {receivers}")
    except Exception as e:
        print("❌ 发送失败，详细错误如下：")
        print(repr(e))  # 打印完整的错误对象
        traceback.print_exc() # 打印报错的具体位置


if __name__ == "__main__":
    send()


