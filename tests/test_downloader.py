import os
import tempfile
import pytest
from unittest.mock import patch
from src.downloader import download_media, ensure_dir, filename_from_url


def test_ensure_dir_creates():
    with tempfile.TemporaryDirectory() as tmp:
        new_dir = os.path.join(tmp, "images")
        ensure_dir(new_dir)
        assert os.path.isdir(new_dir)


def test_filename_unique_per_url():
    """同一 tweet 的多张图有不同文件名"""
    name1 = filename_from_url(
        "https://pbs.twimg.com/media/ABC?format=jpg&name=orig",
        "tweet_456", "image"
    )
    name2 = filename_from_url(
        "https://pbs.twimg.com/media/DEF?format=jpg&name=orig",
        "tweet_456", "image"
    )
    assert name1 != name2
    assert name1.startswith("tweet_456")
    assert name2.startswith("tweet_456")
    assert name1.endswith(".jpg")
    assert name2.endswith(".jpg")


def test_filename_from_query_format():
    """Twitter URL format=jpg 也能提取扩展名"""
    name = filename_from_url(
        "https://pbs.twimg.com/media/ABC123?format=jpg&name=orig",
        "tweet_456", "image"
    )
    assert name.endswith(".jpg")


def test_filename_path_extension():
    """标准 URL 路径提取扩展名"""
    name = filename_from_url(
        "https://example.com/video.mp4?tag=1",
        "tweet_1", "video"
    )
    assert name.endswith(".mp4")


def test_filename_fallback():
    """无扩展名时用 media_type 兜底"""
    name = filename_from_url(
        "https://cdn.example.com/resource/abc",
        "tweet_1", "image"
    )
    assert name.endswith(".jpg")


@patch("src.downloader.requests.get")
def test_download_image(mock_get, tmp_path):
    mock_get.return_value.status_code = 200
    mock_get.return_value.content = b"fake-data"
    mock_get.return_value.headers = {"Content-Type": "image/jpeg"}

    path = download_media(
        "https://example.com/photo.jpg",
        str(tmp_path), "tweet_1", "image"
    )
    assert os.path.exists(path)


@patch("src.downloader.requests.get")
def test_download_skip_existing(mock_get, tmp_path):
    path = download_media(
        "https://example.com/photo.jpg",
        str(tmp_path), "tweet_1", "image"
    )
    path2 = download_media(
        "https://example.com/photo.jpg",
        str(tmp_path), "tweet_1", "image"
    )
    assert path == path2
    assert mock_get.call_count == 1


@patch("src.downloader.requests.get")
def test_download_retry_on_timeout(mock_get, tmp_path):
    """超时自动重试"""
    mock_get.side_effect = [
        __import__("requests").exceptions.Timeout(),
        type("FakeResp", (), {
            "status_code": 200,
            "content": b"ok",
            "headers": {"Content-Type": "image/jpeg"},
            "raise_for_status": lambda self: None,
            "iter_content": lambda self, **kw: [b"ok"],
        })(),
    ]

    path = download_media(
        "https://example.com/retry.jpg",
        str(tmp_path), "tweet_1", "image", retries=2
    )
    assert os.path.exists(path)
    assert mock_get.call_count == 2
