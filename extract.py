"""
extract.py — Giai đoạn 2 của pipeline.
Việc script này làm: tải dữ liệu COVID từ Our World in Data (OWID),
đổ NGUYÊN VĂN (chưa xử lý gì) vào bảng raw_covid_data — đúng vai trò Data Lake.

Cách chạy:
    pip install pandas pymysql requests --break-system-packages
    python extract.py
"""

import os
import sys
from datetime import datetime, date, timedelta

import requests
import pandas as pd
import pymysql

from db_config import get_db_host, get_db_name, get_db_password, get_db_port, get_db_user

# ============================================================
# CẤU HÌNH — sửa lại cho đúng với máy bạn nếu cần
# ============================================================
DB_HOST = get_db_host()
DB_PORT = get_db_port()
DB_USER = get_db_user()
DB_NAME = get_db_name()
CLEAR_RAW_BEFORE_LOAD = True

OWID_URL = "https://covid.ourworldindata.org/data/owid-covid-data.csv"

# Nếu bạn tải file CSV thủ công (do máy không tải được qua mạng),
# đặt file tên đúng như dưới đây, để CÙNG THƯ MỤC với file extract.py này.
# Script sẽ tự ưu tiên dùng file này thay vì tải qua mạng.
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
LOCAL_CSV_PATH = os.path.join(PROJECT_ROOT, "data", "raw", "owid-covid-data.csv")
LEGACY_LOCAL_CSV_PATH = os.path.join(PROJECT_ROOT, "owid-covid-data.csv")

# Chỉ lấy N ngày gần nhất TÍNH TỪ NGÀY MỚI NHẤT CÓ THẬT TRONG DỮ LIỆU
# (không dùng ngày hệ thống hôm nay, vì OWID có thể đã ngừng cập nhật
# liên tục — nếu tính theo ngày hệ thống dễ bị lọc dư ra 0 dòng)
DAYS_TO_KEEP = 400

# Các cột cần lấy từ file OWID (file gốc có hơn 60 cột, ta chỉ cần vài cột)
COLUMNS_NEEDED = [
    "iso_code", "continent", "location", "date",
    "new_cases", "new_deaths", "total_cases", "total_deaths",
    "people_vaccinated", "population",
]


def download_owid_data() -> pd.DataFrame:
    csv_path = LOCAL_CSV_PATH if os.path.exists(LOCAL_CSV_PATH) else LEGACY_LOCAL_CSV_PATH
    if os.path.exists(csv_path):
        print(f"[1/4] Tìm thấy file CSV tải sẵn: {LOCAL_CSV_PATH}")
        print("      Dùng file này, KHÔNG tải qua mạng.")
        df = pd.read_csv(csv_path, usecols=COLUMNS_NEEDED)
    else:
        print(f"[1/4] Không thấy file CSV sẵn, đang tải từ OWID: {OWID_URL}")
        df = pd.read_csv(OWID_URL, usecols=COLUMNS_NEEDED)

    print(f"      Tải xong: {len(df):,} dòng (toàn bộ lịch sử, tất cả quốc gia)")

    df["date"] = pd.to_datetime(df["date"]).dt.date
    latest_date_in_data = df["date"].max()
    min_date = latest_date_in_data - timedelta(days=DAYS_TO_KEEP)
    print(f"      Ngày mới nhất có trong dữ liệu: {latest_date_in_data}")
    df = df[df["date"] >= min_date]
    print(f"      Lấy {DAYS_TO_KEEP} ngày gần nhất (từ {min_date}): còn {len(df):,} dòng")

    print("      Mau du lieu sau khi doc CSV:")
    print(df[["iso_code", "location", "date"]].head(3).to_string(index=False))

    if df.empty:
        raise ValueError("CSV khong co dong du lieu nao sau khi loc ngay.")
    if df["iso_code"].astype(str).eq("iso_code").all():
        raise ValueError(
            "Doc CSV bi sai: cot iso_code dang toan la chu 'iso_code'. "
            "Hay xoa file owid-covid-data.csv hien tai va tai lai file OWID dung."
        )

    return df


