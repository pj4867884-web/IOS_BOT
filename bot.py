import os
import io
import json
import uuid
import sqlite3
import logging
import razorpay
from datetime import datetime
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
UPI_ID = os.environ.get("UPI_ID", "yourname@upi")
RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "")
REPLIT_DEV_DOMAIN = os.environ.get("REPLIT_DEV_DOMAIN", "")

rzp = (
    razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
    if RAZORPAY_KEY_ID
    else None
)

DATA_DIR = "data"
KEYS_FILE = os.path.join(DATA_DIR, "keys.json")
ORDERS_FILE = os.path.join(DATA_DIR, "orders.json")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
PENDING_FILE = os.path.join(DATA_DIR, "pending.json")
QR_IMAGE = os.path.join(DATA_DIR, "payment_qr.jpeg")
DB_FILE = os.path.join(DATA_DIR, "keys.db")
ADMIN_LOG = os.path.join(DATA_DIR, "admin_log.json")

os.makedirs(DATA_DIR, exist_ok=True)

STATE_AWAITING_TXN = "awaiting_txn"

# ── SQLite setup ──────────────────────────────────────────────────────────────
_db = sqlite3.connect(DB_FILE, check_same_thread=False)
_db.execute("""
    CREATE TABLE IF NOT EXISTS user_keys (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id  INTEGER NOT NULL,
        game     TEXT    NOT NULL,
        key      TEXT    NOT NULL,
        bought_at TEXT   NOT NULL
    )
""")
_db.commit()


def save_user_key(user_id: int, game: str, key: str):
    _db.execute(
        "INSERT INTO user_keys (user_id, game, key, bought_at) VALUES (?, ?, ?, ?)",
        (user_id, game, key, datetime.now().strftime("%Y-%m-%d %H:%M")),
    )
    _db.commit()


def _sync_delivered():
    """Pull any Razorpay-auto-delivered keys from JSON into SQLite then clear the file."""
    delivered_file = os.path.join(DATA_DIR, "delivered_keys.json")
    if not os.path.exists(delivered_file):
        return
    try:
        with open(delivered_file) as f:
            rows = json.load(f)
        for row in rows:
            _db.execute(
                "INSERT INTO user_keys (user_id, game, key, bought_at) VALUES (?, ?, ?, ?)",
                (row["user_id"], row["game"], row["key"], row["bought_at"]),
            )
        _db.commit()
        with open(delivered_file, "w") as f:
            json.dump([], f)
    except Exception as e:
        logger.warning(f"delivered_keys sync failed: {e}")


def get_user_keys(user_id: int):
    _sync_delivered()
    cur = _db.execute(
        "SELECT game, key, bought_at FROM user_keys WHERE user_id=? ORDER BY id DESC",
        (user_id,),
    )
    return cur.fetchall()


# ─────────────────────────────────────────────────────────────────────────────


def load(path, default):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return default


