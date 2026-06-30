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
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters, CallbackQueryHandler

from config import ADMIN_ID, QR_IMAGE
from database.users import save_payment_request
from database.keys import get_key, remove_key

ASK_KEY = 1


# USER SENDS SCREENSHOT
async def handle_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not update.message.photo:
        return

    user = update.message.from_user

    photo_id = update.message.photo[-1].file_id

    save_payment_request(user.id, photo_id)

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Accept", callback_data=f"accept:{user.id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject:{user.id}")
        ]
    ])

    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=photo_id,
        caption=f"💰 Payment Request\n\nUser: {user.id}",
        reply_markup=keyboard
    )

    await update.message.reply_text("⏳ Payment sent for approval. Wait...")


# ADMIN BUTTON HANDLER
async def payment_button(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    data = query.data

    # REJECT
    if data.startswith("reject:"):

        user_id = data.split(":")[1]

        await context.bot.send_message(
            chat_id=user_id,
            text="❌ Payment Rejected. Try again."
        )

        await query.edit_message_text("Rejected ❌")

    # ACCEPT
    elif data.startswith("accept:"):

        user_id = data.split(":")[1]

        context.user_data["pending_user"] = user_id

        await query.message.reply_text("🔑 Send Key for this user:")
        return ASK_KEY


# ADMIN SENDS KEY
async def receive_key(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = context.user_data.get("pending_user")
    key = update.message.text

    if not user_id:
        return ConversationHandler.END

    await context.bot.send_message(
        chat_id=user_id,
        text=f"🎉 Payment Approved!\n\n🔑 Your Key:\n{key}"
    )

    await update.message.reply_text("✅ Key sent to user")

    context.user_data["pending_user"] = None

    return ConversationHandler.END


# CONVERSATION HANDLER
def payment_handler():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(payment_button)],
        states={
            ASK_KEY: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_key)]
        },
        fallbacks=[]
    )