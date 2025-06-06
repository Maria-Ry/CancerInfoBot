import os
import logging
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

BOT_TOKEN = os.getenv("TELEGRAM_CANCER_BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("⚠️ TELEGRAM_BOT_TOKEN environment variable not set")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /start – Welcomes the user and briefly explains functionality.
    """
    welcome_text = (
        "👋 Hello! I’m *CancerInfo_by_NeuroNexus_bot*.\n\n"
        "I can provide you with evidence-based lifestyle recommendations to help reduce cancer risk.\n\n"
        "Use /help to see what I can do."
    )
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /help – Shows available commands.
    """
    help_text = (
        "*Available Commands:*\n\n"
        "/start – Greet and explain what I do\n"
        "/help  – Show this help message\n\n"
        "Soon: /list  – Show all topics (e.g., Tobacco, Alcohol…)\n"
        "      /info <topic> – Get IARC classification + lifestyle advice\n\n"
        "_Example:_ `/info Tobacco`"
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Catches any unrecognized / commands.
    """
    await update.message.reply_text(
        "❓ Sorry, I didn’t understand that command. Use /help to see what I can do."
    )


def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))

    application.add_handler(
        MessageHandler(filters.Regex(r"^/"), unknown_command)
    )

    logger.info("🤖 Bot is starting—polling Telegram for updates...")
    application.run_polling()


if __name__ == "__main__":
    main()
