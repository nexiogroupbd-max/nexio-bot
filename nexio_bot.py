import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
from datetime import datetime
import time
import os

# ========== CONFIGURATION ==========
TOKEN = os.environ.get("TELEGRAM_TOKEN", "YOUR_TOKEN_HERE")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 123456789))

bot = telebot.TeleBot(TOKEN)

# ========== DATABASE SETUP ==========
def init_db():
    conn = sqlite3.connect('nexio.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  telegram_id INTEGER UNIQUE,
                  username TEXT,
                  created_at TEXT)''')
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
    c.execute('''CREATE TABLE IF NOT EXISTS rates
                 (currency TEXT PRIMARY KEY,
                  buy_rate REAL,
                  sell_rate REAL,
                  updated_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS payment_methods
                 (currency TEXT PRIMARY KEY,
                  details TEXT,
                  updated_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings
                 (key TEXT PRIMARY KEY, value TEXT)''')
    conn.commit()
    conn.close()

init_db()

# ========== HELPERS ==========
def save_user(telegram_id, username):
    conn = sqlite3.connect('nexio.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (telegram_id, username, created_at) VALUES (?, ?, ?)",
              (telegram_id, username, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_setting(key):
    conn = sqlite3.connect('nexio.db')
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key = ?", (key,))
    r = c.fetchone()
    conn.close()
    return r[0] if r else ""

def update_setting(key, value):
    conn = sqlite3.connect('nexio.db')
    c = conn.cursor()
    c.execute("UPDATE settings SET value = ? WHERE key = ?", (value, key))
    conn.commit()
    conn.close()

def get_rate(currency):
    conn = sqlite3.connect('nexio.db')
    c = conn.cursor()
    c.execute("SELECT buy_rate, sell_rate FROM rates WHERE currency = ?", (currency.upper(),))
    r = c.fetchone()
    conn.close()
    return r

# ========== MAIN MENU ==========
def main_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("💰 Buy USDT", callback_data="buy"),
        InlineKeyboardButton("💵 Sell USDT", callback_data="sell"),
        InlineKeyboardButton("📊 Rates", callback_data="rates"),
        InlineKeyboardButton("📋 My Orders", callback_data="myorders")
    )
    return markup

@bot.message_handler(commands=['start'])
def start(message):
    save_user(message.from_user.id, message.from_user.username)
    bot.send_message(message.chat.id, "Welcome to Nexio Exchange Bot! 🤖\n\nChoose an option:", reply_markup=main_menu())

# ========== CALLBACK HANDLERS ==========
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.data == "buy":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "💰 Send me the currency code (e.g., USD, PHP, NGN):")
        bot.register_next_step_handler(call.message, buy_get_currency)
    elif call.data == "sell":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "💵 Send me the currency code (e.g., USD, PHP, NGN):")
        bot.register_next_step_handler(call.message, sell_get_currency)
    elif call.data == "rates":
        show_rates(call.message)
    elif call.data == "myorders":
        show_my_orders(call.message)
    elif call.data == "menu":
        bot.edit_message_text("Main Menu:", call.message.chat.id, call.message.message_id, reply_markup=main_menu())

def show_rates(message):
    conn = sqlite3.connect('nexio.db')
    c = conn.cursor()
    c.execute("SELECT currency, buy_rate, sell_rate FROM rates LIMIT 10")
    rates = c.fetchall()
    conn.close()
    if rates:
        text = "📊 *Current Rates (1 USDT = X)*\n\n"
        for r in rates:
            text += f"• {r[0]}: Buy={r[1]:,.0f} | Sell={r[2]:,.0f}\n"
        bot.send_message(message.chat.id, text, parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, "No rates available.")

def show_my_orders(message):
    conn = sqlite3.connect('nexio.db')
    c = conn.cursor()
    c.execute("SELECT order_id, type, amount_sent, amount_receive, status FROM orders WHERE user_id = ? ORDER BY created_at DESC LIMIT 5", (message.chat.id,))
    orders = c.fetchall()
    conn.close()
    if orders:
        text = "📋 *Your Orders:*\n\n"
        for o in orders:
            emoji = "✅" if o[4] == "approved" else "⏳" if o[4] == "pending" else "❌"
            text += f"{emoji} {o[0]} | {o[1]} | {o[2]} → {o[3]:.2f}\n"
        bot.send_message(message.chat.id, text, parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, "No orders yet.")

# ========== BUY USDT FLOW ==========
def buy_get_currency(message):
    currency = message.text.upper()
    bot.send_message(message.chat.id, f"Enter amount in {currency}:")
    bot.register_next_step_handler(message, lambda m: buy_get_amount(m, currency))

def buy_get_amount(message, currency):
    try:
        amount = float(message.text)
        rate_data = get_rate(currency)
        if not rate_data:
            bot.send_message(message.chat.id, f"❌ Rate not set for {currency}. Admin will update.")
            return
        buy_rate = rate_data[0]
        usdt = amount / buy_rate
        
        # Store order in database
        order_id = f"NEX-{int(time.time())}"
        conn = sqlite3.connect('nexio.db')
        c = conn.cursor()
        c.execute("INSERT INTO orders (order_id, user_id, type, currency, amount_sent, amount_receive, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                  (order_id, message.chat.id, "buy", currency, amount, usdt, "pending", datetime.now().isoformat()))
        conn.commit()
        conn.close()
        
        # Get payment details
        conn = sqlite3.connect('nexio.db')
        c = conn.cursor()
        c.execute("SELECT details FROM payment_methods WHERE currency = ?", (currency,))
        payment = c.fetchone()
        conn.close()
        
        payment_text = payment[0] if payment else "⚠️ Payment details not set."
        
        bot.send_message(message.chat.id, f"💰 *Order #{order_id}*\n\nCurrency: {currency}\nAmount: {amount:,.2f}\nRate: 1 USDT = {buy_rate:,.2f}\n\n✨ You receive: {usdt:.2f} USDT\n\n📤 *Payment:*\n{payment_text}\n\nSend payment and reply with your receipt image.", parse_mode="Markdown")
        
        # Wait for receipt
        bot.register_next_step_handler(message, lambda m: process_receipt(m, order_id, "buy"))
    except ValueError:
        bot.send_message(message.chat.id, "❌ Please enter a valid number.")
        bot.register_next_step_handler(message, lambda m: buy_get_amount(m, currency))

# ========== SELL USDT FLOW ==========
def sell_get_currency(message):
    currency = message.text.upper()
    bot.send_message(message.chat.id, f"Enter amount in USDT:")
    bot.register_next_step_handler(message, lambda m: sell_get_amount(m, currency))

def sell_get_amount(message, currency):
    try:
        usdt = float(message.text)
        rate_data = get_rate(currency)
        if not rate_data:
            bot.send_message(message.chat.id, f"❌ Rate not set for {currency}. Admin will update.")
            return
        sell_rate = rate_data[1]
        local = usdt * sell_rate
        
        order_id = f"NEX-{int(time.time())}"
        conn = sqlite3.connect('nexio.db')
        c = conn.cursor()
        c.execute("INSERT INTO orders (order_id, user_id, type, currency, amount_sent, amount_receive, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                  (order_id, message.chat.id, "sell", currency, usdt, local, "pending", datetime.now().isoformat()))
        conn.commit()
        conn.close()
        
        trc20 = get_setting("usdt_wallet_trc20")
        wallet_text = f"🔹 TRC20: {trc20}" if trc20 else "⚠️ Wallet not set"
        
        bot.send_message(message.chat.id, f"💵 *Order #{order_id}*\n\nUSDT: {usdt:.2f}\nRate: 1 USDT = {sell_rate:,.2f} {currency}\n\n✨ You receive: {local:,.2f} {currency}\n\n📤 *Send USDT to:*\n{wallet_text}\n\nSend USDT and reply with your transaction screenshot.", parse_mode="Markdown")
        
        bot.register_next_step_handler(message, lambda m: process_receipt(m, order_id, "sell"))
    except ValueError:
        bot.send_message(message.chat.id, "❌ Please enter a valid number.")
        bot.register_next_step_handler(message, lambda m: sell_get_amount(m, currency))

# ========== RECEIPT HANDLER ==========
def process_receipt(message, order_id, order_type):
    if message.photo:
        file_id = message.photo[-1].file_id
        conn = sqlite3.connect('nexio.db')
        c = conn.cursor()
        c.execute("UPDATE orders SET receipt_file_id = ? WHERE order_id = ?", (file_id, order_id))
        conn.commit()
        conn.close()
        
        bot.send_message(message.chat.id, f"✅ Receipt received! Order #{order_id} is pending verification.")
        
        # Notify admin
        bot.send_message(ADMIN_ID, f"🔔 *NEW ORDER #{order_id}*\nUser: {message.chat.id}\nType: {order_type}\nStatus: Pending", parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, "❌ Please send a photo receipt.")
        bot.register_next_step_handler(message, lambda m: process_receipt(m, order_id, order_type))

# ========== ADMIN COMMANDS ==========
@bot.message_handler(commands=['stats'])
def stats(message):
    if message.chat.id != ADMIN_ID:
        return
    conn = sqlite3.connect('nexio.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM orders")
    total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM orders WHERE status = 'pending'")
    pending = c.fetchone()[0]
    conn.close()
    bot.reply_to(message, f"📊 *Stats*\n👥 Users: {users}\n📦 Orders: {total}\n⏳ Pending: {pending}", parse_mode="Markdown")

@bot.message_handler(commands=['orders'])
def list_orders(message):
    if message.chat.id != ADMIN_ID:
        return
    conn = sqlite3.connect('nexio.db')
    c = conn.cursor()
    c.execute("SELECT order_id, user_id, type, status FROM orders WHERE status = 'pending'")
    orders = c.fetchall()
    conn.close()
    if orders:
        text = "📋 *Pending Orders:*\n\n"
        for o in orders:
            text += f"`{o[0]}` | User: {o[1]} | {o[2]}\n"
        bot.reply_to(message, text, parse_mode="Markdown")
    else:
        bot.reply_to(message, "No pending orders.")

@bot.message_handler(commands=['setrate'])
def set_rate(message):
    if message.chat.id != ADMIN_ID:
        return
    try:
        parts = message.text.split()
        curr = parts[1].upper()
        buy = float(parts[2])
        sell = float(parts[3])
        conn = sqlite3.connect('nexio.db')
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO rates (currency, buy_rate, sell_rate, updated_at) VALUES (?, ?, ?, ?)",
                  (curr, buy, sell, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        bot.reply_to(message, f"✅ Rate set: 1 USDT = {buy}/{sell} {curr}")
    except:
        bot.reply_to(message, "❌ Usage: /setrate CURRENCY BUY SELL\nExample: /setrate PHP 60 60")

@bot.message_handler(commands=['setpayment'])
def set_payment(message):
    if message.chat.id != ADMIN_ID:
        return
    try:
        parts = message.text.split(maxsplit=2)
        curr = parts[1].upper()
        details = parts[2]
        conn = sqlite3.connect('nexio.db')
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO payment_methods (currency, details, updated_at) VALUES (?, ?, ?)",
                  (curr, details, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        bot.reply_to(message, f"✅ Payment details set for {curr}")
    except:
        bot.reply_to(message, "❌ Usage: /setpayment CURRENCY DETAILS")

@bot.message_handler(commands=['setwallet'])
def set_wallet(message):
    if message.chat.id != ADMIN_ID:
        return
    try:
        parts = message.text.split(maxsplit=2)
        network = parts[1].lower()
        address = parts[2]
        update_setting(f"usdt_wallet_{network}", address)
        bot.reply_to(message, f"✅ {network.upper()} wallet set")
    except:
        bot.reply_to(message, "❌ Usage: /setwallet trc20 ADDRESS")

@bot.message_handler(commands=['setwhatsapp'])
def set_whatsapp(message):
    if message.chat.id != ADMIN_ID:
        return
    try:
        link = message.text.split(maxsplit=1)[1]
        update_setting("whatsapp_channel", link)
        bot.reply_to(message, f"✅ WhatsApp channel updated")
    except:
        bot.reply_to(message, "❌ Usage: /setwhatsapp LINK")

@bot.message_handler(commands=['setphone'])
def set_phone(message):
    if message.chat.id != ADMIN_ID:
        return
    try:
        phone = message.text.split(maxsplit=1)[1]
        update_setting("support_phone", phone)
        bot.reply_to(message, f"✅ Support number updated")
    except:
        bot.reply_to(message, "❌ Usage: /setphone NUMBER")

@bot.message_handler(commands=['approve'])
def approve(message):
    if message.chat.id != ADMIN_ID:
        return
    try:
        order_id = message.text.split()[1]
        conn = sqlite3.connect('nexio.db')
        c = conn.cursor()
        c.execute("SELECT user_id FROM orders WHERE order_id = ? AND status = 'pending'", (order_id,))
        user = c.fetchone()
        if user:
            c.execute("UPDATE orders SET status = 'approved' WHERE order_id = ?", (order_id,))
            conn.commit()
            bot.send_message(user[0], f"✅ Order {order_id} APPROVED!")
            bot.reply_to(message, f"✅ Order {order_id} approved")
        else:
            bot.reply_to(message, "Order not found")
        conn.close()
    except:
        bot.reply_to(message, "❌ Usage: /approve ORDER_ID")

@bot.message_handler(commands=['reject'])
def reject(message):
    if message.chat.id != ADMIN_ID:
        return
    try:
        parts = message.text.split(maxsplit=2)
        order_id = parts[1]
        reason = parts[2] if len(parts) > 2 else "No reason"
        conn = sqlite3.connect('nexio.db')
        c = conn.cursor()
        c.execute("SELECT user_id FROM orders WHERE order_id = ? AND status = 'pending'", (order_id,))
        user = c.fetchone()
        if user:
            c.execute("UPDATE orders SET status = 'rejected' WHERE order_id = ?", (order_id,))
            conn.commit()
            bot.send_message(user[0], f"❌ Order {order_id} REJECTED\nReason: {reason}")
            bot.reply_to(message, f"✅ Order {order_id} rejected")
        else:
            bot.reply_to(message, "Order not found")
        conn.close()
    except:
        bot.reply_to(message, "❌ Usage: /reject ORDER_ID REASON")

@bot.message_handler(commands=['cancel'])
def cancel(message):
    bot.reply_to(message, "❌ Cancelled. Start over with /start")

# ========== RUN ==========
if __name__ == "__main__":
    print("Bot is running...")
    bot.infinity_polling()
