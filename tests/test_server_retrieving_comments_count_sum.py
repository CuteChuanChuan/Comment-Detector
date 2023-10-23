import os
from loguru import logger
from dotenv import load_dotenv
from tests.config import redis_conn
from src.server.utils_dashboard.utils_mongodb import retrieve_comments_count_sum

load_dotenv(verbose=True)


def test_redis_connection_localhost():
    assert os.getenv("REDIS_HOST") == "localhost"
    assert os.getenv("REDIS_DB") == "1"
    redis_conn.set("test", "test")
    assert redis_conn.get("test").decode("utf-8") == "test"
    redis_conn.delete("test")


def test_retrieve_articles_count_sun():
    redis_conn.delete("total_comments")
    redis_conn.set("total_comments", 2000)
    comments_counts = retrieve_comments_count_sum()
    assert redis_conn.exists("total_comments")
    assert comments_counts == 2000
    redis_conn.delete("total_comments")
