import json
import pytest
from src.twitter import parse_liked_tweets


SAMPLE_JSON = json.dumps({
    "data": [
        {
            "id": "1234567890",
            "text": "Check this out!",
            "created_at": "2026-05-01T10:00:00.000Z",
            "attachments": {"media_keys": ["3_111"]}
        },
        {
            "id": "0987654321",
            "text": "Just text, no media",
            "created_at": "2026-05-02T12:00:00.000Z"
        }
    ],
    "includes": {
        "media": [
            {
                "media_key": "3_111",
                "type": "photo",
                "url": "https://pbs.twimg.com/media/abc.jpg"
            }
        ]
    }
})


def test_parse_liked_tweets_extracts_media():
    results = parse_liked_tweets(SAMPLE_JSON)
    assert len(results) == 1
    r = results[0]
    assert r["tweet_id"] == "1234567890"
    assert r["media_type"] == "photo"
    assert r["media_url"] == "https://pbs.twimg.com/media/abc.jpg"


def test_parse_liked_tweets_skips_no_media():
    results = parse_liked_tweets(json.dumps({
        "data": [{"id": "999", "text": "no media"}]
    }))
    assert len(results) == 0


def test_parse_liked_tweets_handles_video():
    video_json = json.dumps({
        "data": [{
            "id": "v123",
            "text": "video tweet",
            "attachments": {"media_keys": ["7_222"]}
        }],
        "includes": {
            "media": [{
                "media_key": "7_222",
                "type": "video",
                "variants": [
                    {"bit_rate": 832000, "url": "https://video.twimg.com/low.mp4"},
                    {"bit_rate": 2176000, "url": "https://video.twimg.com/high.mp4"}
                ]
            }]
        }
    })
    results = parse_liked_tweets(video_json)
    assert results[0]["media_type"] == "video"
    assert "high.mp4" in results[0]["media_url"]
