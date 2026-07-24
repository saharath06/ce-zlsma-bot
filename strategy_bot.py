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

# إعدادات الاستراتيجية (نفس TradingView)
ATR_PERIOD      = 1
ATR_MULTIPLIER  = 2.0
ZLSMA_LENGTH    = 50
ZLSMA_OFFSET    = 0

# إعدادات إدارة المخاطر
USE_STOP_LOSS      = True
STOP_LOSS_PCT      = 2.0
INITIAL_BALANCE    = 10000
POSITION_SIZE_PCT  = 5     # 5% لكل صفقة (لأن الأزواج كثيرة)

# إعدادات الفحص
SCAN_INTERVAL      = 180    # ثانية (بسبب 60 زوج)
TIMEFRAME          = "15m"
PERIOD             = "5d"

# ============================================
# 60 زوج متنوع
# ============================================
SYMBOLS = {
    # ═══════════════════════════════
    # فوركس - Majors (7)
    # ═══════════════════════════════
    "EURUSD=X": {"name": "EUR/USD",   "cat": "forex", "d": 5},
    "GBPUSD=X": {"name": "GBP/USD",   "cat": "forex", "d": 5},
    "USDJPY=X": {"name": "USD/JPY",   "cat": "forex", "d": 3},
    "USDCHF=X": {"name": "USD/CHF",   "cat": "forex", "d": 5},
    "AUDUSD=X": {"name": "AUD/USD",   "cat": "forex", "d": 5},
    "USDCAD=X": {"name": "USD/CAD",   "cat": "forex", "d": 5},
    "NZDUSD=X": {"name": "NZD/USD",   "cat": "forex", "d": 5},
    
    # ═══════════════════════════════
    # فوركس - Crosses (8)
    # ═══════════════════════════════
    "EURJPY=X": {"name": "EUR/JPY",   "cat": "forex", "d": 3},
    "GBPJPY=X": {"name": "GBP/JPY",   "cat": "forex", "d": 3},
    "AUDJPY=X": {"name": "AUD/JPY",   "cat": "forex", "d": 3},
    "CADJPY=X": {"name": "CAD/JPY",   "cat": "forex", "d": 3},
    "CHFJPY=X": {"name": "CHF/JPY",   "cat": "forex", "d": 3},
    "EURGBP=X": {"name": "EUR/GBP",   "cat": "forex", "d": 5},
    "EURCHF=X": {"name": "EUR/CHF",   "cat": "forex", "d": 5},
    "GBPAUD=X": {"name": "GBP/AUD",   "cat": "forex", "d": 5},
    
    # ═══════════════════════════════
    # كريبتو - Top Coins (15)
    # ═══════════════════════════════
    "BTC-USD":   {"name": "Bitcoin",     "cat": "crypto", "d": 2},
    "ETH-USD":   {"name": "Ethereum",    "cat": "crypto", "d": 2},
    "SOL-USD":   {"name": "Solana",      "cat": "crypto", "d": 3},
    "XRP-USD":   {"name": "XRP",         "cat": "crypto", "d": 4},
    "BNB-USD":   {"name": "BNB",         "cat": "crypto", "d": 2},
    "DOGE-USD":  {"name": "Dogecoin",    "cat": "crypto", "d": 5},
    "ADA-USD":   {"name": "Cardano",     "cat": "crypto", "d": 4},
    "AVAX-USD":  {"name": "Avalanche",   "cat": "crypto", "d": 3},
    "LINK-USD":  {"name": "Chainlink",   "cat": "crypto", "d": 3},
    "DOT-USD":   {"name": "Polkadot",    "cat": "crypto", "d": 3},
    "MATIC-USD": {"name": "Polygon",     "cat": "crypto", "d": 4},
    "LTC-USD":   {"name": "Litecoin",    "cat": "crypto", "d": 2},
    "ATOM-USD":  {"name": "Cosmos",      "cat": "crypto", "d": 3},
    "NEAR-USD":  {"name": "NEAR",        "cat": "crypto", "d": 3},
    "UNI-USD":   {"name": "Uniswap",     "cat": "crypto", "d": 3},
    
    # ═══════════════════════════════
    # سلع (6)
    # ═══════════════════════════════
    "GC=F": {"name": "Gold",        "cat": "commodity", "d": 2},
    "SI=F": {"name": "Silver",      "cat": "commodity", "d": 3},
    "CL=F": {"name": "Crude Oil",   "cat": "commodity", "d": 2},
    "BZ=F": {"name": "Brent Oil",   "cat": "commodity", "d": 2},
    "NG=F": {"name": "Natural Gas", "cat": "commodity", "d": 3},
    "HG=F": {"name": "Copper",      "cat": "commodity", "d": 4},
    
    # ═══════════════════════════════
    # مؤشرات (6)
    # ═══════════════════════════════
    "^GSPC":  {"name": "S&P 500",    "cat": "index", "d": 2},
    "^IXIC":  {"name": "NASDAQ",     "cat": "index", "d": 2},
    "^DJI":   {"name": "Dow Jones",  "cat": "index", "d": 2},
    "^RUT":   {"name": "Russell",    "cat": "index", "d": 2},
    "^FTSE":  {"name": "FTSE 100",   "cat": "index", "d": 2},
    "^N225":  {"name": "Nikkei",     "cat": "index", "d": 2},
    
    # ═══════════════════════════════
    # أسهم - Tech (10)
    # ═══════════════════════════════
    "AAPL":  {"name": "Apple",     "cat": "stock", "d": 2},
    "MSFT":  {"name": "Microsoft", "cat": "stock", "d": 2},
    "GOOGL": {"name": "Google",    "cat": "stock", "d": 2},
    "AMZN":  {"name": "Amazon",    "cat": "stock", "d": 2},
    "META":  {"name": "Meta",      "cat": "stock", "d": 2},
    "NVDA":  {"name": "NVIDIA",    "cat": "stock", "d": 2},
    "TSLA":  {"name": "Tesla",     "cat": "stock", "d": 2},
    "NFLX":  {"name": "Netflix",   "cat": "stock", "d": 2},
    "AMD":   {"name": "AMD",       "cat": "stock", "d": 2},
    "INTC":  {"name": "Intel",     "cat": "stock", "d": 2},
    
    # ═══════════════════════════════
    # أسهم - Finance & Others (8)
    # ═══════════════════════════════
    "JPM":  {"name": "JPMorgan",   "cat": "stock", "d": 2},
    "V":    {"name": "Visa",       "cat": "stock", "d": 2},
    "MA":   {"name": "Mastercard", "cat": "stock", "d": 2},
    "BAC":  {"name": "Bank of Am", "cat": "stock", "d": 2},
    "WMT":  {"name": "Walmart",    "cat": "stock", "d": 2},
    "KO":   {"name": "Coca-Cola",  "cat": "stock", "d": 2},
    "DIS":  {"name": "Disney",     "cat": "stock", "d": 2},
    "XOM":  {"name": "Exxon",      "cat": "stock", "d": 2},
}

