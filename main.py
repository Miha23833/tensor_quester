from collections import defaultdict
import dbRequests
import psycopg2
import psycopg2.extras as extras
import telebot
import json
import time
import os

if __name__ == '__main__':
    with open('messages.json', 'r') as file:
        messages = json.load(file)

    constants_keys = ['TOKEN', 'DB_HOST', 'DB_NAME', 'USER', 'PORT', 'DB_PASSWORD', 'DATABASE_URL', 'BOT_ADMINS'
                      , 'questions_count']
    constants = dict()
    config_vars = dict(os.environ.items()).keys()

    for key in constants_keys:
        if key in config_vars:
            if key == 'BOT_ADMINS':
                constants[key] = [int(value) for value in os.environ.get(key).split('|')]
                continue
            if key == 'questions_count':
                constants[key] = int(os.environ.get(key))
                continue
            constants[key] = os.environ.get(key)
        else:
            raise Exception('Variable ' + key + ' not exists')

    bot = telebot.TeleBot(constants['TOKEN'])
    conn = psycopg2.connect(constants['DATABASE_URL']
                            , dbname=constants['DB_NAME']
                            , user=constants['USER']
                            , password=constants['DB_PASSWORD']
                            , port=5432
                            )
    conn.autocommit = True
    cur = conn.cursor(cursor_factory=extras.NamedTupleCursor)
    admins = constants['BOT_ADMINS']
    opened = True

    # Массив ID пользователей, которые уже начали тест, но не закончили его. Чтобы не лезть в базу за проверкой
    started_users = []
    users = dbRequests.get_not_finished_users(cur)
    if users and isinstance(users, list):
        started_users = users
    # Словарь user_id, которые прошли тест. Нужно для того, чтобы каждый раз не лезть в БД за
    # ответом "Закончил-ли пользователь тест? Есть-ли у нас его телефон? А также пауза между сообщениями - 1.1 секунда"
    finished = {}
    finished = defaultdict(lambda: dict(finished=False, phone=None, msg_time=time.time() - 1.1)
                           , finished)

    # Квота на ответ бота. При достижении лимита бот пропускает сообщения и не реагирует на них. Они
    # разделены по типам и на каждый тип сообщения свой максимум ответов
    quote = {}
    quote = defaultdict(lambda: dict(ready=0, start=0, done=0, contact=0, closed=0, help=0, began=0, phone=0)
                        , quote)


def complete_test(user_id, datetime):
    global cur
    finished[user_id]['finished'] = True
    dbRequests.set_finish_time(user_id, datetime, cur)
    keyboard = telebot.types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    send_phone_button = telebot.types.KeyboardButton(text='Отправить номер телефона', request_contact=True)
    keyboard.add(send_phone_button)
    bot.send_message(chat_id=user_id
                     , text=messages['Quest_done']
                     , reply_markup=keyboard
                     , parse_mode='HTML'
                     , disable_web_page_preview=True)


def ask_question(user_id, datetime):
    global cur
    if (dbRequests.answered_question_count(user_id, cur) or 0) >= constants['questions_count']\
            and (user_id not in finished or finished[user_id]['finished'] is False):
        complete_test(user_id, datetime)
        return
    quest_text, answers = dbRequests.ask_question(user_id, cur)

    if not answers:
        return
    if not quest_text:
        return

    answers_keyboard = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True)
    for answer in answers:
        answers_keyboard.row(answer)
    bot.send_message(chat_id=user_id, text=quest_text, reply_markup=answers_keyboard)


@bot.message_handler(commands=['open', 'close'])
def open_close(message):
    global opened
    if message.from_user.id in constants['BOT_ADMINS']:
        if message.text == '/open':
            opened = True
        elif message.text == '/close':
            opened = False


