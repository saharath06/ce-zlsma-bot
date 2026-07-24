import os
import requests
import pandas as pd
import numpy as np
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
POSITION_SIZE_PCT  = 10

# التوقيت
TIMEFRAME       = "15m"
SCAN_INTERVAL   = 900  # كل 15 دقيقة
DELAY_BETWEEN   = 0.5

# ═══════════════════════════════════════
# 🎯 كريبتو من Binance (20 عملة)
# ═══════════════════════════════════════
SYMBOLS = {
    # Top Cryptocurrencies
    "BTCUSDT":   {"name": "Bitcoin",     "cat": "crypto", "d": 2},
    "ETHUSDT":   {"name": "Ethereum",    "cat": "crypto", "d": 2},
    "BNBUSDT":   {"name": "BNB",         "cat": "crypto", "d": 2},
    "SOLUSDT":   {"name": "Solana",      "cat": "crypto", "d": 3},
    "XRPUSDT":   {"name": "XRP",         "cat": "crypto", "d": 4},
    "ADAUSDT":   {"name": "Cardano",     "cat": "crypto", "d": 4},
    "AVAXUSDT":  {"name": "Avalanche",   "cat": "crypto", "d": 3},
    "DOGEUSDT":  {"name": "Dogecoin",    "cat": "crypto", "d": 5},
    "DOTUSDT":   {"name": "Polkadot",    "cat": "crypto", "d": 3},
    "MATICUSDT": {"name": "Polygon",     "cat": "crypto", "d": 4},
    "LINKUSDT":  {"name": "Chainlink",   "cat": "crypto", "d": 3},
    "LTCUSDT":   {"name": "Litecoin",    "cat": "crypto", "d": 2},
    "UNIUSDT":   {"name": "Uniswap",     "cat": "crypto", "d": 3},
    "ATOMUSDT":  {"name": "Cosmos",      "cat": "crypto", "d": 3},
    "NEARUSDT":  {"name": "NEAR",        "cat": "crypto", "d": 3},
    "APTUSDT":   {"name": "Aptos",       "cat": "crypto", "d": 3},
    "ARBUSDT":   {"name": "Arbitrum",    "cat": "crypto", "d": 4},
    "OPUSDT":    {"name": "Optimism",    "cat": "crypto", "d": 4},
    "INJUSDT":   {"name": "Injective",   "cat": "crypto", "d": 3},
    "SUIUSDT":   {"name": "Sui",         "cat": "crypto", "d": 4},
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
            r = requests.post(url, json={
                "chat_id": CHAT_ID,
                "text": text[i:i+4000],
                "parse_mode": "HTML"
            }, timeout=15)
            if r.status_code != 200:
                print(f"⚠️ Telegram: {r.status_code} - {r.text[:100]}")
            time.sleep(0.3)
    except Exception as e:
        print(f"❌ Telegram: {e}")


# ============================================
# 🚀 Binance API (مجاني، بدون مفتاح!)
# ============================================
def get_binance_klines(symbol, interval="15m", limit=200):
    """جلب البيانات من Binance مباشرة"""
    try:
        url = "https://api.binance.com/api/v3/klines"
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code != 200:
            return None
        
        data = response.json()
        
        # تحويل البيانات إلى DataFrame
        df = pd.DataFrame(data, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ])
        
        # تحويل الأنواع
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        
        # نعيد التسمية لتتوافق مع الكود
        df['Open']   = df['open'].astype(float)
        df['High']   = df['high'].astype(float)
        df['Low']    = df['low'].astype(float)
        df['Close']  = df['close'].astype(float)
        df['Volume'] = df['volume'].astype(float)
        
        return df[['Open', 'High', 'Low', 'Close', 'Volume']]
        
    except Exception as e:
        print(f"    ❌ Binance: {str(e)[:60]}")
        return None


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
    atr = calculate_atr(df, period) * multiplier
    
    highest = df['Close'].rolling(period).max()
    long_stop = (highest - atr).values
    
    lowest = df['Close'].rolling(period).min()
    short_stop = (lowest + atr).values
    
    close_arr = df['Close'].values
    
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


