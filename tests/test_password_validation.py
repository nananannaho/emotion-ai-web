from utils.password_validation import validate_password


def test_password_too_short():
    assert validate_password("Ab1!") is not None


def test_password_forbidden_chars():
    assert validate_password('Abcdef1*') is not None
    assert validate_password('Abcdef1&') is not None
    assert validate_password('Abcdef1"') is not None


def test_password_needs_special():
    assert validate_password("Abcdefgh1") is not None


def test_password_valid():
    assert validate_password("Abcdefg1!") is None
