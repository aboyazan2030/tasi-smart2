# -*- coding: utf-8 -*-
"""
وحدة المؤشرات الفنية - نظام تقييم أسهم تاسي
كل الدوال تعمل على pandas.Series / DataFrame باستخدام أعمدة:
Open, High, Low, Close, Volume
"""
import numpy as np
import pandas as pd


def sma(series, window):
    return series.rolling(window=window, min_periods=window).mean()


def ema(series, window):
    return series.ewm(span=window, adjust=False, min_periods=window).mean()


def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100 - (100 / (1 + rs))
    out = out.fillna(50)
    return out


def macd(series, fast=12, slow=26, signal=9):
    ema_fast = ema(series, fast)
    ema_slow = ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def obv(close, volume):
    direction = np.sign(close.diff().fillna(0))
    return (direction * volume).fillna(0).cumsum()


def ad_line(high, low, close, volume):
    """خط التجميع/التصريف (Accumulation/Distribution Line)"""
    range_ = (high - low).replace(0, np.nan)
    mfm = ((close - low) - (high - close)) / range_  # Money Flow Multiplier
    mfm = mfm.fillna(0)
    mfv = mfm * volume  # Money Flow Volume
    return mfv.cumsum()


def cmf(high, low, close, volume, period=20):
    """Chaikin Money Flow"""
    range_ = (high - low).replace(0, np.nan)
    mfm = ((close - low) - (high - close)) / range_
    mfm = mfm.fillna(0)
    mfv = mfm * volume
    return mfv.rolling(period).sum() / volume.rolling(period).sum()


def atr(high, low, close, period=14):
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def bollinger_bands(close, period=20, num_std=2):
    mid = sma(close, period)
    std = close.rolling(period).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    return upper, mid, lower


def up_down_volume_ratio(close, volume, period=10):
    """نسبة حجم أيام الصعود إلى حجم أيام النزول خلال آخر N جلسة"""
    chg = close.diff()
    up_vol = volume.where(chg > 0, 0.0).rolling(period).sum()
    down_vol = volume.where(chg < 0, 0.0).rolling(period).sum()
    ratio = up_vol / down_vol.replace(0, np.nan)
    return ratio.fillna(up_vol.where(down_vol == 0, np.nan)).fillna(1.0)


def volume_zscore(volume, period=20):
    mean = volume.rolling(period).mean()
    std = volume.rolling(period).std()
    return (volume - mean) / std.replace(0, np.nan)


def linreg_slope(series, window):
    """ميل خط الانحدار الخطي لآخر window نقطة، طبيعي (Normalized) بالنسبة لمتوسط القيمة"""
    s = series.tail(window)
    if s.isna().any() or len(s) < window:
        return np.nan
    x = np.arange(len(s))
    y = s.values
    slope = np.polyfit(x, y, 1)[0]
    denom = np.abs(y).mean()
    if denom == 0 or np.isnan(denom):
        return 0.0
    return slope / denom  # ميل نسبي لكل جلسة


def pct_change_n(series, n):
    if len(series) < n + 1:
        return np.nan
    base = series.iloc[-n - 1]
    if base == 0 or pd.isna(base):
        return np.nan
    return (series.iloc[-1] - base) / base


def rolling_max_excl_last(series, window):
    """أعلى قمة خلال window جلسة سابقة (لا تشمل آخر جلسة) - لكشف الاختراق"""
    return series.shift(1).rolling(window).max()


def is_bullish_candle_reversal(open_, high, low, close):
    """شمعة انعكاسية صعودية: ذيل سفلي طويل وإغلاق في النصف العلوي من مدى الجلسة"""
    rng = (high - low).replace(0, np.nan)
    lower_wick = (pd.concat([open_, close], axis=1).min(axis=1) - low)
    close_position = (close - low) / rng
    cond = (lower_wick / rng > 0.35) & (close_position > 0.55)
    return cond.fillna(False)
