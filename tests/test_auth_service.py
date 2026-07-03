from services.auth_service import AuthService


def test_normalize_email():
    assert AuthService.normalize_email("  Test@Mail.COM ") == "test@mail.com"


def test_valid_email():
    assert AuthService.is_valid_email("user@example.com") is True
    assert AuthService.is_valid_email("not-an-email") is False
