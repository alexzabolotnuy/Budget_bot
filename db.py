from __future__ import annotations
import aiosqlite

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS categories (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  emoji TEXT NOT NULL DEFAULT '📦',
  kind TEXT NOT NULL CHECK(kind IN ('fixed','variable')),
  limit_cents INTEGER, -- default/template, NULL=без ліміту
  is_active INTEGER NOT NULL DEFAULT 1
);

-- помісячні ліміти категорій
CREATE TABLE IF NOT EXISTS category_limits (
  year INTEGER NOT NULL,
  month INTEGER NOT NULL,
  category_id INTEGER NOT NULL,
  limit_cents INTEGER, -- NULL = без ліміту
  PRIMARY KEY (year, month, category_id)
);

CREATE TABLE IF NOT EXISTS expenses (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  amount_cents INTEGER NOT NULL,
  category_id INTEGER NOT NULL,
  spent_date TEXT NOT NULL, -- YYYY-MM-DD
  created_at TEXT NOT NULL, -- ISO datetime
  comment TEXT
);

CREATE TABLE IF NOT EXISTS day_closures (
  spent_date TEXT NOT NULL, -- YYYY-MM-DD
  telegram_id INTEGER NOT NULL,
  closed_at TEXT NOT NULL,
  UNIQUE(spent_date, telegram_id)
);

CREATE TABLE IF NOT EXISTS closed_days (
  spent_date TEXT PRIMARY KEY,
  closed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS monthly_budgets (
  year INTEGER NOT NULL,
  month INTEGER NOT NULL,
  budget_cents INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (year, month)
);
"""

class Database:
    def __init__(self, path: str):
        self.path = path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(SCHEMA_SQL)
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if not self._conn:
            raise RuntimeError("DB not connected")
        return self._conn
