import os
import requests
import pandas as pd
import glob
import sqlite3
import yfinance as yf
import time

TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
REPORTS_DIR = os.path.join(os.path.dirname(__file__), "reports")
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "tasi_scores.db")

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

def get_latest_us_data():
    """يقرأ آخر تقرير أمريكي محفوظ من جدول daily_scores_us في قاعدة البيانات"""
    try:
        if not os.path.exists(DB_PATH):
            return None
        conn = sqlite3.connect(DB_PATH)
        dates = pd.read_sql(
            "SELECT DISTINCT report_date FROM daily_scores_us ORDER BY report_date DESC LIMIT 1",
            conn
        )
        if dates.empty:
            conn.close()
            return None
        latest_date = dates.iloc[0]["report_date"]
        df = pd.read_sql(
            "SELECT * FROM daily_scores_us WHERE report_date = ? ORDER BY score DESC",
            conn, params=(latest_date,)
        )
        conn.close()
        if df.empty:
            return None
        return df
    except Exception:
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

def cmd_ustop10(chat_id):
    df = get_latest_us_data()
    if df is None:
        send(chat_id, "لا توجد بيانات أمريكية متاحة بعد (تحقق من تشغيل التقرير اليومي)")
        return
    top = df.head(10)
    lines = ["🇺🇸🏆 أفضل 10 أسهم أمريكية اليوم:", ""]
    for _, row in top.iterrows():
        lines.append(
            f"• {row.get('code','')} - {row.get('name','')}\n"
            f"  السعر: {row.get('price','')} $\n"
            f"  الدرجة: {row.get('score','')}/100\n"
            f"  التصنيف: {row.get('classification','')}\n"
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

def build_entry_zones(support, fair_value, current):
    """يبني 3 مناطق دخول مرتبة حسب الأفضلية"""
    zone_excellent_low = round(support, 2)
    zone_excellent_high = round(support * 1.03, 2)

    mid = (support + fair_value) / 2
    zone_second_low = round(mid * 0.98, 2)
    zone_second_high = round(mid * 1.02, 2)

    zone_first_low = round(fair_value * 0.95, 2)
    zone_first_high = round(fair_value * 1.0, 2)

    return {
        "ممتازة": (zone_excellent_low, zone_excellent_high),
        "ثانية": (zone_second_low, zone_second_high),
        "أولى": (zone_first_low, zone_first_high),
    }

def _analyze_core(chat_id, code, yahoo_symbol, currency_label, row_data):
    """المنطق المشترك بين تحليل الأسهم السعودية والأمريكية"""
    try:
        ticker = yf.Ticker(yahoo_symbol)
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
        resistance = round(high_30 * 0.99, 2)
        stop = round(current * 0.96, 2)
        target1 = round(current * 1.05, 2)
        target2 = round(current * 1.10, 2)
        rr = round((target1 - current) / (current - stop), 1) if current != stop else 0

        trend = "صاعد 📈" if current > ma20 > ma50 else "هابط 📉" if current < ma20 < ma50 else "محايد ↔️"

        fair_value = round((ma50 + (support + resistance) / 2) / 2, 2)
        diff_pct = round(((current - fair_value) / fair_value) * 100, 1) if fair_value else 0

        if diff_pct <= -5:
            status = "🟢 منطقة شراء (السعر أقل من العادل)"
        elif -5 < diff_pct <= 5:
            status = "🟡 قريب من السعر العادل - دخول حذر"
        else:
            status = "🔴 مرتفع عن السعر العادل - يفضل الانتظار أو جني أرباح"

        zones = build_entry_zones(support, fair_value, current)

        name = row_data.get('name', code) if row_data is not None else code
        score = row_data.get('score', '-') if row_data is not None else '-'
        classification = row_data.get('classification', '-') if row_data is not None else '-'
        rsi = row_data.get('rsi14', '-') if row_data is not None else '-'

        entry_advice = ""
        if diff_pct > 5:
            entry_advice = f"⚠️ لا يُنصح بالدخول عند السعر الحالي {current:.2f} {currency_label}، والانتظار حتى وصول السهم لمناطق الدخول المحددة أدناه.\n\n"

        recommendation = "شراء مضاربي ✅" if trend == "صاعد 📈" and str(score) != '-' and float(str(score)) > 60 and diff_pct <= 5 else "انتظار وترقب ⏳"

        msg = (
            f"📩 تحليل سهم {name} ({code})\n\n"
            f"💰 السعر الحالي: {current:.2f} {currency_label} ({change:+.1f}%)\n"
            f"⚖️ السعر العادل التقديري: {fair_value:.2f} {currency_label}\n"
            f"📐 الفرق عن العادل: {diff_pct:+.1f}%\n"
            f"📍 الحالة: {status}\n\n"
            f"📊 الدرجة: {score}/100 | {classification}\n"
            f"📈 RSI: {rsi} | الاتجاه: {trend}\n\n"
            f"{entry_advice}"
            f"🎯 مناطق الدخول المقترحة (من الأفضل للأقل):\n"
            f"  🥇 ممتازة: {zones['ممتازة'][0]} - {zones['ممتازة'][1]} {currency_label}\n"
            f"  🥈 ثانية: {zones['ثانية'][0]} - {zones['ثانية'][1]} {currency_label}\n"
            f"  🥉 أولى: {zones['أولى'][0]} - {zones['أولى'][1]} {currency_label}\n\n"
            f"🛡️ الدعم: {support} {currency_label}\n"
            f"🔴 وقف الخسارة: {stop} {currency_label}\n"
            f"🎯 الهدف الأول: {target1} {currency_label}\n"
            f"🎯 الهدف الثاني: {target2} {currency_label}\n"
            f"⚖ نسبة المخاطرة/العائد: 1:{rr}\n\n"
            f"📌 التوصية: {recommendation}\n\n"
            f"⚠️ هذا تحليل فني وليس توصية استثمارية"
        )
        send(chat_id, msg)
    except Exception as e:
        send(chat_id, f"خطأ في جلب البيانات: {e}")

def cmd_analyze(chat_id, code):
    send(chat_id, f"⏳ جاري تحليل سهم {code}...")
    df = get_latest_data()
    row_data = None
    if df is not None:
        row = df[df['الرمز'].astype(str) == str(code)]
        if not row.empty:
            r = row.iloc[0]
            row_data = {
                "name": r.get('الاسم', code),
                "score": r.get('الدرجة', '-'),
                "classification": r.get('التصنيف', '-'),
                "rsi14": r.get('RSI14', '-'),
            }
    _analyze_core(chat_id, code, f"{code}.SR", "ر.س", row_data)

def cmd_us(chat_id, code):
    code = code.upper()
    send(chat_id, f"⏳ جاري تحليل سهم {code} (أمريكي)...")
    df = get_latest_us_data()
    row_data = None
    if df is not None:
        row = df[df['code'].astype(str).str.upper() == code]
        if not row.empty:
            r = row.iloc[0]
            row_data = {
                "name": r.get('name', code),
                "score": r.get('score', '-'),
                "classification": r.get('classification', '-'),
                "rsi14": r.get('rsi14', '-'),
            }
    _analyze_core(chat_id, code, code, "$", row_data)

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
            "الأوامر المتاحة (السوق السعودي):\n"
            "/top10 - أفضل 10 أسهم اليوم\n"
            "/search 2222 - بيانات سهم معين\n"
            "/analyze 2230 - تحليل كامل للسهم\n"
            "/sector - أفضل القطاعات\n\n"
            "الأوامر المتاحة (السوق الأمريكي):\n"
            "/ustop10 - أفضل 10 أسهم أمريكية اليوم\n"
            "/us AAPL - تحليل كامل لسهم أمريكي"
        ))
    elif text == "/top10":
        cmd_top10(chat_id)
    elif text == "/ustop10":
        cmd_ustop10(chat_id)
    elif text.startswith("/search "):
        cmd_search(chat_id, text.split()[1])
    elif text.startswith("/analyze "):
        cmd_analyze(chat_id, text.split()[1])
    elif text.startswith("/us "):
        cmd_us(chat_id, text.split()[1])
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
