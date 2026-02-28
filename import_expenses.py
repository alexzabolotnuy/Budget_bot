import csv
import sqlite3
from decimal import Decimal, InvalidOperation
from datetime import datetime

DB_PATH = "db.sqlite3"
CSV_PATH = "expenses_import.csv"

# Мінімальний “довідник” для створення відсутніх категорій
# (те, що у тебе вже є в дефолтах — просто не буде створено повторно)
CATEGORY_SEED = {
    "Інше": {"emoji": "📦", "kind": "variable", "limit_cents": None},  # додаємо спеціально під імпорт
}

SKIP_CATEGORIES = {"Накопичення"}  # ти просив прибрати цю логіку на MVP


def money_to_cents(s: str) -> int:
    s = (s or "").strip().replace(" ", "")
    # підтримка "12,34" або "12.34"
    s = s.replace(",", ".")
    try:
        d = Decimal(s)
    except InvalidOperation:
        raise ValueError(f"Bad amount: {s!r}")
    cents = int((d * 100).quantize(Decimal("1")))
    return cents


def ensure_category(conn: sqlite3.Connection, name: str) -> int:
    cur = conn.execute("SELECT id FROM categories WHERE name=? AND is_active=1", (name,))
    row = cur.fetchone()
    if row:
        return int(row[0])

    meta = CATEGORY_SEED.get(name)
    if not meta:
        # невідома категорія -> не створюємо автоматично, хай користувач вирішить
        raise KeyError(f"Unknown category {name!r} (not in DB and not in CATEGORY_SEED)")

    cur = conn.execute(
        "INSERT INTO categories (name, emoji, kind, limit_cents, is_active) VALUES (?,?,?,?,1)",
        (name, meta["emoji"], meta["kind"], meta["limit_cents"]),
    )
    return int(cur.lastrowid)


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")

    imported = 0
    skipped = 0
    skipped_rows = []

    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"spent_date", "amount_zl", "category", "comment"}
        if set(reader.fieldnames or []) != required:
            raise SystemExit(
                f"CSV header mismatch.\nExpected: {required}\nGot: {reader.fieldnames}"
            )

        for i, row in enumerate(reader, start=2):  # 2 = line after header
            spent_date = (row["spent_date"] or "").strip()
            category = (row["category"] or "").strip()
            comment = (row["comment"] or "").strip() or None

            if category in SKIP_CATEGORIES:
                skipped += 1
                skipped_rows.append((i, category, "SKIP_CATEGORIES"))
                continue

            # validate date YYYY-MM-DD
            try:
                datetime.strptime(spent_date, "%Y-%m-%d")
            except Exception:
                skipped += 1
                skipped_rows.append((i, category, f"Bad date {spent_date!r}"))
                continue

            try:
                amount_cents = money_to_cents(row["amount_zl"])
            except Exception as e:
                skipped += 1
                skipped_rows.append((i, category, f"Bad amount {row['amount_zl']!r}: {e}"))
                continue

            try:
                category_id = ensure_category(conn, category)
            except KeyError as e:
                skipped += 1
                skipped_rows.append((i, category, str(e)))
                continue

            created_at = datetime.now().isoformat(timespec="seconds")

            conn.execute(
                """
                INSERT INTO expenses (amount_cents, category_id, spent_date, created_at, comment)
                VALUES (?,?,?,?,?)
                """,
                (amount_cents, category_id, spent_date, created_at, comment),
            )
            imported += 1

    conn.commit()
    conn.close()

    print(f"Imported: {imported}")
    print(f"Skipped:  {skipped}")

    if skipped_rows:
        print("\nSkipped rows (line, category, reason):")
        for line_no, cat, reason in skipped_rows:
            print(f"  - {line_no}: {cat} -> {reason}")


if __name__ == "__main__":
    main()
