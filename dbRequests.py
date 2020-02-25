import psycopg2
import random


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
    if not cur.description:
        return
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
          ELSE 'User not exists' end 
        FROM "users"
        """
        , [user_id]
    )
    if not cur.description:
        return None
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
    if not cur.description:
        return 'Failed'
    row = cur.fetchone()
    if row.Result == 'Right':
        cur.execute(
            """
            UPDATE "users"
            SET "true_answers" = "true_answers" || %s::bigint
            WHERE "userid" = %s
            RETURNING 'Success' as "Result"
            """
            , [row.QuestID, user_id]
        )
        if not cur.description:
            return 'Failed'
        else:
            return 'Success'
    elif row.Result == 'Wrong':
        cur.execute(
            """
            UPDATE "users"
            SET "false_answers" = "false_answers" || %s::bigint
            WHERE "userid" = %s
            RETURNING 'Success' as "Result"
            """
            , [row.QuestID, user_id]
        )
        if not cur.description:
            return 'Failed'
        else:
            return 'Success'


def get_not_finished_users(cur):
    cur.execute(
        """
        Select array_agg("userid") as "Users"
        FROM "users"
        """
    )
    if not cur.description:
        return 'Failed'
    return cur.fetchone().Users
