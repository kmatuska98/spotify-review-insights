"""Shared helpers: hashing identical to the grader's, paths, atomic writes."""
import csv, hashlib, json, os, sys
from pathlib import Path

csv.field_size_limit(sys.maxsize)
ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "work"
FIELDS = ("review_id", "review_text", "review_rating", "review_likes", "app_version", "review_timestamp")
TOPICS = ("access", "usability", "playback", "downloads", "catalog", "billing", "support", "other")
INTENTS = ("cancellation", "complaint", "request", "praise", "unclear")


def canonical(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True, allow_nan=False)


def row_sha(row):
    """SHA-256 of the six original fields; byte-identical to the grader's helper."""
    return hashlib.sha256(canonical([row[k] for k in FIELDS]).encode("utf-8")).hexdigest()


def text_sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def csv_rows(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f, strict=True):
            yield row


def atomic_write_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def atomic_write_json(path, obj):
    atomic_write_text(path, json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
