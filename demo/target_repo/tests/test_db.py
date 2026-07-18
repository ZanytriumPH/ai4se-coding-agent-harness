from src.app import connect_db


def test_connect_db_returns_connection():
    assert connect_db("dsn") is not None