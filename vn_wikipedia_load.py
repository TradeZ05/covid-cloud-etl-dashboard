import io
import re
import getpass
import urllib.request
from datetime import datetime

import pandas as pd
import pymysql

from db_config import get_db_host, get_db_name, get_db_password, get_db_port, get_db_user


SOURCE_URL = "https://vi.wikipedia.org/wiki/%C4%90%E1%BA%A1i_d%E1%BB%8Bch_COVID-19_t%E1%BA%A1i_Vi%E1%BB%87t_Nam"
DB_HOST = get_db_host()
DB_PORT = get_db_port()
DB_USER = get_db_user()
DB_NAME = get_db_name()


def parse_int(value):
    if pd.isna(value):
        return None
    text = str(value).replace("\xa0", " ").strip()
    if not text or text in {"nan", "n.a.", "—", "-"}:
        return None
    match = re.search(r"\d[\d.]*", text)
    if not match:
        return None
    return int(match.group(0).replace(".", ""))


def clean_province_name(value):
    text = str(value).replace("\xa0", " ").strip()
    text = re.sub(r"\[[^\]]+\]", "", text)
    text = re.sub(r"\s+", " ", text)
    text = text.strip()
    if text.startswith("Cả nước"):
        return "Cả nước"
    return text[:255]


def extract_tables():
    print("[1/4] Tải bảng COVID-19 Việt Nam từ Wikipedia...")
    req = urllib.request.Request(
        SOURCE_URL,
        headers={"User-Agent": "Mozilla/5.0 ETL student project"},
    )
    html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
    tables = pd.read_html(io.StringIO(html))
    if len(tables) < 4:
        raise RuntimeError(f"Không tìm thấy đủ bảng cần thiết, chỉ có {len(tables)} bảng.")

    province_raw = tables[1].copy()
    timeline_raw = tables[3].copy()

    province_rows = []
    for _, row in province_raw.iterrows():
        name = clean_province_name(row.iloc[0])
        if not name or name.lower() == "nan":
            continue
        province_rows.append(
            {
                "province_name": name,
                "total_cases": parse_int(row.iloc[1]) or 0,
                "total_deaths": parse_int(row.iloc[2]) or 0,
                "new_cases": parse_int(row.iloc[3]) or 0,
            }
        )

    timeline_rows = []
    previous_cases = None
    previous_deaths = None
    for _, row in timeline_raw.iloc[1:].iterrows():
        date_text = str(row.iloc[0]).strip()
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_text):
            continue
        total_cases = parse_int(row.iloc[3])
        total_deaths = parse_int(row.iloc[4])
        if total_cases is None or total_deaths is None:
            continue
        new_cases = 0 if previous_cases is None else max(total_cases - previous_cases, 0)
        new_deaths = 0 if previous_deaths is None else max(total_deaths - previous_deaths, 0)
        timeline_rows.append(
            {
                "date": datetime.strptime(date_text, "%Y-%m-%d").date(),
                "total_cases": total_cases,
                "total_deaths": total_deaths,
                "new_cases": new_cases,
                "new_deaths": new_deaths,
            }
        )
        previous_cases = total_cases
        previous_deaths = total_deaths

    print(f"  - Province summary: {len(province_rows)} dòng")
    print(f"  - Timeline: {len(timeline_rows)} dòng")
    long_names = [row["province_name"] for row in province_rows if len(row["province_name"]) > 80]
    if long_names:
        print("  - Cảnh báo tên dài:", long_names[:3])
    return province_rows, timeline_rows


def connect():
    password = getpass.getpass("Nhập mật khẩu MySQL cho user 'root': ")
    return pymysql.connect(
        host="localhost",
        user="root",
        password=password,
        database=DB_NAME,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )

def connect():
    password = get_db_password(prompt=True)
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=password,
        database=DB_NAME,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def ensure_tables(cur):
    print("[2/4] Tạo bảng nếu chưa có...")
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS raw_vn_wikipedia_province_cases (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            province_name VARCHAR(255),
            total_cases BIGINT,
            total_deaths BIGINT,
            new_cases BIGINT,
            source_url VARCHAR(255),
            ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS fact_vn_wikipedia_daily (
            date_id INT PRIMARY KEY,
            total_cases BIGINT,
            total_deaths BIGINT,
            new_cases BIGINT,
            new_deaths BIGINT,
            source_url VARCHAR(255),
            FOREIGN KEY (date_id) REFERENCES dim_date(date_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS agg_vn_wikipedia_province_cases (
            province_name VARCHAR(255) PRIMARY KEY,
            total_cases BIGINT,
            total_deaths BIGINT,
            new_cases BIGINT,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
    )
    cur.execute("ALTER TABLE raw_vn_wikipedia_province_cases MODIFY province_name VARCHAR(255)")
    cur.execute("ALTER TABLE agg_vn_wikipedia_province_cases MODIFY province_name VARCHAR(255)")


def load_data(conn, province_rows, timeline_rows):
    with conn.cursor() as cur:
        ensure_tables(cur)
        print("[3/4] Nạp dữ liệu vào MySQL...")
        cur.execute("TRUNCATE TABLE raw_vn_wikipedia_province_cases")
        cur.execute("DELETE FROM fact_vn_wikipedia_daily")
        cur.execute("DELETE FROM agg_vn_wikipedia_province_cases")

        for row in province_rows:
            cur.execute(
                """
                INSERT INTO raw_vn_wikipedia_province_cases
                    (province_name, total_cases, total_deaths, new_cases, source_url)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (row["province_name"], row["total_cases"], row["total_deaths"], row["new_cases"], SOURCE_URL),
            )
            cur.execute(
                """
                INSERT INTO agg_vn_wikipedia_province_cases
                    (province_name, total_cases, total_deaths, new_cases)
                VALUES (%s, %s, %s, %s)
                """,
                (row["province_name"], row["total_cases"], row["total_deaths"], row["new_cases"]),
            )

        for row in timeline_rows:
            date_id = int(row["date"].strftime("%Y%m%d"))
            cur.execute(
                """
                INSERT IGNORE INTO dim_date (date_id, full_date, year, month, week, quarter)
                VALUES (%s, %s, YEAR(%s), MONTH(%s), WEEK(%s), QUARTER(%s))
                """,
                (date_id, row["date"], row["date"], row["date"], row["date"], row["date"]),
            )
            cur.execute(
                """
                INSERT INTO fact_vn_wikipedia_daily
                    (date_id, total_cases, total_deaths, new_cases, new_deaths, source_url)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    total_cases = VALUES(total_cases),
                    total_deaths = VALUES(total_deaths),
                    new_cases = VALUES(new_cases),
                    new_deaths = VALUES(new_deaths),
                    source_url = VALUES(source_url)
                """,
                (
                    date_id,
                    row["total_cases"],
                    row["total_deaths"],
                    row["new_cases"],
                    row["new_deaths"],
                    SOURCE_URL,
                ),
            )

        cur.execute(
            """
            INSERT INTO etl_job_log (job_name, status, rows_processed, started_at, finished_at)
            VALUES ('load_vietnam_wikipedia_cases', 'success', %s, NOW(), NOW())
            """,
            (len(province_rows) + len(timeline_rows),),
        )
    conn.commit()


def main():
    province_rows, timeline_rows = extract_tables()
    conn = connect()
    try:
        load_data(conn, province_rows, timeline_rows)
    finally:
        conn.close()
    print("[4/4] HOÀN TẤT - đã nạp dữ liệu ca mắc/tử vong Việt Nam từ Wikipedia.")


if __name__ == "__main__":
    main()
