import os
import requests
import sqlite3
import pandas as pd

TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "tasi.db")

def send(chat_id, text):
    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={"chat_id": chat_id, "text": text},
        timeout=10
    )

def get_latest_data():
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql("SELECT * FROM scores ORDER BY date DESC, درجة DESC", conn)
        conn.close()
        latest = df[df['date'] == df['date'].max()]
        return latest
    except:
        return None

def cmd_top10(chat_id):
    df = get_latest_data()
    if df is None:
        send(chat_id, "لا توجد بيانات متاحة")
        return
    top = df.head(10)
    lines = ["🏆 أفضل 10 أسهم اليوم:", ""]
    for i, row in top.iterrows():
        lines.append(f"{row.get('الترتيب','')}- {row.get('الرمز','')} {row.get('الاسم','')} | درجة: {row.get('الدرجة','')} | {row.get('التصنيف','')}")
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
    msg = f"تحليل سهم {r.get('الرمز','')} - {r.get('الاسم','')}\nالسعر: {r.get('السعر','')}\nالدرجة: {r.get('الدرجة','')}\nالتصنيف: {r.get('التصنيف','')}\nRSI: {r.get('RSI14','')}"
    send(chat_id, msg)

def cmd_sector(chat_id):
    df = get_latest_data()
    if df is None:
        send(chat_id, "لا توجد بيانات")
        return
    sectors = df.groupby('القطاع')['الدرجة'].mean().sort_values(ascending=False).head(5)
    lines = ["📊 أفضل القطاعات اليوم:", ""]
    for sector, score in sectors.items():
        lines.append(f"- {sector}: {score:.1f}")
    send(chat_id, "\n".join(lines))

def process_updates():
    offset = 0
    try:
        r = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset={offset}&timeout=5", timeout=10)
        updates = r.json().get("result", [])
        for update in updates:
            offset = update["update_id"] + 1
            msg = update.get("message", {})
            chat_id = msg.get("chat", {}).get("id")
            text = msg.get("text", "").strip()
            if text == "/top10":
                cmd_top10(chat_id)
            elif text.startswith("/search"):
                parts = text.split()
                if len(parts) > 1:
                    cmd_search(chat_id, parts[1])
                else:
                    send(chat_id, "استخدم: /search 2222")
            elif text == "/sector":
                cmd_sector(chat_id)
            elif text == "/start":
                send(chat_id, "مرحباً! الأوامر المتاحة:\n/top10 - أفضل 10 أسهم\n/search 2222 - تحليل سهم\n/sector - أفضل القطاعات")
    except Exception as e:
        print(f"خطا: {e}")

if __name__ == "__main__":
    process_updates()
