import os
import requests
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import time
import warnings
warnings.filterwarnings('ignore')

# ============================================
# الإعدادات
# ============================================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
CHAT_ID        = os.getenv("CHAT_ID", "")

# استراتيجية
ATR_PERIOD      = 1
ATR_MULTIPLIER  = 2.0
ZLSMA_LENGTH    = 50

# مخاطر
USE_STOP_LOSS      = True
STOP_LOSS_PCT      = 2.0
INITIAL_BALANCE    = 10000
POSITION_SIZE_PCT  = 5

# ═══════════════════════════════════════
# 🎯 الإعدادات المحسّنة
# ═══════════════════════════════════════
TIMEFRAME_MINUTES = 60      # إطار الساعة
SCAN_INTERVAL     = 3600    # فحص كل ساعة
DELAY_BETWEEN     = 2       # 2 ثانية بين الطلبات (مهم!)
USE_CLOSED_CANDLE = True    # الشمعة المكتملة

# ═══════════════════════════════════════
# 🎯 الأزواج المتنوعة
# ═══════════════════════════════════════

# كريبتو من Kraken (15 عملة)
KRAKEN_SYMBOLS = {
    "XBTUSD":   {"name": "Bitcoin",     "d": 2},
    "ETHUSD":   {"name": "Ethereum",    "d": 2},
    "SOLUSD":   {"name": "Solana",      "d": 3},
    "XRPUSD":   {"name": "XRP",         "d": 4},
    "ADAUSD":   {"name": "Cardano",     "d": 4},
    "DOTUSD":   {"name": "Polkadot",    "d": 3},
    "LINKUSD":  {"name": "Chainlink",   "d": 3},
    "LTCUSD":   {"name": "Litecoin",    "d": 2},
    "AVAXUSD":  {"name": "Avalanche",   "d": 3},
    "MATICUSD": {"name": "Polygon",     "d": 4},
    "ATOMUSD":  {"name": "Cosmos",      "d": 3},
    "NEARUSD":  {"name": "NEAR",        "d": 3},
    "AAVEUSD":  {"name": "Aave",        "d": 2},
    "BCHUSD":   {"name": "Bitcoin Cash","d": 2},
    "UNIUSD":   {"name": "Uniswap",     "d": 3},
}

# فوركس من Yahoo (10 أزواج)
YAHOO_FOREX = {
    "EURUSD=X": {"name": "EUR/USD",  "d": 5},
    "GBPUSD=X": {"name": "GBP/USD",  "d": 5},
    "USDJPY=X": {"name": "USD/JPY",  "d": 3},
    "USDCHF=X": {"name": "USD/CHF",  "d": 5},
    "AUDUSD=X": {"name": "AUD/USD",  "d": 5},
    "USDCAD=X": {"name": "USD/CAD",  "d": 5},
    "NZDUSD=X": {"name": "NZD/USD",  "d": 5},
    "EURJPY=X": {"name": "EUR/JPY",  "d": 3},
    "GBPJPY=X": {"name": "GBP/JPY",  "d": 3},
    "EURGBP=X": {"name": "EUR/GBP",  "d": 5},
}

# سلع من Yahoo (5)
YAHOO_COMMODITIES = {
    "GC=F":  {"name": "Gold",        "d": 2},
    "SI=F":  {"name": "Silver",      "d": 3},
    "CL=F":  {"name": "Crude Oil",   "d": 2},
    "NG=F":  {"name": "Natural Gas", "d": 3},
    "HG=F":  {"name": "Copper",      "d": 4},
}

