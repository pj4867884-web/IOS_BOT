from telegram import Update
from telegram.ext import ContextTypes

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✅ Payment screenshot received.\n\nYour payment is under review.\nPlease wait for admin approval."
    )