from __future__ import annotations
from db import Database

class Repo:
    def __init__(self, db: Database):
        self.db = db

    # ---------- monthly budget ----------
    async def get_monthly_budget(self, year: int, month: int) -> int:
        cur = await self.db.conn.execute(
            "SELECT budget_cents FROM monthly_budgets WHERE year=? AND month=?",
            (year, month),
        )
        row = await cur.fetchone()
        return int(row["budget_cents"]) if row else 0

    async def set_monthly_budget(self, year: int, month: int, budget_cents: int) -> None:
        await self.db.conn.execute(
            """
            INSERT INTO monthly_budgets (year, month, budget_cents)
            VALUES (?,?,?)
            ON CONFLICT(year, month) DO UPDATE SET budget_cents=excluded.budget_cents
            """,
            (year, month, budget_cents),
        )
        await self.db.conn.commit()

    # ---------- categories ----------
    async def list_categories(self):
        cur = await self.db.conn.execute(
            "SELECT * FROM categories WHERE is_active=1 ORDER BY id"
        )
        return await cur.fetchall()

    async def get_category(self, category_id: int):
        cur = await self.db.conn.execute(
            "SELECT * FROM categories WHERE id=? AND is_active=1",
            (category_id,),
        )
        return await cur.fetchone()

    async def add_category(self, name: str, emoji: str, kind: str, limit_cents: int | None) -> int:
        cur = await self.db.conn.execute(
            "INSERT INTO categories (name, emoji, kind, limit_cents, is_active) VALUES (?,?,?,?,1)",
            (name, emoji, kind, limit_cents),
        )
        await self.db.conn.commit()
        return int(cur.lastrowid)

    async def ensure_default_categories(self) -> None:
        """
        Створює дефолтні категорії (і їх дефолтні ліміти-шаблони) ТІЛЬКИ якщо categories порожня.
        """
        cur = await self.db.conn.execute("SELECT COUNT(*) AS c FROM categories")
        row = await cur.fetchone()
        if int(row["c"]) > 0:
            return

        # ✅ ДЕФОЛТНІ КАТЕГОРІЇ + ЛІМІТИ (PLN у центах)
        # "без ліміту" -> None
        defaults = [
            ("Оренда",              "🏠", "fixed",    8000_00),
            ("Садок / няня",        "👶", "fixed",    3000_00),
            ("Податки + бухгалтер", "🧾", "fixed",    None),

            ("Інвестиції",          "📈", "variable", 2500_00),
            ("Регулярні сервіси",   "🔌", "variable",  900_00),
            ("Продукти (дім)",      "🛒", "variable", 3500_00),
            ("Кафе / доставка",     "🍽", "variable", 3000_00),
            ("Шопінг",              "👕", "variable", 1200_00),
            ("Транспорт",           "🚗", "variable",  900_00),
            ("Розваги",             "🎉", "variable", 1200_00),
            ("Дім / техніка",       "🏡", "variable",  700_00),
            ("Резерв / хаос",       "🎁", "variable", 1000_00),
            ("Медицина",            "💊", "variable", 1000_00),
            ("Підписки / софт",     "💻", "variable",  200_00),
        ]

        await self.db.conn.executemany(
            "INSERT INTO categories (name, emoji, kind, limit_cents, is_active) VALUES (?,?,?,?,1)",
            [(n, e, k, lim) for (n, e, k, lim) in defaults],
        )
        await self.db.conn.commit()

    # ---------- month category limits ----------
    async def get_month_limits_map(self, year: int, month: int) -> dict[int, int | None]:
        cur = await self.db.conn.execute(
            "SELECT category_id, limit_cents FROM category_limits WHERE year=? AND month=?",
            (year, month),
        )
        rows = await cur.fetchall()
        return {int(r["category_id"]): (None if r["limit_cents"] is None else int(r["limit_cents"])) for r in rows}

    async def has_month_limits(self, year: int, month: int) -> bool:
        cur = await self.db.conn.execute(
            "SELECT 1 FROM category_limits WHERE year=? AND month=? LIMIT 1",
            (year, month),
        )
        return (await cur.fetchone()) is not None

    async def set_month_limit(self, year: int, month: int, category_id: int, limit_cents: int | None) -> None:
        await self.db.conn.execute(
            """
            INSERT INTO category_limits (year, month, category_id, limit_cents)
            VALUES (?,?,?,?)
            ON CONFLICT(year, month, category_id) DO UPDATE SET limit_cents=excluded.limit_cents
            """,
            (year, month, category_id, limit_cents),
        )
        await self.db.conn.commit()

    async def ensure_month_limits_from_category_defaults(self, year: int, month: int) -> None:
        """
        Якщо на цей місяць ще не створено category_limits — копіюємо з categories.limit_cents (дефолт-шаблон).
        """
        if await self.has_month_limits(year, month):
            return
        cats = await self.list_categories()
        await self.db.conn.executemany(
            """
            INSERT OR IGNORE INTO category_limits (year, month, category_id, limit_cents)
            VALUES (?,?,?,?)
            """,
            [(year, month, int(c["id"]), c["limit_cents"]) for c in cats],
        )
        await self.db.conn.commit()

    async def copy_limits_from_prev_month(self, year: int, month: int, prev_year: int, prev_month: int) -> None:
        if await self.has_month_limits(year, month):
            return

        prev = await self.get_month_limits_map(prev_year, prev_month)
        if not prev:
            await self.ensure_month_limits_from_category_defaults(year, month)
            return

        cats = await self.list_categories()
        await self.db.conn.executemany(
            """
            INSERT OR IGNORE INTO category_limits (year, month, category_id, limit_cents)
            VALUES (?,?,?,?)
            """,
            [(year, month, int(c["id"]), prev.get(int(c["id"]), c["limit_cents"])) for c in cats],
        )
        await self.db.conn.commit()

    # ---------- expenses ----------
    async def add_expense(self, amount_cents: int, category_id: int, spent_date: str, created_at_iso: str, comment: str | None) -> int:
        cur = await self.db.conn.execute(
            """
            INSERT INTO expenses (amount_cents, category_id, spent_date, created_at, comment)
            VALUES (?,?,?,?,?)
            """,
            (amount_cents, category_id, spent_date, created_at_iso, comment),
        )
        await self.db.conn.commit()
        return int(cur.lastrowid)

    async def set_expense_comment(self, expense_id: int, comment: str) -> None:
        await self.db.conn.execute(
            "UPDATE expenses SET comment=? WHERE id=?",
            (comment, expense_id),
        )
        await self.db.conn.commit()

    async def sum_by_date(self, spent_date: str) -> int:
        cur = await self.db.conn.execute(
            "SELECT COALESCE(SUM(amount_cents),0) AS s FROM expenses WHERE spent_date=?",
            (spent_date,),
        )
        row = await cur.fetchone()
        return int(row["s"])

    async def sum_by_date_and_kind(self, spent_date: str, kind: str) -> int:
        cur = await self.db.conn.execute(
            """
            SELECT COALESCE(SUM(e.amount_cents),0) AS s
            FROM expenses e
            JOIN categories c ON c.id=e.category_id
            WHERE e.spent_date=? AND c.kind=? AND c.is_active=1
            """,
            (spent_date, kind),
        )
        row = await cur.fetchone()
        return int(row["s"])

    async def sum_month_total(self, month_start: str, month_end: str) -> int:
        cur = await self.db.conn.execute(
            """
            SELECT COALESCE(SUM(amount_cents),0) AS s
            FROM expenses
            WHERE spent_date>=? AND spent_date<?
            """,
            (month_start, month_end),
        )
        row = await cur.fetchone()
        return int(row["s"])

    async def sum_month_by_category(self, month_start: str, month_end: str):
        cur = await self.db.conn.execute(
            """
            SELECT c.id AS category_id, COALESCE(SUM(e.amount_cents),0) AS s
            FROM categories c
            LEFT JOIN expenses e
              ON e.category_id=c.id AND e.spent_date>=? AND e.spent_date<?
            WHERE c.is_active=1
            GROUP BY c.id
            ORDER BY c.id
            """,
            (month_start, month_end),
        )
        rows = await cur.fetchall()
        return [(int(r["category_id"]), int(r["s"])) for r in rows]

    async def top_categories_in_range(self, start_date: str, end_date: str, limit: int = 2):
        cur = await self.db.conn.execute(
            """
            SELECT c.emoji AS emoji, c.name AS name, COALESCE(SUM(e.amount_cents),0) AS s
            FROM expenses e
            JOIN categories c ON c.id=e.category_id
            WHERE e.spent_date>=? AND e.spent_date<=? AND c.is_active=1
            GROUP BY c.id
            ORDER BY s DESC
            LIMIT ?
            """,
            (start_date, end_date, limit),
        )
        rows = await cur.fetchall()
        return [(r["emoji"], r["name"], int(r["s"])) for r in rows]

    async def daily_totals_in_range(self, start_date: str, end_date: str):
        cur = await self.db.conn.execute(
            """
            SELECT spent_date, COALESCE(SUM(amount_cents),0) AS s
            FROM expenses
            WHERE spent_date>=? AND spent_date<=?
            GROUP BY spent_date
            """,
            (start_date, end_date),
        )
        rows = await cur.fetchall()
        return [(str(r["spent_date"]), int(r["s"])) for r in rows]

    # ---------- day close ----------
    async def record_user_close(self, spent_date: str, telegram_id: int, closed_at_iso: str) -> None:
        await self.db.conn.execute(
            "INSERT OR IGNORE INTO day_closures (spent_date, telegram_id, closed_at) VALUES (?,?,?)",
            (spent_date, telegram_id, closed_at_iso),
        )
        await self.db.conn.commit()

    async def count_closures_for_date(self, spent_date: str) -> int:
        cur = await self.db.conn.execute(
            "SELECT COUNT(*) AS c FROM day_closures WHERE spent_date=?",
            (spent_date,),
        )
        row = await cur.fetchone()
        return int(row["c"])

    async def is_day_closed(self, spent_date: str) -> bool:
        cur = await self.db.conn.execute(
            "SELECT 1 FROM closed_days WHERE spent_date=?",
            (spent_date,),
        )
        row = await cur.fetchone()
        return row is not None

    async def mark_day_closed(self, spent_date: str, closed_at_iso: str) -> None:
        await self.db.conn.execute(
            "INSERT OR IGNORE INTO closed_days (spent_date, closed_at) VALUES (?,?)",
            (spent_date, closed_at_iso),
        )
        await self.db.conn.commit()
