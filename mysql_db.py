"""Connection helpers for the shared Drishti MariaDB database."""
import os
from contextlib import contextmanager
from urllib.parse import unquote, urlsplit

import pymysql


def enabled():
    return bool(os.getenv("DRISHTI_DATABASE_URL"))


class Connection:
    def __init__(self):
        url = urlsplit(os.environ["DRISHTI_DATABASE_URL"])
        if url.scheme != "mysql" or not url.hostname or not url.username or not url.path.strip("/"):
            raise ValueError("Set DRISHTI_DATABASE_URL to mysql://user:password@host:port/database")
        self.raw = pymysql.connect(host=url.hostname, port=url.port or 3306, user=unquote(url.username),
                                   password=unquote(url.password or ""), database=unquote(url.path[1:]),
                                   charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor,
                                   binary_prefix=True, autocommit=False, connect_timeout=5,
                                   init_command="SET SESSION time_zone = '+00:00', sql_mode = "
                                                "'STRICT_ALL_TABLES,NO_ZERO_DATE,NO_ZERO_IN_DATE,NO_ENGINE_SUBSTITUTION'")

    def execute(self, sql, args=()):
        cursor = self.raw.cursor()
        cursor.execute(sql.replace("?", "%s"), args or None)
        return cursor

    def executescript(self, sql):
        for statement in sql.split(";"):
            if statement.strip():
                self.execute(statement)

    def begin(self):
        self.raw.begin()

    def close(self):
        self.raw.close()

    def __enter__(self):
        return self

    def __exit__(self, kind, value, traceback):
        try:
            self.finish(kind)
        finally:
            self.close()

    def finish(self, kind):
        if kind is None:
            self.raw.commit()
        else:
            self.raw.rollback()


@contextmanager
def transaction(connection):
    try:
        yield connection
        connection.finish(None)
    except BaseException:
        connection.finish(True)
        raise


def require_current(db):
    try:
        versions = db.execute("SELECT version,state FROM schema_migrations ORDER BY version").fetchall()
    except pymysql.MySQLError as error:
        raise RuntimeError("Run the Drishti MariaDB migrator before starting the staff portal.") from error
    if [(r["version"], r["state"]) for r in versions] != [(1, "applied"), (2, "applied"), (3, "applied")]:
        raise RuntimeError("Drishti MariaDB migrations must finish before staff portal startup.")
