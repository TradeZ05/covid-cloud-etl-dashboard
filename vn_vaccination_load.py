from io import StringIO
from datetime import datetime, date
from pathlib import Path

import pandas as pd
import pymysql
import requests

from db_config import get_db_host, get_db_name, get_db_password, get_db_port, get_db_user

DB_HOST = get_db_host()
DB_PORT = get_db_port()
DB_USER = get_db_user()
DB_NAME = get_db_name()
SOURCE_URL = "https://en.wikipedia.org/wiki/COVID-19_vaccination_in_Vietnam"
PROJECT_ROOT = Path(__file__).resolve().parent
RAW_SNAPSHOT = PROJECT_ROOT / "data" / "raw" / "vn_vaccination_by_locality.csv"
LEGACY_RAW_SNAPSHOT = PROJECT_ROOT / "vn_vaccination_by_locality.csv"


def connect_db(password: str):
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=password,
        database=DB_NAME,
        charset="utf8mb4",
    )


def clean_number(value):
    if pd.isna(value):
        return None
    text = str(value).strip()
    if not text or text in {"-", "—", "nan"}:
        return None
    text = text.replace(",", "").replace("\xa0", "").replace("%", "")
    try:
        return int(float(text))
    except ValueError:
        return None


def clean_decimal(value):
    if pd.isna(value):
        return None
    text = str(value).strip()
    if not text or text in {"-", "—", "nan"}:
        return None
    text = text.replace(",", "").replace("\xa0", "").replace("%", "")
    try:
        return round(float(text), 2)
    except ValueError:
        return None


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    normalized = {}
    for col in df.columns:
        key = " ".join(str(col).split()).lower()
        if "locality" in key:
            normalized[col] = "province_name"
        elif "population" in key:
            normalized[col] = "population"
        elif "distributed" in key:
            normalized[col] = "doses_distributed"
        elif "administered per 100" in key:
            normalized[col] = "doses_per_100"
        elif "administered" in key:
            normalized[col] = "doses_administered"
    df = df.rename(columns=normalized)
    required = {"province_name", "population", "doses_distributed", "doses_administered"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Khong tim thay cac cot can thiet trong bang Wikipedia: {sorted(missing)}")
    if "doses_per_100" not in df.columns:
        df["doses_per_100"] = None
    return df


def extract_vaccination_table() -> pd.DataFrame:
    response = requests.get(
        SOURCE_URL,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0 Safari/537.36"
            )
        },
        timeout=30,
    )
    response.raise_for_status()
    tables = pd.read_html(StringIO(response.text))
    candidates = []
    for table in tables:
        text_cols = " ".join(str(c) for c in table.columns).lower()
        if "locality" in text_cols and "doses administered" in text_cols:
            candidates.append(table)
    if not candidates:
        raise ValueError("Khong tim thay bang 'By locality' tren Wikipedia.")

    df = normalize_columns(candidates[0])
    df = df[["province_name", "population", "doses_distributed", "doses_administered", "doses_per_100"]].copy()
    df["province_name"] = (
        df["province_name"]
        .astype(str)
        .str.replace(" province", "", regex=False)
        .str.strip()
    )
    df = df[df["province_name"].notna() & (df["province_name"] != "") & (df["province_name"].str.lower() != "nan")]
    df["population"] = df["population"].apply(clean_number)
    df["doses_distributed"] = df["doses_distributed"].apply(clean_number)
    df["doses_administered"] = df["doses_administered"].apply(clean_number)
    df["doses_per_100"] = df["doses_per_100"].apply(clean_decimal)
    df["doses_per_100"] = df.apply(
        lambda r: round(r["doses_administered"] / r["population"] * 100, 2)
        if pd.isna(r["doses_per_100"]) and r["population"] and r["doses_administered"]
        else r["doses_per_100"],
        axis=1,
    )
    df = df.dropna(subset=["population", "doses_administered"])
    df["source_url"] = SOURCE_URL
    df["snapshot_date"] = date.today()
    RAW_SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(RAW_SNAPSHOT, index=False, encoding="utf-8-sig")
    return df