# أسهم من Yahoo (15)
YAHOO_STOCKS = {
    "AAPL":  {"name": "Apple",     "d": 2},
    "MSFT":  {"name": "Microsoft", "d": 2},
    "GOOGL": {"name": "Google",    "d": 2},
    "AMZN":  {"name": "Amazon",    "d": 2},
    "TSLA":  {"name": "Tesla",     "d": 2},
    "NVDA":  {"name": "NVIDIA",    "d": 2},
    "META":  {"name": "Meta",      "d": 2},
    "AMD":   {"name": "AMD",       "d": 2},
    "NFLX":  {"name": "Netflix",   "d": 2},
    "DIS":   {"name": "Disney",    "d": 2},
    "JPM":   {"name": "JPMorgan",  "d": 2},
    "V":     {"name": "Visa",      "d": 2},
    "WMT":   {"name": "Walmart",   "d": 2},
    "KO":    {"name": "Coca-Cola", "d": 2},
    "MCD":   {"name": "McDonalds", "d": 2},
}

# مؤشرات من Yahoo (5)
YAHOO_INDICES = {
    "^GSPC":  {"name": "S&P 500",    "d": 2},
    "^IXIC":  {"name": "NASDAQ",     "d": 2},
    "^DJI":   {"name": "Dow Jones",  "d": 2},
    "^FTSE":  {"name": "FTSE 100",   "d": 2},
    "^N225":  {"name": "Nikkei",     "d": 2},
}

# متغيرات
active_trades = {}
trade_history = []
balance       = INITIAL_BALANCE

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}


# ============================================
# تلغرام
# ============================================
def send_telegram(text):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        for i in range(0, len(text), 4000):
            r = requests.post(url, json={
                "chat_id": CHAT_ID,
                "text": text[i:i+4000],
                "parse_mode": "HTML"
            }, timeout=15)
            time.sleep(0.3)
    except Exception as e:
        print(f"❌ Telegram: {e}")


# ============================================
# 🌐 Kraken API (للكريبتو)
# ============================================
def get_kraken_data(pair, interval=60):
    try:
        url = "https://api.kraken.com/0/public/OHLC"
        params = {"pair": pair, "interval": interval}
        
        response = requests.get(url, params=params, headers=HEADERS, timeout=15)
        
        if response.status_code != 200:
            return None
        
        data = response.json()
        
        if data.get('error') and len(data['error']) > 0:
            return None
        
        result = data.get('result', {})
        keys = [k for k in result.keys() if k != 'last']
        
        if not keys:
            return None
        
        candles = result[keys[0]]
        
        if not candles or len(candles) < 60:
            return None
        
        df = pd.DataFrame(candles, columns=[
            'timestamp', 'Open', 'High', 'Low', 'Close', 'vwap', 'Volume', 'count'
        ])
        
        df['timestamp'] = pd.to_datetime(df['timestamp'].astype(int), unit='s')
        df.set_index('timestamp', inplace=True)
        
        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            df[col] = df[col].astype(float)
        
        return df[['Open', 'High', 'Low', 'Close', 'Volume']]
        
    except Exception as e:
        return None


# ============================================
# 🌐 Yahoo Finance (للفوركس والأسهم والسلع)
# ⭐ مع threads=False لتجنب Rate Limiting!
# ============================================
def get_yahoo_data(symbol, period="30d", interval="1h"):
    """جلب البيانات من Yahoo Finance"""
    try:
        df = yf.download(
            symbol,
            period=period,
            interval=interval,
            progress=False,
            auto_adjust=True,
            threads=False  # ⭐ مهم جداً!
        )
        
        if df.empty or len(df) < 60:
            return None
        
        # تنظيف الأعمدة
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        # تأكد من الأعمدة
        required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        for col in required_cols:
            if col not in df.columns:
                return None
        
        return df[required_cols]
        
    except Exception as e:
        return None


# ============================================
# دالة موحدة لجلب البيانات
# ============================================
def get_data(symbol, category):
    """جلب البيانات حسب النوع"""
    if category == "crypto":
        return get_kraken_data(symbol, interval=TIMEFRAME_MINUTES)
    else:  # forex, commodity, stock, index
        interval = "1h" if TIMEFRAME_MINUTES == 60 else f"{TIMEFRAME_MINUTES}m"
        return get_yahoo_data(symbol, period="30d", interval=interval)


