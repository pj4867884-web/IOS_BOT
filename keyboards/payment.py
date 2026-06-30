from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def payment_keyboard(game, plan, price):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "💳 Buy Now",
                callback_data=f"pay:{game}:{plan}:{price}"
            )
        ],
        [
            InlineKeyboardButton(
                "⬅️ Back",
                callback_data="games"
            )
        ]
    ])