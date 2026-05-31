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
    assert db.is_downloaded("tweet_999", "http://a.jpg") is False


def test_mark_and_check_downloaded(db):
    db.mark_downloaded("tweet_123", "http://a.jpg", "/tmp/a.jpg", "image")
    assert db.is_downloaded("tweet_123", "http://a.jpg") is True


def test_same_tweet_multiple_media(db):
    db.mark_downloaded("multi", "http://img1.jpg", "/tmp/img1.jpg", "image")
    db.mark_downloaded("multi", "http://img2.jpg", "/tmp/img2.jpg", "image")
    assert db.is_downloaded("multi", "http://img1.jpg") is True
    assert db.is_downloaded("multi", "http://img2.jpg") is True


def test_get_stats(db):
    db.mark_downloaded("t1", "u1", "/t1.jpg", "image")
    db.mark_downloaded("t2", "u2", "/t2.mp4", "video")
    stats = db.get_stats()
    assert stats["total"] == 2
    assert stats["unique_tweets"] == 2


def test_are_all_downloaded_true(db):
    db.mark_downloaded("a", "u1", "/a.jpg", "image")
    db.mark_downloaded("b", "u2", "/b.jpg", "image")
    assert db.are_all_downloaded(["a", "b"]) is True


def test_are_all_downloaded_false(db):
    db.mark_downloaded("a", "u1", "/a.jpg", "image")
    assert db.are_all_downloaded(["a", "b"]) is False


def test_are_all_downloaded_empty(db):
    assert db.are_all_downloaded([]) is True


def test_relative_db_path_in_current_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    db = DownloadDB("downloads.db")
    try:
        db.mark_downloaded("t1", "u1", "file.jpg", "image")
        assert db.is_downloaded("t1", "u1") is True
    finally:
        db.close()