# ============================================
# حساب المؤشرات (نفس الكود السابق)
# ============================================
def calculate_atr(df, period=1):
    high = df['High'].values
    low = df['Low'].values
    close = df['Close'].values
    
    tr = np.zeros(len(df))
    for i in range(1, len(df)):
        tr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i-1]),
            abs(low[i] - close[i-1])
        )
    
    return pd.Series(tr).rolling(period).mean()


def calculate_chandelier_exit(df, period=1, multiplier=2.0):
    atr = calculate_atr(df, period) * multiplier
    atr_values = atr.values
    
    highest = df['Close'].rolling(period).max().values
    lowest = df['Close'].rolling(period).min().values
    close_arr = df['Close'].values
    
    long_stop = np.zeros(len(df))
    short_stop = np.zeros(len(df))
    
    for i in range(len(df)):
        if not np.isnan(atr_values[i]):
            long_stop[i] = highest[i] - atr_values[i]
            short_stop[i] = lowest[i] + atr_values[i]
    
    for i in range(1, len(df)):
        if not np.isnan(long_stop[i]) and not np.isnan(long_stop[i-1]):
            if close_arr[i-1] > long_stop[i-1]:
                long_stop[i] = max(long_stop[i], long_stop[i-1])
        
        if not np.isnan(short_stop[i]) and not np.isnan(short_stop[i-1]):
            if close_arr[i-1] < short_stop[i-1]:
                short_stop[i] = min(short_stop[i], short_stop[i-1])
    
    dir_arr = np.ones(len(df))
    for i in range(1, len(df)):
        if close_arr[i] > short_stop[i-1]:
            dir_arr[i] = 1
        elif close_arr[i] < long_stop[i-1]:
            dir_arr[i] = -1
        else:
            dir_arr[i] = dir_arr[i-1]
    
    return pd.Series(dir_arr, index=df.index)


def calculate_zlsma_fast(df, length=50):
    close = df['Close'].values
    n = len(close)
    
    if n < length * 2:
        return pd.Series(np.full(n, np.nan), index=df.index)
    
    lsma = np.full(n, np.nan)
    x = np.arange(length)
    x_mean = x.mean()
    x_var = ((x - x_mean) ** 2).sum()
    
    for i in range(length, n):
        y = close[i-length:i]
        y_mean = y.mean()
        slope = ((x - x_mean) * (y - y_mean)).sum() / x_var
        intercept = y_mean - slope * x_mean
        lsma[i] = intercept + slope * (length - 1)
    
    lsma2 = np.full(n, np.nan)
    for i in range(length * 2, n):
        y = lsma[i-length:i]
        if not np.any(np.isnan(y)):
            y_mean = y.mean()
            slope = ((x - x_mean) * (y - y_mean)).sum() / x_var
            intercept = y_mean - slope * x_mean
            lsma2[i] = intercept + slope * (length - 1)
    
    zlsma = lsma + (lsma - lsma2)
    return pd.Series(zlsma, index=df.index)


def generate_signals(df):
    try:
        df = df.copy()
        df['CE_Dir'] = calculate_chandelier_exit(df, ATR_PERIOD, ATR_MULTIPLIER)
        df['ZLSMA'] = calculate_zlsma_fast(df, ZLSMA_LENGTH)
        
        df = df.dropna(subset=['CE_Dir', 'ZLSMA'])
        
        if len(df) < 5:
            return None
        
        df['CE_Buy']  = (df['CE_Dir'] == 1)  & (df['CE_Dir'].shift(1) == -1)
        df['CE_Sell'] = (df['CE_Dir'] == -1) & (df['CE_Dir'].shift(1) == 1)
        
        df['Buy_Signal']  = df['CE_Buy']  & (df['Close'] > df['ZLSMA'])
        df['Sell_Signal'] = df['CE_Sell'] & (df['Close'] < df['ZLSMA'])
        
        return df
    except Exception as e:
        raise Exception(f"signals: {str(e)}")


