from telegram import InlineKeyboardButton, InlineKeyboardMarkup

GAMES_MENU = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("👑 KING iOS", callback_data="game_king"),
        InlineKeyboardButton("🔥 WINIOS BGMI", callback_data="game_winios"),
    ],
    [
        InlineKeyboardButton("🚀 IOS ZOON", callback_data="game_zoon"),
        InlineKeyboardButton("🐬 DOLPHIN IOS", callback_data="game_dolphin"),
    ],
    [
        InlineKeyboardButton("⚡ NEXT IOS", callback_data="game_next"),
        InlineKeyboardButton("💎 VNHAX PRO", callback_data="game_vnhax"),
    ],
    [
        InlineKeyboardButton("🔥 MARS LOADER", callback_data="game_mars"),
        InlineKeyboardButton("🎯 DEADEYE", callback_data="game_deadeye"),
    ],
    [
        InlineKeyboardButton("⬅️ Back", callback_data="back_main"),
    ]
])