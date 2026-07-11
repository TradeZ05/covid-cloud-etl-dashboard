"""
transform_load.py — Giai đoạn 3 + 4 của pipeline.
Việc script này làm:
  1. Đọc dữ liệu THÔ từ bảng raw_covid_data (tầng Data Lake)
  2. TRANSFORM: làm sạch, ép kiểu đúng, tính vaccination_rate, case_fatality_rate
  3. LOAD: nạp vào dim_country, dim_date, fact_covid_global_daily (Data Warehouse)
  4. Tính lại agg_country_summary, agg_daily_global (Serving Layer) để web đọc nhanh

Lưu ý: bản này xử lý phần TOÀN CẦU (OWID). Phần Việt Nam theo tỉnh sẽ làm
riêng ở script khác (vn_load.py) vì nguồn dữ liệu khác (Kaggle), chưa có ở bước này.

Cách chạy:
    pip install pandas pymysql --break-system-packages
    python transform_load.py
"""

import sys
from datetime import datetime

import pandas as pd
import pymysql

from db_config import get_db_host, get_db_name, get_db_password, get_db_port, get_db_user

DB_HOST = get_db_host()
DB_PORT = get_db_port()
DB_USER = get_db_user()
DB_NAME = get_db_name()


def connect_db(password: str):
    return pymysql.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=password, database=DB_NAME,
        charset="utf8mb4",
    )


def clean_cell(v):
    if pd.isna(v):
        return None
    return str(v)


def clean_number(v):
    if pd.isna(v):
        return None
    return v


def parse_date_column(series: pd.Series) -> pd.Series:
    raw = series.astype("string").str.strip()
    parsed = pd.to_datetime(raw, errors="coerce")

    # Some CSV/Excel exports are stored as dd/mm/yyyy. Try that format too for
    # rows that the default parser could not understand.
    missing = parsed.isna() & raw.notna() & (raw != "")
    if missing.any():
        parsed_alt = pd.to_datetime(raw[missing], errors="coerce", dayfirst=True)
        parsed.loc[missing] = parsed_alt

    return parsed


# ============================================================
# BƯỚC 1: Đọc dữ liệu thô từ raw_covid_data
# ============================================================
def read_raw_data(conn) -> pd.DataFrame:
    print("[1/6] Đang đọc dữ liệu từ raw_covid_data...")
    df = pd.read_sql("SELECT * FROM raw_covid_data", conn)
    print(f"      Đọc được {len(df):,} dòng thô.")
    return df