def calculate_zlsma(df, length=50, offset=0):
    close = df['Close'].values
    n = len(close)
    result = np.full(n, np.nan)
    
    if n < length * 2:
        return pd.Series(result, index=df.index)
    
    lsma = np.full(n, np.nan)
    for i in range(length, n):
        y = close[i-length:i]
        x = np.arange(length)
        coef = np.polyfit(x, y, 1)
        lsma[i] = coef[1] + coef[0] * (length - 1)
    
    lsma2 = np.full(n, np.nan)
    for i in range(length * 2, n):
        y = lsma[i-length:i]
        if not np.any(np.isnan(y)):
            x = np.arange(length)
            coef = np.polyfit(x, y, 1)
            lsma2[i] = coef[1] + coef[0] * (length - 1)
    
    zlsma = lsma + (lsma - lsma2)
    return pd.Series(zlsma, index=df.index)


def generate_signals(df):
    df = df.copy()
    df['CE_Dir'] = calculate_chandelier_exit(df, ATR_PERIOD, ATR_MULTIPLIER)
    df['ZLSMA']  = calculate_zlsma(df, ZLSMA_LENGTH)
    
    df['CE_Buy']  = (df['CE_Dir'] == 1)  & (df['CE_Dir'].shift(1) == -1)
    df['CE_Sell'] = (df['CE_Dir'] == -1) & (df['CE_Dir'].shift(1) == 1)
    
    df['Buy_Signal']  = df['CE_Buy']  & (df['Close'] > df['ZLSMA'])
    df['Sell_Signal'] = df['CE_Sell'] & (df['Close'] < df['ZLSMA'])
    
    return df


# ============================================
# منطق الصفقات
# ============================================
def open_trade(symbol, info, signal_type, price, timestamp):
    global balance
    
    if symbol in active_trades:
        return None
    
    if signal_type == "BUY":
        sl = price * (1 - STOP_LOSS_PCT/100) if USE_STOP_LOSS else None
    else:
        sl = price * (1 + STOP_LOSS_PCT/100) if USE_STOP_LOSS else None
    
    trade_size = balance * (POSITION_SIZE_PCT / 100)
    quantity   = trade_size / price
    
    trade = {
        "symbol": symbol, "name": info['name'],
        "type": signal_type, "entry_price": price,
        "sl": sl, "quantity": quantity,
        "trade_size": trade_size, "entry_time": timestamp,
        "status": "OPEN"
    }
    
    active_trades[symbol] = trade
    
    emoji = "🟢" if signal_type == "BUY" else "🔴"
    d = info['d']
    
    msg = f"{emoji} <b>صفقة جديدة!</b>\n"
    msg += f"━━━━━━━━━━━━━━━━━━━\n"
    msg += f"🪙 {info['name']} ({symbol})\n"
    msg += f"📊 {'شراء LONG' if signal_type == 'BUY' else 'بيع SHORT'}\n"
    msg += f"━━━━━━━━━━━━━━━━━━━\n"
    msg += f"💵 الدخول: ${price:.{d}f}\n"
    if sl:
        msg += f"🛡️ SL: ${sl:.{d}f} ({STOP_LOSS_PCT}%)\n"
    msg += f"🎯 الخروج: عند الإشارة العكسية\n"
    msg += f"━━━━━━━━━━━━━━━━━━━\n"
    msg += f"💰 الحجم: ${trade_size:.2f}\n"
    msg += f"⏰ {timestamp.strftime('%Y-%m-%d %H:%M')}\n"
    msg += f"━━━━━━━━━━━━━━━━━━━\n"
    msg += f"💼 الرصيد: ${balance:.2f}\n"
    msg += f"📊 مفتوحة: {len(active_trades)}"
    
    send_telegram(msg)
    print(f"✅ OPEN: {info['name']} {signal_type} @ ${price:.{d}f}")
    return trade


def close_trade(symbol, close_price, reason, timestamp):
    global balance
    
    if symbol not in active_trades:
        return None
    
    trade = active_trades[symbol]
    d = SYMBOLS[symbol]['d']
    info = SYMBOLS[symbol]
    
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
    
    msg = f"{emoji} <b>صفقة مغلقة!</b>\n"
    msg += f"━━━━━━━━━━━━━━━━━━━\n"
    msg += f"🪙 {trade['name']}\n"
    msg += f"📊 {trade['type']}\n"
    msg += f"🔔 {reason}\n"
    msg += f"━━━━━━━━━━━━━━━━━━━\n"
    msg += f"💵 دخول: ${trade['entry_price']:.{d}f}\n"
    msg += f"💸 خروج: ${close_price:.{d}f}\n"
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
    print(f"{emoji} CLOSE: {trade['name']} {result} ${profit_usd:+.2f}")
    return trade


