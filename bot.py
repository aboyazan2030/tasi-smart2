import os
import requests
import pandas as pd
import glob
import yfinance as yf
import time

TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
REPORTS_DIR = os.path.join(os.path.dirname(__file__), "reports")

def send(chat_id, text):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=10
        )
    except Exception as e:
        print(f"خطأ إرسال: {e}")

def get_latest_data():
    try:
        files = glob.glob(os.path.join(REPORTS_DIR, "tasi_report_*.csv"))
        if not files:
            return None
        latest = max(files)
        df = pd.read_csv(latest, encoding="utf-8-sig")
        return df
    except:
        return None

def cmd_top10(chat_id):
    df = get_latest_data()
    if df is None:
        send(chat_id, "لا توجد بيانات متاحة")
        return
    top = df.head(10)
    lines = ["🏆 أفضل 10 أسهم اليوم:", ""]
    for _, row in top.iterrows():
        lines.append(
            f"• {row.get('الرمز','')} - {row.get('الاسم','')}\n"
            f"  السعر: {row.get('السعر','')} ر.س\n"
            f"  الدرجة: {row.get('الدرجة','')}/100\n"
            f"  التصنيف: {row.get('التصنيف','')}\n"
        )
    send(chat_id, "\n".join(lines))

def cmd_search(chat_id, code):
    df = get_latest_data()
    if df is None:
        send(chat_id, "لا توجد بيانات")
        return
    row = df[df['الرمز'].astype(str) == str(code)]
    if row.empty:
        send(chat_id, f"لم يتم العثور على السهم {code}")
        return
    r = row.iloc[0]
    msg = (
        f"📊 {r.get('الرمز','')} - {r.get('الاسم','')}\n\n"
        f"السعر: {r.get('السعر','')} ر.س\n"
        f"الدرجة: {r.get('الدرجة','')}/100\n"
        f"التصنيف: {r.get('التصنيف','')}\n"
        f"RSI: {r.get('RSI14','')}\n"
        f"القطاع: {r.get('القطاع','')}"
    )
    send(chat_id, msg)

def cmd_sector(chat_id):
    df = get_latest_data()
    if df is None:
        send(chat_id, "لا توجد بيانات")
        return
    sectors = df.groupby('القطاع')['الدرجة'].mean().sort_values(ascending=False).head(5)
    lines = ["📊 أفضل القطاعات اليوم:", ""]
    for sector, score in sectors.items():
        lines.append(f"• {sector}: {score:.1f}/100")
    send(chat_id, "\n".join(lines))

def cmd_analyze(chat_id, code):
    send(chat_id, f"⏳ جاري تحليل سهم {code}...")
    df = get_latest_data()
    row_data = None
    if df is not None:
        row = df[df['الرمز'].astype(str) == str(code)]
        if not row.empty:
            row_data = row.iloc[0]

    try:
        ticker = yf.Ticker(f"{code}.SR")
        hist = ticker.history(period="60d")
        if hist.empty:
            send(chat_id, "لم يتم العثور على بيانات السهم")
            return

        close_valid = hist['Close'].dropna()
        if close_valid.empty:
            send(chat_id, f"⚠️ لا تتوفر بيانات سعر حديثة لسهم {code} حالياً (قد يكون متوقفاً عن التداول مؤقتاً)")
            return
        current = close_valid.iloc[-1]
        prev = close_valid.iloc[-2] if len(close_valid) >= 2 else current

        change = ((current - prev) / prev) * 100
        high_30 = hist['High'].tail(30).max()
        low_30 = hist['Low'].tail(30).min()
        ma20 = hist['Close'].tail(20).mean()
        ma50 = hist['Close'].tail(50).mean() if len(hist) >= 50 else ma20

        support = round(low_30 * 1.01, 2)
        target1 = round(current * 1.05, 2)
        target2 = round(current * 1.10, 2)
        stop = round(current * 0.96, 2)
        rr = round((target1 - current) / (current - stop), 1)

        trend = "صاعد 📈" if current > ma20 > ma50 else "هابط 📉" if current < ma20 < ma50 else "محايد ↔️"

        name = row_data.get('الاسم', code) if row_data is not None else code
        score = row_data.get('الدرجة', '-') if row_data is not None else '-'
        classification = row_data.get('التصنيف', '-') if row_data is not None else '-'
        rsi = row_data.get('RSI14', '-') if row_data is not None else '-'

        recommendation = "شراء مضاربي ✅" if trend == "صاعد 📈" and str(score) != '-' and float(str(score)) > 60 else "انتظار وترقب ⏳"

        msg = (
            f"📩 تحليل سهم {name} ({code})\n\n"
            f"💰 السعر: {current:.2f} ر.س ({change:+.1f}%)\n"
            f"📊 الدرجة: {score}/100 | {classification}\n"
            f"📈 RSI: {rsi} | الاتجاه: {trend}\n\n"
            f"📍 منطقة الدخول: {current:.2f} ر.س\n"
            f"🛡️ الدعم: {support} ر.س\n"
            f"🔴 وقف الخسارة: {stop} ر.س\n"
            f"🎯 الهدف الأول: {target1} ر.س\n"
            f"🎯 الهدف الثاني: {target2} ر.س\n"
            f"⚖ نسبة المخاطرة/العائد: 1:{rr}\n\n"
            f"📌 التوصية: {recommendation}\n\n"
            f"⚠️ هذا تحليل فني وليس توصية استثمارية"
        )
        send(chat_id, msg)
    except Exception as e:
        send(chat_id, f"خطأ في جلب البيانات: {e}")

def process_update(update, processed_ids):
    update_id = update.get("update_id")
    if update_id in processed_ids:
        return update_id
    processed_ids.add(update_id)

    msg = update.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    text = msg.get("text", "").strip()

    if not chat_id or not text:
        return update_id

    if text == "/start":
        send(chat_id, (
            "مرحباً بك في بوت تاسي الذكي! 🤖\n\n"
            "الأوامر المتاحة:\n"
            "/top10 - أفضل 10 أسهم اليوم\n"
            "/search 2222 - بيانات سهم معين\n"
            "/analyze 2230 - تحليل كامل للسهم\n"
            "/sector - أفضل القطاعات"
        ))
    elif text == "/top10":
        cmd_top10(chat_id)
    elif text.startswith("/search "):
        cmd_search(chat_id, text.split()[1])
    elif text.startswith("/analyze "):
        cmd_analyze(chat_id, text.split()[1])
    elif text == "/sector":
        cmd_sector(chat_id)

    return update_id

def run_bot():
    print("🚀 البوت يعمل الآن...")
    offset = 0
    processed_ids = set()
    while True:
        try:
            r = requests.get(
                f"https://api.telegram.org/bot{TOKEN}/getUpdates",
                params={"offset": offset, "timeout": 30},
                timeout=35
            )
            updates = r.json().get("result", [])
            for update in updates:
                update_id = process_update(update, processed_ids)
                offset = max(offset, update_id + 1)
        except Exception as e:
            print(f"خطأ: {e}")
        time.sleep(5)

if __name__ == "__main__":
    run_bot()