# متغيرات
active_trades = {}
trade_history = []
balance       = INITIAL_BALANCE


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
# حساب المؤشرات
# ============================================
def calculate_atr(df, period=1):
    high, low, close = df['High'], df['Low'], df['Close']
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def calculate_chandelier_exit(df, period=1, multiplier=2.0):
    """Chandelier Exit - نفس منطق TradingView"""
    atr = calculate_atr(df, period) * multiplier
    
    highest = df['Close'].rolling(period).max()
    long_stop = (highest - atr).values
    
    lowest = df['Close'].rolling(period).min()
    short_stop = (lowest + atr).values
    
    close_arr = df['Close'].values
    
    # تحسين Stops
    for i in range(1, len(df)):
        if not np.isnan(long_stop[i]) and not np.isnan(long_stop[i-1]):
            if close_arr[i-1] > long_stop[i-1]:
                long_stop[i] = max(long_stop[i], long_stop[i-1])
        
        if not np.isnan(short_stop[i]) and not np.isnan(short_stop[i-1]):
            if close_arr[i-1] < short_stop[i-1]:
                short_stop[i] = min(short_stop[i], short_stop[i-1])
    
    # Direction
    dir_arr = np.ones(len(df))
    for i in range(1, len(df)):
        if close_arr[i] > short_stop[i-1]:
            dir_arr[i] = 1
        elif close_arr[i] < long_stop[i-1]:
            dir_arr[i] = -1
        else:
            dir_arr[i] = dir_arr[i-1]
    
    return pd.Series(dir_arr, index=df.index)