def save(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def get_keys() -> dict:
    return load(KEYS_FILE, {})


def get_orders() -> list:
    return load(ORDERS_FILE, [])


def get_users() -> dict:
    return load(USERS_FILE, {})


def get_pending() -> dict:
    return load(PENDING_FILE, {})


def track_user(user):
    users = get_users()
    uid = str(user.id)
    if uid not in users:
        users[uid] = {
            "name": user.full_name,
            "username": f"@{user.username}" if user.username else "—",
            "joined": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        save(USERS_FILE, users)


def is_admin(user_id: int) -> bool:
    return ADMIN_ID != 0 and user_id == ADMIN_ID


def admin_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not is_admin(update.effective_user.id):
            await update.message.reply_text(
                "⛔ You are not authorized to use this command."
            )
            return
        await func(update, context)

    return wrapper


def get_main_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    if is_admin(user_id):
        return ReplyKeyboardMarkup(
            [
                ["🎮 Games", "🔑 My Keys"],
                ["💬 Support", "📢 Setup Channel"],
                ["👑 Admin Panel"],
                ["➕ Add Key", "📦 Stock"],
                ["📋 Orders", "📊 Stats"],
            ],
            resize_keyboard=True,
        )
    return ReplyKeyboardMarkup(
        [["🎮 Games", "🔑 My Keys"], ["💬 Support", "📢 Setup Channel"]],
        resize_keyboard=True,
    )


games_keyboard = ReplyKeyboardMarkup(
    [
        ["KING iOS", "Win iOS"],
        ["VISION", "LETHAL"],
        ["RAGE", "DEAD EYE"],
        ["ESING CODE", "KC Std"],
        ["KC pro", "NEXT iOS"],
        ["TITAN (non root)", "TITAN (root)"],
        ["DOLPHIN iOS"],
        ["⬅️ Back"],
    ],
    resize_keyboard=True,
)

admin_keyboard = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton("📦 Add Stock", callback_data="admin_add_stock"),
            InlineKeyboardButton("📋 View Stock", callback_data="admin_view_stock"),
        ],
        [
            InlineKeyboardButton("💰 Edit Price", callback_data="admin_edit_price"),
            InlineKeyboardButton("🗑 Remove Stock", callback_data="admin_remove_stock"),
        ],
        [
            InlineKeyboardButton("📈 Sales", callback_data="admin_sales"),
            InlineKeyboardButton("⚙ Settings", callback_data="admin_settings"),
        ],
    ]
)

back_to_admin_keyboard = InlineKeyboardMarkup(
    [[InlineKeyboardButton("⬅️ Back to Admin", callback_data="admin_panel")]]
)

GAME_TITLES = {
    "KING iOS",
    "Win iOS",
    "VISION",
    "LETHAL",
    "RAGE",
    "DEAD EYE",
    "ESING CODE",
    "KC Std",
    "KC pro",
    "NEXT iOS",
    "TITAN (non root)",
    "TITAN (root)",
    "DOLPHIN iOS",
}

PLAN_PRICES = {
    "king_day": ("KING iOS - Day", 200),
    "king_week": ("KING iOS - Week", 800),
    "king_month": ("KING iOS - Month", 2000),
    "win_day": ("Win iOS - 1 Day", 180),
    "win_week": ("Win iOS - 1 Week", 500),
    "win_month": ("Win iOS - 1 Month", 999),
    "esing_month": ("ESING CODE - Month", 400),
    "next_day": ("NEXT iOS - 1 Day", 250),
    "next_week": ("NEXT iOS - 1 Week", 800),
    "dead_day": ("DEAD EYE - 1 Day", 150),
    "dead_week": ("DEAD EYE - 1 Week", 600),
    "dead_month": ("DEAD EYE - 1 Month", 1300),
    "vision_day": ("VISION - 1 Day", 199),
    "vision_week": ("VISION - 1 Week", 799),
    "vision_month": ("VISION - 1 Month", 2199),
    "rage_day": ("RAGE - 1 Day", 150),
    "rage_week": ("RAGE - 1 Week", 599),
    "rage_month": ("RAGE - 1 Month", 1499),
}