def ensure_schema(conn):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS raw_vn_vaccination_data (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                province_name VARCHAR(100),
                population BIGINT,
                doses_distributed BIGINT,
                doses_administered BIGINT,
                doses_per_100 DECIMAL(8,2),
                snapshot_date DATE,
                source_url VARCHAR(255),
                ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS fact_vn_vaccination (
                fact_id BIGINT AUTO_INCREMENT PRIMARY KEY,
                province_id INT,
                date_id INT,
                population BIGINT,
                doses_distributed BIGINT,
                doses_administered BIGINT,
                doses_per_100 DECIMAL(8,2),
                UNIQUE KEY uq_vn_vax_province_date (province_id, date_id),
                FOREIGN KEY (province_id) REFERENCES dim_province(province_id),
                FOREIGN KEY (date_id) REFERENCES dim_date(date_id)
            ) ENGINE=InnoDB
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS agg_vn_vaccination_summary (
                province_id INT PRIMARY KEY,
                province_name VARCHAR(100),
                population BIGINT,
                doses_distributed BIGINT,
                doses_administered BIGINT,
                doses_per_100 DECIMAL(8,2),
                last_updated TIMESTAMP,
                FOREIGN KEY (province_id) REFERENCES dim_province(province_id)
            ) ENGINE=InnoDB
        """)
        conn.commit()


def load_to_mysql(conn, df: pd.DataFrame) -> int:
    snapshot = date.today()
    date_id = int(snapshot.strftime("%Y%m%d"))
    iso_cal = snapshot.isocalendar()

    with conn.cursor() as cur:
        cur.execute("SET FOREIGN_KEY_CHECKS = 0")
        cur.execute("TRUNCATE TABLE raw_vn_vaccination_data")
        cur.execute("TRUNCATE TABLE agg_vn_vaccination_summary")
        cur.execute("TRUNCATE TABLE fact_vn_vaccination")
        cur.execute("SET FOREIGN_KEY_CHECKS = 1")

        raw_rows = [
            (
                r.province_name,
                int(r.population),
                int(r.doses_distributed) if pd.notna(r.doses_distributed) else None,
                int(r.doses_administered),
                float(r.doses_per_100) if pd.notna(r.doses_per_100) else None,
                snapshot,
                SOURCE_URL,
            )
            for r in df.itertuples(index=False)
        ]
        cur.executemany(
            """
            INSERT INTO raw_vn_vaccination_data
                (province_name, population, doses_distributed, doses_administered,
                 doses_per_100, snapshot_date, source_url)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            raw_rows,
        )

        cur.execute(
            """
            INSERT IGNORE INTO dim_date (date_id, full_date, year, month, week, quarter)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (date_id, snapshot, snapshot.year, snapshot.month, iso_cal[1], (snapshot.month - 1) // 3 + 1),
        )

        for r in df.itertuples(index=False):
            cur.execute(
                """
                INSERT INTO dim_province (province_name, region, population)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    population = VALUES(population)
                """,
                (r.province_name, None, int(r.population)),
            )

        cur.execute("SELECT province_id, province_name FROM dim_province")
        province_map = {name: province_id for province_id, name in cur.fetchall()}

        fact_rows = []
        for r in df.itertuples(index=False):
            province_id = province_map.get(r.province_name)
            if not province_id:
                continue
            fact_rows.append((
                province_id,
                date_id,
                int(r.population),
                int(r.doses_distributed) if pd.notna(r.doses_distributed) else None,
                int(r.doses_administered),
                float(r.doses_per_100) if pd.notna(r.doses_per_100) else None,
            ))

        cur.executemany(
            """
            INSERT INTO fact_vn_vaccination
                (province_id, date_id, population, doses_distributed, doses_administered, doses_per_100)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                population = VALUES(population),
                doses_distributed = VALUES(doses_distributed),
                doses_administered = VALUES(doses_administered),
                doses_per_100 = VALUES(doses_per_100)
            """,
            fact_rows,
        )

        cur.execute("""
            INSERT INTO agg_vn_vaccination_summary
                (province_id, province_name, population, doses_distributed,
                 doses_administered, doses_per_100, last_updated)
            SELECT
                p.province_id,
                p.province_name,
                f.population,
                f.doses_distributed,
                f.doses_administered,
                f.doses_per_100,
                NOW()
            FROM dim_province p
            JOIN fact_vn_vaccination f ON f.province_id = p.province_id
            WHERE f.date_id = %s
        """, (date_id,))

        cur.execute(
            """
            INSERT INTO etl_job_log
                (job_name, status, rows_processed, started_at, finished_at, error_message)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            ("load_vietnam_vaccination", "success", len(fact_rows), datetime.now(), datetime.now(), None),
        )
        conn.commit()
    return len(fact_rows)


def main():
    started = datetime.now()
    password = get_db_password(prompt=True)
    conn = connect_db(password)
    try:
        print("[1/4] Tai bang tiem chung Viet Nam theo dia phuong...")
        df = extract_vaccination_table()
        print(f"      Tai duoc {len(df):,} dong. Raw snapshot: {RAW_SNAPSHOT.name}")
        print("[2/4] Tao bang MySQL neu can...")
        ensure_schema(conn)
        print("[3/4] Nap Data Lake / Warehouse / Serving...")
        rows = load_to_mysql(conn, df)
        print(f"[4/4] HOAN TAT - da nap {rows:,} dong tiem chung theo dia phuong.")
    except Exception as exc:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO etl_job_log
                        (job_name, status, rows_processed, started_at, finished_at, error_message)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    ("load_vietnam_vaccination", "failed", 0, started, datetime.now(), str(exc)),
                )
                conn.commit()
        finally:
            raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