@bot.message_handler(commands=['start'])
def send_hello(message):
    if not opened:
        if quote[message.from_user.id]['closed'] >= 3:
            return
        bot.send_message(chat_id=message.from_user.id, text=messages['Closed'])
        quote[message.from_user.id]['closed'] += 1
        return
    if message.date - finished[message.from_user.id]['msg_time'] < 0.7:
        finished[message.from_user.id]['msg_time'] = message.date
        return
    if message.from_user.id in started_users:
        if quote[message.from_user.id]['start'] >= 4:
            return
        bot.send_message(chat_id=message.from_user.id, text=messages['Already_started'])
        quote[message.from_user.id]['start'] += 1
        return
    if message.from_user.id in finished:
        if quote[message.from_user.id]['done'] >= 4:
            return
        bot.send_message(chat_id=message.from_user.id, text=messages['Already_done'])
        quote[message.from_user.id]['done'] += 1
    if quote[message.from_user.id]['start'] >= 4:
        return
    start_message = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    start_message.row('Готов')
    bot.send_message(
        chat_id=message.chat.id
        , text=messages['Hello']
        , reply_markup=start_message)
    finished[message.from_user.id]['msg_time'] = message.date
    quote[message.from_user.id]['start'] += 1


# Функция обрабатывает текстовые сообщения
@bot.message_handler(content_types=['text'])
def get_text_commands(message):
    if not opened:
        if quote[message.from_user.id]['closed'] >= 3:
            quote[message.from_user.id]['closed'] += 1
            return
        bot.send_message(chat_id=message.from_user.id, text=messages['Closed'])
        return
    if message.date - finished[message.from_user.id]['msg_time'] < 0.7:
        finished[message.from_user.id]['msg_time'] = message.date
        return
    if message.text == 'Готов':
        if quote[message.from_user.id]['ready'] >= 3:
            return
        if message.from_user.id not in started_users \
                or dbRequests.check_user_in_database(message.from_user.id, cur) == 'User not exists':
            started_users.append(message.from_user.id)
            dbRequests.create_user(
                message.from_user.id
                , message.from_user.username or 'hidden'
                , str(message.from_user.first_name) + ' ' + str(message.from_user.last_name)
                , message.date
                , cur
            )
            ask_question(message.from_user.id, message.date)
            return
        elif message.from_user.id in started_users:
            if quote[message.from_user.id]['start'] >= 4:
                return
            bot.send_message(chat_id=message.from_user.id, text=messages['Already_started'])
            quote[message.from_user.id]['start'] += 1
            return
        elif message.from_user.id in finished:
            if quote[message.from_user.id]['done'] >= 4:
                return
            bot.send_message(chat_id=message.from_user.id, text=messages['Already_done'])
            quote[message.from_user.id]['done'] += 1
            return
        quote[message.from_user.id]['ready'] += 1
    finished[message.from_user.id]['msg_time'] = message.date
    get_text(message)


@bot.message_handler(content_types=['contact'])
def update_phone(message):
    if not opened:
        if quote[message.from_user.id]['closed'] >= 2:
            return
        bot.send_message(chat_id=message.from_user.id, text=messages['Closed'])
        quote[message.from_user.id]['closed'] += 1
        return
    if quote[message.from_user.id]['contact'] >= 3:
        return
    if message.from_user.id != message.contact.user_id or not message.contact.user_id:
        return
    if message.from_user.id not in started_users \
            or dbRequests.check_user_in_database(message.from_user.id, cur) == 'User not exists':
        return
    finished[message.from_user.id]['phone'] = message.contact.phone_number
    dbRequests.update_phone(message.from_user.id, message.contact.phone_number, cur)
    quote[message.from_user.id]['contact'] += 1


def get_text(message):
    if not opened:
        return
    if message.from_user.id not in started_users \
            or dbRequests.check_user_in_database(message.from_user.id, cur) == 'User not exists':
        return
    if message.from_user.id in finished and finished[message.from_user.id]['finished']:
        return

    res = dbRequests.answer_validation(message.text, message.from_user.id, cur)
    if res == 'Failed':
        return
    ask_question(message.from_user.id, message.date)


bot.polling(none_stop=True)
