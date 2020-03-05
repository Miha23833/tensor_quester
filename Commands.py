from dbRequests import valid_table


def get_results(cur):
    cur.execute(
        """
        SELECT
            ARRAY_LENGTH(true_answers, 1) as true_answers_count,
            username,
            fullname,
            finish_time - start_time as spent_time,
            finish_rime,
            start_time,
            phone
        FROM
        users
        WHERE FINISH_TIME NOTNULL
        ORDER BY true_answers_count DESC, spent_time        
        """)
    if not valid_table([], cur.description):
        return None
    else:
        answ_str = """================================
Имя: {0}:
Правильных ответов: <b>{1}</b>
Затраченное время: <b>{2}</b>
Телефон: <b>{3}</b>
Имя пользователя: {4}\n"""
        result = ''
        record = cur.fetchall()
        if not record:
            return None
        for i in record:
            result = result + (answ_str.format(i.fullname
                               , i.true_answers_count
                               , i.spent_time
                               , i.phone
                               , i.username))
        return result


def my_results(time_zone, user_id, cur):
    cur.execute(
        """
        SET LOCAL TIMEZONE = %s;
        SELECT 
            ARRAY_LENGTH(true_answers, 1) as true_answers_count,
            to_char(FINISH_TIME - START_TIME, 'HH24:MI:SS') as spent_time,
            to_char(FINISH_TIME, 'DD/MM/YYYY HH24:MI:SS') as finish_time, 
            to_char(START_TIME, 'DD/MM/YYYY HH24:MI:SS') as start_time 
        FROM users
        WHERE userid = %s
        AND finish_time NOTNULL
        """, [time_zone, user_id]
    )
    if not valid_table(['true_answers_count', 'start_time', 'finish_time', 'spent_time'], cur.description):
        return None
    else:
        results = cur.fetchone()
        if not results:
            return None
        return """Вы ответили правильно на {0} вопросов.
Время начала теста: {1}
Время завершения теста: {2}
Затраченное время: {3}""".format(results.true_answers_count
                                 , results.start_time
                                 , results.finish_time
                                 , results.spent_time)
