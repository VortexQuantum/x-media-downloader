import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock
from src.downloader import download_media, ensure_dir, filename_from_url


class FakeResponse:
    def __init__(self, status=200, content=b"data", ct="image/jpeg", url="http://x.jpg"):
        self.status_code = status
        self.content = content
        self.headers = {"Content-Type": ct}
        self.url = url
        self.raw = None

    def raise_for_status(self):
        if self.status_code >= 400:
            raise __import__("requests").exceptions.HTTPError()


class FakeSession:
    def __init__(self, resp):
        self._resp = resp

    def get(self, *a, **kw):
        return self._resp

    def close(self):
        pass


def test_ensure_dir_creates():
    with tempfile.TemporaryDirectory() as tmp:
        ensure_dir(os.path.join(tmp, "images"))
        assert os.path.isdir(os.path.join(tmp, "images"))


def test_filename_unique_per_url():
    n1 = filename_from_url("https://pbs.twimg.com/media/A?format=jpg", "t1", "image")
    n2 = filename_from_url("https://pbs.twimg.com/media/B?format=jpg", "t1", "image")
    assert n1 != n2
    assert n1.endswith(".jpg")


def test_filename_from_query_format():
    name = filename_from_url("https://pbs.twimg.com/media/ABC?format=jpg", "t1", "image")
    assert name.endswith(".jpg")


@patch("src.downloader.requests.Session")
def test_download_success(mock_session, tmp_path):
    mock_session.return_value = FakeSession(FakeResponse())
    path = download_media("http://x.jpg", str(tmp_path), "t1", "image")
    assert path is not None
    assert os.path.exists(path)


@patch("src.downloader.requests.Session")
def test_download_skip_existing(mock_session, tmp_path):
    mock_session.return_value = FakeSession(FakeResponse())
    p1 = download_media("http://x.jpg", str(tmp_path), "t1", "image")
    p2 = download_media("http://x.jpg", str(tmp_path), "t1", "image")
    assert p1 == p2
    # File exists: second call should skip, first returned path matches


@patch("src.downloader.requests.Session")
@patch("src.downloader.time.sleep")
def test_retry_then_skip(mock_sleep, mock_session, tmp_path):
    """重试2次后跳过"""
    bad_sess = FakeSession(FakeResponse(status=503))
    mock_session.return_value = bad_sess
    path = download_media("http://x.jpg", str(tmp_path), "t1", "image", retries=2)
    assert path is None


@patch("src.downloader.requests.Session")
@patch("src.downloader.time.sleep")
def test_retry_then_succeed(mock_sleep, mock_session, tmp_path):
    """前2次失败, 第3次成功"""
    calls = []

    class Sess:
        def __init__(self):
            self.call = 0
        def get(self, *a, **kw):
            self.call += 1
            if self.call < 3:
                raise __import__("requests").exceptions.Timeout("timeout")
            return FakeResponse(content=b"ok")
        def close(self):
            pass

    mock_session.return_value = Sess()
    path = download_media("http://x.jpg", str(tmp_path), "t1", "image", retries=2)
    assert path is not None
    assert os.path.exists(path)
