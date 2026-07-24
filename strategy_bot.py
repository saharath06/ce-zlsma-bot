import os
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import warnings
import traceback
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
TIMEFRAME_MINUTES = 15
SCAN_INTERVAL     = 900
DELAY_BETWEEN     = 1.5

# ═══════════════════════════════════════
# 🎯 عملات Kraken (30 عملة)
# ═══════════════════════════════════════
SYMBOLS = {
    "XBTUSD":   {"name": "Bitcoin",     "d": 2},
    "ETHUSD":   {"name": "Ethereum",    "d": 2},
    "SOLUSD":   {"name": "Solana",      "d": 3},
    "XRPUSD":   {"name": "XRP",         "d": 4},
    "ADAUSD":   {"name": "Cardano",     "d": 4},
    "DOTUSD":   {"name": "Polkadot",    "d": 3},
    "LINKUSD":  {"name": "Chainlink",   "d": 3},
    "LTCUSD":   {"name": "Litecoin",    "d": 2},
    "UNIUSD":   {"name": "Uniswap",     "d": 3},
    "AVAXUSD":  {"name": "Avalanche",   "d": 3},
    "MATICUSD": {"name": "Polygon",     "d": 4},
    "ATOMUSD":  {"name": "Cosmos",      "d": 3},
    "NEARUSD":  {"name": "NEAR",        "d": 3},
    "APTUSD":   {"name": "Aptos",       "d": 3},
    "ARBUSD":   {"name": "Arbitrum",    "d": 4},
    "OPUSD":    {"name": "Optimism",    "d": 4},
    "INJUSD":   {"name": "Injective",   "d": 3},
    "SUIUSD":   {"name": "Sui",         "d": 4},
    "ALGOUSD":  {"name": "Algorand",    "d": 4},
    "FILUSD":   {"name": "Filecoin",    "d": 3},
    "XLMUSD":   {"name": "Stellar",     "d": 5},
    "TRXUSD":   {"name": "TRON",        "d": 5},
    "ETCUSD":   {"name": "Eth Classic", "d": 3},
    "BCHUSD":   {"name": "Bitcoin Cash","d": 2},
    "AAVEUSD":  {"name": "Aave",        "d": 2},
    "MKRUSD":   {"name": "Maker",       "d": 2},
    "SNXUSD":   {"name": "Synthetix",   "d": 3},
    "SANDUSD":  {"name": "Sandbox",     "d": 4},
    "MANAUSD":  {"name": "Decentraland","d": 4},
    "GRTUSD":   {"name": "The Graph",   "d": 4},
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
# Kraken API
# ============================================
def get_kraken_data(pair, interval=15):
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
# 🎯 المؤشرات المحسّنة (أسرع وأكثر موثوقية)
# ============================================
def calculate_atr(df, period=1):
    """حساب ATR"""
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
    
    atr = pd.Series(tr).rolling(period).mean()
    return atr


def calculate_chandelier_exit(df, period=1, multiplier=2.0):
    """Chandelier Exit - محسّن"""
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


def calculate_zlsma_fast(df, length=50):
    """ZLSMA محسّن (أسرع 10x)"""
    close = df['Close'].values
    n = len(close)
    
    if n < length * 2:
        return pd.Series(np.full(n, np.nan), index=df.index)
    
    # استخدم numpy للسرعة
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
    """توليد الإشارات مع معالجة أخطاء"""
    try:
        df = df.copy()
        df['CE_Dir'] = calculate_chandelier_exit(df, ATR_PERIOD, ATR_MULTIPLIER)
        df['ZLSMA'] = calculate_zlsma_fast(df, ZLSMA_LENGTH)
        
        # إزالة NaN
        df = df.dropna(subset=['CE_Dir', 'ZLSMA'])
        
        if len(df) < 5:
            return None
        
        df['CE_Buy']  = (df['CE_Dir'] == 1)  & (df['CE_Dir'].shift(1) == -1)
        df['CE_Sell'] = (df['CE_Dir'] == -1) & (df['CE_Dir'].shift(1) == 1)
        
        df['Buy_Signal']  = df['CE_Buy']  & (df['Close'] > df['ZLSMA'])
        df['Sell_Signal'] = df['CE_Sell'] & (df['Close'] < df['ZLSMA'])
        
        return df
    except Exception as e:
        raise Exception(f"generate_signals: {str(e)}")


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
    quantity = trade_size / price
    
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
    msg += f"🪙 {info['name']}\n"
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
    print(f"\n  ✅ OPEN: {info['name']} {signal_type} @ ${price:.{d}f}")
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
    print(f"\n  {emoji} CLOSE: {trade['name']} {result} ${profit_usd:+.2f}")
    return trade


def process_signals(symbol, info, df):
    if df is None or len(df) < 5:
        return
    
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
            open_trade(symbol, info, "BUY", current, ts)
    
    elif has_sell:
        if symbol in active_trades and active_trades[symbol]['type'] == "BUY":
            close_trade(symbol, current, "🔄 عكس الاتجاه", ts)
        if symbol not in active_trades:
            open_trade(symbol, info, "SELL", current, ts)


# ============================================
# 🎯 scan_symbol محسّن (يطبع الأخطاء)
# ============================================
def scan_symbol(symbol, info):
    # 1. جلب البيانات
    df = get_kraken_data(symbol, interval=TIMEFRAME_MINUTES)
    
    if df is None:
        return False, "لا بيانات"
    
    if len(df) < 60:
        return False, f"بيانات قليلة ({len(df)})"
    
    # 2. حساب المؤشرات
    try:
        df = generate_signals(df)
        
        if df is None:
            return False, "signals=None"
        
        # 3. معالجة الإشارات
        process_signals(symbol, info, df)
        return True, "OK"
        
    except Exception as e:
        error_msg = str(e)[:60]
        return False, error_msg


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
            d = SYMBOLS[sym]['d']
            msg += f"  • {t['name']} {t['type']} @ ${t['entry_price']:.{d}f}\n"
    
    send_telegram(msg)


# ============================================
# الحلقة الرئيسية
# ============================================
def main():
    print("=" * 60)
    print("🤖 CE + ZLSMA Bot v8.0 - Debug Mode")
    print("=" * 60)
    print(f"📊 العملات: {len(SYMBOLS)}")
    print(f"⏰ الإطار: {TIMEFRAME_MINUTES} دقيقة")
    print(f"🔄 الفحص: كل {SCAN_INTERVAL//60} دقيقة")
    print(f"💰 الرصيد: ${INITIAL_BALANCE}")
    print("=" * 60)
    
    # اختبار Kraken
    print("\n📡 اختبار Kraken...")
    test = get_kraken_data("XBTUSD", interval=15)
    
    if test is not None:
        print(f"✅ Kraken يعمل!")
        print(f"   BTC: ${test['Close'].iloc[-1]:.2f}")
        print(f"   الشموع: {len(test)}")
        
        # اختبار حساب المؤشرات على BTC
        print("\n📊 اختبار المؤشرات على BTC...")
        try:
            test_signals = generate_signals(test)
            if test_signals is not None:
                print(f"   ✅ المؤشرات تعمل!")
                print(f"   ✅ عدد الصفوف: {len(test_signals)}")
            else:
                print(f"   ❌ المؤشرات فشلت!")
        except Exception as e:
            print(f"   ❌ خطأ: {e}")
            traceback.print_exc()
    else:
        print("❌ Kraken لا يعمل!")
        return
    
    send_telegram(
        f"🤖 <b>Trading Bot v8.0 - Debug</b>\n\n"
        f"✅ <b>تم التشغيل!</b>\n\n"
        f"📋 CE + ZLSMA على Kraken\n"
        f"⚙️ Timeframe: {TIMEFRAME_MINUTES}m\n"
        f"📊 {len(SYMBOLS)} عملة\n"
        f"💰 ${INITIAL_BALANCE}\n\n"
        f"🚀 جاري الفحص..."
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
            errors = {}
            
            for i, (symbol, info) in enumerate(SYMBOLS.items(), 1):
                print(f"  [{i:2}/{len(SYMBOLS)}] 🪙 {info['name']:15}", end=" ")
                
                ok, msg = scan_symbol(symbol, info)
                
                if ok:
                    print("✓")
                    success += 1
                else:
                    print(f"❌ {msg}")
                    errors[msg] = errors.get(msg, 0) + 1
                
                time.sleep(DELAY_BETWEEN)
            
            print(f"\n📊 نجح: {success}/{len(SYMBOLS)}")
            
            if errors:
                print(f"❌ الأخطاء:")
                for err, count in errors.items():
                    print(f"   • {err}: {count} مرة")
            
            print(f"💼 الرصيد: ${balance:.2f}")
            print(f"🔴 مفتوحة: {len(active_trades)}")
            print(f"📈 مغلقة: {len(trade_history)}")
            
            # رسالة أول scan
            if scan_count == 1:
                if success > 0:
                    send_telegram(
                        f"✅ <b>أول فحص ناجح!</b>\n\n"
                        f"📊 نجح: {success}/{len(SYMBOLS)}\n"
                        f"⏳ الفحص القادم بعد {SCAN_INTERVAL//60} دقيقة"
                    )
                else:
                    err_summary = ", ".join([f"{e}({c})" for e, c in list(errors.items())[:3]])
                    send_telegram(
                        f"⚠️ <b>فشل الفحص الأول!</b>\n\n"
                        f"📊 نجح: 0/{len(SYMBOLS)}\n"
                        f"❌ الأخطاء: {err_summary}\n"
                        f"🔧 راجع Logs للتفاصيل"
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
            traceback.print_exc()
            time.sleep(60)


if __name__ == "__main__":
    main()
