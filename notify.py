import os
import requests

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = "7213801520"

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        r = requests.post(url, json=data, timeout=10)
        print(f"تيليجرام response: {r.text}")
        return r.status_code == 200
    except Exception as e:
        print(f"خطا: {e}")
        return False

def build_alert_message(top_stocks, date_str):
    buy_signals = [s for s in top_stocks if s["التصنيف"] in ("🚀 اختراق صاعد", "📦 تجميع هادئ")]
    lines = ["تقرير تاسي الذكي - " + date_str, ""]
    if buy_signals:
        lines.append("اشارات شراء:")
        for s in buy_signals[:8]:
            lines.append(f"- {s['الرمز']} {s['الاسم']} | درجة: {s['الدرجة']} | السعر: {s['السعر']}")
    else:
        lines.append("لا توجد اشارات قوية اليوم.")
    lines.append("هذا تحليل فني وليس توصية استثمارية.")
    return "\n".join(lines)

def send_daily_alerts(top_stocks, date_str):
    msg = build_alert_message(top_stocks, date_str)
    send_telegram(msg)

def send_email(subject, body):
    pass
