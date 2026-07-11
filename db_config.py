import getpass
import os
from pathlib import Path


def get_db_host() -> str:
    return os.getenv("MYSQL_HOST") or os.getenv("MYSQLHOST") or "localhost"


def get_db_port() -> int:
    raw_port = os.getenv("MYSQL_PORT") or os.getenv("MYSQLPORT") or "3306"
    return int(raw_port)


def get_db_user() -> str:
    return os.getenv("MYSQL_USER") or os.getenv("MYSQLUSER") or "root"


def get_db_name() -> str:
    return os.getenv("MYSQL_DATABASE") or os.getenv("MYSQLDATABASE") or "covid_dashboard"


def get_db_password(prompt: bool = False) -> str:
    password = os.getenv("MYSQL_PASSWORD") or os.getenv("MYSQLPASSWORD") or ""
    local_password_file = Path(__file__).with_name(".mysql_password")
    if not password and local_password_file.exists():
        password = local_password_file.read_text(encoding="utf-8").strip()
    if not password and prompt:
        password = getpass.getpass(f"Nhap mat khau MySQL cho user '{get_db_user()}': ")
    return password
