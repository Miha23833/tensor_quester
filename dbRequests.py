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
                SELECT UNNEST (answered)
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