def calculate_zlsma(df, length=50, offset=0):
    """ZLSMA - Zero Lag SMA"""
    close = df['Close'].values
    n = len(close)
    result = np.full(n, np.nan)
    
    if n < length * 2:
        return pd.Series(result, index=df.index)
    
    # Linear Regression 1
    lsma = np.full(n, np.nan)
    for i in range(length, n):
        y = close[i-length:i]
        x = np.arange(length)
        coef = np.polyfit(x, y, 1)
        lsma[i] = coef[1] + coef[0] * (length - 1)
    
    # Linear Regression 2
    lsma2 = np.full(n, np.nan)
    for i in range(length * 2, n):
        y = lsma[i-length:i]
        if not np.any(np.isnan(y)):
            x = np.arange(length)
            coef = np.polyfit(x, y, 1)
            lsma2[i] = coef[1] + coef[0] * (length - 1)
    
    # ZLSMA
    zlsma = lsma + (lsma - lsma2)
    
    return pd.Series(zlsma, index=df.index)


def generate_signals(df):
    """توليد إشارات Buy/Sell"""
    df = df.copy()
    df['CE_Dir'] = calculate_chandelier_exit(df, ATR_PERIOD, ATR_MULTIPLIER)
    df['ZLSMA']  = calculate_zlsma(df, ZLSMA_LENGTH, ZLSMA_OFFSET)
    
    df['CE_Buy']  = (df['CE_Dir'] == 1)  & (df['CE_Dir'].shift(1) == -1)
    df['CE_Sell'] = (df['CE_Dir'] == -1) & (df['CE_Dir'].shift(1) == 1)
    
    df['Buy_Signal']  = df['CE_Buy']  & (df['Close'] > df['ZLSMA'])
    df['Sell_Signal'] = df['CE_Sell'] & (df['Close'] < df['ZLSMA'])
    
    return df


# ============================================
# منطق الصفقات
# ============================================
def open_trade(symbol, info, signal_type, price, timestamp):
    """فتح صفقة جديدة"""
    global balance
    
    if symbol in active_trades:
        return None
    
    # Stop Loss للحماية فقط
    if signal_type == "BUY":
        sl = price * (1 - STOP_LOSS_PCT/100) if USE_STOP_LOSS else None
    else:
        sl = price * (1 + STOP_LOSS_PCT/100) if USE_STOP_LOSS else None
    
    trade_size = balance * (POSITION_SIZE_PCT / 100)
    quantity   = trade_size / price
    
    trade = {
        "symbol":      symbol,
        "name":        info['name'],
        "type":        signal_type,
        "entry_price": price,
        "sl":          sl,
        "quantity":    quantity,
        "trade_size":  trade_size,
        "entry_time":  timestamp,
        "status":      "OPEN"
    }
    
    active_trades[symbol] = trade
    
    emoji = "🟢" if signal_type == "BUY" else "🔴"
    d     = info['d']
    
    cat_emoji = {
        "forex":     "💱",
        "crypto":    "🪙",
        "commodity": "🥇",
        "index":     "📊",
        "stock":     "🏢"
    }.get(info['cat'], "📈")
    
    msg  = f"{emoji} <b>صفقة جديدة!</b>\n"
    msg += f"━━━━━━━━━━━━━━━━━━━\n"
    msg += f"{cat_emoji} {info['name']}\n"
    msg += f"📊 النوع: {'شراء LONG' if signal_type == 'BUY' else 'بيع SHORT'}\n"
    msg += f"━━━━━━━━━━━━━━━━━━━\n"
    msg += f"💵 الدخول: {price:.{d}f}\n"
    if sl:
        msg += f"🛡️ حماية SL: {sl:.{d}f} ({STOP_LOSS_PCT}%)\n"
    msg += f"🎯 الخروج: عند الإشارة العكسية\n"
    msg += f"━━━━━━━━━━━━━━━━━━━\n"
    msg += f"💰 حجم الصفقة: ${trade_size:.2f}\n"
    msg += f"⏰ {timestamp.strftime('%Y-%m-%d %H:%M')}\n"
    msg += f"━━━━━━━━━━━━━━━━━━━\n"
    msg += f"💼 الرصيد: ${balance:.2f}\n"
    msg += f"📊 صفقات مفتوحة: {len(active_trades)}"
    
    send_telegram(msg)
    print(f"✅ OPEN: {info['name']} {signal_type} @ {price:.{d}f}")
    
    return trade


