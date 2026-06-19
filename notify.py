import requests

TOKEN = "8963367611:AAGCwaWQUP5x1dUBXW610ZyxiLnPJruEk2o"
CHAT = "7213801520"

def send_telegram(msg):
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={"chat_id": CHAT, "text": msg},
            timeout=10
        )
        print(f"تيليجرام: {r.status_code} - {r.text[:100]}")
    except Exception as e:
        print(f"خطا: {e}")

def build_alert_message(stocks, date):
    buys = [s for s in stocks if "صاعد" in s.get("التصنيف","") or "تجميع" in s.get("التصنيف","")]
    lines = [f"تقرير تاسي - {date}", ""]
    for s in buys[:10]:
        lines.append(f"- {s['الرمز']} {s['الاسم']} | {s['الدرجة']} | {s['السعر']}")
    if not buys:
        lines.append("لا توجد اشارات اليوم")
    lines.append("هذا تحليل فني وليس توصية")
    return "\n".join(lines)

def send_daily_alerts(stocks, date):
    msg = build_alert_message(stocks, date)
    send_telegram(msg)

def send_email(s, b):
    pass
