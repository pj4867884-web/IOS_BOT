from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from config import BOT_TOKEN
from handlers.start import start
from handlers.games import handle_message, button
from handlers.payment import photo_handler

app = Application.builder().token(BOT_TOKEN).build()

# Start Command
app.add_handler(CommandHandler("start", start))

# Menu Buttons
app.add_handler(
    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
)

# Inline Buttons
app.add_handler(CallbackQueryHandler(button))

# Payment Screenshot
app.add_handler(
    MessageHandler(filters.PHOTO, photo_handler)
)

print("✅ IOS SHUBHAM SHOP BOT STARTED")

app.run_polling()
