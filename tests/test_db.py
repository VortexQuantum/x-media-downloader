import os
import tempfile
import pytest
from src.db import DownloadDB


@pytest.fixture
def db():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db = DownloadDB(tmp.name)
    yield db
    db.close()
    os.unlink(tmp.name)


def test_init_creates_tables(db):
    rows = db.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    names = {r[0] for r in rows}
    assert "downloads" in names
    assert "fetch_state" in names


def test_is_downloaded_false(db):
    assert db.is_downloaded("tweet_999", "http://a.jpg") is False


def test_mark_and_check_downloaded(db):
    db.mark_downloaded("tweet_123", "http://a.jpg", "/tmp/a.jpg", "image")
    assert db.is_downloaded("tweet_123", "http://a.jpg") is True


def test_mark_downloaded_idempotent(db):
    db.mark_downloaded("tweet_456", "http://a.jpg", "/tmp/a.jpg", "image")
    db.mark_downloaded("tweet_456", "http://a.jpg", "/tmp/a.jpg", "image")
    assert db.is_downloaded("tweet_456", "http://a.jpg") is True


def test_same_tweet_multiple_media(db):
    """同一 tweet 的多张图片都能记录"""
    db.mark_downloaded("multi", "http://img1.jpg", "/tmp/img1.jpg", "image")
    db.mark_downloaded("multi", "http://img2.jpg", "/tmp/img2.jpg", "image")
    assert db.is_downloaded("multi", "http://img1.jpg") is True
    assert db.is_downloaded("multi", "http://img2.jpg") is True
    stats = db.get_stats()
    assert stats["total"] == 2
    assert stats["unique_tweets"] == 1


def test_get_stats(db):
    db.mark_downloaded("t1", "u1", "/t1.jpg", "image")
    db.mark_downloaded("t2", "u2", "/t2.mp4", "video")
    stats = db.get_stats()
    assert stats["total"] == 2
    assert stats["unique_tweets"] == 2
    assert stats["by_type"]["image"] == 1
    assert stats["by_type"]["video"] == 1


def test_fetch_offset(db):
    assert db.get_fetch_offset() == 0
    db.set_fetch_offset(100)
    assert db.get_fetch_offset() == 100
