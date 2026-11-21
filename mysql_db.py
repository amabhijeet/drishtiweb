"""Minimal parameterized MySQL adapter for the existing Drishti SQL call sites.

The application uses SQLite's positional placeholders. This adapter keeps those
call sites compatible while the production storage backend uses MySQL 8.4.
"""
import hashlib
from urllib.parse import unquote, urlsplit

import pymysql
from pymysql.cursors import DictCursor


class Row(dict):
    """Support both SQLite-style row['column'] and row[0] lookups."""
    def __getitem__(self, key):
        if isinstance(key, int):
            return tuple(self.values())[key]
        return super().__getitem__(key)


class Result:
    def __init__(self, cursor):
        self.cursor = cursor
        self.rowcount = cursor.rowcount

    def fetchone(self):
        value = self.cursor.fetchone()
        return Row(value) if value is not None else None

    def fetchall(self):
        return [Row(value) for value in self.cursor.fetchall()]

    def __iter__(self):
        for value in self.cursor:
            yield Row(value)


class Connection:
    def __init__(self, url, close_on_exit=True):
        parsed = urlsplit(url)
        if parsed.scheme not in ('mysql', 'mysql+pymysql') or not parsed.hostname or not parsed.path.strip('/'):
            raise ValueError('DRISHTI_DATABASE_URL must be mysql+pymysql://USER:PASSWORD@HOST:PORT/DATABASE')
        if parsed.query or parsed.fragment:
            raise ValueError('Do not include query parameters in DRISHTI_DATABASE_URL')
        self.raw = pymysql.connect(
            host=parsed.hostname,
            port=parsed.port or 3306,
            user=unquote(parsed.username or ''),
            password=unquote(parsed.password or ''),
            database=unquote(parsed.path.lstrip('/')),
            charset='utf8mb4',
            cursorclass=DictCursor,
            autocommit=False,
            connect_timeout=10,
            read_timeout=120,
            write_timeout=120,
        )
        self.close_on_exit = close_on_exit

    def execute(self, sql, params=()):
        query = sql.strip()
        if query.upper() == 'BEGIN IMMEDIATE':
            sql = 'START TRANSACTION'
        elif query.upper().startswith('INSERT OR IGNORE '):
            sql = 'INSERT IGNORE ' + query[len('INSERT OR IGNORE '):]
        # All SQL originates in the application, never in user-supplied strings.
        sql = sql.replace('?', '%s')
        if sql.lstrip().upper().startswith('INSERT INTO DETECTIONS VALUES'):
            sql = sql.replace('INSERT INTO detections VALUES', 'INSERT INTO detections (id,segment,asset,latitude,longitude,confidence,`offset`,accuracy,bbox,image) VALUES')
        cursor = self.raw.cursor()
        cursor.execute(sql, params)
        return Result(cursor)

    def executescript(self, script):
        raise RuntimeError('Use mysql_schema.initialize_schema for MySQL DDL')

    def lock_segment(self, segment_id):
        """Serialize competing uploads for the same segment across connections."""
        name = 'drishti:' + hashlib.sha256(segment_id.encode()).hexdigest()[:56]
        row = self.execute('SELECT GET_LOCK(?, 30) AS acquired', (name,)).fetchone()
        if not row or row['acquired'] != 1:
            raise TimeoutError('Could not obtain the segment upload lock')

    def close(self):
        self.raw.close()

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception, traceback):
        try:
            if exception_type:
                self.raw.rollback()
            else:
                self.raw.commit()
        finally:
            if self.close_on_exit:
                self.close()
        return False

