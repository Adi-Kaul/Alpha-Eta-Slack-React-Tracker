"""SQLite persistence so the bot remembers which reports it already posted, across restarts."""

from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass


@dataclass
class Record:
    channel: str
    ts: str
    sent: set[str]  # checkpoint keys already posted ("halfway", "warn:4", "deadline")
    completed: bool


class Store:
    def __init__(self, path: str):
        self._lock = threading.Lock()
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.executescript(
            """CREATE TABLE IF NOT EXISTS announcements (
                channel TEXT NOT NULL,
                ts TEXT NOT NULL,
                completed INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (channel, ts)
            );
            CREATE TABLE IF NOT EXISTS sent (
                channel TEXT NOT NULL,
                ts TEXT NOT NULL,
                checkpoint TEXT NOT NULL,
                PRIMARY KEY (channel, ts, checkpoint)
            );"""
        )

    def get(self, channel: str, ts: str) -> Record:
        with self._lock:
            row = self._db.execute(
                "SELECT completed FROM announcements WHERE channel = ? AND ts = ?", (channel, ts)
            ).fetchone()
            if row is None:
                self._db.execute("INSERT INTO announcements (channel, ts) VALUES (?, ?)", (channel, ts))
                self._db.commit()
            sent = {r[0] for r in self._db.execute(
                "SELECT checkpoint FROM sent WHERE channel = ? AND ts = ?", (channel, ts))}
            return Record(channel, ts, sent, bool(row and row[0]))

    def mark_sent(self, channel: str, ts: str, checkpoints: list[str]) -> None:
        with self._lock:
            self._db.executemany(
                "INSERT OR IGNORE INTO sent (channel, ts, checkpoint) VALUES (?, ?, ?)",
                [(channel, ts, c) for c in checkpoints],
            )
            self._db.commit()

    def mark_completed(self, channel: str, ts: str) -> None:
        with self._lock:
            self._db.execute(
                "UPDATE announcements SET completed = 1 WHERE channel = ? AND ts = ?", (channel, ts)
            )
            self._db.commit()