# ============================================
# منطق الصفقات
# ============================================
def open_trade(symbol, info, signal_type, price, timestamp, category):
    global balance
    
    if symbol in active_trades:
        return None
    
    if signal_type == "BUY":
        sl = price * (1 - STOP_LOSS_PCT/100) if USE_STOP_LOSS else None
    else:
        sl = price * (1 + STOP_LOSS_PCT/100) if USE_STOP_LOSS else None
    
    trade_size = balance * (POSITION_SIZE_PCT / 100)
    quantity = trade_size / price
    
    trade = {
        "symbol": symbol, "name": info['name'],
        "type": signal_type, "entry_price": price,
        "sl": sl, "quantity": quantity,
        "trade_size": trade_size, "entry_time": timestamp,
        "status": "OPEN", "category": category
    }
    
    active_trades[symbol] = trade
    
    emoji = "🟢" if signal_type == "BUY" else "🔴"
    cat_emoji = {"crypto":"🪙","forex":"💱","commodity":"🥇","stock":"🏢","index":"📊"}.get(category,"📈")
    d = info['d']
    
    msg = f"{emoji} <b>صفقة جديدة!</b>\n"
    msg += f"━━━━━━━━━━━━━━━━━━━\n"
    msg += f"{cat_emoji} {info['name']}\n"
    msg += f"📊 {'شراء LONG' if signal_type == 'BUY' else 'بيع SHORT'}\n"
    msg += f"━━━━━━━━━━━━━━━━━━━\n"
    msg += f"💵 الدخول: {price:.{d}f}\n"
    if sl:
        msg += f"🛡️ SL: {sl:.{d}f} ({STOP_LOSS_PCT}%)\n"
    msg += f"🎯 الخروج: عند الإشارة العكسية\n"
    msg += f"━━━━━━━━━━━━━━━━━━━\n"
    msg += f"💰 الحجم: ${trade_size:.2f}\n"
    msg += f"⏰ {timestamp.strftime('%Y-%m-%d %H:%M')}\n"
    msg += f"━━━━━━━━━━━━━━━━━━━\n"
    msg += f"💼 الرصيد: ${balance:.2f}\n"
    msg += f"📊 مفتوحة: {len(active_trades)}"
    
    send_telegram(msg)
    print(f"\n  ✅ OPEN: {info['name']} {signal_type} @ {price:.{d}f}")
    return trade


