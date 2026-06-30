from telegram import ReplyKeyboardMarkup

MAIN_MENU = ReplyKeyboardMarkup(
    [
        ["🎮 Games", "🔑 My Keys"],
        ["🛒 Buy Key", "👤 Profile"],
        ["📞 Support", "📢 Setup Channel"],
    ],
    resize_keyboard=True,
    input_field_placeholder="Select an option..."
)