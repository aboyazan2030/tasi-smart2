# -*- coding: utf-8 -*-
"""
==================================================================
نظام تقييم ذكي لأسهم السوق السعودي (تاسي) - التقرير اليومي
==================================================================
يجلب بيانات الأسعار والأحجام تلقائياً من Yahoo Finance لكل أسهم
السوق الرئيسية في تداول، ويحسب درجة من 100 توضح احتمالية بدء
موجة صعود جديدة بالاعتماد على: التجميع الذكي، السيولة، تشبع البيع
والارتداد، الاختراق الفني، وبنية الاتجاه - مع رصد إشارات التصريف.

طريقة التشغيل:
    pip install -r requirements.txt
    python tasi_smart_score.py

المخرجات (في مجلد reports/):
    - tasi_report_YYYY-MM-DD.csv   (الترتيب الكامل لكل الأسهم)
    - tasi_top20_YYYY-MM-DD.html   (تقرير Top 20 منسّق للعرض)

ملاحظة مهمة:
    بيانات Yahoo Finance لأسهم تاسي قد تتأخر أو تنقطع لبعض الرموز
    القليلة التداول. السكربت يتجاوز تلقائياً أي رمز يفشل جلبه أو لا
    تتوفر له بيانات كافية (أقل من 60 جلسة) ويسجل ذلك في الطرفية.
==================================================================
"""
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
    print("الحزمة yfinance غير مثبتة. ثبّتها أولاً:\n    pip install yfinance")
    sys.exit(1)


TICKERS_FILE = os.path.join(os.path.dirname(__file__), "tickers_tasi.csv")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "reports")
HISTORY_PERIOD = "1y"      # طول البيانات التاريخية المطلوبة لكل سهم
BATCH_SIZE = 25            # عدد الأسهم في كل طلب دفعة لـ yfinance
TOP_N = 20                 # عدد الأسهم في التقرير اليومي المختصر
REQUEST_PAUSE_SEC = 1.0    # توقف بين الدفعات لتفادي حظر الطلبات


def load_universe(path=TICKERS_FILE):
    df = pd.read_csv(path, dtype=str)
    df["yahoo_symbol"] = df["code"].str.strip() + ".SR"
    return df


def fetch_batch(symbols, period=HISTORY_PERIOD):
    """يجلب بيانات OHLCV لمجموعة رموز دفعة واحدة، يرجع dict[symbol] = DataFrame"""
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
        except (KeyError, Exception):
            continue
    return result


def build_report(universe_df):
    rows = []
    failed = []
    symbols = universe_df["yahoo_symbol"].tolist()

    for i in range(0, len(symbols), BATCH_SIZE):
        batch_syms = symbols[i:i + BATCH_SIZE]
        print(f"جلب البيانات: دفعة {i // BATCH_SIZE + 1} "
              f"({i + 1}-{min(i + BATCH_SIZE, len(symbols))} من {len(symbols)})...")
        try:
            batch_data = fetch_batch(batch_syms)
        except Exception as e:
            print(f"  تعذّر جلب الدفعة: {e}")
            failed.extend(batch_syms)
            continue

        for sym in batch_syms:
            df = batch_data.get(sym)
            if df is None or df.empty:
                failed.append(sym)
                continue
            try:
                result = scoring.compute_score(df)
            except Exception as e:
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
                "أسباب_الاختيار": " | ".join(result["signals"]) if result["signals"] else "لا توجد إشارات قوية حالياً",
            })

        time.sleep(REQUEST_PAUSE_SEC)

    report_df = pd.DataFrame(rows)
    if not report_df.empty:
        report_df = report_df.sort_values("الدرجة", ascending=False).reset_index(drop=True)
        report_df.index += 1
        report_df.index.name = "الترتيب"

    print(f"\nتم تحليل {len(rows)} سهماً بنجاح. تعذّر جلب/تحليل {len(failed)} رمز.")
    if failed:
        print("الرموز التي تعذّر تحليلها:", ", ".join(failed[:30]),
              "..." if len(failed) > 30 else "")
    return report_df


