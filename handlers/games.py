from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

# यहाँ अपने डेटा को डिफाइन करें (यह महत्वपूर्ण है)
GAMES = {
    "king": {"Weekly": 100, "Monthly": 300},
    "winios": {"Weekly": 150, "Monthly": 400}
}
QR_IMAGE = "qr.jpg"  # अपनी इमेज का सही नाम लिखें
UPI_ID = "your_upi_id@bank" # अपना UPI ID यहाँ डालें

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🎮 Games":
        keyboard = [
            [
                InlineKeyboardButton("👑 KING iOS", callback_data="game:king"),
                InlineKeyboardButton("🔥 WINIOS BGMI", callback_data="game:winios"),
            ],
            [
                InlineKeyboardButton("⬅️ Back", callback_data="back"),
            ],
        ]
        await update.message.reply_text(
            "🎮 Select a Game",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("game:"):
        game = data.split(":")[1]
        keyboard = []
        for plan, price in GAMES[game].items():
            keyboard.append([InlineKeyboardButton(f"{plan} • ₹{price}", callback_data=f"buy:{game}:{plan}:{price}")])
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_games")])
        await query.edit_message_text(f"🎮 {game}\n\nSelect Your Plan", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("buy:"):
        _, game, plan, price = data.split(":")
        caption = f"💳 PAYMENT\n\n🎮 Game : {game}\n📅 Plan : {plan}\n💰 Price : ₹{price}\n\n💳 UPI: {UPI_ID}\n\n✅ Send Screenshot here."
        await context.bot.send_photo(chat_id=query.message.chat.id, photo=open(QR_IMAGE, "rb"), caption=caption)