import asyncio,json,logging,os
from pathlib import Path
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import config
from exchanges import fetch_from_best
from analyzer import ohlcv_to_df, compute_indicators, detect_signals

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

STORAGE_PATH=config.STORAGE_PATH
if not STORAGE_PATH.exists():
    STORAGE_PATH.write_text(json.dumps({'symbols':config.DEFAULT_SYMBOLS},indent=2))

def read_storage(): return json.loads(STORAGE_PATH.read_text())
def write_storage(data): STORAGE_PATH.write_text(json.dumps(data,indent=2))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Привет! Я слежу за криптой на 4H таймфрейме и присылаю STRONG сигналы.')

async def list_symbols(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data=read_storage()
    await update.message.reply_text('Слежу за: '+', '.join(data.get('symbols',[])))

async def add_symbol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text('Использование: /addpair BTC/USDT')
        return
    symbol=context.args[0].upper()
    data=read_storage()
    symbols=data.get('symbols',[])
    if symbol in symbols:
        await update.message.reply_text(symbol+' уже в списке.')
        return
    symbols.append(symbol)
    data['symbols']=symbols
    write_storage(data)
    await update.message.reply_text(symbol+' добавлен.')

async def remove_symbol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text('Использование: /removepair BTC/USDT')
        return
    symbol=context.args[0].upper()
    data=read_storage()
    symbols=data.get('symbols',[])
    if symbol not in symbols:
        await update.message.reply_text(symbol+' не найден.')
        return
    symbols.remove(symbol)
    data['symbols']=symbols
    write_storage(data)
    await update.message.reply_text(symbol+' удалён.')

async def analyze_symbol_and_format(symbol: str) -> str:
    exchange_data=fetch_from_best(['binance','bybit'],symbol,config.TIMEFRAME,config.OHLCV_LIMIT)
    if not exchange_data:
        return f'Не удалось получить данные для {symbol}.'
    ex_name,ohlcv=exchange_data[0]
    df=ohlcv_to_df(ohlcv)
    df=compute_indicators(df)
    res=detect_signals(df)
    long_votes=res['long_votes']
    short_votes=res['short_votes']
    text=[f"{symbol} ({ex_name}) — close: {res['last_close']:.4f}",
          f"RSI: {res['rsi']:.2f}, MACD: {res['macd']:.4f} (sig {res['macd_signal']:.4f})",
          f"EMA50: {res['ema50']:.4f}, EMA200: {res['ema200']:.4f}",
          f"BB: [{res['bb_l']:.4f} — {res['bb_h']:.4f}]"]
    if long_votes>=config.MIN_AGREE and long_votes>short_votes:
        text.append(f"✅ *STRONG LONG* — {long_votes} indicators")
    elif short_votes>=config.MIN_AGREE and short_votes>long_votes:
        text.append(f"✅ *STRONG SHORT* — {short_votes} indicators")
    else:
        text.append("⚪ No strong consensus — пропускаем.")
    flags=', '.join([k for k,v in res['signals'].items() if v]) or 'None'
    text.append('Flags: '+flags)
'.join(text)

async def background_worker(app: Application):
    await app.start()
    last_sent={}
    while True:
        try:
            data=read_storage()
            symbols=data.get('symbols',[])
            for symbol in symbols:
                try:
                    exchange_data=fetch_from_best(['binance','bybit'],symbol,config.TIMEFRAME,config.OHLCV_LIMIT)
                    if not exchange_data: continue
                    ex_name,ohlcv=exchange_data[0]
                    df=ohlcv_to_df(ohlcv)
                    df=compute_indicators(df)
                    res=detect_signals(df)
                    last_ts=df.index[-1].isoformat()
                    key=f"{symbol}:{last_ts}"
                    long_votes=res['long_votes']
                    short_votes=res['short_votes']
                    strong_long=(long_votes>=config.MIN_AGREE and long_votes>short_votes)
                    strong_short=(short_votes>=config.MIN_AGREE and short_votes>long_votes)
                    if (strong_long or strong_short) and (key not in last_sent):
                        msg=await analyze_symbol_and_format(symbol)
                        await app.bot.send_message(chat_id=config.CHAT_ID,text=msg,parse_mode='Markdown',message_thread_id=config.THREAD_ID)
                        last_sent[key]=True
                        if len(last_sent)>500:
                            keys=list(last_sent.keys())[-300:]
                            last_sent={k:True for k in keys}
                except Exception as e:
                    logger.exception('Error analyzing %s: %s',symbol,e)
        except Exception as e:
            logger.exception('Background worker error: %s',e)
        await asyncio.sleep(config.CHECK_INTERVAL_MINUTES*60)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data=read_storage()
    symbols=data.get('symbols',[])
    lines=["📊 Crypto Signal Bot — Статус","","| Пара | Сигнал | Последний анализ |","|------|-------|----------------|"]
    from datetime import datetime
    for symbol in symbols:
        try:
            exchange_data=fetch_from_best(['binance','bybit'],symbol,config.TIMEFRAME,config.OHLCV_LIMIT)
            if not exchange_data:
                lines.append(f"| {symbol} | ❌ no data | - |")
                continue
            ex_name,ohlcv=exchange_data[0]
            df=ohlcv_to_df(ohlcv)
            df=compute_indicators(df)
            res=detect_signals(df)
            lv=res['long_votes']; sv=res['short_votes']
            if lv>=config.MIN_AGREE and lv>sv: sig="✅ STRONG LONG"
            elif sv>=config.MIN_AGREE and sv>lv: sig="✅ STRONG SHORT"
            else: sig="⚪ No consensus"
            ts=df.index[-1].strftime("%Y-%m-%d %H:%M")
            lines.append(f"| {symbol} | {sig} | {ts} |")
        except Exception:
            lines.append(f"| {symbol} | ❌ error | - |")
    text="
".join(lines)
    await update.message.reply_text(text)

def main():
    if not os.getenv('BOT_TOKEN'):
        raise RuntimeError('BOT_TOKEN not set')
    app=Application.builder().token(os.getenv('BOT_TOKEN')).build()
    app.add_handler(CommandHandler('start',lambda u,c: asyncio.create_task(start(u,c))))
    app.add_handler(CommandHandler('list',lambda u,c: asyncio.create_task(list_symbols(u,c))))
    app.add_handler(CommandHandler('addpair',lambda u,c: asyncio.create_task(add_symbol(u,c))))
    app.add_handler(CommandHandler('removepair',lambda u,c: asyncio.create_task(remove_symbol(u,c))))
    app.add_handler(CommandHandler('status',status_command))
    async def run(): asyncio.create_task(background_worker(app)); await app.run_polling()
    asyncio.run(run())

if __name__=='__main__': main()
