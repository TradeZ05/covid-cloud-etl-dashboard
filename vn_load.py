from datetime import datetime
from pathlib import Path

import pandas as pd
import pymysql

from db_config import get_db_host, get_db_name, get_db_password, get_db_port, get_db_user

DB_HOST = get_db_host()
DB_PORT = get_db_port()
DB_USER = get_db_user()
DB_NAME = get_db_name()
PROJECT_ROOT = Path(__file__).resolve().parent
CSV_PATH = PROJECT_ROOT / "data" / "raw" / "covid19-provinces_vn_vi_v2.csv"
LEGACY_CSV_PATH = PROJECT_ROOT / "covid19-provinces_vn_vi_v2.csv"


def connect_db(password: str):
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=password,
        database=DB_NAME,
        charset="utf8mb4",
    )


def parse_vn_number(value):
    if pd.isna(value):
        return 0
    text = str(value).strip()
    if not text:
        return 0
    if "." in text:
        whole, frac = text.split(".", 1)
        # Source file uses values such as "2.96" for 2,960 cases.
        return int(f"{whole}{frac.ljust(3, '0')}")
    return int(float(text))


def ensure_schema(conn):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*)
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'fact_covid_vn_daily'
              AND COLUMN_NAME = 'total_deaths'
        """)
        if cur.fetchone()[0] == 0:
            cur.execute("ALTER TABLE fact_covid_vn_daily ADD COLUMN total_deaths BIGINT DEFAULT 0 AFTER total_cases")

        cur.execute("""
            SELECT COUNT(*)
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'agg_vn_province_summary'
              AND COLUMN_NAME = 'latest_total_deaths'
        """)
        if cur.fetchone()[0] == 0:
            cur.execute("""
                ALTER TABLE agg_vn_province_summary
                    ADD COLUMN latest_total_deaths BIGINT DEFAULT 0 AFTER latest_total_cases,
                    ADD COLUMN latest_new_cases INT DEFAULT 0 AFTER latest_total_deaths
            """)

        conn.commit()


def load_csv() -> pd.DataFrame:
    csv_path = CSV_PATH if CSV_PATH.exists() else LEGACY_CSV_PATH
    last_error = None
    for encoding in ("utf-16", "utf-8-sig", "utf-8"):
        try:
            df = pd.read_csv(csv_path, sep="\t", encoding=encoding)
            print(f"      Doc file bang encoding: {encoding}")
            break
        except UnicodeDecodeError as exc:
            last_error = exc
    else:
        raise last_error

    df = df.rename(columns={
        "Tỉnh": "province_name",
        "Tổng số ca lây nhiễm": "total_cases",
        "Số ca lây nhiễm mới": "new_cases",
        "Tổng số ca tử vong": "total_deaths",
        "Ngày": "date_raw",
    })
    df["province_name"] = df["province_name"].astype(str).str.strip()
    df["total_cases"] = df["total_cases"].apply(parse_vn_number)
    df["new_cases"] = df["new_cases"].apply(parse_vn_number)
    df["total_deaths"] = df["total_deaths"].apply(parse_vn_number)
    df["date_raw"] = pd.to_datetime(df["date_raw"], format="%m-%d-%Y", errors="coerce")
    df = df.dropna(subset=["province_name", "date_raw"])
    df = df.sort_values(["province_name", "date_raw"])
    return df


def load_dimensions(conn, df: pd.DataFrame):
    with conn.cursor() as cur:
        cur.execute("SET FOREIGN_KEY_CHECKS = 0")
        cur.execute("TRUNCATE TABLE agg_daily_vn")
        cur.execute("TRUNCATE TABLE agg_vn_province_summary")
        cur.execute("TRUNCATE TABLE fact_covid_vn_daily")
        cur.execute("TRUNCATE TABLE dim_province")
        cur.execute("SET FOREIGN_KEY_CHECKS = 1")

        provinces = sorted(df["province_name"].unique())
        cur.executemany(
            "INSERT INTO dim_province (province_name, region, population) VALUES (%s, %s, %s)",
            [(name, None, None) for name in provinces],
        )

        dates = sorted(df["date_raw"].dt.date.unique())
        date_rows = []
        for d in dates:
            iso_cal = d.isocalendar()
            date_rows.append((
                int(d.strftime("%Y%m%d")),
                d,
                d.year,
                d.month,
                iso_cal[1],
                (d.month - 1) // 3 + 1,
            ))
        cur.executemany(
            """
            INSERT IGNORE INTO dim_date (date_id, full_date, year, month, week, quarter)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            date_rows,
        )
        conn.commit()


