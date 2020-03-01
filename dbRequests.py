import psycopg2
import logging
import random


def valid_table(columns, description):
    if not description:
        return None
    description = [desc[0] for desc in description]
    if set(columns).issubset(description):
        return True
    else:
        return False


def create_user(user_id: int, username: str, name: str, start: int, cur):
    cur.execute(
        """
        INSERT INTO "users"(
        "userid"
        , "username"
        , "fullname"
        , "start_time"
        )
        VALUES (
        %s
        , %s
        , %s
        , to_timestamp(%s)
        )
        ON CONFLICT DO NOTHING
        """,
        [
            user_id
            , username
            , name
            , start
        ]
    )


def ask_question(user_id, cur):
    cur.execute(
        """        
        SELECT 
            "QuestID"
            , "Text"
            , "Answer" || "FalseAnswers" as "Answers"
        FROM "Questions"
        WHERE "QuestID" not in 
            (
                SELECT UNNEST ("true_answers" || "false_answers")
                FROM "users"
                WHERE "userid" = %s
                UNION 
                SELECT current_quest
                FROM "users"
                WHERE CURRENT_QUEST NOTNULL
            )
        """
        , [user_id]
    )
    if not valid_table(['QuestID', 'Text', 'Answers'], cur.description):
        return 'Failed', None
    question = random.choice(list(cur))

    cur.execute(
        """
        UPDATE "users"
        SET "current_quest" = %s
        WHERE "userid" = %s
        """
        , [question.QuestID, user_id]
    )
    random.shuffle(question.Answers)
    return question.Text, question.Answers


def check_user_in_database(user_id, cur):
    cur.execute(
        """
        SELECT 
          CASE WHEN "userid" = %s
            THEN 'User exists'
          ELSE 'User not exists' end as "Check"
        FROM "users"
        """
        , [user_id]
    )
    if not valid_table(['Check'], cur.description):
        return 'Failed'
    return


def answer_validation(text, user_id, cur):
    cur.execute(
        """
        SELECT 
          CASE 
            WHEN lower("Answer") = lower(%s::text)
              THEN 'Right'
            ELSE 'Wrong' 
          END as "Result"
          , "QuestID"
        FROM "users" u
        LEFT JOIN "Questions" q
          ON ( q."QuestID" = u."current_quest" )
        WHERE
          u."userid" = %s
        """,
        [text, user_id]
    )
    if not valid_table(['Result', 'QuestID'], cur.description):
        return 'Failed'
    try:
        row = cur.fetchone()
    except psycopg2.ProgrammingError as err:
        print('slovil')
        return
    if not row:
        print('Failed on get row.Result!')
        return 'Failed'
    if row.Result == 'Right':
        cur.execute(
            """
            UPDATE "users"
            SET "true_answers" = "true_answers" || %s::bigint
            WHERE "userid" = %s
            AND %s <> all (true_answers)
            OR "true_answers" ISNULL
            RETURNING 'Success' as "Result"
            """
            , [row.QuestID, user_id, row.QuestID]
        )
        if not valid_table(['Result'], cur.description):
            return 'Failed'
        else:
            return 'Success'
    elif row.Result == 'Wrong':
        cur.execute(
            """
            UPDATE "users"
            SET "false_answers" = "false_answers" || %s::bigint
            WHERE "userid" = %s
            AND %s <> all (false_answers)
            OR "false_answers" ISNULL
            RETURNING 'Success' as "Result"
            """
            , [row.QuestID, user_id, row.QuestID]
        )
        if not valid_table(['Result'], cur.description):
            return 'Failed'
        else:
            return 'Success'
    else:
        return 'Failed'


def get_not_finished_users(cur):
    cur.execute(
        """
        Select array_agg("userid") as "Users"
        FROM "users"
        """
    )
    if not valid_table(['Users'], cur.description):
        return 'Failed'
    return cur.fetchone().Users


def answered_question_count(user_id, cur):
    cur.execute(
        """
        SELECT 
        CASE
            WHEN array_length("true_answers" || "false_answers", 1) NOTNULL
            THEN array_length("true_answers" || "false_answers", 1)
            ELSE 0 END as "Count"
        FROM "users"
        WHERE "userid" = %s        
        """,
        [user_id]
    )
    if not valid_table(["Count"], cur.description):
        return None
    return cur.fetchone().Count


def set_finish_time(user_id, time, cur):
    cur.execute(
        """
        UPDATE users
        SET finish_time = to_timestamp(%s)
        WHERE "userid" = %s
        """,
        [time, user_id]
    )
