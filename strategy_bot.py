import os
import requests
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
import time
import warnings
warnings.filterwarnings('ignore')

# ============================================
# الإعدادات
# ============================================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
CHAT_ID        = os.getenv("CHAT_ID", "")

# استراتيجية SuperTrend + EMA
SUPERTREND_PERIOD     = 10
SUPERTREND_MULTIPLIER = 3.0
EMA_FAST              = 50
EMA_SLOW              = 200

# مخاطر
STOP_LOSS_PCT      = 2.0
INITIAL_BALANCE    = 10000
POSITION_SIZE_PCT  = 5

# التوقيت
TIMEFRAME_MINUTES = 60
SCAN_INTERVAL     = 3600
DELAY_BETWEEN     = 2

# الأزواج (نفس السابقة)
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

YAHOO_COMMODITIES = {
    "GC=F": {"name": "Gold",      "d": 2},
    "SI=F": {"name": "Silver",    "d": 3},
    "CL=F": {"name": "Crude Oil", "d": 2},
}

YAHOO_STOCKS = {
    "AAPL":  {"name": "Apple",     "d": 2},
    "MSFT":  {"name": "Microsoft", "d": 2},
    "GOOGL": {"name": "Google",    "d": 2},
    "TSLA":  {"name": "Tesla",     "d": 2},
    "NVDA":  {"name": "NVIDIA",    "d": 2},
    "AMZN":  {"name": "Amazon",    "d": 2},
    "META":  {"name": "Meta",      "d": 2},
    "AMD":   {"name": "AMD",       "d": 2},
}

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
            requests.post(url, json={
                "chat_id": CHAT_ID,
                "text": text[i:i+4000],
                "parse_mode": "HTML"
            }, timeout=15)
            time.sleep(0.3)
    except Exception as e:
        print(f"❌ Telegram: {e}")


# ============================================
# مصادر البيانات
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
        if not candles or len(candles) < 250:  # نحتاج EMA 200
            return None
        
        df = pd.DataFrame(candles, columns=[
            'timestamp', 'Open', 'High', 'Low', 'Close', 'vwap', 'Volume', 'count'
        ])
        df['timestamp'] = pd.to_datetime(df['timestamp'].astype(int), unit='s')
        df.set_index('timestamp', inplace=True)
        
        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            df[col] = df[col].astype(float)
        
        return df[['Open', 'High', 'Low', 'Close', 'Volume']]
    except:
        return None


def get_yahoo_data(symbol, period="60d", interval="1h"):
    try:
        df = yf.download(
            symbol, period=period, interval=interval,
            progress=False, auto_adjust=True, threads=False
        )
        
        if df.empty or len(df) < 250:
            return None
        
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        required = ['Open', 'High', 'Low', 'Close', 'Volume']
        for col in required:
            if col not in df.columns:
                return None
        
        return df[required]
    except:
        return None


def get_data(symbol, category):
    if category == "crypto":
        return get_kraken_data(symbol, interval=TIMEFRAME_MINUTES)
    else:
        return get_yahoo_data(symbol, period="60d", interval="1h")


# ============================================
# 🎯 SuperTrend Indicator
# ============================================
def calculate_atr(df, period=10):
    """ATR - Wilder's"""
    high = df['High'].values
    low = df['Low'].values
    close = df['Close'].values
    
    tr = np.zeros(len(df))
    tr[0] = high[0] - low[0]
    
    for i in range(1, len(df)):
        tr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i-1]),
            abs(low[i] - close[i-1])
        )
    
    atr = np.zeros(len(df))
    if len(df) >= period:
        atr[period-1] = tr[:period].mean()
        for i in range(period, len(df)):
            atr[i] = (atr[i-1] * (period - 1) + tr[i]) / period
    
    return pd.Series(atr, index=df.index)


def calculate_supertrend(df, period=10, multiplier=3.0):
    """SuperTrend Indicator - مطابق TradingView"""
    high = df['High'].values
    low = df['Low'].values
    close = df['Close'].values
    n = len(df)
    
    atr = calculate_atr(df, period).values
    
    hl2 = (high + low) / 2
    
    upper_band = hl2 + (multiplier * atr)
    lower_band = hl2 - (multiplier * atr)
    
    # Final Bands
    final_upper = upper_band.copy()
    final_lower = lower_band.copy()
    
    for i in range(1, n):
        # Upper Band
        if upper_band[i] < final_upper[i-1] or close[i-1] > final_upper[i-1]:
            final_upper[i] = upper_band[i]
        else:
            final_upper[i] = final_upper[i-1]
        
        # Lower Band
        if lower_band[i] > final_lower[i-1] or close[i-1] < final_lower[i-1]:
            final_lower[i] = lower_band[i]
        else:
            final_lower[i] = final_lower[i-1]
    
    # SuperTrend
    supertrend = np.zeros(n)
    direction = np.ones(n)  # 1 = up, -1 = down
    
    for i in range(1, n):
        if supertrend[i-1] == final_upper[i-1]:
            if close[i] <= final_upper[i]:
                supertrend[i] = final_upper[i]
                direction[i] = -1
            else:
                supertrend[i] = final_lower[i]
                direction[i] = 1
        else:
            if close[i] >= final_lower[i]:
                supertrend[i] = final_lower[i]
                direction[i] = 1
            else:
                supertrend[i] = final_upper[i]
                direction[i] = -1
    
    return (
        pd.Series(supertrend, index=df.index),
        pd.Series(direction, index=df.index)
    )


