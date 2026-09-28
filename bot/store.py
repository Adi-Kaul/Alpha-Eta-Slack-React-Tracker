"""SQLite persistence so reminder timing survives restarts."""

from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass


@dataclass
class Record:
    channel: str
    ts: str
    last_reminded_at: float | None
    reminders_sent: int
    completed: bool


class Store:
    def __init__(self, path: str):
        self._lock = threading.Lock()
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.execute(
            """CREATE TABLE IF NOT EXISTS announcements (
                channel TEXT NOT NULL,
                ts TEXT NOT NULL,
                last_reminded_at REAL,
                reminders_sent INTEGER NOT NULL DEFAULT 0,
                completed INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (channel, ts)
            )"""
        )
        self._db.commit()

    def get(self, channel: str, ts: str) -> Record:
        with self._lock:
            row = self._db.execute(
                "SELECT last_reminded_at, reminders_sent, completed FROM announcements"
                " WHERE channel = ? AND ts = ?",
                (channel, ts),
            ).fetchone()
            if row is None:
                self._db.execute(
                    "INSERT INTO announcements (channel, ts) VALUES (?, ?)", (channel, ts)
                )
                self._db.commit()
                return Record(channel, ts, None, 0, False)
            return Record(channel, ts, row[0], row[1], bool(row[2]))

    def mark_reminded(self, channel: str, ts: str, at: float) -> None:
        with self._lock:
            self._db.execute(
                "UPDATE announcements SET last_reminded_at = ?, reminders_sent = reminders_sent + 1"
                " WHERE channel = ? AND ts = ?",
                (at, channel, ts),
            )
            self._db.commit()

    def mark_completed(self, channel: str, ts: str) -> None:
        with self._lock:
            self._db.execute(
                "UPDATE announcements SET completed = 1 WHERE channel = ? AND ts = ?",
                (channel, ts),
            )
            self._db.commit()