GAME_INLINE_KEYBOARDS = {
    "KING iOS": {
        "label": "KING iOS",
        "keyboard": InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Day - ₹200", callback_data="king_day"),
                    InlineKeyboardButton("Week - ₹800", callback_data="king_week"),
                ],
                [
                    InlineKeyboardButton("Month - ₹2000", callback_data="king_month"),
                ],
                [
                    InlineKeyboardButton("⬅️ Back", callback_data="games"),
                ],
            ]
        ),
    },
    "Win iOS": {
        "label": "Win iOS",
        "keyboard": InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("📅 1 Day — ₹180", callback_data="win_day"),
                    InlineKeyboardButton("📅 1 Week — ₹500", callback_data="win_week"),
                ],
                [
                    InlineKeyboardButton(
                        "📅 1 Month — ₹999", callback_data="win_month"
                    ),
                ],
                [InlineKeyboardButton("⬅️ Back", callback_data="games"),
                ],
            ]
        ),
    },
    "ESING CODE": {
        "label": "ESING CODE",
        "keyboard": InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Month - ₹400", callback_data="esing_month"),
                ],
                [
                    InlineKeyboardButton("⬅️ Back", callback_data="games"),
                ],
            ]
        ),
    },
    "NEXT iOS": {
        "label": "NEXT iOS",
        "keyboard": InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("📅 1 DAY - ₹250", callback_data="next_day"),
                    InlineKeyboardButton("📅 1 WEEK - ₹800", callback_data="next_week"),
                ],
                [
                    InlineKeyboardButton("⬅️ Back", callback_data="games"),
                ],
            ]
        ),
    },
    "DEAD EYE": {
        "label": "DEAD EYE",
        "keyboard": InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("📅 1 DAY - ₹150", callback_data="dead_day"),
                    InlineKeyboardButton("📅 1 WEEK - ₹600", callback_data="dead_week"),
                ],
                [
                    InlineKeyboardButton(
                        "📅 1 MONTH - ₹1300", callback_data="dead_month"
                    ),
                ],
                [
                    InlineKeyboardButton("⬅️ Back", callback_data="games"),
                ],
            ]
        ),
    },
    "VISION": {
        "label": "VISION",
        "keyboard": InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("📅 1 DAY - ₹199", callback_data="vision_day"),
                    InlineKeyboardButton(
                        "📅 1 WEEK - ₹799", callback_data="vision_week"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "📅 1 MONTH - ₹2199", callback_data="vision_month"
                    ),
                ],
                [
                    InlineKeyboardButton("⬅️ Back", callback_data="games"),
                ],
            ]
        ),
    },
    "RAGE": {
        "label": "RAGE",
        "keyboard": InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("📅 1 DAY - ₹150", callback_data="rage_day"),
                    InlineKeyboardButton("📅 1 WEEK - ₹599", callback_data="rage_week"),
                ],
                [
                    InlineKeyboardButton(
                        "📅 1 MONTH - ₹1499", callback_data="rage_month"
                    ),
                ],
                [
                    InlineKeyboardButton("⬅️ Back", callback_data="games"),
                ],
            ]
        ),
    },
}

ADMIN_HELP = {
    "admin_add_stock": (
        "📦 Add Stock",
        "Use the command:\n<code>/addkey &lt;plan&gt; &lt;key&gt;</code>\n\nExample:\n<code>/addkey king_day MYKEY123</code>",
    ),
    "admin_view_stock": ("📋 View Stock", "Use the command:\n<code>/stock</code>"),
    "admin_edit_price": (
        "💰 Edit Price",
        "Prices are set in <code>PLAN_PRICES</code> inside <code>bot.py</code>.\n\n<i>In-bot editing coming soon.</i>",
    ),
    "admin_remove_stock": (
        "🗑 Remove Stock",
        "Use the command:\n<code>/removekey &lt;plan&gt; &lt;key&gt;</code>\n\nExample:\n<code>/removekey king_day MYKEY123</code>",
    ),
    "admin_sales": ("📈 Sales", "Use the command:\n<code>/orders</code>"),
    "admin_settings": (
        "⚙ Settings",
        "Use the command:\n<code>/stats</code> — overall stats\n<code>/users</code> — registered users\n<code>/broadcast &lt;msg&gt;</code> — message all users",
    ),
}


def create_razorpay_link(order_id: str, label: str, price: int) -> str | None:
    if not rzp:
        return None
    try:
        link = rzp.payment_link.create(
            {
                "amount": price * 100,"currency": "INR",
                "description": f"Game Key — {label}",
                "reference_id": order_id,
                "notify": {"sms": False, "email": False},
                "reminder_enable": False,
            }
        )
        return link.get("short_url")
    except Exception as e:
        logger.error(f"Razorpay link creation failed: {e}")
        return None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    track_user(update.effective_user)
    context.user_data.clear()
    uid = update.effective_user.id
    await update.message.reply_text(
        "🌟 Welcome to Game Key Shop! 🌟\n\n"
        "Your one-stop destination for premium gaming keys.\n\n"
        "Select a category below to get started! 🚀",
        reply_markup=get_main_keyboard(uid),
    )


async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text(
            "⛔ You are not authorized to use this command."
        )
        return
    await update.message.reply_text(
        "🔐 <b>Admin Panel</b>\n\nChoose an action or use a command:",
        parse_mode="HTML",
        reply_markup=admin_keyboard,
    )