def close_trade(symbol, close_price, reason, timestamp):
    global balance
    
    if symbol not in active_trades:
        return None
    
    trade = active_trades[symbol]
    
    # جلب معلومات الرمز
    cat = trade['category']
    if cat == 'crypto':
        info = KRAKEN_SYMBOLS.get(symbol, {})
    elif cat == 'forex':
        info = YAHOO_FOREX.get(symbol, {})
    elif cat == 'commodity':
        info = YAHOO_COMMODITIES.get(symbol, {})
    elif cat == 'stock':
        info = YAHOO_STOCKS.get(symbol, {})
    elif cat == 'index':
        info = YAHOO_INDICES.get(symbol, {})
    else:
        info = {}
    
    d = info.get('d', 2)
    
    if trade['type'] == "BUY":
        profit_pct = ((close_price - trade['entry_price']) / trade['entry_price']) * 100
    else:
        profit_pct = ((trade['entry_price'] - close_price) / trade['entry_price']) * 100
    
    profit_usd = trade['trade_size'] * (profit_pct / 100)
    balance += profit_usd
    
    trade['exit_price'] = close_price
    trade['exit_time'] = timestamp
    trade['profit_pct'] = profit_pct
    trade['profit_usd'] = profit_usd
    trade['reason'] = reason
    trade['status'] = "CLOSED"
    
    trade_history.append(trade.copy())
    del active_trades[symbol]
    
    is_profit = profit_usd > 0
    emoji = "✅" if is_profit else "❌"
    result = "ربح" if is_profit else "خسارة"
    
    duration = timestamp - trade['entry_time']
    hours = int(duration.total_seconds() / 3600)
    minutes = int((duration.total_seconds() % 3600) / 60)
    
    cat_emoji = {"crypto":"🪙","forex":"💱","commodity":"🥇","stock":"🏢","index":"📊"}.get(cat,"📈")
    
    msg = f"{emoji} <b>صفقة مغلقة!</b>\n"
    msg += f"━━━━━━━━━━━━━━━━━━━\n"
    msg += f"{cat_emoji} {trade['name']}\n"
    msg += f"📊 {trade['type']}\n"
    msg += f"🔔 {reason}\n"
    msg += f"━━━━━━━━━━━━━━━━━━━\n"
    msg += f"💵 دخول: {trade['entry_price']:.{d}f}\n"
    msg += f"💸 خروج: {close_price:.{d}f}\n"
    msg += f"⏱️ المدة: {hours}س {minutes}د\n"
    msg += f"━━━━━━━━━━━━━━━━━━━\n"
    msg += f"{'🟢' if is_profit else '🔴'} <b>{result}: {profit_pct:+.2f}%</b>\n"
    msg += f"💰 ${profit_usd:+.2f}\n"
    msg += f"━━━━━━━━━━━━━━━━━━━\n"
    msg += f"💼 الرصيد: ${balance:.2f}\n"
    
    total = len(trade_history)
    wins = sum(1 for t in trade_history if t['profit_usd'] > 0)
    wr = (wins / total * 100) if total > 0 else 0
    profit = sum(t['profit_usd'] for t in trade_history)
    
    msg += f"\n📊 الصفقات: {total} | ✅ {wins} | ❌ {total - wins}\n"
    msg += f"📈 Win Rate: {wr:.1f}%\n"
    msg += f"💰 إجمالي: ${profit:+.2f}"
    
    send_telegram(msg)
    print(f"\n  {emoji} CLOSE: {trade['name']} {result} ${profit_usd:+.2f}")
    return trade


def process_signals(symbol, info, df, category):
    """استخدام الشمعة المكتملة"""
    if df is None or len(df) < 5:
        return
    
    if USE_CLOSED_CANDLE and len(df) > 2:
        last = df.iloc[-2]  # الشمعة المكتملة
        current = float(df.iloc[-1]['Close'])  # السعر الحالي
    else:
        last = df.iloc[-1]
        current = float(last['Close'])
    
    ts = last.name.to_pydatetime()
    
    if symbol in active_trades:
        trade = active_trades[symbol]
        if trade['sl'] is not None:
            if trade['type'] == "BUY" and current <= trade['sl']:
                close_trade(symbol, trade['sl'], "🛡️ Stop Loss", ts)
            elif trade['type'] == "SELL" and current >= trade['sl']:
                close_trade(symbol, trade['sl'], "🛡️ Stop Loss", ts)
    
    has_buy = bool(last.get('Buy_Signal', False))
    has_sell = bool(last.get('Sell_Signal', False))
    
    if has_buy:
        if symbol in active_trades and active_trades[symbol]['type'] == "SELL":
            close_trade(symbol, current, "🔄 عكس الاتجاه", ts)
        if symbol not in active_trades:
            open_trade(symbol, info, "BUY", current, ts, category)
    
    elif has_sell:
        if symbol in active_trades and active_trades[symbol]['type'] == "BUY":
            close_trade(symbol, current, "🔄 عكس الاتجاه", ts)
        if symbol not in active_trades:
            open_trade(symbol, info, "SELL", current, ts, category)


def scan_symbol(symbol, info, category):
    df = get_data(symbol, category)
    
    if df is None:
        return False, "لا بيانات"
    
    if len(df) < 60:
        return False, f"بيانات قليلة ({len(df)})"
    
    try:
        df = generate_signals(df)
        
        if df is None:
            return False, "signals=None"
        
        process_signals(symbol, info, df, category)
        return True, "OK"
        
    except Exception as e:
        return False, str(e)[:60]


