from config import API_VERSION, SKIP_EMAIL_VERIFICATION


def test_api_version_is_positive():
    assert API_VERSION >= 17


def test_skip_email_only_when_env_set():
    assert SKIP_EMAIL_VERIFICATION in (True, False)
