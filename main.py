from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from handlers.games import handle_message, button

# अपना बोट टोकन यहाँ डालें
TOKEN = "YOUR_BOT_TOKEN_HERE"

def main():
    # एप्लिकेशन का सेटअप
    app = ApplicationBuilder().token(TOKEN).build()

    # मैसेज हैंडलर (🎮 Games बटन के लिए)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # बटन हैंडलर (CallbackQuery के लिए)
    app.add_handler(CallbackQueryHandler(button))

    print("बॉट चालू हो गया है...")
    app.run_polling()

if __name__ == '__main__':
    main()