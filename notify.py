import os
import requests

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("تيليجرام: لم يتم ضبط TOKEN او CHAT_ID")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        r = requests.post(url, json=data, timeout=10)
        if r.status_code == 200:
            print("تم ارسال اشعار تيليجرام")
            return True
        else:
            print(f"خطا تيليجرام: {r.text}")
            return False
    except Exception as e:
        print(f"خطا ارسال تيليجرام: {e}")
        return False

def build_alert_message(top_stocks, date_str):
    buy_signals = [s for s in top_stocks if s["التصنيف"] in ("🚀 اختراق صاعد", "📦 تجميع هادئ", "🔄 ارتداد من تشبع بيع")]
    sell_signals = [s for s in top_stocks if s["التصنيف"] == "تصريف/توزيع"]
    lines = ["تقرير تاسي الذكي - " + date_str, ""]
    if buy_signals:
        lines.append("اشارات شراء / تجميع")
        for s in buy_signals[:8]:
            lines.append(f"- {s['الرمز']} {s['الاسم']} | درجة: {s['الدرجة']} | السعر: {s['السعر']}")
        lines.append("")
    if not buy_signals and not sell_signals:
        lines.append("لا توجد اشارات قوية اليوم.")
    lines.append("هذا تحليل فني وليس توصية استثمارية.")
    return "\n".join(lines)

def send_daily_alerts(top_stocks, date_str):
    msg = build_alert_message(top_stocks, date_str)
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        send_telegram(msg)
    else:
        print("تحذير: لم يُرسَل اي اشعار")

def send
