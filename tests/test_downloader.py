import os
import tempfile
import pytest
from unittest.mock import patch
from src.downloader import download_media, ensure_dir


def test_ensure_dir_creates():
    with tempfile.TemporaryDirectory() as tmp:
        new_dir = os.path.join(tmp, "images")
        ensure_dir(new_dir)
        assert os.path.isdir(new_dir)


def test_filename_from_url():
    from src.downloader import filename_from_url
    name = filename_from_url(
        "https://pbs.twimg.com/media/ABC123.jpg?format=jpg&name=large",
        "tweet_456", "image"
    )
    assert "tweet_456" in name
    assert name.endswith(".jpg")


@patch("src.downloader.requests.get")
def test_download_image(mock_get, tmp_path):
    mock_get.return_value.status_code = 200
    mock_get.return_value.content = b"fake-image-data"
    mock_get.return_value.headers = {"Content-Type": "image/jpeg"}

    path = download_media(
        "https://example.com/photo.jpg",
        str(tmp_path), "tweet_1", "photo"
    )
    assert os.path.exists(path)
    assert path.endswith(".jpg")


@patch("src.downloader.requests.get")
def test_download_skip_existing(mock_get, tmp_path):
    path = download_media(
        "https://example.com/photo.jpg",
        str(tmp_path), "tweet_1", "photo"
    )
    path2 = download_media(
        "https://example.com/photo.jpg",
        str(tmp_path), "tweet_1", "photo"
    )
    assert path == path2
    assert mock_get.call_count == 1