# ============================================
# التقرير
# ============================================
def send_report():
    total = len(trade_history)
    active = len(active_trades)
    
    if total == 0 and active == 0:
        return
    
    wins = sum(1 for t in trade_history if t['profit_usd'] > 0)
    losses = total - wins
    wr = (wins / total * 100) if total > 0 else 0
    profit = sum(t['profit_usd'] for t in trade_history)
    roi = ((balance - INITIAL_BALANCE) / INITIAL_BALANCE) * 100
    
    msg = f"📊 <b>التقرير الدوري</b>\n"
    msg += f"━━━━━━━━━━━━━━━━━━━\n"
    msg += f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
    msg += f"💼 الرصيد: ${balance:.2f}\n"
    msg += f"📈 ROI: {roi:+.2f}%\n"
    msg += f"━━━━━━━━━━━━━━━━━━━\n"
    msg += f"إجمالي: {total}\n"
    msg += f"✅ رابحة: {wins}\n"
    msg += f"❌ خاسرة: {losses}\n"
    msg += f"📊 Win Rate: {wr:.1f}%\n"
    msg += f"💰 الربح: ${profit:+.2f}\n"
    msg += f"━━━━━━━━━━━━━━━━━━━\n"
    msg += f"🔴 المفتوحة: {active}\n"
    
    if active_trades:
        for sym, t in active_trades.items():
            msg += f"  • {t['name']} {t['type']} @ {t['entry_price']:.4f}\n"
    
    send_telegram(msg)