def close_trade(symbol, close_price, reason, timestamp):
    """إغلاق صفقة"""
    global balance
    
    if symbol not in active_trades:
        return None
    
    trade = active_trades[symbol]
    d     = SYMBOLS[symbol]['d']
    info  = SYMBOLS[symbol]
    
    if trade['type'] == "BUY":
        profit_pct = ((close_price - trade['entry_price']) / trade['entry_price']) * 100
    else:
        profit_pct = ((trade['entry_price'] - close_price) / trade['entry_price']) * 100
    
    profit_usd = trade['trade_size'] * (profit_pct / 100)
    balance   += profit_usd
    
    trade['exit_price'] = close_price
    trade['exit_time']  = timestamp
    trade['profit_pct'] = profit_pct
    trade['profit_usd'] = profit_usd
    trade['reason']     = reason
    trade['status']     = "CLOSED"
    
    trade_history.append(trade.copy())
    del active_trades[symbol]
    
    is_profit = profit_usd > 0
    emoji     = "✅" if is_profit else "❌"
    result    = "ربح" if is_profit else "خسارة"
    
    duration = timestamp - trade['entry_time']
    hours    = int(duration.total_seconds() / 3600)
    minutes  = int((duration.total_seconds() % 3600) / 60)
    
    cat_emoji = {
        "forex":     "💱",
        "crypto":    "🪙",
        "commodity": "🥇",
        "index":     "📊",
        "stock":     "🏢"
    }.get(info['cat'], "📈")
    
    msg  = f"{emoji} <b>صفقة مغلقة!</b>\n"
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
    
    # إحصائيات
    total  = len(trade_history)
    wins   = sum(1 for t in trade_history if t['profit_usd'] > 0)
    wr     = (wins / total * 100) if total > 0 else 0
    profit = sum(t['profit_usd'] for t in trade_history)
    
    msg += f"\n📊 الصفقات: {total} | ✅ {wins} | ❌ {total - wins}\n"
    msg += f"📈 Win Rate: {wr:.1f}%\n"
    msg += f"💰 إجمالي: ${profit:+.2f}"
    
    send_telegram(msg)
    print(f"{emoji} CLOSE: {trade['name']} {result} ${profit_usd:+.2f}")
    
    return trade


