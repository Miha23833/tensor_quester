from collections import defaultdict
import Commands
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
                      , 'questions_count', 'user_info_answered_count', 'TIME_ZONE']
    constants = dict()
    config_vars = dict(os.environ.items()).keys()

    for key in constants_keys:
        if key in config_vars:
            if key == 'BOT_ADMINS':
                constants[key] = [int(value) for value in os.environ.get(key).split('|')]
                continue
            if key == 'questions_count' or key == 'user_info_answered_count':
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

    # Массив ID пользователей, которые уже начали тест. Чтобы не лезть в базу за проверкой
    started_users = []
    users = dbRequests.get_not_finished_users(cur)
    if users and isinstance(users, list):
        started_users = users
    # Словарь user_id, которые прошли тест. Нужно для того, чтобы каждый раз не лезть в БД за
    # ответом "Закончил-ли пользователь тест? Есть-ли у нас его телефон? А также пауза между сообщениями - 1.1 секунда"
    finished = {}
    finished = defaultdict(lambda: dict(finished=False
                                        , phone=None
                                        , msg_time=time.time() - 1.1
                                        , command_time=time.time() - 10
                                        , user_info_answered_count=1)
                           , finished)

    # Квота на ответ бота. При достижении лимита бот пропускает сообщения и не реагирует на них. Они
    # разделены по типам и на каждый тип сообщения свой максимум ответов
    quote = {}
    quote = defaultdict(lambda: dict(ready=0
                                     , start=0
                                     , done=0
                                     , contact=0
                                     , closed=0
                                     , help=0
                                     , began=0
                                     , phone=0
                                     , wrong_contact=0
                                     , finished=0
                                     , ask_to_give_user_info=0
                                     , is_ready_to_give_user_info=False)
                        , quote)


def ask_user_info(user_id):
    text = dbRequests.get_user_info_question(user_id, cur)
    if not text or text == 'Failed':
        return
    if text == 'Done':
        start_message = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
        start_message.row('Готов')
        bot.send_message(
            chat_id=user_id
            , text=messages['Hello']
            , reply_markup=start_message)
        quote[user_id]['ready'] += 1
        return 'Done'
    rm_keyboard = telebot.types.ReplyKeyboardRemove()
    bot.send_message(chat_id=user_id, text=text, reply_markup=rm_keyboard)


def complete_test(user_id, datetime):
    global cur
    finished[user_id]['finished'] = True
    dbRequests.set_finish_time(user_id, datetime, cur)
    keyboard = telebot.types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    send_phone_button = telebot.types.KeyboardButton(text='Отправить номер телефона', request_contact=True)
    keyboard.add(send_phone_button)
    bot.send_message(chat_id=user_id, text=messages['Quest_done'])
    bot.send_message(chat_id=user_id
                     , text=messages['Ask_for_phone']
                     , reply_markup=keyboard
                     , parse_mode='HTML'
                     , disable_web_page_preview=True)


def ask_question(user_id, datetime):
    global cur
    if (dbRequests.answered_question_count(user_id, cur) or 0) >= constants['questions_count'] \
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


@bot.message_handler(commands=['results'])
def show_results(message):
    if message.from_user.id not in constants['BOT_ADMINS']:
        return
    response_text = Commands.get_results(cur)
    if not response_text:
        return
    if len(response_text) > 4096:
        for x in range(0, len(response_text), 4096):
            bot.send_message(chat_id=message.from_user.id, text=response_text[x:x + 4096], parse_mode='HTML')
    else:
        bot.send_message(chat_id=message.from_user.id, text=response_text, parse_mode='HTML')


