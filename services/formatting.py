from __future__ import annotations
import re

def bar_squares_5(p: float) -> str:
    p = max(0.0, p)
    filled = min(5, round(p * 5))
    return "🟩" * filled + "⬜" * (5 - filled)

def format_int_with_spaces(n: int) -> str:
    s = str(abs(n))
    parts = []
    while s:
        parts.append(s[-3:])
        s = s[:-3]
    out = " ".join(reversed(parts)) if parts else "0"
    return f"-{out}" if n < 0 else out

def money(cents: int) -> str:
    # cents = grosz
    zl = cents // 100
    return f"{format_int_with_spaces(zl)} zł"

def parse_amount_to_cents(text: str) -> int | None:
    t = (text or "").strip()
    if not t:
        return None
    t = t.replace(",", ".")
    if not re.fullmatch(r"\d+(\.\d{1,2})?", t):
        return None
    if "." in t:
        a, b = t.split(".", 1)
        b = (b + "00")[:2]
    else:
        a, b = t, "00"
    return int(a) * 100 + int(b)

def parse_date_ddmmyyyy(text: str) -> str | None:
    # returns YYYY-MM-DD
    t = (text or "").strip()
    if not re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", t):
        return None
    dd, mm, yyyy = t.split(".")
    d = int(dd); m = int(mm); y = int(yyyy)
    if not (1 <= m <= 12):
        return None
    if not (1 <= d <= 31):
        return None
    # мінімальна перевірка: календар не буду ускладнювати (MVP)
    return f"{y:04d}-{m:02d}-{d:02d}"