def process_signals(symbol, info, df):
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
    
    has_buy = bool(last['Buy_Signal'])
    has_sell = bool(last['Sell_Signal'])
    
    if has_buy:
        if symbol in active_trades and active_trades[symbol]['type'] == "SELL":
            close_trade(symbol, current, "🔄 عكس الاتجاه", ts)
        if symbol not in active_trades:
            open_trade(symbol, info, "BUY", current, ts)
    
    elif has_sell:
        if symbol in active_trades and active_trades[symbol]['type'] == "BUY":
            close_trade(symbol, current, "🔄 عكس الاتجاه", ts)
        if symbol not in active_trades:
            open_trade(symbol, info, "SELL", current, ts)


# ============================================
# فحص العملة
# ============================================
def scan_symbol(symbol, info):
    df = get_binance_klines(symbol, interval=TIMEFRAME, limit=200)
    if df is None or len(df) < 60:
        return False
    
    try:
        df = generate_signals(df)
        process_signals(symbol, info, df)
        return True
    except Exception as e:
        print(f"    ❌ خطأ: {str(e)[:60]}")
        return False


# ============================================
# التقرير الدوري
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
            d = SYMBOLS[sym]['d']
            msg += f"  • {t['name']} {t['type']} @ ${t['entry_price']:.{d}f}\n"
    
    send_telegram(msg)


# ============================================
# الحلقة الرئيسية
# ============================================
def main():
    print("=" * 60)
    print("🤖 CE + ZLSMA Bot v5.0 - Binance Edition")
    print("=" * 60)
    print(f"📊 العملات: {len(SYMBOLS)}")
    print(f"⏰ الإطار: {TIMEFRAME}")
    print(f"🔄 الفحص: كل {SCAN_INTERVAL//60} دقيقة")
    print(f"💰 الرصيد: ${INITIAL_BALANCE}")
    print(f"🌐 المصدر: Binance API (بدون حظر!)")
    print("=" * 60)
    
    # اختبار Binance
    print("\n📡 اختبار Binance API...")
    test = get_binance_klines("BTCUSDT", interval="15m", limit=5)
    if test is not None and len(test) > 0:
        print(f"✅ Binance يعمل! BTC آخر سعر: ${test['Close'].iloc[-1]:.2f}")
    else:
        print("❌ Binance لا يعمل!")
        return
    
    # رسالة البداية
    send_telegram(
        f"🤖 <b>Trading Bot v5.0 - Binance</b>\n\n"
        f"✅ <b>تم التشغيل بنجاح!</b>\n\n"
        f"📋 الاستراتيجية: CE + ZLSMA\n"
        f"🌐 المصدر: Binance (لا حظر!)\n"
        f"⚙️ الإعدادات:\n"
        f"  • ATR: {ATR_PERIOD}, Multi: {ATR_MULTIPLIER}\n"
        f"  • ZLSMA: {ZLSMA_LENGTH}\n"
        f"  • Timeframe: {TIMEFRAME}\n"
        f"  • Scan: كل {SCAN_INTERVAL//60} دقيقة\n"
        f"  • SL: {STOP_LOSS_PCT}%\n\n"
        f"📊 <b>{len(SYMBOLS)} عملة كريبتو</b>\n"
        f"💰 الرصيد: ${INITIAL_BALANCE}\n\n"
        f"🚀 يعمل بشكل مثالي!"
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
            
            for i, (symbol, info) in enumerate(SYMBOLS.items(), 1):
                print(f"  [{i:2}/{len(SYMBOLS)}] 🪙 {info['name']:15}", end=" ")
                
                if scan_symbol(symbol, info):
                    print("✓")
                    success += 1
                else:
                    print("❌")
                
                time.sleep(DELAY_BETWEEN)
            
            print(f"\n📊 نجح: {success}/{len(SYMBOLS)}")
            print(f"💼 الرصيد: ${balance:.2f}")
            print(f"🔴 مفتوحة: {len(active_trades)}")
            print(f"📈 مغلقة: {len(trade_history)}")
            
            # تقرير كل 6 ساعات
            if (now - last_report).total_seconds() > 21600:
                send_report()
                last_report = now
            
            print(f"\n⏳ انتظار {SCAN_INTERVAL//60} دقيقة...")
            time.sleep(SCAN_INTERVAL)
            
        except KeyboardInterrupt:
            send_telegram("🛑 تم إيقاف البوت")
            break
        except Exception as e:
            print(f"❌ خطأ عام: {e}")
            time.sleep(60)


if __name__ == "__main__":
    main()