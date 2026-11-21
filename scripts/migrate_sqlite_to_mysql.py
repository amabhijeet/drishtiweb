#!/usr/bin/env python3
"""One-time offline transfer of a frozen Drishti SQLite snapshot to MySQL 8.

Usage:
    DRISHTI_DATABASE_URL=... python scripts/migrate_sqlite_to_mysql.py /backups/drishti.sqlite3

Requirements:
* Stop API and Flask writers and create an independently verified backup first.
* Run FastAPI Store() and Flask `flask --app app init` on the MySQL target.
* Destination tables must be EMPTY; this script never overwrites target records.
* Keep the original media tree (uploads/, instances/) mounted at DRISHTI_DATA_DIR.
"""
import argparse
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mysql_db import Connection

TABLES = (
    "segments", "images", "detections",
    "web_reports", "web_media", "web_video_clips", "web_audit",
)


def sqlite_tables(db):
    return {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def inspect_media(db, root):
    """Reject a cutover if recorded source videos or output images are missing."""
    if "segments" in sqlite_tables(db):
        for segment_id, directory in db.execute("SELECT id,directory FROM segments"):
            parent = (root / "uploads" / directory).resolve()
            if not parent.is_relative_to((root / "uploads").resolve()):
                raise RuntimeError(f"Unsafe upload directory in segment {segment_id}")
            for filename in ("video.mp4", "track.gpx"):
                if not (parent / filename).is_file():
                    raise RuntimeError(f"Missing {filename} for segment {segment_id}")
    if "detections" in sqlite_tables(db):
        for detection_id, image in db.execute("SELECT id,image FROM detections"):
            path = (root / "instances" / image).resolve()
            if not path.is_relative_to((root / "instances").resolve()) or not path.is_file():
                raise RuntimeError(f"Missing detection evidence for {detection_id}")


def migrate(snapshot, root, url):
    if not snapshot.is_file():
        raise RuntimeError(f"SQLite snapshot not found: {snapshot}")
    root = root.resolve()
    # Read-only snapshot: never alter the original SQLite database.
    uri = snapshot.resolve().as_uri() + "?mode=ro"
    source = sqlite3.connect(uri, uri=True)
    try:
        integrity = source.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"SQLite integrity failure: {integrity}")
        tables = sqlite_tables(source)
        if "segments" not in tables or "images" not in tables or "detections" not in tables:
            raise RuntimeError("Snapshot missing required core Drishti tables")
        inspect_media(source, root)
        counts = {table: source.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                  for table in TABLES if table in tables}
        with Connection(url) as target:
            # Verify all target tables exist and none contains records before any insert.
            for table in TABLES:
                n = target.execute(f"SELECT COUNT(*) FROM `{table}`").fetchone()[0]
                if n:
                    raise RuntimeError(f"Destination {table} contains {n} rows; aborting")
            for table in TABLES:
                if table not in tables:
                    print(f"SKIP {table}: not present in SQLite snapshot")
                    continue
                columns = [row[1] for row in source.execute(f"PRAGMA table_info(`{table}`)")]
                if not columns:
                    continue
                escaped = ",".join(f"`{column}`" for column in columns)
                placeholders = ",".join(["%s"] * len(columns))
                statement = f"INSERT INTO `{table}` ({escaped}) VALUES ({placeholders})"
                copied = 0
                for row in source.execute(f"SELECT {escaped} FROM `{table}`"):
                    target.execute(statement, row)
                    copied += 1
                migrated = target.execute(f"SELECT COUNT(*) FROM `{table}`").fetchone()[0]
                if copied != counts[table] or migrated != counts[table]:
                    raise RuntimeError(f"Count mismatch for {table}: {counts[table]}, {copied}, {migrated}")
                print(f"OK {table}: {copied} rows")
            print("All row counts verified. Committing transaction.")
        # Verify committed data from a NEW connection.
        with Connection(url) as verified:
            for table, count in counts.items():
                actual = verified.execute(f"SELECT COUNT(*) FROM `{table}`").fetchone()[0]
                if actual != count:
                    raise RuntimeError(f"Post-commit verification failed: {table}")
        print("COMPLETE: data committed and row counts verified.")
    finally:
        source.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path, help="Frozen, backed-up SQLite file")
    parser.add_argument("--data-dir", type=Path, default=Path(os.environ.get("DRISHTI_DATA_DIR", "data")),
                        help="Root containing original uploads/ and instances/")
    args = parser.parse_args()
    url = os.getenv("DRISHTI_DATABASE_URL", "")
    if not url:
        parser.error("Set DRISHTI_DATABASE_URL to the private MySQL 8 database connection")
    migrate(args.snapshot, args.data_dir, url)