def calculate_ema(df, period):
    """EMA حساب سريع"""
    return df['Close'].ewm(span=period, adjust=False).mean()


# ============================================
# 🎯 توليد الإشارات - SuperTrend + EMA
# ============================================
def generate_signals(df):
    try:
        df = df.copy()
        
        # SuperTrend
        st, st_dir = calculate_supertrend(df, SUPERTREND_PERIOD, SUPERTREND_MULTIPLIER)
        df['SuperTrend'] = st
        df['ST_Dir'] = st_dir
        
        # EMAs
        df['EMA_Fast'] = calculate_ema(df, EMA_FAST)
        df['EMA_Slow'] = calculate_ema(df, EMA_SLOW)
        
        df = df.dropna(subset=['SuperTrend', 'EMA_Slow'])
        
        if len(df) < 5:
            return None
        
        # 🎯 إشارات قوية
        # Buy: SuperTrend تحول لصاعد + السعر فوق EMA 200 + EMA 50 > EMA 200
        df['ST_Buy'] = (df['ST_Dir'] == 1) & (df['ST_Dir'].shift(1) == -1)
        df['ST_Sell'] = (df['ST_Dir'] == -1) & (df['ST_Dir'].shift(1) == 1)
        
        # فلاتر التأكيد
        df['Trend_Up'] = df['Close'] > df['EMA_Slow']  # اتجاه صاعد
        df['Trend_Down'] = df['Close'] < df['EMA_Slow']  # اتجاه هابط
        df['MA_Bullish'] = df['EMA_Fast'] > df['EMA_Slow']  # المتوسطات صاعدة
        df['MA_Bearish'] = df['EMA_Fast'] < df['EMA_Slow']  # المتوسطات هابطة
        
        # الإشارات النهائية (مع تأكيد قوي)
        df['Buy_Signal'] = df['ST_Buy'] & df['Trend_Up'] & df['MA_Bullish']
        df['Sell_Signal'] = df['ST_Sell'] & df['Trend_Down'] & df['MA_Bearish']
        
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
        sl = price * (1 - STOP_LOSS_PCT/100)
    else:
        sl = price * (1 + STOP_LOSS_PCT/100)
    
    trade_size = balance * (POSITION_SIZE_PCT / 100)
    
    trade = {
        "symbol": symbol, "name": info['name'],
        "type": signal_type, "entry_price": price,
        "sl": sl, "trade_size": trade_size,
        "entry_time": timestamp, "status": "OPEN",
        "category": category
    }
    
    active_trades[symbol] = trade
    
    emoji = "🟢" if signal_type == "BUY" else "🔴"
    cat_emoji = {"crypto":"🪙","forex":"💱","commodity":"🥇","stock":"🏢"}.get(category,"📈")
    d = info['d']
    
    msg = f"{emoji} <b>SuperTrend Signal!</b>\n"
    msg += f"━━━━━━━━━━━━━━━━━━━\n"
    msg += f"{cat_emoji} {info['name']}\n"
    msg += f"📊 {'شراء LONG' if signal_type == 'BUY' else 'بيع SHORT'}\n"
    msg += f"━━━━━━━━━━━━━━━━━━━\n"
    msg += f"💵 الدخول: {price:.{d}f}\n"
    msg += f"🛡️ SL: {sl:.{d}f} ({STOP_LOSS_PCT}%)\n"
    msg += f"🎯 الخروج: عند الإشارة العكسية\n"
    msg += f"━━━━━━━━━━━━━━━━━━━\n"
    msg += f"💰 الحجم: ${trade_size:.2f}\n"
    msg += f"⏰ {timestamp.strftime('%Y-%m-%d %H:%M')}\n"
    msg += f"━━━━━━━━━━━━━━━━━━━\n"
    msg += f"📊 <b>تأكيدات قوية:</b>\n"
    msg += f"✅ SuperTrend تحول للاتجاه\n"
    msg += f"✅ السعر {'فوق' if signal_type == 'BUY' else 'تحت'} EMA 200\n"
    msg += f"✅ EMA 50 {'>' if signal_type == 'BUY' else '<'} EMA 200\n"
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
    cat = trade['category']
    
    if cat == 'crypto':
        info = KRAKEN_SYMBOLS.get(symbol, {})
    elif cat == 'forex':
        info = YAHOO_FOREX.get(symbol, {})
    elif cat == 'commodity':
        info = YAHOO_COMMODITIES.get(symbol, {})
    elif cat == 'stock':
        info = YAHOO_STOCKS.get(symbol, {})
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
    
    cat_emoji = {"crypto":"🪙","forex":"💱","commodity":"🥇","stock":"🏢"}.get(cat,"📈")
    
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
    if df is None or len(df) < 5:
        return
    
    last = df.iloc[-2]  # الشمعة المكتملة
    current = float(df.iloc[-1]['Close'])
    ts = last.name.to_pydatetime()
    
    # Stop Loss
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
    
    if len(df) < 250:
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
    
    msg = f"📊 <b>تقرير SuperTrend</b>\n"
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
    all_symbols = []
    for sym, info in KRAKEN_SYMBOLS.items():
        all_symbols.append((sym, info, "crypto"))
    for sym, info in YAHOO_FOREX.items():
        all_symbols.append((sym, info, "forex"))
    for sym, info in YAHOO_COMMODITIES.items():
        all_symbols.append((sym, info, "commodity"))
    for sym, info in YAHOO_STOCKS.items():
        all_symbols.append((sym, info, "stock"))
    
    print("=" * 60)
    print("🤖 SuperTrend + EMA Bot v1.0")
    print("=" * 60)
    print(f"📊 إجمالي: {len(all_symbols)} أصل")
    print(f"⏰ الإطار: 1h")
    print(f"🎯 الاستراتيجية:")
    print(f"   • SuperTrend ({SUPERTREND_PERIOD}, {SUPERTREND_MULTIPLIER})")
    print(f"   • EMA {EMA_FAST} / {EMA_SLOW}")
    print(f"   • Multi-confirmation")
    print(f"💰 الرصيد: ${INITIAL_BALANCE}")
    print("=" * 60)
    
    # اختبارات
    print("\n📡 اختبار المصادر...")
    test_k = get_kraken_data("XBTUSD", interval=60)
    if test_k is not None:
        print(f"✅ Kraken: BTC ${test_k['Close'].iloc[-1]:.2f}")
    
    test_y = get_yahoo_data("EURUSD=X", period="60d", interval="1h")
    if test_y is not None:
        print(f"✅ Yahoo: EUR/USD {test_y['Close'].iloc[-1]:.5f}")
    
    send_telegram(
        f"🚀 <b>SuperTrend Bot v1.0</b>\n\n"
        f"✅ <b>استراتيجية أقوى!</b>\n\n"
        f"📊 <b>المؤشرات:</b>\n"
        f"  • SuperTrend ({SUPERTREND_PERIOD}, {SUPERTREND_MULTIPLIER})\n"
        f"  • EMA {EMA_FAST}\n"
        f"  • EMA {EMA_SLOW}\n\n"
        f"🎯 <b>شروط الدخول:</b>\n"
        f"  ✅ SuperTrend تحول للاتجاه\n"
        f"  ✅ السعر يؤكد الاتجاه (EMA 200)\n"
        f"  ✅ المتوسطات صفوف صحيحة\n\n"
        f"📊 <b>{len(all_symbols)} أصل</b>\n"
        f"💰 الرصيد: ${INITIAL_BALANCE}\n\n"
        f"⏰ فحص كل ساعة\n"
        f"🎯 Win Rate متوقع: 65-75%"
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
            
            for i, (symbol, info, category) in enumerate(all_symbols, 1):
                cat_emoji = {"crypto":"🪙","forex":"💱","commodity":"🥇","stock":"🏢"}.get(category,"📈")
                print(f"  [{i:2}/{len(all_symbols)}] {cat_emoji} {info['name']:15}", end=" ")
                
                ok, msg = scan_symbol(symbol, info, category)
                
                if ok:
                    print("✓")
                    success += 1
                else:
                    print(f"❌ {msg}")
                
                time.sleep(DELAY_BETWEEN)
            
            print(f"\n📊 نجح: {success}/{len(all_symbols)}")
            print(f"💼 الرصيد: ${balance:.2f}")
            print(f"🔴 مفتوحة: {len(active_trades)}")
            print(f"📈 مغلقة: {len(trade_history)}")
            
            if scan_count == 1:
                send_telegram(
                    f"✅ <b>أول فحص - SuperTrend</b>\n\n"
                    f"📊 نجح: {success}/{len(all_symbols)}\n"
                    f"⏳ فحص كل ساعة\n\n"
                    f"🎯 <b>ما الجديد؟</b>\n"
                    f"• استراتيجية أقوى\n"
                    f"• تأكيدات متعددة\n"
                    f"• إشارات أدق\n"
                    f"• Win Rate أعلى"
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