@admin_only
async def cmd_addkey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        plans = ", ".join(PLAN_PRICES.keys())
        await update.message.reply_text(
            f"❌ Usage: <code>/addkey &lt;plan&gt; &lt;key&gt;</code>\n\nAvailable plans: <code>{plans}</code>",
            parse_mode="HTML",
        )
        return
    plan, key = context.args[0].lower(), context.args[1]
    if plan not in PLAN_PRICES:
        await update.message.reply_text(
            f"❌ Unknown plan <code>{plan}</code>.", parse_mode="HTML"
        )
        return
    keys = get_keys()
    keys.setdefault(plan, [])
    if key in keys[plan]:
        await update.message.reply_text(
            f"⚠️ Key already exists in <b>{plan}</b>.", parse_mode="HTML"
        )
        return
    keys[plan].append(key)
    save(KEYS_FILE, keys)
    await update.message.reply_text(
        f"✅ Key added to <b>{PLAN_PRICES[plan][0]}</b>\n🔑 <code>{key}</code>\n📦 Total stock: {len(keys[plan])}",
        parse_mode="HTML",
        reply_markup=get_main_keyboard(update.effective_user.id),
    )


@admin_only
async def cmd_removekey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Usage: <code>/removekey &lt;plan&gt; &lt;key&gt;</code>",
            parse_mode="HTML",
        )
        return
    plan, key = context.args[0].lower(), context.args[1]
    keys = get_keys()
    if plan not in keys or key not in keys[plan]:
        await update.message.reply_text(
            f"❌ Key not found in <b>{plan}</b>.", parse_mode="HTML"
        )
        return
    keys[plan].remove(key)
    save(KEYS_FILE, keys)
    await update.message.reply_text(
        f"🗑 Removed from <b>{plan}</b>\n🔑 <code>{key}</code>\n📦 Remaining: {len(keys[plan])}",
        parse_mode="HTML",
    )


@admin_only
async def cmd_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keys = get_keys()
    lines = ["📦 <b>Stock Overview</b>\n"]
    for plan_id, (label, price) in PLAN_PRICES.items():
        count = len(keys.get(plan_id, []))
        status = f"{count} key(s)" if count > 0 else "❌ Out of stock"
        lines.append(f"• <b>{label}</b> (₹{price}) — {status}")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


@admin_only
async def cmd_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    orders = get_orders()
    if not orders:
        await update.message.reply_text("📋 No orders yet.")
        return
    recent = orders[-10:][::-1]
    lines = [f"📋 <b>Last {len(recent)} Orders</b>\n"]
    for o in recent:
        lines.append(
            f"• <b>{o['plan']}</b> → User {o['user_id']}\n"
            f"  🔑 <code>{o['key']}</code>  🕐 {o['timestamp']}"
        )
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


@admin_only
async def cmd_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pending = get_pending()
    if not pending:
        await update.message.reply_text("✅ No pending payment approvals.")
        return
    lines = [f"⏳ <b>Pending Approvals ({len(pending)})</b>\n"]
    for order_id, o in pending.items():
        approve_kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "✅ Approve", callback_data=f"approve_{order_id}"
                    ),
                    InlineKeyboardButton(
                        "❌ Reject", callback_data=f"reject_{order_id}"
                    ),
                ]
            ]
        )
        await update.message.reply_text(
            f"🔔 <b>New Payment Request</b>\n\n"
            f"👤 User: {o['username']}\n"
            f"🆔 User ID: <code>{o['user_id']}</code>\n"
            f"📦 Plan: <b>{o['label']}</b>\n"
            f"💰 Amount: ₹{o['price']}\n"
            f"🧾 UTR: <code>{o['txn_id']}</code>",
            parse_mode="HTML",
            reply_markup=approve_kb,
        )


@admin_only
async def cmd_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = get_users()
    total = len(users)
    if total == 0:
        await update.message.reply_text("👤 No users yet.")
        return
    lines = [f"👥 <b>Users ({total} total)</b>\n"]
    for uid, info in list(users.items())[-20:]:
        lines.append(f"• {info['name']} {info['username']} — joined {info['joined']}")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


