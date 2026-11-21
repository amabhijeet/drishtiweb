"""Copy a stopped Drishti SQLite installation into an empty MariaDB schema."""
import argparse
import sqlite3
from contextlib import closing
from pathlib import Path

from mysql_db import Connection

TABLES = ("surveys", "segments", "images", "detections", "web_reports", "web_media", "web_video_clips", "web_audit")


def migrate(path):
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as source, Connection() as target:
        source.execute("BEGIN")
        existing = {name for name, in source.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        required = {"segments", "images", "detections"}
        if not required.issubset(existing):
            raise ValueError("Source is missing a Drishti processing table.")
        for table in TABLES:
            if target.execute(f"SELECT 1 FROM `{table}` LIMIT 1").fetchone():
                raise ValueError(f"Destination table {table} already contains data.")
        for table in TABLES:
            if table not in existing:
                continue
            rows = source.execute(f"SELECT * FROM `{table}`")
            columns = [field[0] for field in rows.description]
            destination = {field["Field"] for field in target.execute(f"SHOW COLUMNS FROM `{table}`")}
            if not set(columns).issubset(destination):
                raise ValueError(f"Unexpected source columns in {table}. Update the destination schema first.")
            identifiers = ",".join(f"`{column}`" for column in columns)
            placeholders = ",".join("?" for _ in columns)
            inserted = 0
            for row in rows:
                target.execute(f"INSERT INTO `{table}` ({identifiers}) VALUES ({placeholders})", row)
                inserted += 1
            count = target.execute(f"SELECT COUNT(*) AS total FROM `{table}`").fetchone()["total"]
            if count != inserted:
                raise RuntimeError(f"Row count differs for {table}.")
            print(f"{table}: {count} rows checked")
    print("Migration committed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sqlite_file", type=Path)
    migrate(parser.parse_args().sqlite_file)
