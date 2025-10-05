import asyncio
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import config
from analyzer import fetch_from_best, ohlcv_to_df, compute_indicators, detect_signals

# --- Настройка логов ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Создание приложения Telegram ---
app = ApplicationBuilder().token(config.TELEGRAM_TOKEN).build()

# --- Команда /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Бот запущен и готов к работе!\n\nКоманды:\n/status — текущие сигналы")

# --- Анализ одной пары ---
async def analyze_symbol_and_format(symbol: str) -> str:
    exchange_data = fetch_from_best(['binance', 'bybit'], symbol, config.TIMEFRAME, config.OHLCV_LIMIT)
    if not exchange_data:
        return f"❌ Не удалось получить данные для {symbol}"

    ex_name, ohlcv = exchange_data[0]
    df = ohlcv_to_df(ohlcv)
    df = compute_indicators(df)
    res = detect_signals(df)

    long_votes = res["long_votes"]
    short_votes = res["short_votes"]

    text = [
        f"{symbol} ({ex_name}) — close: {res['last_close']:.4f}",
        f"RSI: {res['rsi']:.2f}, MACD: {res['macd']:.4f} (sig {res['macd_signal']:.4f})",
        f"EMA50: {res['ema50']:.4f}, EMA200: {res['ema200']:.4f}",
        f"BB: [{res['bb_l']:.4f} — {res['bb_h']:.4f}]"
    ]

    if long_votes >= config.MIN_AGREE and long_votes > short_votes:
        text.append(f"✅ *STRONG LONG* — {long_votes} indicators")
    elif short_votes >= config.MIN_AGREE and short_votes > long_votes:
        text.append(f"❌ *STRONG SHORT* — {short_votes} indicators")
    else:
        text.append("⚪️ No strong consensus — пропускаем.")

    flags = ", ".join([k for k, v in res["signals"].items() if v]) or "None"
    text.append("Flags: " + flags)

    return "\n".join(text)

# --- Команда /status ---
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = ["| Symbol | Signal | Last Update |", "|--------|---------|--------------|"]
    for symbol in config.SYMBOLS:
        try:
            ex_data = fetch_from_best(['binance', 'bybit'], symbol, config.TIMEFRAME, config.OHLCV_LIMIT)
            if not ex_data:
                lines.append(f"| {symbol} | ❌ no data | - |")
                continue
            _, ohlcv = ex_data[0]
            df = ohlcv_to_df(ohlcv)
            df = compute_indicators(df)
            res = detect_signals(df)

            lv, sv = res["long_votes"], res["short_votes"]
            if lv >= config.MIN_AGREE and lv > sv:
                sig = "✅ STRONG LONG"
            elif sv >= config.MIN_AGREE and sv > lv:
                sig = "❌ STRONG SHORT"
            else:
                sig = "⚪️ No consensus"

            ts = df.index[-1].strftime("%Y-%m-%d %H:%M")
            lines.append(f"| {symbol} | {sig} | {ts} |")

        except Exception as e:
            lines.append(f"| {symbol} | ⚠️ error | - |")
            logger.error(f"Ошибка при анализе {symbol}: {e}")

    text = "\n".join(lines)
    await update.message.reply_text(text)

# --- Регистрация команд ---
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("status", status))

# --- Фоновый анализ ---
async def background_worker():
    while True:
        logger.info("🔍 Запуск фонового анализа...")
        try:
            for symbol in config.SYMBOLS:
                result = await analyze_symbol_and_format(symbol)
                await app.bot.send_message(
                    chat_id=config.CHAT_ID,
                    message_thread_id=config.THREAD_ID,
                    text=result,
                    parse_mode="Markdown"
                )
        except Exception as e:
            logger.error(f"Ошибка фонового анализа: {e}")
        await asyncio.sleep(60 * 60)  # каждые 60 минут

# --- Основной запуск ---
async def main():
    asyncio.create_task(background_worker())
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
