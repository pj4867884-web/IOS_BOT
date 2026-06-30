from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.games import GAMES


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text != "🎮 Games":
        return

    keyboard = []

    games = list(GAMES.keys())

    for i in range(0, len(games), 2):
        row = []

        row.append(
            InlineKeyboardButton(
                games[i],
                callback_data=f"game:{games[i]}"
            )
        )

        if i + 1 < len(games):
            row.append(
                InlineKeyboardButton(
                    games[i + 1],
                    callback_data=f"game:{games[i+1]}"
                )
            )

        keyboard.append(row)

    keyboard.append(
        [InlineKeyboardButton("⬅️ Back", callback_data="back")]
    )

    await update.message.reply_text(
        "🎮 Select Your Game",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data.startswith("game:"):

        game = data.split(":")[1]

        plans = GAMES[game]

        keyboard = []

        for plan, price in plans.items():
            keyboard.append([
                InlineKeyboardButton(
                    f"{plan} • ₹{price}",
                    callback_data=f"buy:{game}:{plan}"
                )
            ])

        keyboard.append([
            InlineKeyboardButton("⬅️ Back", callback_data="back")
        ])

        await query.edit_message_text(
            f"🎮 {game}\n\nSelect Your Plan",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
GAMES = {
    "KING iOS": {
        "1 Day": 200,
        "2 Weeks": 799,
        "1 Month": 2000,
    },

    "WINIOS BGMI": {
        "1 Day": 180,
        "1 Week": 600,
        "1 Month": 1299,
    },

    "IOS ZOON": {
        "1 Day": 200,
        "1 Week": 500,
        "1 Month": 1499,
    },

    "DOLPHIN IOS": {
        "1 Day": 200,
        "1 Week": 800,
        "1 Month": 1700,
    },

    "NEXT IOS": {
        "1 Day": 200,
        "1 Week": 799,
        "1 Month": 2000,
    },

    "VNHAX PRO": {
        "1 Day": 200,
        "1 Week": 700,
        "1 Month": 1599,
    },

    "MARS LOADER": {
        "1 Day": 130,
        "1 Week": 500,
        "1 Month": 999,
    },

    "DEADEYE": {
        "1 Day": 150,
        "1 Week": 600,
        "1 Month": 1499,
    }
}