def process_signals(symbol, info, df):
    """معالجة الإشارات الذكية"""
    last     = df.iloc[-1]
    current  = float(last['Close'])
    ts       = last.name.to_pydatetime()
    
    # 1. فحص Stop Loss (حماية)
    if symbol in active_trades:
        trade = active_trades[symbol]
        
        if trade['sl'] is not None:
            if trade['type'] == "BUY" and current <= trade['sl']:
                close_trade(symbol, trade['sl'], "🛡️ Stop Loss", ts)
            elif trade['type'] == "SELL" and current >= trade['sl']:
                close_trade(symbol, trade['sl'], "🛡️ Stop Loss", ts)
    
    # 2. فحص الإشارات
    has_buy  = bool(last['Buy_Signal'])
    has_sell = bool(last['Sell_Signal'])
    
    if has_buy:
        # إغلاق صفقة SHORT قديمة إن وجدت
        if symbol in active_trades and active_trades[symbol]['type'] == "SELL":
            close_trade(symbol, current, "🔄 عكس الاتجاه", ts)
        
        # فتح صفقة LONG
        if symbol not in active_trades:
            open_trade(symbol, info, "BUY", current, ts)
    
    elif has_sell:
        # إغلاق صفقة LONG قديمة إن وجدت
        if symbol in active_trades and active_trades[symbol]['type'] == "BUY":
            close_trade(symbol, current, "🔄 عكس الاتجاه", ts)
        
        # فتح صفقة SHORT
        if symbol not in active_trades:
            open_trade(symbol, info, "SELL", current, ts)


# ============================================
# جلب البيانات
# ============================================
def get_data(symbol):
    try:
        df = yf.download(
            symbol, period=PERIOD, interval=TIMEFRAME,
            progress=False, auto_adjust=True
        )
        if df.empty or len(df) < 60:
            return None
        
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        return df
    except:
        return None


def scan_symbol(symbol, info):
    df = get_data(symbol)
    if df is None:
        return
    
    df = generate_signals(df)
    process_signals(symbol, info, df)


# ============================================
# التقرير الدوري
# ============================================
def send_report():
    total    = len(trade_history)
    active   = len(active_trades)
    
    if total == 0 and active == 0:
        return
    
    wins     = sum(1 for t in trade_history if t['profit_usd'] > 0)
    losses   = total - wins
    wr       = (wins / total * 100) if total > 0 else 0
    profit   = sum(t['profit_usd'] for t in trade_history)
    roi      = ((balance - INITIAL_BALANCE) / INITIAL_BALANCE) * 100
    
    # أفضل صفقة
    best  = max(trade_history, key=lambda x: x['profit_usd']) if trade_history else None
    worst = min(trade_history, key=lambda x: x['profit_usd']) if trade_history else None
    
    msg  = f"📊 <b>التقرير الدوري</b>\n"
    msg += f"━━━━━━━━━━━━━━━━━━━\n"
    msg += f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
    msg += f"💼 الرصيد: ${balance:.2f}\n"
    msg += f"💰 الأصلي: ${INITIAL_BALANCE}\n"
    msg += f"📈 ROI: {roi:+.2f}%\n"
    msg += f"━━━━━━━━━━━━━━━━━━━\n"
    msg += f"📊 <b>الإحصائيات:</b>\n"
    msg += f"إجمالي الصفقات: {total}\n"
    msg += f"✅ رابحة: {wins}\n"
    msg += f"❌ خاسرة: {losses}\n"
    msg += f"📊 Win Rate: {wr:.1f}%\n"
    msg += f"💰 إجمالي الربح: ${profit:+.2f}\n"
    
    if best:
        msg += f"\n🏆 أفضل صفقة:\n"
        msg += f"  {best['name']} {best['type']} +${best['profit_usd']:.2f}\n"
    
    if worst and worst['profit_usd'] < 0:
        msg += f"\n💔 أسوأ صفقة:\n"
        msg += f"  {worst['name']} {worst['type']} ${worst['profit_usd']:.2f}\n"
    
    msg += f"\n━━━━━━━━━━━━━━━━━━━\n"
    msg += f"🔴 المفتوحة الآن: {active}\n"
    
    if active_trades:
        for sym, t in list(active_trades.items())[:10]:
            d = SYMBOLS[sym]['d']
            msg += f"  • {t['name']} {t['type']} @ {t['entry_price']:.{d}f}\n"
        if len(active_trades) > 10:
            msg += f"  ... و {len(active_trades) - 10} أخرى\n"
    
    send_telegram(msg)


