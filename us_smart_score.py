# -*- coding: utf-8 -*-
"""
محرك تحليل السوق الأمريكي
يستخدم نفس خوارزميات السوق السعودي (scoring.py + indicators.py)
"""
import os
import time
import warnings
import pandas as pd

import scoring
import db
import notify

warnings.filterwarnings("ignore")

try:
    import yfinance as yf
except ImportError:
    print("yfinance غير مثبتة")
    import sys; sys.exit(1)

TICKERS_FILE = os.path.join(os.path.dirname(__file__), "tickers_us.csv")
BATCH_SIZE   = 10
REQUEST_PAUSE_SEC = 1.0
TOP_N = 20


def load_us_universe(path=TICKERS_FILE):
    df = pd.read_csv(path, dtype=str)
    df["yahoo_symbol"] = df["code"].str.strip()
    return df


def fetch_us_batch(symbols, period="1y"):
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
        except Exception:
            continue
    return result


def build_us_report(universe_df):
    rows   = []
    failed = []
    symbols = universe_df["yahoo_symbol"].tolist()

    for i in range(0, len(symbols), BATCH_SIZE):
        batch = symbols[i:i + BATCH_SIZE]
        print(f"🇺🇸 جلب US دفعة {i//BATCH_SIZE+1} ({i+1}-{min(i+BATCH_SIZE,len(symbols))} من {len(symbols)})...")
        try:
            batch_data = fetch_us_batch(batch)
        except Exception as e:
            print(f"  خطأ: {e}")
            failed.extend(batch)
            continue

        for sym in batch:
            df = batch_data.get(sym)
            if df is None or df.empty:
                failed.append(sym); continue
            try:
                result = scoring.compute_score(df)
            except Exception:
                failed.append(sym); continue
            if result is None:
                failed.append(sym); continue

            meta = universe_df.loc[universe_df["yahoo_symbol"] == sym].iloc[0]
            rows.append({
                "الرمز":             sym,
                "الاسم":             meta["name"],
                "القطاع":            meta["sector"],
                "السعر":             result["close"],
                "التغير_20يوم_%":    result["price_chg_20d_pct"],
                "RSI14":             result["rsi14"],
                "الدرجة":            result["total"],
                "التصنيف":           result["classification"],
                "تجميع_ذكي":        result["sub_scores"]["تجميع_ذكي"],
                "سيولة_ذكية":       result["sub_scores"]["سيولة_ذكية"],
                "تشبع_بيع_وارتداد": result["sub_scores"]["تشبع_بيع_وارتداد"],
                "اختراق_فني":        result["sub_scores"]["اختراق_فني"],
                "بنية_الاتجاه":     result["sub_scores"]["بنية_الاتجاه"],
                "عقوبة_تصريف":      result["penalty"],
                "أسباب_الاختيار":   " | ".join(result["signals"]) if result["signals"] else "لا توجد إشارات",
            })
        time.sleep(REQUEST_PAUSE_SEC)

    report_df = pd.DataFrame(rows)
    if not report_df.empty:
        report_df = report_df.sort_values("الدرجة", ascending=False).reset_index(drop=True)
        report_df.index += 1
        report_df.index.name = "الترتيب"

    print(f"\n✅ US: تم تحليل {len(rows)} سهم. فشل {len(failed)}.")
    return report_df


def run_us_analysis(date_str):
    print("🇺🇸 بدء تحليل السوق الأمريكي...")
    universe = load_us_universe()
    print(f"عدد الأسهم: {len(universe)}")

    report_df = build_us_report(universe)
    if report_df.empty:
        print("لم تُنتج نتائج للسوق الأمريكي.")
        return

    # حفظ في قاعدة البيانات (جدول منفصل عبر market flag)
    db.init_db()
    import sqlite3
    db_path = db.DB_PATH
    conn = sqlite3.connect(db_path)
    cur  = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS daily_scores_us (
            report_date TEXT NOT NULL,
            code TEXT NOT NULL,
            name TEXT, sector TEXT, price REAL,
            price_chg_20d_pct REAL, rsi14 REAL, score REAL,
            classification TEXT, score_accumulation REAL,
            score_liquidity REAL, score_reversal REAL,
            score_breakout REAL, score_trend REAL,
            distribution_penalty REAL, reasons TEXT,
            PRIMARY KEY (report_date, code)
        )
    """)
    for _, r in report_df.iterrows():
        cur.execute("""
            INSERT INTO daily_scores_us VALUES
            (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(report_date,code) DO UPDATE SET
            name=excluded.name, sector=excluded.sector,
            price=excluded.price,
            price_chg_20d_pct=excluded.price_chg_20d_pct,
            rsi14=excluded.rsi14, score=excluded.score,
            classification=excluded.classification,
            score_accumulation=excluded.score_accumulation,
            score_liquidity=excluded.score_liquidity,
            score_reversal=excluded.score_reversal,
            score_breakout=excluded.score_breakout,
            score_trend=excluded.score_trend,
            distribution_penalty=excluded.distribution_penalty,
            reasons=excluded.reasons
        """, (
            date_str, r["الرمز"], r["الاسم"], r["القطاع"],
            r["السعر"], r["التغير_20يوم_%"], r["RSI14"], r["الدرجة"],
            r["التصنيف"], r["تجميع_ذكي"], r["سيولة_ذكية"],
            r["تشبع_بيع_وارتداد"], r["اختراق_فني"], r["بنية_الاتجاه"],
            r["عقوبة_تصريف"], r["أسباب_الاختيار"],
        ))
    conn.commit(); conn.close()
    print(f"✅ تم حفظ {len(report_df)} سهم أمريكي في قاعدة البيانات.")

    # إرسال تنبيه تيليجرام
    top = report_df.head(TOP_N).to_dict("records")
    notify.send_daily_alerts_us(top, date_str)
