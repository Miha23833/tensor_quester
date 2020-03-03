import psycopg2
from dbRequests import valid_table
import os
import psycopg2.extras as extras


def get_results(cur):
    cur.execute(
        """
        SELECT
            ARRAY_LENGTH(true_answers, 1) as true_answers_count,
            USERNAME,
            FULLNAME,
            FINISH_TIME - START_TIME as spent_time,
            FINISH_TIME,
            START_TIME,
            phone
        FROM
        users
        ORDER BY true_answers_count, spent_time        
        """)
    if not valid_table([], cur.description):
        return None
    else:
        answ_str = """================================
{0}:
Правильных ответов: {1}
Затраченное время: {2}
Телефон: {3}
Имя пользователя: {4}\n"""
        result = ''
        for i in cur.fetchall():
            result = result + (answ_str.format(i.fullname
                               , i.true_answers_count
                               , i.spent_time
                               , i.phone
                               , i.username))
        return result


def my_results(user_id, cur):
    cur.execute(
        """
        SELECT 
            ARRAY_LENGTH(true_answers, 1) as true_answers_count,
            FINISH_TIME - START_TIME as spent_time,
            FINISH_TIME,
            START_TIME
        FROM USERS U
        WHERE userid = %s
        """, [user_id]
    )
    if not valid_table(['true_answers_count', 'start_time', 'finish_time', 'spent_time'], cur.description):
        return None
    else:
        results = cur.fetchone()
        return """Вы ответили правильно на {0} вопросов.
Время начала теста: {1}
Время завершения теста: {2}
Затраченное время: {3}""".format(results.true_answers_count
                                 , results.start_time
                                 , results.finish_time
                                 , results.spent_time)

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

conn = psycopg2.connect(constants['DATABASE_URL']
                        , dbname=constants['DB_NAME']
                        , user='wwmifahmadbqbn'
                        , password=constants['DB_PASSWORD']
                        , port=5432
                        )
conn.autocommit = True
cur = conn.cursor(cursor_factory=extras.NamedTupleCursor)
print(my_results(539249298, cur))