@bot.message_handler(commands=['myresult'])
def get_my_result(message):
    if not opened:
        if quote[message.from_user.id]['closed'] >= 3:
            return
        bot.send_message(chat_id=message.from_user.id, text=messages['Closed'])
        quote[message.from_user.id]['closed'] += 1
        return
    if message.date - finished[message.from_user.id]['command_time'] < 10:
        return
    text = Commands.my_results(constants['TIME_ZONE'], message.from_user.id, cur)
    if not text:
        finished[message.from_user.id]['command_time'] = message.date
        return
    bot.send_message(chat_id=message.from_user.id, text=text
                     , parse_mode='HTML')
    finished[message.from_user.id]['command_time'] = message.date


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
    if finished[message.from_user.id]['user_info_answered_count'] < constants['user_info_answered_count']:
        if quote[message.from_user.id]['is_ready_to_give_user_info']\
                or quote[message.from_user.id]['ask_to_give_user_info'] > 2:
            return
        start_message = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
        start_message.row('Готов отвечать')
        bot.send_message(
            chat_id=message.chat.id
            , text=messages['Ask_For_User_Info']
            , reply_markup=start_message)
        quote[message.from_user.id]['ask_to_give_user_info'] += 1
        return
    if finished[message.from_user.id]['finished']:
        if quote[message.from_user.id]['finished'] >= 4:
            return
        bot.send_message(chat_id=message.from_user.id, text=messages['Already_finished'])
        quote[message.from_user.id]['finished'] += 1
        return
    if message.from_user.id in started_users:
        if quote[message.from_user.id]['start'] >= 4:
            return
        bot.send_message(chat_id=message.from_user.id, text=messages['Already_started'])
        quote[message.from_user.id]['start'] += 1
        return
    if message.from_user.id in finished[message.from_user.id] \
            and message.date - finished[message.from_user.id]['msg_time'] < 1:
        finished[message.from_user.id]['msg_time'] = message.date
        return
    if message.from_user.id in finished and finished[message.from_user.id]['finished']:
        if quote[message.from_user.id]['done'] >= 4:
            return
        bot.send_message(chat_id=message.from_user.id, text=messages['Already_done'])
        quote[message.from_user.id]['done'] += 1
        return
    if quote[message.from_user.id]['start'] >= 4:
        return
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
    if message.date - finished[message.from_user.id]['msg_time'] < 1:
        finished[message.from_user.id]['msg_time'] = message.date
        return
    if message.text == 'Готов отвечать' and not quote[message.from_user.id]['is_ready_to_give_user_info']:
        dbRequests.create_user(
            message.from_user.id
            , message.from_user.username or 'hidden'
            , str(message.from_user.first_name) + ' ' + (
             message.from_user.last_name if message.from_user.last_name is not None else '[Фамилия отсутствует]')
            , message.date
            , cur
        )
        quote[message.from_user.id]['is_ready_to_give_user_info'] = True
        ask_user_info(message.from_user.id)
        finished[message.from_user.id]['msg_time'] = message.date
        return
    elif message.text == 'Готов отвечать' and quote[message.from_user.id]['is_ready_to_give_user_info']:
        return
    if not quote[message.from_user.id]['is_ready_to_give_user_info']:
        return
    if finished[message.from_user.id]['user_info_answered_count'] <= constants['user_info_answered_count']:
        responce = dbRequests.update_user_info(message.from_user.id
                                               , finished[message.from_user.id]['user_info_answered_count']
                                               , message.text
                                               , cur)
        if responce == 'Success':
            finished[message.from_user.id]['user_info_answered_count'] += 1
            answer = ask_user_info(message.from_user.id)
            finished[message.from_user.id]['msg_time'] = message.date
            return
    if message.text == 'Готов':
        if quote[message.from_user.id]['ready'] >= 3:
            return
        if finished[message.from_user.id]['finished']:
            if quote[message.from_user.id]['finished'] >= 4:
                return
            bot.send_message(chat_id=message.from_user.id, text=messages['Already_finished'])
            quote[message.from_user.id]['finished'] += 1
            return
        if message.from_user.id not in started_users \
                or dbRequests.check_user_in_database(message.from_user.id, cur) == 'User not exists':
            started_users.append(message.from_user.id)
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
    if not finished[message.from_user.id]['finished']:
        return
    if quote[message.from_user.id]['contact'] >= 3:
        return
    if message.from_user.id != message.contact.user_id:
        if quote[message.from_user.id]['wrong_contact'] >= 5:
            return
        bot.send_message(chat_id=message.from_user.id, text=messages['Wrong_contact'])
        quote[message.from_user.id]['wrong_contact'] += 1
        return
    if message.from_user.id not in started_users \
            or dbRequests.check_user_in_database(message.from_user.id, cur) == 'User not exists':
        return
    finished[message.from_user.id]['phone'] = message.contact.phone_number
    dbRequests.update_phone(message.from_user.id, message.contact.phone_number, cur)
    no_kb = telebot.types.ReplyKeyboardRemove()
    bot.send_message(chat_id=message.from_user.id, text=messages['InviteLink'], parse_mode='HTML',
                     reply_markup=no_kb)
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


print('Bot started')
bot.polling(none_stop=True)
