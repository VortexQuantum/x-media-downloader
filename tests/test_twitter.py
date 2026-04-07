import json
import pytest
from src.twitter import parse_liked_tweets


SAMPLE_JSON = json.dumps(["twitter", 1, {
    "tweet_id": "1234567890",
    "date": "2026-05-01T10:00:00+00:00",
    "content": "Check this out!",
    "entities": {
        "media": [
            {
                "media_url": "https://pbs.twimg.com/media/abc",
                "type": "photo"
            }
        ]
    }
}])


def test_parse_liked_tweets_extracts_media():
    results = parse_liked_tweets(SAMPLE_JSON + "\n")
    assert len(results) == 1
    r = results[0]
    assert r["tweet_id"] == "1234567890"
    assert r["media_type"] == "image"
    assert "pbs.twimg.com" in r["media_url"]


def test_parse_liked_tweets_skips_no_media():
    results = parse_liked_tweets(
        json.dumps(["twitter", 1, {"tweet_id": "999", "content": "no media"}])
    )
    assert len(results) == 0


def test_parse_liked_tweets_handles_video():
    video_json = json.dumps(["twitter", 1, {
        "tweet_id": "v123",
        "entities": {
            "media": [{
                "media_url": "https://video.twimg.com/vid",
                "type": "video",
                "video_info": {
                    "variants": [
                        {"bitrate": 832000, "url": "https://video.twimg.com/low.mp4",
                         "content_type": "video/mp4"},
                        {"bitrate": 2176000, "url": "https://video.twimg.com/high.mp4",
                         "content_type": "video/mp4"}
                    ]
                }
            }]
        }
    }])
    results = parse_liked_tweets(video_json)
    assert results[0]["media_type"] == "video"
    assert "high.mp4" in results[0]["media_url"]


def test_parse_multiple_tweets():
    """多行 JSON，混合有/无媒体的 tweet"""
    data = "\n".join([
        json.dumps(["twitter", 1, {
            "tweet_id": "t1",
            "entities": {"media": [{"media_url": "http://a.jpg", "type": "photo"}]}
        }]),
        json.dumps(["twitter", 2, {
            "tweet_id": "t2",
            "content": "no media"
        }]),
        json.dumps(["twitter", 3, {
            "tweet_id": "t3",
            "entities": {"media": [{"media_url": "http://b.jpg", "type": "photo"}]}
        }]),
    ])
    results = parse_liked_tweets(data)
    assert len(results) == 2
    assert results[0]["tweet_id"] == "t1"
    assert results[1]["tweet_id"] == "t3"
