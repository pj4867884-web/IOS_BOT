from telegram import Update
from telegram.ext import ContextTypes

from config import ADMIN_ID


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.message.from_user

    caption = f"""
💳 New Payment Received

👤 Name : {user.first_name}
🆔 User ID : {user.id}
📛 Username : @{user.username if user.username else 'None'}

Please Verify Payment.
"""

    await context.bot.forward_message(
        chat_id=ADMIN_ID,
        from_chat_id=update.effective_chat.id,
        message_id=update.message.message_id,
    )

    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=caption
    )

    await update.message.reply_text(
        "✅ Payment screenshot received.\n\nPlease wait for admin approval."
    )