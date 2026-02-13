from dataclasses import dataclass
from dotenv import load_dotenv
import os

load_dotenv()

@dataclass
class Config:
    token: str
    tz: str
    db_path: str
    users: list[int]

def _parse_users(val: str) -> list[int]:
    return [int(x.strip()) for x in val.split(",") if x.strip()]

cfg = Config(
    token=os.getenv("TOKEN"),
    tz=os.getenv("TZ", "Europe/Warsaw"),
    db_path=os.getenv("DB_PATH", "db.sqlite3"),
    users=_parse_users(os.getenv("USERS", "")),
)