# ============================================
# الحلقة الرئيسية
# ============================================
def main():
    print("=" * 60)
    print("🤖 CE + ZLSMA Smart Trading Bot v3.0")
    print("=" * 60)
    print(f"📊 الأزواج: {len(SYMBOLS)}")
    print(f"⏰ الإطار: {TIMEFRAME}")
    print(f"💰 الرصيد: ${INITIAL_BALANCE}")
    print(f"🔄 فحص كل: {SCAN_INTERVAL} ثانية")
    print("=" * 60)
    
    # تقسيم حسب الفئة
    cats = {}
    for s, info in SYMBOLS.items():
        cats[info['cat']] = cats.get(info['cat'], 0) + 1
    
    cat_summary = ""
    for c, n in cats.items():
        emoji = {
            "forex":     "💱",
            "crypto":    "🪙",
            "commodity": "🥇",
            "index":     "📊",
            "stock":     "🏢"
        }.get(c, "📈")
        cat_summary += f"  {emoji} {c}: {n}\n"
    
    send_telegram(
        f"🤖 <b>Smart Trading Bot v3.0</b>\n\n"
        f"📋 <b>الاستراتيجية:</b> CE + ZLSMA\n\n"
        f"🎯 <b>المنطق:</b>\n"
        f"• 🟢 BUY → فتح شراء\n"
        f"• 🔴 SELL → عكس + فتح بيع\n"
        f"• 🔄 عكس مستمر مع الترند\n\n"
        f"⚙️ <b>الإعدادات:</b>\n"
        f"• ATR: {ATR_PERIOD}, Multi: {ATR_MULTIPLIER}\n"
        f"• ZLSMA: {ZLSMA_LENGTH}\n"
        f"• 🛡️ SL: {STOP_LOSS_PCT}%\n"
        f"• 💰 حجم: {POSITION_SIZE_PCT}%/صفقة\n\n"
        f"📊 <b>الأزواج ({len(SYMBOLS)}):</b>\n{cat_summary}\n"
        f"💰 الرصيد: ${INITIAL_BALANCE}\n"
        f"⏰ فحص كل {SCAN_INTERVAL}s\n\n"
        f"✅ جاهز للتداول!"
    )
    
    scan_count  = 0
    last_report = datetime.now()
    
    while True:
        try:
            scan_count += 1
            now = datetime.now()
            print(f"\n{'='*60}")
            print(f"🔍 Scan #{scan_count} - {now.strftime('%H:%M:%S')}")
            print(f"{'='*60}")
            
            success = 0
            for i, (symbol, info) in enumerate(SYMBOLS.items(), 1):
                emoji = {
                    "forex":     "💱",
                    "crypto":    "🪙",
                    "commodity": "🥇",
                    "index":     "📊",
                    "stock":     "🏢"
                }.get(info['cat'], "📈")
                
                print(f"  [{i:2}/{len(SYMBOLS)}] {emoji} {info['name']:15}", end=" ")
                try:
                    scan_symbol(symbol, info)
                    print("✓")
                    success += 1
                except Exception as e:
                    print(f"❌")
                
                time.sleep(0.3)
            
            print(f"\n📊 نجح: {success}/{len(SYMBOLS)}")
            print(f"💼 الرصيد: ${balance:.2f}")
            print(f"🔴 مفتوحة: {len(active_trades)}")
            print(f"📈 مغلقة: {len(trade_history)}")
            
            # تقرير كل 6 ساعات
            if (now - last_report).total_seconds() > 21600:
                send_report()
                last_report = now
            
            print(f"\n⏳ ينتظر {SCAN_INTERVAL}s...")
            time.sleep(SCAN_INTERVAL)
            
        except KeyboardInterrupt:
            send_telegram("🛑 تم إيقاف البوت")
            break
        except Exception as e:
            print(f"❌ خطأ: {e}")
            time.sleep(60)


if __name__ == "__main__":
    main()