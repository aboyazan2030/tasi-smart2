# -*- coding: utf-8 -*-
"""
وحدة الإشعارات - تيليجرام + بريد إلكتروني
"""
import os
import requests

TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
EMAIL_TO         = os.getenv("EMAIL_TO", "")
EMAIL_FROM       = os.getenv("EMAIL_FROM", "")
EMAIL_PASSWORD   = os.getenv("EMAIL_PASSWORD", "")


def send_telegram(message: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("تيليجرام: لم يتم ضبط TOKEN أو CHAT_ID")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        r = requests.post(url, data=data, timeout=10)
        if r.status_code == 200:
            print("✅ تم إرسال إشعار تيليجرام")
            return True
        else:
            print(f"خطأ تيليجرام: {r.text}")
            return False
    except Exception as e:
        print(f"خطأ إرسال تيليجرام: {e}")
        return False


def send_email(subject: str, body: str):
    if not EMAIL_TO or not EMAIL_FROM or not EMAIL_PASSWORD:
        print("البريد: لم يتم ضبط إعدادات الإيميل")
        return False
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    try:
        msg = MIMEMultipart()
        msg["From"]    = EMAIL_FROM
        msg["To"]      = EMAIL_TO
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "html", "utf-8"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as s:
            s.login(EMAIL_FROM, EMAIL_PASSWORD)
            s.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
        print("✅ تم إرسال البريد الإلكتروني")
        return True
    except Exception as e:
        print(f"خطأ إرسال البريد: {e}")
        return False


def build_alert_message(top_stocks, date_str: str) -> str:
    """يبني رسالة التنبيه اليومية"""
    buy_signals  = [s for s in top_stocks if s["التصنيف"] in ("🚀 اختراق صاعد", "📦 تجميع هادئ", "🔄 ارتداد من تشبع بيع")]
    sell_signals = [s for s in top_stocks if s["التصنيف"] == "⚠️ تصريف/توزيع"]

    lines = [
        f"<b>📊 تقرير تاسي الذكي – {date_str}</b>",
        "",
    ]

    if buy_signals:
        lines.append("🟢 <b>إشارات شراء / تجميع</b>")
        for s in buy_signals[:8]:
            lines.append(
                f"  • <b>{s['الرمز']} {s['الاسم']}</b> | درجة: {s['الدرجة']} | {s['التصنيف']}\n"
                f"    السعر: {s['السعر']} ر.س | RSI: {s['RSI14']}"
            )
        lines.append("")

    if sell_signals:
        lines.append("🔴 <b>تحذيرات تصريف / بيع</b>")
        for s in sell_signals[:5]:
            lines.append(
                f"  • <b>{s['الرمز']} {s['الاسم']}</b> | درجة: {s['الدرجة']} | {s['التصنيف']}\n"
                f"    السعر: {s['السعر']} ر.س | RSI: {s['RSI14']}"
            )
        lines.append("")

    if not buy_signals and not sell_signals:
        lines.append("لا توجد إشارات قوية اليوم.")

    lines.append("⚠️ هذا تحليل فني وليس توصية استثمارية.")
    return "\n".join(lines)


def send_daily_alerts(top_stocks, date_str: str):
    msg = build_alert_message(top_stocks, date_str)
    sent = False
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        sent = send_telegram(msg)
    if EMAIL_TO and EMAIL_FROM and EMAIL_PASSWORD:
        plain = msg.replace("<b>", "").replace("</b>", "")
        html  = msg.replace("\n", "<br>")
        send_email(f"تقرير تاسي الذكي – {date_str}", html)
        sent = True
    if not sent:
        print("تحذير: لم يُرسَل أي إشعار (لم تُضبط بيانات تيليجرام أو البريد)")
