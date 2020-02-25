from collections import defaultdict
import dbRequests
import psycopg2
import psycopg2.extras as extras
import telebot
import json
import time

if __name__ == '__main__':
    with open('const.json', 'r') as file:
        constants = json.load(file)

    bot = telebot.TeleBot(constants['token'])
    conn = psycopg2.connect(dbname=constants['dbname']
                            , user=constants['user']
                            , password=constants['password']
                            , port=constants['port']
                            , host=constants['host'])
    conn.autocommit = True
    cur = conn.cursor(cursor_factory=extras.NamedTupleCursor)
    admins = constants['admins']
    opened = True

    # Массив ID пользователей, которые уже начали тест, но не закончили его. Чтобы не лезть в базу за проверкой
    started_users = []
    # Словарь user_id, которые прошли тест. Нужно для того, чтобы каждый раз не лезть в БД за
    # ответом "Закончил-ли пользователь тест? Есть-ли у нас его телефон? А также пауза между сообщениями - 1.1 секунда"
    finished = {}
    finished = defaultdict(lambda: {
                           'finished': False
                           , 'phone': None
                           , 'msg_time': time.time() - 1.1
                           }
                           , finished)

    quote = {}
    quote = defaultdict(lambda: {
                                 'start': 0
                                 , 'finish': 0
                                 , 'contact': 0
                                 , 'closed': 0
                                 , 'help': 0
                                 , 'began': 0
                                 , 'phone': 0}
                        , quote)
    dbRequests.answer_validation('1', 539249298, cur)


def ask_question(user_id):
    global cur
    quest_text, answers = dbRequests.ask_question(user_id, cur) or [None, None]
    print(quest_text, '\n', answers)

    if not quest_text and not answers:
        return

    answers_keyboard = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True)
    for answer in answers:
        answers_keyboard.row(answer)
    bot.send_message(chat_id=user_id, text=quest_text, reply_markup=answers_keyboard)


@bot.message_handler(commands=['open', 'close'])
def open_close(message):
    global opened
    if message.from_user.id in constants['admins']:
        if message.text == '/open':
            opened = True
        elif message.text == '/close':
            opened = False


@bot.message_handler(commands=['start'])
def send_hello(message):
    if not opened:
        return
    start_message = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    start_message.row('Готов')
    bot.send_message(
        chat_id=message.chat.id
        # Заменить
        , text='Приветственное сообщение. Нажми Готов, чтобы быть в базе'
        , reply_markup=start_message)


# Функция пропускает только ключевые слова
@bot.message_handler(content_types=['text'])
def get_text_commands(message):
    if not opened:
        return
    if message.text == 'Готов' \
            and message.from_user.id not in started_users\
            or dbRequests.check_user_in_database(message.from_user.id, cur) == 'User not exists':
        started_users.append(message.from_user.id)
        dbRequests.create_user(
            message.from_user.id
            , message.from_user.username or 'hidden'
            , str(message.from_user.first_name) + ' ' + str(message.from_user.last_name)
            , message.date
            , cur
        )
        ask_question(message.from_user.id)


@bot.message_handler(content_types=['text'])
def get_text(message):
    if not opened:
        return
    if message.from_user.id not in started_users:
        return
    if message.from_user.id in finished and finished[message.from_user.id]['finished']:
        return


bot.polling(none_stop=True)
