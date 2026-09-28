"""Database access: lightweight psycopg connection pool.

DSN comes from the DATABASE_URL environment variable. The pool is created
lazily (first use), so importing this module never opens a connection.
Connections are returned to the pool on context exit; broken ones are
discarded. All queries use ``row_factory=dict_row`` so rows are dicts.

Note: only the ``psycopg[binary]`` package is used (per requirements.txt) --
no ``psycopg_pool`` dependency, hence the small hand-rolled pool below.
"""

from __future__ import annotations

import logging
import os
import queue
import threading
from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg.rows import dict_row

log = logging.getLogger("topaz.db")

_pool = None
_pool_lock = threading.Lock()


class _Pool:
    """Minimal thread-safe connection pool for psycopg3 connections."""

    def __init__(self, dsn: str, maxsize: int = 10):
        self._dsn = dsn
        self._idle: "queue.Queue[psycopg.Connection]" = queue.Queue(maxsize=maxsize)

    def _new(self) -> "psycopg.Connection":
        return psycopg.connect(self._dsn, row_factory=dict_row)

    @contextmanager
    def connection(self) -> Iterator["psycopg.Connection"]:
        conn = None
        try:
            conn = self._idle.get_nowait()
            if conn.closed:
                conn = None
        except queue.Empty:
            pass
        if conn is None:
            conn = self._new()
        try:
            yield conn
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise
        finally:
            if conn.closed:
                return
            try:
                self._idle.put_nowait(conn)
            except queue.Full:
                conn.close()


def get_pool() -> _Pool:
    """Return the process-wide pool, creating it on first call."""
    global _pool
    with _pool_lock:
        if _pool is None:
            dsn = os.environ.get("DATABASE_URL")
            if not dsn:
                raise RuntimeError("DATABASE_URL environment variable is not set")
            _pool = _Pool(dsn)
    return _pool


def get_conn():
    """Context manager yielding a pooled psycopg connection (dict rows).

    Usage::

        with get_conn() as conn:
            row = conn.execute("SELECT 1").fetchone()
    """
    return get_pool().connection()
