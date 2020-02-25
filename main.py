from collections import defaultdict
import dbRequests
import psycopg2
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
    cur = conn.cursor()
    opened = False
    admins = constants['admins']

    # Массив user_id, которые прошли тест. Нужно для того, чтобы каждый раз не лезть в БД за
    # ответом "Закончил-ли пользователь тест?"
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


def ask_question(user_id):
    global cur
    dbRequests.ask_question(user_id, cur)



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


@bot.message_handler(content_types=['text'])
def get_text(message):
    if not opened:
        return
    if message.text == 'Готов':
        dbRequests.create_user(
            message.from_user.id
            , message.from_user.username or 'hidden'
            , str(message.from_user.first_name) + ' ' + str(message.from_user.last_name)
            , message.date
            , cur
        )
        ask_question(message.from_user.id)
        return
    if message.from_user.id in finished and finished[message.from_user.id]['finished']:
        return


bot.polling(none_stop=True)