def load_fact_and_serving(conn, df: pd.DataFrame) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT province_id, province_name FROM dim_province")
        province_map = {name: province_id for province_id, name in cur.fetchall()}

        rows = []
        for r in df.itertuples(index=False):
            province_id = province_map.get(r.province_name)
            date_id = int(r.date_raw.strftime("%Y%m%d"))
            if province_id is None:
                continue
            rows.append((
                province_id,
                date_id,
                int(r.new_cases),
                0,
                int(r.total_cases),
                int(r.total_deaths),
                0,
                0,
            ))

        cur.executemany(
            """
            INSERT INTO fact_covid_vn_daily
                (province_id, date_id, new_cases, new_deaths, total_cases,
                 total_deaths, recovered, active_cases)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                new_cases = VALUES(new_cases),
                total_cases = VALUES(total_cases),
                total_deaths = VALUES(total_deaths)
            """,
            rows,
        )

        cur.execute("""
            INSERT INTO agg_vn_province_summary
                (province_id, province_name, latest_total_cases, latest_total_deaths,
                 latest_new_cases, active_cases, last_updated)
            SELECT
                p.province_id,
                p.province_name,
                f.total_cases,
                f.total_deaths,
                f.new_cases,
                f.active_cases,
                NOW()
            FROM dim_province p
            JOIN (
                SELECT province_id, MAX(date_id) AS max_date_id
                FROM fact_covid_vn_daily
                GROUP BY province_id
            ) latest ON latest.province_id = p.province_id
            JOIN fact_covid_vn_daily f
              ON f.province_id = latest.province_id
             AND f.date_id = latest.max_date_id
        """)

        cur.execute("""
            INSERT INTO agg_daily_vn (date_id, total_new_cases_vn, total_new_deaths_vn)
            SELECT date_id, SUM(new_cases), SUM(new_deaths)
            FROM fact_covid_vn_daily
            GROUP BY date_id
            ON DUPLICATE KEY UPDATE
                total_new_cases_vn = VALUES(total_new_cases_vn),
                total_new_deaths_vn = VALUES(total_new_deaths_vn)
        """)

        cur.execute(
            """
            INSERT INTO etl_job_log
                (job_name, status, rows_processed, started_at, finished_at, error_message)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            ("load_vietnam_provinces", "success", len(rows), datetime.now(), datetime.now(), None),
        )
        conn.commit()
    return len(rows)


def main():
    started = datetime.now()
    password = get_db_password(prompt=True)
    conn = connect_db(password)
    try:
        print("[1/4] Doc CSV Viet Nam...")
        df = load_csv()
        print(f"      Doc duoc {len(df):,} dong, {df['province_name'].nunique()} tinh/thanh.")
        print("[2/4] Cap nhat schema neu can...")
        ensure_schema(conn)
        print("[3/4] Nap dim_province va dim_date...")
        load_dimensions(conn, df)
        print("[4/4] Nap fact_covid_vn_daily va agg_*...")
        rows_loaded = load_fact_and_serving(conn, df)
        print(f"\nHOAN TAT - da nap {rows_loaded:,} dong du lieu Viet Nam.")
    except Exception as exc:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO etl_job_log
                    (job_name, status, rows_processed, started_at, finished_at, error_message)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                ("load_vietnam_provinces", "failed", 0, started, datetime.now(), str(exc)),
            )
            conn.commit()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
