import os
import sys
import time
import warnings
from datetime import datetime

import numpy as np
import pandas as pd

import scoring
import db
import notify

warnings.filterwarnings("ignore")

try:
    import yfinance as yf
except ImportError:
    print("yfinance غير مثبتة")
    sys.exit(1)

TICKERS_FILE = os.path.join(os.path.dirname(__file__), "tickers_tasi.csv")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "reports")
HISTORY_PERIOD = "1y"
BATCH_SIZE = 25
TOP_N = 20
REQUEST_PAUSE_SEC = 1.0

def load_universe(path=TICKERS_FILE):
    df = pd.read_csv(path, dtype=str)
    df["yahoo_symbol"] = df["code"].str.strip() + ".SR"
    return df

def fetch_batch(symbols, period=HISTORY_PERIOD):
    data = yf.download(
        tickers=" ".join(symbols),
        period=period,
        interval="1d",
        group_by="ticker",
        auto_adjust=False,
        threads=True,
        progress=False,
    )
    result = {}
    if len(symbols) == 1:
        sym = symbols[0]
        if not data.empty:
            result[sym] = data
        return result
    for sym in symbols:
        try:
            sub = data[sym].dropna(how="all")
            if not sub.empty:
                result[sym] = sub
        except:
            continue
    return result

def build_report(universe_df):
    rows = []
    failed = []
    symbols = universe_df["yahoo_symbol"].tolist()
    for i in range(0, len(symbols), BATCH_SIZE):
        batch_syms = symbols[i:i + BATCH_SIZE]
        print(f"جلب البيانات: دفعة {i // BATCH_SIZE + 1} ({i + 1}-{min(i + BATCH_SIZE, len(symbols))} من {len(symbols)})...")
        try:
            batch_data = fetch_batch(batch_syms)
        except Exception as e:
            failed.extend(batch_syms)
            continue
        for sym in batch_syms:
            df = batch_data.get(sym)
            if df is None or df.empty:
                failed.append(sym)
                continue
            try:
                result = scoring.compute_score(df)
            except:
                failed.append(sym)
                continue
            if result is None:
                failed.append(sym)
                continue
            code = sym.replace(".SR", "")
            meta = universe_df.loc[universe_df["yahoo_symbol"] == sym].iloc[0]
            rows.append({
                "الرمز": code,
                "الاسم": meta["name"],
                "القطاع": meta["sector"],
                "السعر": result["close"],
                "التغير_20يوم_%": result["price_chg_20d_pct"],
                "RSI14": result["rsi14"],
                "الدرجة": result["total"],
                "التصنيف": result["classification"],
                "تجميع_ذكي": result["sub_scores"]["تجميع_ذكي"],
                "سيولة_ذكية": result["sub_scores"]["سيولة_ذكية"],
                "تشبع_بيع_وارتداد": result["sub_scores"]["تشبع_بيع_وارتداد"],
                "اختراق_فني": result["sub_scores"]["اختراق_فني"],
                "بنية_الاتجاه": result["sub_scores"]["بنية_الاتجاه"],
                "عقوبة_تصريف": result["penalty"],
                "أسباب_الاختيار": " | ".join(result["signals"]) if result["signals"] else "لا توجد إشارات",
            })
        time.sleep(REQUEST_PAUSE_SEC)
    report_df = pd.DataFrame(rows)
    if not report_df.empty:
        report_df = report_df.sort_values("الدرجة", ascending=False).reset_index(drop=True)
        report_df.index += 1
        report_df.index.name = "الترتيب"
    print(f"\nتم تحليل {len(rows)} سهماً. تعذّر {len(failed)} رمز.")
    return report_df

def save_html_report(top_df, path):
    today_str = datetime.now().strftime("%Y-%m-%d")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"<html><body><h1>تقرير تاسي {today_str}</h1></body></html>")

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print("تحميل قائمة أسهم تاسي...")
    universe = load_universe()
    print(f"عدد الأسهم في القائمة: {len(universe)}")
    report_df = build_report(universe)
    if report_df.empty:
        return
    today_str = datetime.now().strftime("%Y-%m-%d")
    n_saved = db.save_report(report_df, today_str)
    print(f"\nتم حفظ {n_saved} سهماً لتاريخ {today_str}")
    print("جاري ارسال تيليجرام...")
    top_for_notify = report_df.head(30).to_dict("records")
    notify.send_daily_alerts(top_for_notify, today_str)
    csv_path = os.path.join(OUTPUT_DIR, f"tasi_report_{today_str}.csv")
    html_path = os.path.join(OUTPUT_DIR, f"tasi_top20_{today_str}.html")
    report_df.to_csv(csv_path, encoding="utf-8-sig")
    save_html_report(report_df.head(TOP_N), html_path)
    print(f"CSV: {csv_path}")
    print(f"HTML: {html_path}")
    display_cols = ["الرمز", "الاسم", "السعر", "الدرجة", "التصنيف"]
    print(report_df.head(TOP_N)[display_cols].to_string())

if __name__ == "__main__":
    main()