@admin_only
async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "❌ Usage: <code>/broadcast &lt;message&gt;</code>", parse_mode="HTML"
        )
        return
    message = " ".join(context.args)
    users = get_users()
    sent, failed = 0, 0
    for uid in users:
        try:
            await context.bot.send_message(chat_id=int(uid), text=f"📢 {message}")
            sent += 1
        except Exception:
            failed += 1
    await update.message.reply_text(
        f"📢 Broadcast complete\n✅ Sent: {sent}\n❌ Failed: {failed}"
    )


def log_admin_action(admin_id: int, action: str, detail: str):
    """Append a timestamped entry to data/admin_log.json."""
    log = load(ADMIN_LOG, [])
    log.append(
        {
            "admin_id": admin_id,
            "action": action,
            "detail": detail,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    )
    save(ADMIN_LOG, log)


@admin_only
async def cmd_clearstock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keys = get_keys()
    buttons = []
    for plan_id, (label, price) in PLAN_PRICES.items():
        count = len(keys.get(plan_id, []))
        buttons.append(
            [
                InlineKeyboardButton(
                    f"{label} (₹{price}) — {count} key(s)",
                    callback_data=f"clearstock_plan_{plan_id}",
                )
            ]
        )
    buttons.append(
        [InlineKeyboardButton("❌ Cancel", callback_data="clearstock_cancel")]
    )
    await update.message.reply_text(
        "🗑 <b>Clear Stock</b>\n\nSelect a plan to wipe its keys:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


@admin_only
async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keys = get_keys()
    orders = get_orders()
    users = get_users()
    pending = get_pending()
    total_keys = sum(len(v) for v in keys.values())
    total_orders = len(orders)
    total_users = len(users)
    revenue = sum(PLAN_PRICES.get(o["plan"], ("", 0))[1] for o in orders)
    webhook_url = (
        f"https://{REPLIT_DEV_DOMAIN}/api/razorpay-webhook"
        if REPLIT_DEV_DOMAIN
        else "Not configured"
    )
    await update.message.reply_text(
        f"📈 <b>Bot Statistics</b>\n\n"f"👥 Users: <b>{total_users}</b>\n"
        f"📦 Keys in stock: <b>{total_keys}</b>\n"
        f"🛒 Total orders: <b>{total_orders}</b>\n"
        f"⏳ Pending approvals: <b>{len(pending)}</b>\n"
        f"💰 Total revenue: <b>₹{revenue}</b>\n\n"
        f"🔗 Webhook URL:\n<code>{webhook_url}</code>",
        parse_mode="HTML",
    )


async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    track_user(update.effective_user)
    uid = update.effective_user.id
    text = update.message.text

    # ── Awaiting UTR after manual "I've Paid" ──
    if context.user_data.get("state") == STATE_AWAITING_TXN:
        txn_id = text.strip()
        plan = context.user_data.get("plan")
        user = update.effective_user
        label, price = PLAN_PRICES.get(plan, ("Unknown", 0))

        order_id = uuid.uuid4().hex[:8].upper()
        pending = get_pending()
        pending[order_id] = {
            "user_id": user.id,
            "username": f"@{user.username}" if user.username else user.full_name,
            "plan": plan,
            "label": label,
            "price": price,
            "txn_id": txn_id,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        save(PENDING_FILE, pending)
        context.user_data.clear()

        approve_kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "✅ Approve", callback_data=f"approve_{order_id}"
                    ),
                    InlineKeyboardButton(
                        "❌ Reject", callback_data=f"reject_{order_id}"
                    ),
                ]
            ]
        )
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"🔔 <b>New Payment Request</b>\n\n"
                f"👤 User: {pending[order_id]['username']}\n"
                f"🆔 User ID: <code>{user.id}</code>\n"
                f"📦 Plan: <b>{label}</b>\n"
                f"💰 Amount: ₹{price}\n"
                f"🧾 UTR: <code>{txn_id}</code>"
            ),
            parse_mode="HTML",
            reply_markup=approve_kb,
        )
        await update.message.reply_text(
            "✅ <b>Payment submitted!</b>\n\n"
            "Your transaction is under review. You'll receive your key once verified. ⏳",
            parse_mode="HTML",
            reply_markup=get_main_keyboard(uid),
        )
        return

    # ── Admin shortcut buttons ──
    if text == "👑 Admin Panel" and is_admin(uid):
        await update.message.reply_text(
            "🔐 <b>Admin Panel</b>\n\nChoose an action or use a command:",
            parse_mode="HTML",
            reply_markup=admin_keyboard,
        )
    elif text == "➕ Add Key" and is_admin(uid):
        await update.message.reply_text(
            "📦 Usage: <code>/addkey &lt;plan&gt; &lt;key&gt;</code>\n\n"
            "Plans: <code>" + ", ".join(PLAN_PRICES.keys()) + "</code>",
            parse_mode="HTML",
        )
    elif text == "📦 Stock" and is_admin(uid):
        await cmd_stock(update, context)
    elif text == "📋 Orders" and is_admin(uid):
        await cmd_orders(update, context)
    elif text == "📊 Stats" and is_admin(uid):
        await cmd_stats(update, context)

    # ── Regular menu ──
    elif text == "🎮 Games":
        await update.message.reply_text(
            "🎮 *Choose a Game*\n\nSelect a title to view available keys:",
            parse_mode="Markdown",
            reply_markup=games_keyboard,
        )
    elif text == "⬅️ Back":
        await update.message.reply_text(
            "🏠 *Main Menu*\n\nSelect a category below:",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard(uid),
        )
    elif text in GAME_INLINE_KEYBOARDS:
        game = GAME_INLINE_KEYBOARDS[text]
        await update.message.reply_text(
            f"⏱️ *{game['label']}* - Select Duration:",
            parse_mode="Markdown",
            reply_markup=game["keyboard"],
        )
    elif text in GAME_TITLES:
        await update.message.reply_text(
            f"🎮 *{text}*\n\nKeys for this title are coming soon! Check back later.",
            parse_mode="Markdown",
            reply_markup=games_keyboard,
        )
    elif text == "🔑 My Keys":
        rows = get_user_keys(uid)
        if not rows:
            await update.message.reply_text(
                "🔑 *My Keys*\n\nYou haven't purchased any keys yet.",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard(uid),
            )
        else:
            lines = ["🔑 <b>My Keys</b>\n"]
            for game, key, bought_at in rows:
                lines.append(
                    f"🎮 <b>{game}</b>\n🔑 <code>{key}</code>\n🕐 {bought_at}\n"
                )
            await update.message.reply_text(
                "\n".join(lines), parse_mode="HTML", reply_markup=get_main_keyboard(uid)
            )
    elif text == "💬 Support":
        await update.message.reply_text(
            "🆘 *Customer Support*\n\n"
            "For any issues, please contact our support team:\n\n"
            "👤 @IOS\_HACK\_S",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard(uid),
        )
    elif text == "📢 Setup Channel":
        await update.message.reply_text(
            "📢 *Setup Channel*\n\nLink not set yet. Please contact admin.",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard(uid),
        )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    uid = query.from_user.id

    if data == "games":
        await query.message.reply_text(
            "🎮 *Choose a Game*\n\nSelect a title to view available keys:",
            parse_mode="Markdown",
            reply_markup=games_keyboard,
        )

    elif data in PLAN_PRICES:
        keys = get_keys()
        label, price = PLAN_PRICES[data]
        stock = len(keys.get(data, []))

        if stock == 0:
            await query.message.reply_text(
                f"😔 <b>{label}</b> is currently out of stock.\nPlease check back later or contact support.",
                parse_mode="HTML",
                reply_markup=get_main_keyboard(uid),
            )
            return

        pay_kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("💳 Purchase Now", callback_data=f"pay_{data}")],
                [InlineKeyboardButton("⬅️ Back", callback_data="games")],
            ]
        )
        await query.message.reply_text(
            f"🎮 <b>{label}</b>\n\n"
            f"💰 Price: ₹{price}\n"
            f"📦 Stock: {stock} available\n\n"
            f"Tap below to proceed with payment 👇",
            parse_mode="HTML",
            reply_markup=pay_kb,
        )

    elif data.startswith("pay_"):
        plan = data[4:]
        label, price = PLAN_PRICES.get(plan, ("Unknown", 0))
        order_id = uuid.uuid4().hex[:8].upper()

        # Save pending order before creating link
        pending = get_pending()
        pending[order_id] = {
            "user_id": uid,
            "username": f"@{query.from_user.username}"
            if query.from_user.username
            else query.from_user.full_name,
            "plan": plan,
            "label": label,
            "price": price,
            "txn_id": "razorpay_pending",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        save(PENDING_FILE, pending)

        rzp_url = create_razorpay_link(order_id, label, price)

        buttons = []
        if rzp_url:
            buttons.append(
                [InlineKeyboardButton("🔗 Pay via Razorpay (Auto-Verify)", url=rzp_url)]
            )
        buttons.append(
            [InlineKeyboardButton("✅ Send Payment", callback_data=f"paid_{plan}")]
        )

        caption = (
            f"🛒 <b>{label}</b> — ₹{price}\n\n"
            f"📲 <b>Option 1 (Auto-Verify):</b>\n"
            f"Pay via Razorpay link — key delivered instantly ✅\n\n"
            f"📲 <b>Option 2 (Manual UPI):</b>\n"f"Scan QR → Pay ₹{price} → tap <b>I Have Paid</b>"
        )
        if os.path.exists(QR_IMAGE):
            with open(QR_IMAGE, "rb") as qr:
                await query.message.reply_photo(
                    photo=qr,
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(buttons),
                )
        else:
            await query.message.reply_text(
                caption, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(buttons)
            )

    elif data.startswith("paid_"):
        plan = data[5:]
        if plan not in PLAN_PRICES:
            return
        _, price = PLAN_PRICES[plan]
        context.user_data["state"] = STATE_AWAITING_TXN
        context.user_data["plan"] = plan
        await query.message.reply_text(
            f"🧾 Please send your <b>UPI Transaction ID</b> (UTR number) to confirm payment of ₹{price}.",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardMarkup(
                [["❌ Cancel"]], resize_keyboard=True, one_time_keyboard=True
            ),
        )

    # ── Admin approve / reject ──
    elif data.startswith("approve_"):
        if not is_admin(uid):
            await query.answer("⛔ Unauthorized", show_alert=True)
            return
        order_id = data[8:]
        pending = get_pending()
        if order_id not in pending:
            await query.message.edit_text("⚠️ Order not found or already processed.")
            return
        order = pending[order_id]
        keys = get_keys()
        if not keys.get(order["plan"]):
            await query.message.edit_text(
                f"❌ No keys left for <b>{order['label']}</b>.", parse_mode="HTML"
            )
            return
        key = keys[order["plan"]].pop(0)
        save(KEYS_FILE, keys)
        orders = get_orders()
        orders.append(
            {
                "order_id": order_id,
                "user_id": order["user_id"],
                "plan": order["plan"],
                "key": key,
                "txn_id": order["txn_id"],
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }
        )
        save(ORDERS_FILE, orders)
        del pending[order_id]
        save(PENDING_FILE, pending)
        save_user_key(order["user_id"], order["label"], key)
        await context.bot.send_message(
            chat_id=order["user_id"],
            text=(
                f"🎉 <b>Payment Approved!</b>\n\n"
                f"🎮 Plan: <b>{order['label']}</b>\n"
                f"🔑 Your Key:\n\n<code>{key}</code>\n\n"
                f"Thank you! For help: @IOS_HACK_S"
            ),
            parse_mode="HTML",
        )
        await query.message.edit_text(
            f"✅ Approved — Order <code>{order_id}</code>\n"
            f"🔑 Key <code>{key}</code> sent to user <code>{order['user_id']}</code>.",
            parse_mode="HTML",
        )

    elif data.startswith("reject_"):
        if not is_admin(uid):
            await query.answer("⛔ Unauthorized", show_alert=True)
            return
        order_id = data[7:]
        pending = get_pending()
        if order_id not in pending:
            await query.message.edit_text("⚠️ Order not found or already processed.")
            return
        order = pending.pop(order_id)
        save(PENDING_FILE, pending)
        await context.bot.send_message(
            chat_id=order["user_id"],
            text=(
                "❌ <b>Payment Rejected</b>\n\n"
                "Your payment could not be verified.\nContact support: 👤 @IOS_HACK_S"
            ),
            parse_mode="HTML",
        )
        await query.message.edit_text(
            f"❌ Rejected — Order <code>{order_id}</code>. User notified.",
            parse_mode="HTML",
        )

    elif data == "clearstock_cancel":
        if not is_admin(uid):
            await query.answer("⛔ Unauthorized", show_alert=True)
            return
        await query.message.edit_text("❌ Clear stock cancelled.")

    elif data.startswith("clearstock_plan_"):if not is_admin(uid):
            await query.answer("⛔ Unauthorized", show_alert=True)
            return
        plan_id = data[len("clearstock_plan_") :]
        if plan_id not in PLAN_PRICES:
            await query.message.edit_text("⚠️ Unknown plan.")
            return
        label, price = PLAN_PRICES[plan_id]
        keys = get_keys()
        count = len(keys.get(plan_id, []))
        confirm_kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "✅ Yes, delete all",
                        callback_data=f"clearstock_confirm_{plan_id}",
                    ),
                    InlineKeyboardButton(
                        "❌ Cancel", callback_data="clearstock_cancel"
                    ),
                ]
            ]
        )
        await query.message.edit_text(
            f"⚠️ <b>Confirm Clear Stock</b>\n\n"
            f"Plan: <b>{label}</b> (₹{price})\n"
            f"Keys to delete: <b>{count}</b>\n\n"
            f"This cannot be undone. Are you sure?",
            parse_mode="HTML",
            reply_markup=confirm_kb,
        )

    elif data.startswith("clearstock_confirm_"):
        if not is_admin(uid):
            await query.answer("⛔ Unauthorized", show_alert=True)
            return
        plan_id = data[len("clearstock_confirm_") :]
        if plan_id not in PLAN_PRICES:
            await query.message.edit_text("⚠️ Unknown plan.")
            return
        label, price = PLAN_PRICES[plan_id]
        keys = get_keys()
        count = len(keys.get(plan_id, []))
        keys[plan_id] = []
        save(KEYS_FILE, keys)
        log_admin_action(
            admin_id=uid,
            action="clearstock",
            detail=f"Cleared {count} key(s) from plan '{plan_id}' ({label})",
        )
        await query.message.edit_text(
            f"✅ <b>Stock Cleared</b>\n\n"
            f"Plan: <b>{label}</b>\n"
            f"🗑 <b>{count}</b> key(s) removed.\n"
            f"📦 Stock is now empty for this plan.",
            parse_mode="HTML",
        )

    elif data == "admin_panel":
        if not is_admin(uid):
            await query.answer("⛔ Unauthorized", show_alert=True)
            return
        await query.message.edit_text(
            "🔐 <b>Admin Panel</b>\n\nChoose an action:",
            parse_mode="HTML",
            reply_markup=admin_keyboard,
        )

    elif data in ADMIN_HELP:
        if not is_admin(uid):
            await query.answer("⛔ Unauthorized", show_alert=True)
            return
        label, body = ADMIN_HELP[data]
        await query.message.edit_text(
            f"<b>{label}</b>\n\n{body}",
            parse_mode="HTML",
            reply_markup=back_to_admin_keyboard,
        )


def main():
    if not BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("addkey", cmd_addkey))
    app.add_handler(CommandHandler("removekey", cmd_removekey))
    app.add_handler(CommandHandler("stock", cmd_stock))
    app.add_handler(CommandHandler("orders", cmd_orders))
    app.add_handler(CommandHandler("pending", cmd_pending))
    app.add_handler(CommandHandler("users", cmd_users))
    app.add_handler(CommandHandler("broadcast", cmd_broadcast))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("clearstock", cmd_clearstock))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu))

    logger.info("Bot started. Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if name == "__main__":
    main()