# ============================================
# الحلقة الرئيسية
# ============================================
def main():
    # جمع كل الأزواج
    all_symbols = []
    for sym, info in KRAKEN_SYMBOLS.items():
        all_symbols.append((sym, info, "crypto"))
    for sym, info in YAHOO_FOREX.items():
        all_symbols.append((sym, info, "forex"))
    for sym, info in YAHOO_COMMODITIES.items():
        all_symbols.append((sym, info, "commodity"))
    for sym, info in YAHOO_STOCKS.items():
        all_symbols.append((sym, info, "stock"))
    for sym, info in YAHOO_INDICES.items():
        all_symbols.append((sym, info, "index"))
    
    print("=" * 60)
    print("🤖 CE + ZLSMA Bot v10.0 - Multi-Market (FREE)")
    print("=" * 60)
    print(f"📊 إجمالي الأزواج: {len(all_symbols)}")
    print(f"  🪙 كريبتو: {len(KRAKEN_SYMBOLS)} (Kraken)")
    print(f"  💱 فوركس: {len(YAHOO_FOREX)} (Yahoo)")
    print(f"  🥇 سلع: {len(YAHOO_COMMODITIES)} (Yahoo)")
    print(f"  🏢 أسهم: {len(YAHOO_STOCKS)} (Yahoo)")
    print(f"  📊 مؤشرات: {len(YAHOO_INDICES)} (Yahoo)")
    print(f"⏰ الإطار: 1h (الساعة)")
    print(f"🔄 الفحص: كل ساعة")
    print(f"🎯 الشمعة المكتملة (دقة عالية)")
    print(f"💰 الرصيد: ${INITIAL_BALANCE}")
    print(f"✅ مصادر مجانية 100%")
    print("=" * 60)
    
    # اختبارات
    print("\n📡 اختبار Kraken...")
    test_k = get_kraken_data("XBTUSD", interval=60)
    if test_k is not None:
        print(f"✅ Kraken: BTC ${test_k['Close'].iloc[-1]:.2f}")
    else:
        print("❌ Kraken لا يعمل!")
    
    print("\n📡 اختبار Yahoo Finance...")
    test_y = get_yahoo_data("EURUSD=X", period="10d", interval="1h")
    if test_y is not None:
        print(f"✅ Yahoo: EUR/USD {test_y['Close'].iloc[-1]:.5f}")
    else:
        print("❌ Yahoo لا يعمل!")
        print("⚠️ سنستخدم Kraken فقط")
    
    send_telegram(
        f"🤖 <b>Trading Bot v10.0</b>\n\n"
        f"✅ <b>تم التشغيل!</b>\n\n"
        f"📊 <b>{len(all_symbols)} أصل متنوع:</b>\n"
        f"  🪙 كريبتو: {len(KRAKEN_SYMBOLS)}\n"
        f"  💱 فوركس: {len(YAHOO_FOREX)}\n"
        f"  🥇 سلع: {len(YAHOO_COMMODITIES)}\n"
        f"  🏢 أسهم: {len(YAHOO_STOCKS)}\n"
        f"  📊 مؤشرات: {len(YAHOO_INDICES)}\n\n"
        f"🎯 <b>التحسينات:</b>\n"
        f"  ✅ إطار 1h (دقة عالية)\n"
        f"  ✅ شمعة مكتملة\n"
        f"  ✅ فحص كل ساعة\n"
        f"  ✅ threads=False (لا حظر)\n\n"
        f"⚙️ الإعدادات:\n"
        f"  • CE: {ATR_PERIOD}/{ATR_MULTIPLIER}\n"
        f"  • ZLSMA: {ZLSMA_LENGTH}\n"
        f"  • SL: {STOP_LOSS_PCT}%\n"
        f"  • الحجم: {POSITION_SIZE_PCT}%\n\n"
        f"💰 الرصيد: ${INITIAL_BALANCE}\n"
        f"✅ 100% مجاني!"
    )
    
    scan_count = 0
    last_report = datetime.now()
    
    while True:
        try:
            scan_count += 1
            now = datetime.now()
            print(f"\n{'='*60}")
            print(f"🔍 Scan #{scan_count} - {now.strftime('%H:%M:%S')}")
            print(f"{'='*60}")
            
            success = 0
            success_by_cat = {}
            errors = {}
            
            for i, (symbol, info, category) in enumerate(all_symbols, 1):
                cat_emoji = {"crypto":"🪙","forex":"💱","commodity":"🥇","stock":"🏢","index":"📊"}.get(category,"📈")
                print(f"  [{i:2}/{len(all_symbols)}] {cat_emoji} {info['name']:15}", end=" ")
                
                ok, msg = scan_symbol(symbol, info, category)
                
                if ok:
                    print("✓")
                    success += 1
                    success_by_cat[category] = success_by_cat.get(category, 0) + 1
                else:
                    print(f"❌ {msg}")
                    errors[msg] = errors.get(msg, 0) + 1
                
                time.sleep(DELAY_BETWEEN)
            
            print(f"\n📊 نجح: {success}/{len(all_symbols)}")
            
            if success_by_cat:
                print(f"📈 حسب الفئة:")
                for cat, count in success_by_cat.items():
                    print(f"   {cat}: {count}")
            
            if errors:
                print(f"❌ الأخطاء:")
                for err, count in list(errors.items())[:3]:
                    print(f"   • {err}: {count}")
            
            print(f"💼 الرصيد: ${balance:.2f}")
            print(f"🔴 مفتوحة: {len(active_trades)}")
            print(f"📈 مغلقة: {len(trade_history)}")
            
            if scan_count == 1:
                cat_summary = "\n".join([f"  ✅ {c}: {n}" for c, n in success_by_cat.items()])
                send_telegram(
                    f"✅ <b>أول فحص!</b>\n\n"
                    f"📊 نجح: {success}/{len(all_symbols)}\n\n"
                    f"{cat_summary}\n\n"
                    f"⏳ فحص كل ساعة"
                )
            
            if (now - last_report).total_seconds() > 21600:
                send_report()
                last_report = now
            
            print(f"\n⏳ انتظار {SCAN_INTERVAL//60} دقيقة...")
            time.sleep(SCAN_INTERVAL)
            
        except KeyboardInterrupt:
            send_telegram("🛑 تم إيقاف البوت")
            break
        except Exception as e:
            print(f"❌ خطأ: {e}")
            time.sleep(60)


if __name__ == "__main__":
    main()
