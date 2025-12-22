import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import config


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
    msg['Subject'] = f"【电信早报】南非电信市场新闻分析 ({datetime.now().strftime('%Y-%m-%d')})"
    msg.attach(MIMEText(html, 'html'))

    try:
        s = smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT)
        s.starttls()
        s.login(config.SENDER_EMAIL, config.SENDER_PASSWORD)
        s.sendmail(config.SENDER_EMAIL, receivers, msg.as_string())
        s.quit()
        print(f"邮件已发送给: {receivers}")
    except Exception as e:
        print(f"发送失败: {e}")


if __name__ == "__main__":
    send()
