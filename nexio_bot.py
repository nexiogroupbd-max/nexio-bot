import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
import json
from datetime import datetime
import os
import re

# ========== CONFIGURATION ==========
# !!! REPLACE THESE TWO LINES WITH YOUR ACTUAL VALUES !!!
TOKEN = "8898175828:AAG2gAYvaVGHlYvDsRc_RBDHOnXfHfsS4iM"  # Get from @BotFather after revoking old token
ADMIN_ID = 8795577073  # Get from @userinfobot - replace with your numeric ID

# These can be updated via admin commands (no need to change here)
WHATSAPP_CHANNEL = "https://whatsapp.com/channel/0029Vb8G3z1HQbSCVQwrt52K"
SUPPORT_PHONE = "639524529849"  # Without + sign for WhatsApp link

bot = telebot.TeleBot(TOKEN)

# ========== DATABASE SETUP ==========
def init_db():
    conn = sqlite3.connect('nexio.db')
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  telegram_id INTEGER UNIQUE,
                  username TEXT,
                  created_at TEXT)''')
    
    # Orders table
    c.execute('''CREATE TABLE IF NOT EXISTS orders
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  order_id TEXT UNIQUE,
                  user_id INTEGER,
                  type TEXT,
                  currency TEXT,
                  amount_sent REAL,
                  amount_receive REAL,
                  status TEXT,
                  receipt_file_id TEXT,
                  created_at TEXT)''')
    
    # Rates table
    c.execute('''CREATE TABLE IF NOT EXISTS rates
                 (currency TEXT PRIMARY KEY,
                  buy_rate REAL,
                  sell_rate REAL,
                  updated_at TEXT)''')
    
    # Payment methods table
    c.execute('''CREATE TABLE IF NOT EXISTS payment_methods
                 (currency TEXT PRIMARY KEY,
                  details TEXT,
                  updated_at TEXT)''')
    
    # Settings table
    c.execute('''CREATE TABLE IF NOT EXISTS settings
                 (key TEXT PRIMARY KEY,
                  value TEXT)''')
    
    # Insert default settings
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('whatsapp_channel', ?)", (WHATSAPP_CHANNEL,))
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('support_phone', ?)", (SUPPORT_PHONE,))
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('usdt_wallet_trc20', '')")
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('usdt_wallet_bep20', '')")
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('usdt_wallet_apt', '')")
    
    conn.commit()
    conn.close()

init_db()

# ========== HELPER FUNCTIONS ==========
def get_setting(key):
    conn = sqlite3.connect('nexio.db')
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key = ?", (key,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else ""

def update_setting(key, value):
    conn = sqlite3.connect('nexio.db')
    c = conn.cursor()
    c.execute("UPDATE settings SET value = ? WHERE key = ?", (value, key))
    conn.commit()
    conn.close()

def get_rate(currency, order_type):
    conn = sqlite3.connect('nexio.db')
    c = conn.cursor()
    c.execute("SELECT buy_rate, sell_rate FROM rates WHERE currency = ?", (currency.upper(),))
    result = c.fetchone()
    conn.close()
    if result:
        return result[0] if order_type == "buy" else result[1]
    return None

def save_user(telegram_id, username):
    conn = sqlite3.connect('nexio.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (telegram_id, username, created_at) VALUES (?, ?, ?)",
              (telegram_id, username, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def generate_order_id():
    return f"NEX-{datetime.now().strftime('%Y%m%d%H%M%S')}"

# ========== CURRENCIES ==========
CURRENCIES = {
    "USD": "🇺🇸 US Dollar", "EUR": "🇪🇺 Euro", "GBP": "🇬🇧 British Pound",
    "NGN": "🇳🇬 Nigerian Naira", "KES": "🇰🇪 Kenyan Shilling", "GHS": "🇬🇭 Ghanaian Cedi",
    "ZAR": "🇿🇦 South African Rand", "INR": "🇮🇳 Indian Rupee", "PKR": "🇵🇰 Pakistani Rupee",
    "BDT": "🇧🇩 Bangladeshi Taka", "LKR": "🇱🇰 Sri Lankan Rupee", "NPR": "🇳🇵 Nepalese Rupee",
    "CNY": "🇨🇳 Chinese Yuan", "JPY": "🇯🇵 Japanese Yen", "CAD": "🇨🇦 Canadian Dollar",
    "AUD": "🇦🇺 Australian Dollar", "MYR": "🇲🇾 Malaysian Ringgit", "SGD": "🇸🇬 Singapore Dollar",
    "THB": "🇹🇭 Thai Baht", "VND": "🇻🇳 Vietnamese Dong", "PHP": "🇵🇭 Philippine Peso",
    "IDR": "🇮🇩 Indonesian Rupiah", "AED": "🇦🇪 UAE Dirham", "SAR": "🇸🇦 Saudi Riyal",
    "TRY": "🇹🇷 Turkish Lira", "RUB": "🇷🇺 Russian Ruble", "BRL": "🇧🇷 Brazilian Real",
    "MXN": "🇲🇽 Mexican Peso", "CHF": "🇨🇭 Swiss Franc"
}

# ========== MAIN MENU ==========
def main_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("💰 Buy USDT", callback_data="buy_usdt"),
        InlineKeyboardButton("💵 Sell USDT", callback_data="sell_usdt")
    )
    markup.add(
        InlineKeyboardButton("📊 Current Rates", callback_data="show_rates"),
        InlineKeyboardButton("📋 My Orders", callback_data="my_orders")
    )
    markup.add(
        InlineKeyboardButton("📢 WhatsApp Channel", callback_data="whatsapp_channel"),
        InlineKeyboardButton("👤 Contact Support", callback_data="contact_support")
    )
    markup.add(
        InlineKeyboardButton("❓ Help", callback_data="help")
    )
    return markup

def currency_keyboard():
    markup = InlineKeyboardMarkup(row_width=3)
    buttons = []
    for code, name in list(CURRENCIES.items())[:15]:
        buttons.append(InlineKeyboardButton(name, callback_data=f"curr_{code}"))
    markup.add(*buttons)
    markup.add(InlineKeyboardButton("🌐 Show All Currencies", callback_data="show_all_currencies"))
    markup.add(InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu"))
    return markup

# ========== USER STATES ==========
user_states = {}

# ========== COMMAND HANDLERS ==========
@bot.message_handler(commands=['start'])
def start(message):
    save_user(message.from_user.id, message.from_user.username)
    bot.send_message(
        message.chat.id,
        "Welcome to Nexio Exchange Bot! 🤖\n\n"
        "💱 I help you exchange any currency to USDT and vice versa.\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "Choose an option below:",
        reply_markup=main_menu()
    )

@bot.callback_query_handler(func=lambda call: call.data == "back_to_menu")
def back_to_menu(call):
    bot.edit_message_text(
        "Main Menu:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=main_menu()
    )

@bot.callback_query_handler(func=lambda call: call.data == "buy_usdt")
def buy_usdt_start(call):
    bot.edit_message_text(
        "💰 *Buy USDT*\n\nSelect your local currency:",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown",
        reply_markup=currency_keyboard()
    )
    user_states[call.from_user.id] = {"action": "buy_waiting_currency"}

@bot.callback_query_handler(func=lambda call: call.data == "sell_usdt")
def sell_usdt_start(call):
    bot.edit_message_text(
        "💵 *Sell USDT*\n\nSelect your local currency:",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown",
        reply_markup=currency_keyboard()
    )
    user_states[call.from_user.id] = {"action": "sell_waiting_currency"}

@bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("curr_"))
def currency_selected(call):
    action = user_states.get(call.from_user.id, {}).get("action", "")
    if "waiting_currency" not in action:
        return
    
    currency = call.data.replace("curr_", "")
    
    if action == "buy_waiting_currency":
        user_states[call.from_user.id] = {"action": "buy_waiting_amount", "currency": currency}
        bot.edit_message_text(
            f"💰 *Buy USDT*\n\nCurrency: {CURRENCIES.get(currency, currency)} ({currency})\n\nEnter amount in {currency}:",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Cancel", callback_data="back_to_menu"))
        )
    elif action == "sell_waiting_currency":
        user_states[call.from_user.id] = {"action": "sell_waiting_amount", "currency": currency}
        bot.edit_message_text(
            f"💵 *Sell USDT*\n\nLocal Currency: {CURRENCIES.get(currency, currency)} ({currency})\n\nEnter amount in USDT:",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Cancel", callback_data="back_to_menu"))
        )

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id, {}).get("action") == "buy_waiting_amount")
def buy_amount_received(message):
    try:
        amount = float(message.text)
        state = user_states[message.from_user.id]
        currency = state["currency"]
        
        rate = get_rate(currency, "buy")
        if rate is None:
            bot.reply_to(message, f"❌ Rate not available for {currency}. Admin will update soon.")
            return
        
        usdt_amount = amount / rate
        
        user_states[message.from_user.id] = {
            "action": "buy_confirm",
            "currency": currency,
            "amount": amount,
            "usdt_amount": usdt_amount
        }
        
        conn = sqlite3.connect('nexio.db')
        c = conn.cursor()
        c.execute("SELECT details FROM payment_methods WHERE currency = ?", (currency,))
        payment = c.fetchone()
        conn.close()
        
        payment_text = payment[0] if payment else "⚠️ Payment details not set. Admin will contact you."
        
        bot.send_message(
            message.chat.id,
            f"💰 *Order Summary*\n\n"
            f"Currency: {currency}\n"
            f"Amount: {amount:,.2f} {currency}\n"
            f"Rate: 1 USDT = {rate:,.2f} {currency}\n\n"
            f"✨ You will receive: *{usdt_amount:.2f} USDT*\n\n"
            f"📤 *Payment Details:*\n{payment_text}\n\n"
            f"Send payment and tap '✅ I Have Paid' below.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup().add(
                InlineKeyboardButton("✅ I Have Paid", callback_data="submit_receipt"),
                InlineKeyboardButton("❌ Cancel", callback_data="back_to_menu")
            )
        )
    except ValueError:
        bot.reply_to(message, "❌ Please enter a valid number.")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id, {}).get("action") == "sell_waiting_amount")
def sell_amount_received(message):
    try:
        usdt_amount = float(message.text)
        state = user_states[message.from_user.id]
        currency = state["currency"]
        
        rate = get_rate(currency, "sell")
        if rate is None:
            bot.reply_to(message, f"❌ Rate not available for {currency}. Admin will update soon.")
            return
        
        local_amount = usdt_amount * rate
        
        user_states[message.from_user.id] = {
            "action": "sell_confirm",
            "currency": currency,
            "usdt_amount": usdt_amount,
            "local_amount": local_amount
        }
        
        trc20 = get_setting("usdt_wallet_trc20")
        bep20 = get_setting("usdt_wallet_bep20")
        apt = get_setting("usdt_wallet_apt")
        
        wallet_text = ""
        if trc20:
            wallet_text += f"🔹 TRC20: `{trc20}`\n"
        if bep20:
            wallet_text += f"🔹 BEP20: `{bep20}`\n"
        if apt:
            wallet_text += f"🔹 APT: `{apt}`\n"
        
        if not wallet_text:
            wallet_text = "⚠️ Wallet address not set. Admin will contact you."
        
        bot.send_message(
            message.chat.id,
            f"💵 *Order Summary*\n\n"
            f"Currency: {currency}\n"
            f"USDT Amount: {usdt_amount:.2f} USDT\n"
            f"Rate: 1 USDT = {rate:,.2f} {currency}\n\n"
            f"✨ You will receive: *{local_amount:,.2f} {currency}*\n\n"
            f"📤 *Send USDT to:*\n{wallet_text}\n\n"
            f"Minimum: 10 USDT\n\n"
            f"Send USDT and tap '✅ I Have Sent' below.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup().add(
                InlineKeyboardButton("✅ I Have Sent", callback_data="submit_receipt"),
                InlineKeyboardButton("❌ Cancel", callback_data="back_to_menu")
            )
        )
    except ValueError:
        bot.reply_to(message, "❌ Please enter a valid number.")

@bot.callback_query_handler(func=lambda call: call.data == "submit_receipt")
def submit_receipt(call):
    user_states[call.from_user.id] = {"action": "waiting_receipt"}
    bot.edit_message_text(
        "📸 Please send your payment receipt/screenshot.\n\n"
        "You can send a photo or document.\n\n"
        "Type /cancel to cancel order.",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("❌ Cancel", callback_data="back_to_menu")
        )
    )

@bot.message_handler(content_types=['photo', 'document'])
def handle_receipt(message):
    state = user_states.get(message.from_user.id, {})
    if state.get("action") != "waiting_receipt":
        return
    
    if message.photo:
        file_id = message.photo[-1].file_id
    else:
        file_id = message.document.file_id
    
    order_id = generate_order_id()
    
    conn = sqlite3.connect('nexio.db')
    c = conn.cursor()
    c.execute("""INSERT INTO orders 
                 (order_id, user_id, type, currency, amount_sent, amount_receive, 
                  status, receipt_file_id, created_at)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
              (order_id, message.from_user.id, 
               "buy" if "buy" in str(state) else "sell",
               state.get("currency", ""),
               state.get("amount", 0) or state.get("usdt_amount", 0),
               state.get("usdt_amount", 0) or state.get("local_amount", 0),
               "pending", file_id, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    
    admin_markup = InlineKeyboardMarkup()
    admin_markup.add(
        InlineKeyboardButton(f"✅ Approve {order_id}", callback_data=f"approve_{order_id}"),
        InlineKeyboardButton(f"❌ Reject {order_id}", callback_data=f"reject_{order_id}")
    )
    
    bot.send_message(
        ADMIN_ID,
        f"🔔 *NEW ORDER*\n\n"
        f"Order ID: `{order_id}`\n"
        f"User: @{message.from_user.username or message.from_user.id}\n"
        f"Type: {'Buy USDT' if 'buy' in str(state) else 'Sell USDT'}\n"
        f"Details: Check database\n\n"
        f"Receipt attached below.",
        parse_mode="Markdown",
        reply_markup=admin_markup
    )
    
    if message.photo:
        bot.send_photo(ADMIN_ID, file_id)
    else:
        bot.send_document(ADMIN_ID, file_id)
    
    bot.reply_to(message, f"✅ Receipt received!\n\nOrder ID: {order_id}\n\n⏳ Admin will verify and process your order.")
    del user_states[message.from_user.id]

# ========== ADMIN COMMANDS ==========
@bot.message_handler(commands=['setrate'])
def set_rate(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        parts = message.text.split()
        currency = parts[1].upper()
        buy_rate = float(parts[2])
        sell_rate = float(parts[3])
        
        conn = sqlite3.connect('nexio.db')
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO rates (currency, buy_rate, sell_rate, updated_at) VALUES (?, ?, ?, ?)",
                  (currency, buy_rate, sell_rate, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        
        bot.reply_to(message, f"✅ Rate set for {currency}: Buy={buy_rate}, Sell={sell_rate}")
    except:
        bot.reply_to(message, "❌ Usage: /setrate CURRENCY BUY_RATE SELL_RATE\nExample: /setrate NGN 1650 1650")

@bot.message_handler(commands=['setpayment'])
def set_payment(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        parts = message.text.split(maxsplit=2)
        currency = parts[1].upper()
        details = parts[2]
        
        conn = sqlite3.connect('nexio.db')
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO payment_methods (currency, details, updated_at) VALUES (?, ?, ?)",
                  (currency, details, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        
        bot.reply_to(message, f"✅ Payment details set for {currency}")
    except:
        bot.reply_to(message, "❌ Usage: /setpayment CURRENCY DETAILS\nExample: /setpayment NGN Bank: First Bank, Account: 123")

@bot.message_handler(commands=['setwallet'])
def set_wallet(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        parts = message.text.split(maxsplit=2)
        network = parts[1].lower()
        address = parts[2]
        
        if network in ["trc20", "bep20", "apt"]:
            update_setting(f"usdt_wallet_{network}", address)
            bot.reply_to(message, f"✅ {network.upper()} wallet address set")
        else:
            bot.reply_to(message, "❌ Network must be: trc20, bep20, or apt")
    except:
        bot.reply_to(message, "❌ Usage: /setwallet NETWORK ADDRESS\nExample: /setwallet trc20 TYxo...3aB7")

@bot.message_handler(commands=['setwhatsapp'])
def set_whatsapp(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        link = message.text.split(maxsplit=1)[1]
        update_setting("whatsapp_channel", link)
        bot.reply_to(message, f"✅ WhatsApp channel link updated")
    except:
        bot.reply_to(message, "❌ Usage: /setwhatsapp LINK")

@bot.message_handler(commands=['setphone'])
def set_phone(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        phone = message.text.split(maxsplit=1)[1].replace("+", "").replace(" ", "")
        update_setting("support_phone", phone)
        bot.reply_to(message, f"✅ Support phone number updated")
    except:
        bot.reply_to(message, "❌ Usage: /setphone NUMBER\nExample: /setphone 639524529849")

@bot.message_handler(commands=['approve'])
def approve_order(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        order_id = message.text.split()[1]
        conn = sqlite3.connect('nexio.db')
        c = conn.cursor()
        c.execute("SELECT user_id FROM orders WHERE order_id = ? AND status = 'pending'", (order_id,))
        result = c.fetchone()
        if result:
            c.execute("UPDATE orders SET status = 'approved' WHERE order_id = ?", (order_id,))
            conn.commit()
            bot.send_message(result[0], f"✅ Order {order_id} APPROVED!\n\nYour exchange has been processed.")
            bot.reply_to(message, f"✅ Order {order_id} approved")
        else:
            bot.reply_to(message, "❌ Order not found or already processed")
        conn.close()
    except:
        bot.reply_to(message, "❌ Usage: /approve ORDER_ID")

@bot.message_handler(commands=['reject'])
def reject_order(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        parts = message.text.split(maxsplit=2)
        order_id = parts[1]
        reason = parts[2] if len(parts) > 2 else "No reason provided"
        
        conn = sqlite3.connect('nexio.db')
        c = conn.cursor()
        c.execute("SELECT user_id FROM orders WHERE order_id = ? AND status = 'pending'", (order_id,))
        result = c.fetchone()
        if result:
            c.execute("UPDATE orders SET status = 'rejected' WHERE order_id = ?", (order_id,))
            conn.commit()
            bot.send_message(result[0], f"❌ Order {order_id} REJECTED\n\nReason: {reason}")
            bot.reply_to(message, f"✅ Order {order_id} rejected")
        else:
            bot.reply_to(message, "❌ Order not found")
        conn.close()
    except:
        bot.reply_to(message, "❌ Usage: /reject ORDER_ID REASON")

@bot.message_handler(commands=['orders'])
def list_orders(message):
    if message.from_user.id != ADMIN_ID:
        return
    conn = sqlite3.connect('nexio.db')
    c = conn.cursor()
    c.execute("SELECT order_id, user_id, type, status, created_at FROM orders WHERE status = 'pending'")
    orders = c.fetchall()
    conn.close()
    
    if orders:
        text = "📋 *Pending Orders:*\n\n"
        for order in orders:
            text += f"`{order[0]}` | User: {order[1]} | {order[2]} | {order[3]}\n"
        bot.reply_to(message, text, parse_mode="Markdown")
    else:
        bot.reply_to(message, "No pending orders")

@bot.message_handler(commands=['stats'])
def stats(message):
    if message.from_user.id != ADMIN_ID:
        return
    conn = sqlite3.connect('nexio.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM orders")
    total_orders = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM orders WHERE status = 'pending'")
    pending = c.fetchone()[0]
    conn.close()
    
    bot.reply_to(message, f"📊 *Bot Statistics*\n\n👥 Users: {users}\n📦 Total Orders: {total_orders}\n⏳ Pending: {pending}", parse_mode="Markdown")

# ========== USER CALLBACKS ==========
@bot.callback_query_handler(func=lambda call: call.data == "show_rates")
def show_rates(call):
    conn = sqlite3.connect('nexio.db')
    c = conn.cursor()
    c.execute("SELECT currency, buy_rate, sell_rate FROM rates LIMIT 20")
    rates = c.fetchall()
    conn.close()
    
    if rates:
        text = "📊 *Current Exchange Rates (1 USDT = X)*\n\n"
        for rate in rates:
            text += f"• {rate[0]}: Buy={rate[1]:,.0f} | Sell={rate[2]:,.0f}\n"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown",
                              reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")))
    else:
        bot.edit_message_text("⚠️ No rates available. Admin will update soon.", call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == "my_orders")
def my_orders(call):
    conn = sqlite3.connect('nexio.db')
    c = conn.cursor()
    c.execute("SELECT order_id, type, amount_sent, amount_receive, status FROM orders WHERE user_id = ? ORDER BY created_at DESC LIMIT 10",
              (call.from_user.id,))
    orders = c.fetchall()
    conn.close()
    
    if orders:
        text = "📋 *Your Recent Orders:*\n\n"
        for order in orders:
            status_emoji = "✅" if order[4] == "approved" else "⏳" if order[4] == "pending" else "❌"
            text += f"{status_emoji} `{order[0]}` | {order[1]} | {order[2]} → {order[3]:.2f}\n"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown",
                              reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")))
    else:
        bot.edit_message_text("📋 No orders yet.", call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == "whatsapp_channel")
def whatsapp_channel(call):
    channel = get_setting("whatsapp_channel")
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, f"📢 *Join our WhatsApp Channel for updates:*\n\n{channel}", parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "contact_support")
def contact_support(call):
    phone = get_setting("support_phone")
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, f"👤 *Contact Admin*\n\nClick below to chat on WhatsApp:\n\nhttps://wa.me/{phone}", parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "help")
def help_menu(call):
    bot.edit_message_text(
        "❓ *Help Guide*\n\n"
        "💰 **Buy USDT**: Send local currency, receive USDT\n"
        "💵 **Sell USDT**: Send USDT, receive local currency\n\n"
        "📋 **Process**:\n"
        "1. Select currency and amount\n"
        "2. Send payment to provided details\n"
        "3. Upload receipt\n"
        "4. Admin verifies and processes\n\n"
        "⏳ Wait time: Usually 10-30 minutes\n\n"
        "For urgent issues: Contact support via WhatsApp",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back", callback_data="back_to_menu"))
    )

@bot.callback_query_handler(func=lambda call: call.data == "show_all_currencies")
def show_all_currencies(call):
    text = "🌐 *All Available Currencies:*\n\n"
    for code, name in CURRENCIES.items():
        text += f"• {name} ({code})\n"
    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("🔙 Back", callback_data="back_to_currency_select")
        )
    )

@bot.callback_query_handler(func=lambda call: call.data == "back_to_currency_select")
def back_to_currency(call):
    bot.edit_message_text(
        "Select your currency:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=currency_keyboard()
    )

# ========== ADMIN APPROVAL CALLBACKS ==========
@bot.callback_query_handler(func=lambda call: call.data.startswith("approve_"))
def admin_approve(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Unauthorized")
        return
    order_id = call.data.replace("approve_", "")
    conn = sqlite3.connect('nexio.db')
    c = conn.cursor()
    c.execute("SELECT user_id FROM orders WHERE order_id = ? AND status = 'pending'", (order_id,))
    result = c.fetchone()
    if result:
        c.execute("UPDATE orders SET status = 'approved' WHERE order_id = ?", (order_id,))
        conn.commit()
        bot.send_message(result[0], f"✅ Order {order_id} APPROVED!\n\nYour exchange has been processed.")
        bot.answer_callback_query(call.id, f"Order {order_id} approved")
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    conn.close()

@bot.callback_query_handler(func=lambda call: call.data.startswith("reject_"))
def admin_reject(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Unauthorized")
        return
    order_id = call.data.replace("reject_", "")
    conn = sqlite3.connect('nexio.db')
    c = conn.cursor()
    c.execute("SELECT user_id FROM orders WHERE order_id = ? AND status = 'pending'", (order_id,))
    result = c.fetchone()
    if result:
        c.execute("UPDATE orders SET status = 'rejected' WHERE order_id = ?", (order_id,))
        conn.commit()
        bot.send_message(result[0], f"❌ Order {order_id} REJECTED.\n\nContact support for details.")
        bot.answer_callback_query(call.id, f"Order {order_id} rejected")
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    conn.close()

# ========== CANCEL COMMAND ==========
@bot.message_handler(commands=['cancel'])
def cancel(message):
    if message.from_user.id in user_states:
        del user_states[message.from_user.id]
        bot.reply_to(message, "❌ Order cancelled.")
        bot.send_message(message.chat.id, "Main Menu:", reply_markup=main_menu())
    else:
        bot.reply_to(message, "No active order to cancel.")

# ========== RUN BOT ==========
if __name__ == "__main__":
    print("🤖 Nexio Exchange Bot is running...")
    bot.infinity_polling()