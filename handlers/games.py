async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    # Select Game
    if data.startswith("game:"):
        game = data.split(":")[1]
        keyboard = []

        for plan, price in GAMES[game].items():
            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"{plan} • ₹{price}",
                        callback_data=f"buy:{game}:{plan}:{price}"
                    )
                ]
            )

        keyboard.append(
            [
                InlineKeyboardButton("⬅️ Back", callback_data="back_games")
            ]
        )

        await query.edit_message_text(
            f"🎮 {game}\n\nSelect Your Plan",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # Buy Screen
    elif data.startswith("buy:"):
        _, game, plan, price = data.split(":")

        await context.bot.send_photo(
            chat_id=query.message.chat.id,
            photo=open(QR_IMAGE, "rb"),
            caption=f"""
💳 PAYMENT
🎮 Game : {game}
📅 Plan : {plan}
💰 Price : ₹{price}
━━━━━━━━━━━━━━━
💳 UPI
{UPI_ID}
━━━━━━━━━━━━━━━
✅ Complete Payment
📷 Then Send Payment Screenshot Here.
"""
        )