def save_html_report(top_df, path):
    today_str = datetime.now().strftime("%Y-%m-%d")
    rows_html = ""
    for rank, row in top_df.iterrows():
        chg = row["التغير_20يوم_%"]
        chg_color = "#0a8a3a" if (chg or 0) >= 0 else "#c0392b"
        rows_html += f"""
        <tr>
          <td class="rank">{rank}</td>
          <td class="code">{row['الرمز']}</td>
          <td class="name">{row['الاسم']}<div class="sector">{row['القطاع']}</div></td>
          <td class="price">{row['السعر']}</td>
          <td style="color:{chg_color}">{chg:+.1f}%</td>
          <td class="score"><div class="bar" style="width:{row['الدرجة']}%"></div><span>{row['الدرجة']}</span></td>
          <td class="class">{row['التصنيف']}</td>
          <td class="reasons">{row['أسباب_الاختيار']}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<title>تقرير تاسي اليومي - أعلى 20 سهم - {today_str}</title>
<style>
  body {{ font-family: 'Tahoma', 'Segoe UI', sans-serif; background:#0f1115; color:#eaeaea; margin:0; padding:24px; }}
  h1 {{ font-size: 20px; margin-bottom:4px; }}
  .sub {{ color:#9aa0a6; margin-bottom:20px; font-size:13px; }}
  table {{ width:100%; border-collapse: collapse; font-size:13px; }}
  th {{ background:#1c1f26; text-align:right; padding:10px 8px; position:sticky; top:0; }}
  td {{ padding:10px 8px; border-bottom:1px solid #20232b; vertical-align: top; }}
  tr:hover {{ background:#171a21; }}
  .rank {{ color:#9aa0a6; width:30px; }}
  .code {{ font-weight:bold; color:#7fb3ff; }}
  .name {{ font-weight:600; }}
  .sector {{ color:#8a909a; font-size:11px; }}
  .score {{ position:relative; width:160px; }}
  .score .bar {{ background: linear-gradient(90deg,#2e8b57,#7CFC00); height:18px; border-radius:4px; }}
  .score span {{ position:absolute; left:6px; top:0; font-weight:bold; font-size:12px; }}
  .reasons {{ color:#c5c9d0; font-size:12px; max-width:420px; }}
  .class {{ white-space:nowrap; }}
  .footer {{ margin-top:18px; color:#6f7580; font-size:11px; }}
</style>
</head>
<body>
  <h1>📊 التقرير اليومي - أعلى 20 سهماً حسب التجميع والسيولة الذكية (تاسي)</h1>
  <div class="sub">تاريخ التقرير: {today_str} | يعتمد التحليل على بيانات تاريخية حتى آخر إغلاق متاح</div>
  <table>
    <thead>
      <tr>
        <th>#</th><th>الرمز</th><th>الشركة</th><th>السعر</th><th>تغير 20ي</th>
        <th>الدرجة /100</th><th>التصنيف</th><th>أسباب الاختيار</th>
      </tr>
    </thead>
    <tbody>{rows_html}
    </tbody>
  </table>
  <div class="footer">
    تنبيه: هذا تقرير تحليل فني وكمي إحصائي وليس توصية استثمارية أو ضمانة لأي تحرك سعري.
    البيانات من Yahoo Finance وقد تتأخر عن السوق الفعلي.
  </div>
</body>
</html>"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print("تحميل قائمة أسهم تاسي...")
    universe = load_universe()
    print(f"عدد الأسهم في القائمة: {len(universe)}")

    report_df = build_report(universe)
    if report_df.empty:
        print("لم يتم إنتاج أي نتائج. تحقق من الاتصال بالإنترنت أو من توفر مكتبة yfinance.")
        return

    today_str = datetime.now().strftime("%Y-%m-%d")

    # 1) الحفظ الدائم في قاعدة البيانات التاريخية
    n_saved = db.save_report(report_df, today_str)
    print(f"\nتم حفظ {n_saved} سهماً في قاعدة البيانات لتاريخ {today_str}")

    # 2) إرسال إشعارات تيليجرام / بريد إلكتروني
    top_for_notify = report_df.head(30).to_dict("records")
    notify.send_daily_alerts(top_for_notify, today_str)

    # 3) نسخ إضافية CSV + HTML للمراجعة السريعة اليدوية
    csv_path = os.path.join(OUTPUT_DIR, f"tasi_report_{today_str}.csv")
    html_path = os.path.join(OUTPUT_DIR, f"tasi_top20_{today_str}.html")
    report_df.to_csv(csv_path, encoding="utf-8-sig")
    top_df = report_df.head(TOP_N)
    save_html_report(top_df, html_path)

    print(f"تم حفظ نسخة CSV في: {csv_path}")
    print(f"تم حفظ نسخة HTML في: {html_path}")

    print(f"\n===== أعلى {TOP_N} سهماً اليوم =====")
    display_cols = ["الرمز", "الاسم", "السعر", "الدرجة", "التصنيف"]
    print(top_df[display_cols].to_string())


if __name__ == "__main__":
    main()
