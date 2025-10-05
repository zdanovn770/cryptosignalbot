import pandas as pd
import ta

def ohlcv_to_df(ohlcv):
    df = pd.DataFrame(ohlcv, columns=['timestamp','open','high','low','close','volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    return df.astype(float)

def compute_indicators(df):
    df = df.copy()
    df['rsi'] = ta.momentum.rsi(df['close'], window=14)
    macd = ta.trend.MACD(df['close'])
    df['macd'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()
    df['ema50'] = ta.trend.ema_indicator(df['close'], window=50)
    df['ema200'] = ta.trend.ema_indicator(df['close'], window=200)
    bb = ta.volatility.BollingerBands(df['close'], window=20, window_dev=2)
    df['bb_h'] = bb.bollinger_hband()
    df['bb_l'] = bb.bollinger_lband()
    df['vol_mean_20'] = df['volume'].rolling(20).mean()
    return df

def detect_signals(df):
    last = df.iloc[-1]
    prev = df.iloc[-2]
    signals = {'rsi_long': False,'rsi_short': False,'macd_long': False,'macd_short': False,
               'trend_up': False,'trend_down': False,'bb_long': False,'bb_short': False,'vol_spike': False}
    if last['rsi'] < 30: signals['rsi_long']=True
    if last['rsi'] > 70: signals['rsi_short']=True
    if (prev['macd']<prev['macd_signal']) and (last['macd']>last['macd_signal']): signals['macd_long']=True
    if (prev['macd']>prev['macd_signal']) and (last['macd']<last['macd_signal']): signals['macd_short']=True
    if last['ema50']>last['ema200']: signals['trend_up']=True
    elif last['ema50']<last['ema200']: signals['trend_down']=True
    if last['close']<last['bb_l']: signals['bb_long']=True
    if last['close']>last['bb_h']: signals['bb_short']=True
    if last['volume']>(last['vol_mean_20']*1.8): signals['vol_spike']=True
    long_votes=sum([signals[k] for k in ['rsi_long','macd_long','trend_up','bb_long','vol_spike']])
    short_votes=sum([signals[k] for k in ['rsi_short','macd_short','trend_down','bb_short','vol_spike']])
    return {'signals':signals,'long_votes':int(long_votes),'short_votes':int(short_votes),'last_close':float(last['close']),
            'rsi':float(last['rsi']),'macd':float(last['macd']),'macd_signal':float(last['macd_signal']),
            'ema50':float(last['ema50']),'ema200':float(last['ema200']),'bb_h':float(last['bb_h']),
            'bb_l':float(last['bb_l']),'vol':float(last['volume'])}
