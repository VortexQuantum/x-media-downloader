import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock
from src.downloader import download_media, ensure_dir, filename_from_url


class FakeResponse:
    def __init__(self, status=200, content=b"data", ct="image/jpeg"):
        self.status_code = status
        self.content = content
        self.headers = {"Content-Type": ct}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise __import__("requests").exceptions.HTTPError()

    def iter_content(self, chunk_size=8192):
        yield self.content


def test_ensure_dir_creates():
    with tempfile.TemporaryDirectory() as tmp:
        ensure_dir(os.path.join(tmp, "images"))
        assert os.path.isdir(os.path.join(tmp, "images"))


def test_filename_unique_per_url():
    name1 = filename_from_url("https://pbs.twimg.com/media/ABC?format=jpg&name=orig",
                               "tweet_456", "image")
    name2 = filename_from_url("https://pbs.twimg.com/media/DEF?format=jpg&name=orig",
                               "tweet_456", "image")
    assert name1 != name2
    assert name1.endswith(".jpg")
    assert name2.endswith(".jpg")


def test_filename_from_query_format():
    name = filename_from_url("https://pbs.twimg.com/media/ABC123?format=jpg&name=orig",
                             "tweet_456", "image")
    assert name.endswith(".jpg")


@patch("src.downloader.requests.get")
def test_download_success(mock_get, tmp_path):
    mock_get.return_value = FakeResponse()
    path = download_media("https://example.com/p.jpg", str(tmp_path), "t1", "image")
    assert path is not None
    assert os.path.exists(path)


@patch("src.downloader.requests.get")
def test_download_skip_existing(mock_get, tmp_path):
    mock_get.return_value = FakeResponse()
    path1 = download_media("https://example.com/p.jpg", str(tmp_path), "t1", "image")
    path2 = download_media("https://example.com/p.jpg", str(tmp_path), "t1", "image")
    assert path1 == path2
    assert mock_get.call_count == 1


@patch("src.downloader.requests.get")
@patch("src.downloader.time.sleep")
def test_download_retry_then_skip(mock_sleep, mock_get, tmp_path):
    """重试2次失败后返回 None（跳过），不抛异常"""
    mock_get.side_effect = __import__("requests").exceptions.Timeout()
    path = download_media("https://example.com/fail.jpg", str(tmp_path), "t1", "image", retries=2)
    assert path is None
    assert mock_get.call_count == 3  # 1 initial + 2 retries


@patch("src.downloader.requests.get")
@patch("src.downloader.time.sleep")
def test_download_retry_then_succeed(mock_sleep, mock_get, tmp_path):
    """第2次重试成功"""
    mock_get.side_effect = [
        __import__("requests").exceptions.Timeout(),
        __import__("requests").exceptions.Timeout(),
        FakeResponse(),
    ]
    path = download_media("https://example.com/ok.jpg", str(tmp_path), "t1", "image", retries=2)
    assert path is not None
    assert mock_get.call_count == 3  # initial + 2 failures = 3 total (succeeds on 3rd)
