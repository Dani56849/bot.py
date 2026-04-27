import os
import base64
import json
import logging
import anthropic
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, CallbackQueryHandler
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "YOUR_ANTHROPIC_API_KEY")

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

ANALYSIS_PROMPT = """You are an expert binary options / Quotex trading chart analyst. The user has sent you a chart screenshot from the Quotex trading platform.

Analyze the chart image carefully and provide a trading signal for the NEXT candle. Your analysis must:

1. IDENTIFY key information visible in the chart:
   - Currency pair being traded
   - Timeframe (1min, 5min, etc.)
   - Current price level
   - Recent candlestick patterns (last 5-10 candles)
   - Support and resistance levels
   - Any visible trend direction

2. ANALYZE the following patterns:
   - Is there a double top / double bottom?
   - Are candles getting smaller (momentum loss)?
   - Is price near a resistance or support level?
   - What is the dominant trend (up/down/sideways)?
   - Any engulfing, pin bar, or doji patterns?

3. GIVE A CLEAR SIGNAL in this exact format at the end:

📊 *PAIR:* [pair name]
⏱ *TIMEFRAME:* [timeframe]
💰 *CURRENT PRICE:* [price]

🔍 *ANALYSIS:*
• [Key observation 1]
• [Key observation 2]
• [Key observation 3]

🎯 *NEXT CANDLE SIGNAL:*
Direction: [UP ✅ / DOWN 🔴]
Trade: [CALL / PUT]
Confidence: [percentage]%
Reason: [1-sentence key reason]

⚠️ *RISK:* [Brief note on what could invalidate this signal]

Keep the response concise and actionable. Always end with a clear UP or DOWN call."""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("How to use", callback_data="howto")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "👋 *Quotex Signal Bot*\n\n"
        "Send me a screenshot of your Quotex chart and I'll analyze it using AI to predict the next candle direction.\n\n"
        "📸 Just send a chart image directly in this chat!\n\n"
        "Supported: EUR/GBP, EUR/USD, GBP/USD, AUD/USD, and any Quotex pair.",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *How to use this bot:*\n\n"
        "1. Open your Quotex chart\n"
        "2. Take a screenshot of the chart\n"
        "3. Send the screenshot to this bot\n"
        "4. Wait a few seconds for AI analysis\n"
        "5. Get your UP/DOWN signal!\n\n"
        "💡 *Tips for better signals:*\n"
        "• Use 1-min or 5-min candles\n"
        "• Make sure the chart is clear and not zoomed out too much\n"
        "• Include at least 10-15 candles in the screenshot\n"
        "• Capture the price level on the right side\n\n"
        "⚠️ *Disclaimer:* This is for educational purposes only. Always trade responsibly.",
        parse_mode="Markdown"
    )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "howto":
        await query.message.reply_text(
            "📖 *How to use:*\n\n"
            "1. Take a screenshot of your Quotex chart\n"
            "2. Send it directly to this chat\n"
            "3. Get your signal in seconds!\n\n"
            "💡 Works best with 1-min candles on any Quotex pair.",
            parse_mode="Markdown"
        )


async def analyze_chart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    await message.reply_text("🔍 Analyzing your chart... Please wait a moment.")

    try:
        photo = message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        image_bytes = await file.download_as_bytearray()
        image_b64 = base64.standard_b64encode(bytes(image_bytes)).decode("utf-8")

        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=1000,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": image_b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": ANALYSIS_PROMPT
                        }
                    ],
                }
            ],
        )

        analysis_text = response.content[0].text

        if "UP" in analysis_text.upper() and "DOWN" not in analysis_text.upper().split("UP")[0][-20:]:
            header = "✅ *SIGNAL: UP / CALL*\n\n"
        elif "DOWN" in analysis_text.upper():
            header = "🔴 *SIGNAL: DOWN / PUT*\n\n"
        else:
            header = "📊 *CHART ANALYSIS*\n\n"

        full_message = header + analysis_text

        if len(full_message) > 4096:
            full_message = full_message[:4090] + "..."

        await message.reply_text(full_message, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error analyzing chart: {e}")
        await message.reply_text(
            "❌ Sorry, I couldn't analyze this image. Please make sure:\n"
            "• The image is a clear chart screenshot\n"
            "• The image is not blurry or too dark\n"
            "• Try sending it again\n\n"
            f"Error: {str(e)[:100]}"
        )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📸 Please send me a *chart screenshot* to analyze!\n\n"
        "Just take a screenshot of your Quotex chart and send it here.",
        parse_mode="Markdown"
    )


def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.PHOTO, analyze_chart))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
