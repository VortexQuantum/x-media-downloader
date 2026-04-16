import pytest
from unittest.mock import patch
from src.notifier import TelegramNotifier


@pytest.fixture
def notifier():
    return TelegramNotifier(bot_token="test-token", chat_id="123")


@patch("src.notifier.requests.post")
def test_send_text(mock_post, notifier):
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {"ok": True}
    assert notifier.send_text("你好") is True
    mock_post.assert_called_once()


@patch("src.notifier.requests.post")
def test_send_download_report(mock_post, notifier):
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {"ok": True}

    result = notifier.send_download_report(
        new_count=5, total_count=120, failed_count=2,
        details=["tweet_1: image", "tweet_2: video"]
    )
    assert result is True
    call_text = mock_post.call_args[1]["json"]["text"]
    assert "5" in call_text
    assert "120" in call_text
    assert "2" in call_text  # failed count


@patch("src.notifier.requests.post")
def test_send_text_failure(mock_post, notifier):
    mock_post.return_value.status_code = 400
    mock_post.return_value.json.return_value = {"ok": False}
    assert notifier.send_text("test") is False
