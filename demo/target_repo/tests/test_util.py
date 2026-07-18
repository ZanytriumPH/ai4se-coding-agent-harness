from src.app import add, unused_helper


def test_add_integers():
    assert add(2, 3) == 5


def test_add_returns_int():
    assert isinstance(add(1, 1), int)


def test_unused_helper_returns_one():
    assert unused_helper() == 1