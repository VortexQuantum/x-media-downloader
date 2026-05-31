from src.main import _run_simple


class FakeDB:
    def __init__(self, downloaded):
        self.downloaded = set(downloaded)
        self.marked = []

    def is_downloaded(self, tweet_id, media_url):
        return (tweet_id, media_url) in self.downloaded

    def mark_downloaded(self, tweet_id, media_url, file_path, media_type):
        self.marked.append((tweet_id, media_url, file_path, media_type))


def test_run_simple_returns_actual_skipped_count(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "src.main.download_media",
        lambda media_url, download_dir, tweet_id, media_type, retries=2: str(tmp_path / "ok.jpg"),
    )
    db = FakeDB({("t1", "u1")})
    tweet_groups = {
        "t1": [
            {"tweet_id": "t1", "media_url": "u1", "media_type": "image"},
            {"tweet_id": "t1", "media_url": "u2", "media_type": "image"},
        ]
    }
    new_downloads = []
    failed_items = []

    skipped = _run_simple(
        tweet_groups,
        {"download_dir": str(tmp_path)},
        db,
        new_downloads,
        failed_items,
    )

    assert skipped == 1
    assert len(new_downloads) == 1
    assert failed_items == []
    assert db.marked == [("t1", "u2", str(tmp_path / "ok.jpg"), "image")]