# ============================================================
# BƯỚC 2: TRANSFORM — làm sạch, ép kiểu, tính toán
# ============================================================
def transform(df: pd.DataFrame) -> pd.DataFrame:
    print("[2/6] Đang làm sạch và tính toán (Transform)...")

    # Loại các dòng không phải quốc gia thật (OWID gộp cả châu lục/thế giới
    # vào cùng file, mã bắt đầu bằng "OWID_", ví dụ OWID_WRL = World)
    df = df.copy()
    before = len(df)
    df["iso_code"] = df["iso_code"].astype("string").str.strip()
    df = df[df["iso_code"].notna() & ~df["iso_code"].str.startswith("OWID_")]
    header_rows = df["iso_code"].eq("iso_code").sum()
    if header_rows:
        print(f"      Bo {header_rows:,} dong bi nap nham header CSV vao raw_covid_data.")
        df = df[df["iso_code"] != "iso_code"]
    print(f"      Loại bỏ dòng châu lục/thế giới: {before:,} → {len(df):,} dòng")

    # Ép kiểu đúng — dữ liệu thô đang toàn dạng string
    original_date_raw = df["date_raw"].copy()
    df["date_raw"] = parse_date_column(df["date_raw"])
    numeric_cols = ["new_cases", "new_deaths", "total_cases", "total_deaths",
                     "people_vaccinated", "population"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Bỏ dòng không có ngày hợp lệ (không xác định được thuộc kỳ nào)
    invalid_date_count = df["date_raw"].isna().sum()
    if invalid_date_count:
        examples = (
            pd.DataFrame({
                "iso_code": df.loc[df["date_raw"].isna(), "iso_code"],
                "date_raw": original_date_raw.loc[df["date_raw"].isna()],
            })
            .head(5)
            .to_dict("records")
        )
        print(f"      Bo {invalid_date_count:,} dong vi date_raw khong parse duoc. Mau: {examples}")
    df = df.dropna(subset=["date_raw"])

    if df.empty:
        raise ValueError(
            "Khong con dong hop le sau Transform. raw_covid_data co the dang bi nap sai "
            "(vi du gia tri iso_code/date_raw la ten cot). Hay TRUNCATE raw_covid_data "
            "roi chay lai extract.py truoc khi chay transform_load.py."
        )

    before_dedup = len(df)
    df = df.sort_values("id").drop_duplicates(subset=["iso_code", "date_raw"], keep="last")
    if before_dedup != len(df):
        print(f"      Loai bo dong trung iso_code + date: {before_dedup:,} -> {len(df):,} dong")

    # Tính 2 cột phái sinh — đây chính là phần "Transform" quan trọng nhất
    df["vaccination_rate"] = (df["people_vaccinated"] / df["population"] * 100).round(2)
    df["case_fatality_rate"] = (df["total_deaths"] / df["total_cases"] * 100).round(2)
    df[["vaccination_rate", "case_fatality_rate"]] = df[["vaccination_rate", "case_fatality_rate"]].replace(
        [float("inf"), float("-inf")], pd.NA
    )

    # new_cases/new_deaths không thể âm (dữ liệu nguồn thỉnh thoảng bị lỗi
    # do điều chỉnh số liệu hồi tố) — ép về 0 nếu âm, tránh sai lệch biểu đồ
    df["new_cases"] = df["new_cases"].clip(lower=0)
    df["new_deaths"] = df["new_deaths"].clip(lower=0)

    print(f"      Sau transform: {len(df):,} dòng sẵn sàng để load.")
    return df


# ============================================================
# BƯỚC 3: LOAD — dim_country
# ============================================================
def load_dim_country(conn, df: pd.DataFrame) -> dict:
    print("[3/6] Đang nạp dim_country...")
    countries = (
        df.sort_values("date_raw")
        .groupby("iso_code")
        .agg(country_name=("location", "last"),
             continent=("continent", "last"),
             population=("population", "last"))
        .reset_index()
    )

    sql = """
        INSERT INTO dim_country (iso_code, country_name, continent, population)
        VALUES (%s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            country_name = VALUES(country_name),
            continent = VALUES(continent),
            population = VALUES(population)
    """
    with conn.cursor() as cur:
        for _, r in countries.iterrows():
            cur.execute(sql, (
                r["iso_code"], clean_cell(r["country_name"]),
                clean_cell(r["continent"]), clean_cell(r["population"]),
            ))
        conn.commit()

    # Lấy lại map iso_code -> country_id để dùng cho fact table
    with conn.cursor() as cur:
        cur.execute("SELECT country_id, iso_code FROM dim_country")
        id_map = {iso_code: country_id for country_id, iso_code in cur.fetchall()}
    print(f"      Đã nạp {len(countries):,} quốc gia.")
    return id_map


# ============================================================
# BƯỚC 4: LOAD — dim_date
# ============================================================
def load_dim_date(conn, df: pd.DataFrame) -> dict:
    print("[4/6] Đang nạp dim_date...")
    dates = df["date_raw"].dt.date.unique()

    sql = """
        INSERT IGNORE INTO dim_date (date_id, full_date, year, month, week, quarter)
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    id_map = {}
    with conn.cursor() as cur:
        for d in dates:
            date_id = int(d.strftime("%Y%m%d"))
            iso_cal = d.isocalendar()
            cur.execute(sql, (
                date_id, d, d.year, d.month, iso_cal[1], (d.month - 1) // 3 + 1,
            ))
            id_map[d] = date_id
        conn.commit()
    print(f"      Đã nạp {len(dates):,} ngày.")
    return id_map


# ============================================================
# BƯỚC 5: LOAD — fact_covid_global_daily
# ============================================================
def load_fact_table(conn, df: pd.DataFrame, country_id_map: dict, date_id_map: dict) -> int:
    print("[5/6] Đang nạp fact_covid_global_daily...")
    sql = """
        INSERT INTO fact_covid_global_daily
            (country_id, date_id, new_cases, new_deaths, total_cases,
             total_deaths, people_vaccinated, vaccination_rate, case_fatality_rate)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            new_cases = VALUES(new_cases), new_deaths = VALUES(new_deaths),
            total_cases = VALUES(total_cases), total_deaths = VALUES(total_deaths),
            people_vaccinated = VALUES(people_vaccinated),
            vaccination_rate = VALUES(vaccination_rate),
            case_fatality_rate = VALUES(case_fatality_rate)
    """
    rows = []
    for _, r in df.iterrows():
        country_id = country_id_map.get(r["iso_code"])
        date_id = date_id_map.get(r["date_raw"].date())
        if country_id is None or date_id is None:
            continue
        rows.append((
            country_id, date_id,
            clean_cell(r["new_cases"]), clean_cell(r["new_deaths"]),
            clean_cell(r["total_cases"]), clean_cell(r["total_deaths"]),
            clean_cell(r["people_vaccinated"]), clean_cell(r["vaccination_rate"]),
            clean_cell(r["case_fatality_rate"]),
        ))

    with conn.cursor() as cur:
        batch_size = 1000
        for i in range(0, len(rows), batch_size):
            cur.executemany(sql, rows[i:i + batch_size])
            conn.commit()
            print(f"      Đã nạp {min(i + batch_size, len(rows)):,}/{len(rows):,} dòng")

    print(f"      Nạp fact table xong: {len(rows):,} dòng.")
    return len(rows)


# ============================================================
# BƯỚC 6: Tính lại Serving Layer — agg_country_summary, agg_daily_global
# ============================================================
def refresh_serving_layer(conn):
    print("[6/6] Đang tính lại Serving Layer (agg_country_summary, agg_daily_global)...")

    with conn.cursor() as cur:
        # ---- agg_daily_global: tổng ca nhiễm/tử vong mới theo từng ngày, toàn cầu
        cur.execute("TRUNCATE TABLE agg_daily_global")
        cur.execute("""
            INSERT INTO agg_daily_global (date_id, total_new_cases_global, total_new_deaths_global)
            SELECT date_id, SUM(new_cases), SUM(new_deaths)
            FROM fact_covid_global_daily
            GROUP BY date_id
        """)

        # ---- agg_country_summary: số liệu mới nhất + xu hướng 7 ngày mỗi quốc gia
        cur.execute("TRUNCATE TABLE agg_country_summary")
        cur.execute("""
            INSERT INTO agg_country_summary
                (country_id, country_name, latest_total_cases, latest_total_deaths,
                 latest_vaccination_rate, trend_7d_cases, last_updated)
            SELECT
                f.country_id,
                c.country_name,
                latest.total_cases,
                latest.total_deaths,
                (
                    SELECT f2.vaccination_rate
                    FROM fact_covid_global_daily f2
                    WHERE f2.country_id = f.country_id
                      AND f2.vaccination_rate IS NOT NULL
                    ORDER BY f2.date_id DESC
                    LIMIT 1
                ),
                CASE WHEN prev7.cases_prev7 > 0
                     THEN ROUND((last7.cases_last7 - prev7.cases_prev7) / prev7.cases_prev7 * 100, 2)
                     ELSE NULL END,
                NOW()
            FROM (
                SELECT country_id, MAX(date_id) AS max_date_id
                FROM fact_covid_global_daily GROUP BY country_id
            ) f
            JOIN dim_country c ON c.country_id = f.country_id
            JOIN fact_covid_global_daily latest
                ON latest.country_id = f.country_id AND latest.date_id = f.max_date_id
            LEFT JOIN (
                SELECT country_id, SUM(new_cases) AS cases_last7
                FROM fact_covid_global_daily
                WHERE date_id >= (SELECT MAX(date_id) FROM fact_covid_global_daily) - 7
                GROUP BY country_id
            ) last7 ON last7.country_id = f.country_id
            LEFT JOIN (
                SELECT country_id, SUM(new_cases) AS cases_prev7
                FROM fact_covid_global_daily
                WHERE date_id < (SELECT MAX(date_id) FROM fact_covid_global_daily) - 7
                  AND date_id >= (SELECT MAX(date_id) FROM fact_covid_global_daily) - 14
                GROUP BY country_id
            ) prev7 ON prev7.country_id = f.country_id
        """)
        conn.commit()
    print("      Serving Layer đã cập nhật xong.")


def refresh_serving_layer(conn):
    print("[6/6] Dang tinh lai Serving Layer (agg_country_summary, agg_daily_global)...")

    with conn.cursor() as cur:
        print("      Cap nhat agg_daily_global...")
        cur.execute("TRUNCATE TABLE agg_daily_global")
        cur.execute("""
            INSERT INTO agg_daily_global (date_id, total_new_cases_global, total_new_deaths_global)
            SELECT date_id, SUM(new_cases), SUM(new_deaths)
            FROM fact_covid_global_daily
            GROUP BY date_id
        """)

        print("      Tao bang tam latest / vaccine / trend...")
        cur.execute("TRUNCATE TABLE agg_country_summary")

        cur.execute("DROP TEMPORARY TABLE IF EXISTS tmp_latest_country")
        cur.execute("""
            CREATE TEMPORARY TABLE tmp_latest_country AS
            SELECT f.country_id, f.date_id, f.total_cases, f.total_deaths
            FROM fact_covid_global_daily f
            JOIN (
                SELECT country_id, MAX(date_id) AS max_date_id
                FROM fact_covid_global_daily
                GROUP BY country_id
            ) latest
              ON latest.country_id = f.country_id
             AND latest.max_date_id = f.date_id
        """)

        cur.execute("DROP TEMPORARY TABLE IF EXISTS tmp_latest_vaccine")
        cur.execute("""
            CREATE TEMPORARY TABLE tmp_latest_vaccine AS
            SELECT country_id, vaccination_rate
            FROM (
                SELECT
                    country_id,
                    vaccination_rate,
                    ROW_NUMBER() OVER (PARTITION BY country_id ORDER BY date_id DESC) AS rn
                FROM fact_covid_global_daily
                WHERE vaccination_rate IS NOT NULL
            ) ranked
            WHERE rn = 1
        """)

        cur.execute("DROP TEMPORARY TABLE IF EXISTS tmp_global_max_date")
        cur.execute("""
            CREATE TEMPORARY TABLE tmp_global_max_date AS
            SELECT MAX(d.full_date) AS max_full_date
            FROM fact_covid_global_daily f
            JOIN dim_date d ON d.date_id = f.date_id
        """)

        cur.execute("DROP TEMPORARY TABLE IF EXISTS tmp_last7")
        cur.execute("""
            CREATE TEMPORARY TABLE tmp_last7 AS
            SELECT f.country_id, SUM(f.new_cases) AS cases_last7
            FROM fact_covid_global_daily f
            JOIN dim_date d ON d.date_id = f.date_id
            JOIN tmp_global_max_date m
            WHERE d.full_date > DATE_SUB(m.max_full_date, INTERVAL 7 DAY)
              AND d.full_date <= m.max_full_date
            GROUP BY f.country_id
        """)

        cur.execute("DROP TEMPORARY TABLE IF EXISTS tmp_prev7")
        cur.execute("""
            CREATE TEMPORARY TABLE tmp_prev7 AS
            SELECT f.country_id, SUM(f.new_cases) AS cases_prev7
            FROM fact_covid_global_daily f
            JOIN dim_date d ON d.date_id = f.date_id
            JOIN tmp_global_max_date m
            WHERE d.full_date > DATE_SUB(m.max_full_date, INTERVAL 14 DAY)
              AND d.full_date <= DATE_SUB(m.max_full_date, INTERVAL 7 DAY)
            GROUP BY f.country_id
        """)

        print("      Ghi agg_country_summary...")
        cur.execute("""
            INSERT INTO agg_country_summary
                (country_id, country_name, latest_total_cases, latest_total_deaths,
                 latest_vaccination_rate, trend_7d_cases, last_updated)
            SELECT
                latest.country_id,
                c.country_name,
                latest.total_cases,
                latest.total_deaths,
                vax.vaccination_rate,
                CASE WHEN prev7.cases_prev7 > 0
                     THEN ROUND((last7.cases_last7 - prev7.cases_prev7) / prev7.cases_prev7 * 100, 2)
                     ELSE NULL END,
                NOW()
            FROM tmp_latest_country latest
            JOIN dim_country c ON c.country_id = latest.country_id
            LEFT JOIN tmp_latest_vaccine vax ON vax.country_id = latest.country_id
            LEFT JOIN tmp_last7 last7 ON last7.country_id = latest.country_id
            LEFT JOIN tmp_prev7 prev7 ON prev7.country_id = latest.country_id
        """)
        conn.commit()

    print("      Serving Layer da cap nhat xong.")


def log_job(conn, job_name: str, status: str, rows_processed: int,
            started_at: datetime, error_message: str = None):
    sql = """
        INSERT INTO etl_job_log
            (job_name, status, rows_processed, started_at, finished_at, error_message)
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    with conn.cursor() as cur:
        cur.execute(sql, (job_name, status, rows_processed, started_at, datetime.now(), error_message))
        conn.commit()


def main():
    started_at = datetime.now()
    password = get_db_password(prompt=True)
    conn = connect_db(password)

    try:
        raw_df = read_raw_data(conn)
        clean_df = transform(raw_df)
        country_id_map = load_dim_country(conn, clean_df)
        date_id_map = load_dim_date(conn, clean_df)
        rows_loaded = load_fact_table(conn, clean_df, country_id_map, date_id_map)
        refresh_serving_layer(conn)

        log_job(conn, "transform_load_global", "success", rows_loaded, started_at)
        print(f"\n✅ HOÀN TẤT — đã transform + load {rows_loaded:,} dòng vào Data Warehouse.")
        print("   Web giờ có thể đọc dữ liệu thật từ agg_country_summary / agg_daily_global.")
    except Exception as e:
        log_job(conn, "transform_load_global", "failed", 0, started_at, error_message=str(e))
        print(f"\n❌ LỖI: {e}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
