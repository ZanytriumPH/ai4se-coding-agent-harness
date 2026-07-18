from src.app import login


def test_login_returns_200_for_valid():
    assert login("user", "pass") == 200


def test_login_returns_401_for_invalid():
    assert login("user", "wrong") == 401