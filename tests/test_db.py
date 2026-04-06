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


def test_init_creates_table(db):
    rows = db.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='downloads'"
    ).fetchall()
    assert len(rows) == 1


def test_is_downloaded_false(db):
    assert db.is_downloaded("tweet_999") is False


def test_mark_and_check_downloaded(db):
    db.mark_downloaded("tweet_123", "https://pbs.twimg.com/media/abc.jpg",
                        "/tmp/abc.jpg", "image")
    assert db.is_downloaded("tweet_123") is True


def test_mark_downloaded_idempotent(db):
    db.mark_downloaded("tweet_456", "url", "/tmp/x.jpg", "image")
    db.mark_downloaded("tweet_456", "url", "/tmp/x.jpg", "image")
    assert db.is_downloaded("tweet_456") is True


def test_get_stats(db):
    db.mark_downloaded("t1", "u1", "/t1.jpg", "image")
    db.mark_downloaded("t2", "u2", "/t2.mp4", "video")
    stats = db.get_stats()
    assert stats["total"] == 2
    assert stats["by_type"]["image"] == 1
    assert stats["by_type"]["video"] == 1
