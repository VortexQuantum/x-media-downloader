import json
import pytest
from src.twitter import fetch_liked_tweets, parse_liked_tweets


def test_parse_image_tweet():
    """单图片 tweet: tweet entry + 1 media URL entry"""
    data = json.dumps([
        [2, {
            "tweet_id": "1234567890",
            "date": "2026-05-01T10:00:00",
            "count": 1,
        }],
        [3, "https://pbs.twimg.com/media/abc.jpg", {"extension": "jpg"}],
    ])
    results = parse_liked_tweets(data)
    assert len(results) == 1
    r = results[0]
    assert r["tweet_id"] == "1234567890"
    assert r["media_type"] == "image"
    assert "abc.jpg" in r["media_url"]


def test_parse_video_tweet():
    """视频 tweet"""
    data = json.dumps([
        [2, {"tweet_id": "v123", "date": "2026-05-02", "count": 1}],
        [3, "https://video.twimg.com/amplify_video/xxx.mp4?tag=27",
         {"extension": "mp4"}],
    ])
    results = parse_liked_tweets(data)
    assert len(results) == 1
    assert results[0]["media_type"] == "video"


def test_parse_multi_media_tweet():
    """多条媒体的 tweet"""
    data = json.dumps([
        [2, {"tweet_id": "m123", "date": "2026-05-03", "count": 3}],
        [3, "https://pbs.twimg.com/media/a.jpg", {"extension": "jpg"}],
        [4, "https://pbs.twimg.com/media/b.jpg", {"extension": "jpg"}],
        [5, "https://pbs.twimg.com/media/c.jpg", {"extension": "jpg"}],
    ])
    results = parse_liked_tweets(data)
    assert len(results) == 3
    assert all(r["tweet_id"] == "m123" for r in results)


def test_parse_no_media_tweet():
    """无媒体的 tweet 被跳过"""
    data = json.dumps([
        [2, {
            "tweet_id": "999",
            "count": 0,
            "content": "just text"
        }],
    ])
    results = parse_liked_tweets(data)
    assert len(results) == 0


def test_parse_mixed_tweets():
    """混合：有媒体 + 无媒体 + 有媒体"""
    data = json.dumps([
        [2, {"tweet_id": "t1", "count": 1}],
        [3, "https://pbs.twimg.com/media/a.jpg", {}],
        [4, {"tweet_id": "t2", "count": 0}],
        [5, {"tweet_id": "t3", "count": 2}],
        [6, "https://pbs.twimg.com/media/b.jpg", {}],
        [7, "https://video.twimg.com/v.mp4", {"extension": "mp4"}],
    ])
    results = parse_liked_tweets(data)
    assert len(results) == 3
    assert results[0]["tweet_id"] == "t1"
    assert results[1]["tweet_id"] == "t3"
    assert results[2]["tweet_id"] == "t3"


def test_fetch_liked_tweets_requires_username(tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text("cookie", encoding="utf-8")

    with pytest.raises(ValueError, match="X username is required"):
        fetch_liked_tweets(str(cookies_file), username="")

    with pytest.raises(ValueError, match="X username is required"):
        fetch_liked_tweets(str(cookies_file), username="YOUR_X_USERNAME")


def test_fetch_liked_tweets_rejects_url_as_username(tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text("cookie", encoding="utf-8")

    with pytest.raises(ValueError, match="must be a handle"):
        fetch_liked_tweets(str(cookies_file), username="https://x.com/someuser")


def test_fetch_liked_tweets_uses_username_in_url(monkeypatch, tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text("cookie", encoding="utf-8")
    captured = {}

    class DummyResult:
        returncode = 0
        stdout = "[]"
        stderr = ""

    def fake_run(cmd, capture_output, text, timeout):
        captured["cmd"] = cmd
        return DummyResult()

    monkeypatch.setattr("src.twitter.subprocess.run", fake_run)

    fetch_liked_tweets(
        str(cookies_file),
        username="@someuser",
        max_results=50,
        offset=100,
    )

    assert captured["cmd"][-1] == "https://x.com/someuser/likes"
    assert "--range" in captured["cmd"]
    assert "101-150" in captured["cmd"]
