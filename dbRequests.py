import psycopg2
import random


def create_user(user_id: int, username: str, name: str, start: int, cur):
    cur.execute(
        """
        INSERT INTO "Users"(
        "UserID"
        , "UserName"
        , "Name"
        , "StartTime"
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
        SELECT * FROM "Questions" q 
        WHERE "QuestID"::text NOT IN (
            SELECT 
                JSONB_OBJECT_KEYS("Questions"::jsonb)
            FROM 
                "Users" u 
            WHERE u."UserID" = 539249298
            )
        """
    )
    try:
        print(cur.fetchall())