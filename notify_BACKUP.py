import os
import requests

def send_telegram(msg):
    token = os.environ.get("TELEGRAM_TOKEN", "")
    chat = os.environ.get("TELEGRAM_CHAT_ID", "")
    print(f"TOKEN_LEN={len(token)} CHAT={chat}")
    if not token or not chat:
        print("لا يوجد token او chat_id")
        return
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": msg},
            timeout=10
        )
        print(f"response: {r.status_code} {r.text[:100]}")
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