def clean_cell(v):
    """
    Chuyển 1 giá trị bất kỳ thành dạng an toàn để ghi vào MySQL:
    - Nếu trống/thiếu (None, NaN, NaT...) → trả về None (MySQL hiểu là NULL)
    - Nếu có giá trị → ép về string (đúng bản chất Data Lake: giữ dạng thô)
    Hàm này được gọi NGAY LÚC lấy giá trị ra để insert, không gán ngược
    vào cột DataFrame — vì pandas hay tự đổi None thành NaN trở lại nếu
    gán ngược vào cột vốn là kiểu số, gây lỗi khi ghi vào MySQL.
    """
    if pd.isna(v):
        return None
    return str(v)


def connect_db(password: str):
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=password,
        database=DB_NAME,
        charset="utf8mb4",
    )


def load_into_raw_table(conn, df: pd.DataFrame) -> int:
    print(f"[2/4] Đang ghi {len(df):,} dòng vào bảng raw_covid_data...")
    sql = """
        INSERT INTO raw_covid_data
            (iso_code, continent, location, date_raw,
             new_cases, new_deaths, total_cases, total_deaths,
             people_vaccinated, population, source_file)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    rows = []
    for r in df.itertuples(index=False):
        rows.append((
            clean_cell(r.iso_code), clean_cell(r.continent),
            clean_cell(r.location), clean_cell(r.date),
            clean_cell(r.new_cases), clean_cell(r.new_deaths),
            clean_cell(r.total_cases), clean_cell(r.total_deaths),
            clean_cell(r.people_vaccinated), clean_cell(r.population),
            "owid-covid-data.csv",
        ))

    print(f"      Mau dong sap ghi vao MySQL: {rows[0][:4] if rows else None}")
    if rows and rows[0][0] == "iso_code":
        raise ValueError(
            "Dong dau tien sap ghi vao MySQL van la header CSV. Dung lai de tranh nap sai raw_covid_data."
        )

    with conn.cursor() as cur:
        if CLEAR_RAW_BEFORE_LOAD:
            print("      Dang xoa du lieu raw cu trong raw_covid_data...")
            cur.execute("TRUNCATE TABLE raw_covid_data")
            conn.commit()

        # Ghi theo lô 1000 dòng/lần cho nhanh, tránh timeout
        batch_size = 1000
        for i in range(0, len(rows), batch_size):
            batch = rows[i : i + batch_size]
            cur.executemany(sql, batch)
            conn.commit()
            print(f"      Đã ghi {min(i + batch_size, len(rows)):,}/{len(rows):,} dòng")

    print("[3/4] Ghi dữ liệu xong.")
    return len(rows)


def log_job(conn, status: str, rows_processed: int, started_at: datetime,
            error_message: str = None):
    print(f"[4/4] Ghi log vào etl_job_log (status={status})...")
    sql = """
        INSERT INTO etl_job_log
            (job_name, status, rows_processed, started_at, finished_at, error_message)
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    with conn.cursor() as cur:
        cur.execute(sql, (
            "extract_owid", status, rows_processed,
            started_at, datetime.now(), error_message,
        ))
        conn.commit()


def main():
    started_at = datetime.now()
    password = get_db_password(prompt=True)
    conn = connect_db(password)

    try:
        df = download_owid_data()
        rows_written = load_into_raw_table(conn, df)
        log_job(conn, "success", rows_written, started_at)
        print(f"\n✅ HOÀN TẤT — đã nạp {rows_written:,} dòng dữ liệu thô vào raw_covid_data.")
    except Exception as e:
        log_job(conn, "failed", 0, started_at, error_message=str(e))
        print(f"\n❌ LỖI: {e}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
