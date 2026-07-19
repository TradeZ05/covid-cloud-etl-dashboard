from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import pymysql
import requests

from db_config import get_db_host, get_db_name, get_db_password, get_db_port, get_db_user


DB_HOST = get_db_host()
DB_PORT = get_db_port()
DB_USER = get_db_user()
DB_NAME = get_db_name()

SOURCE_URL = "https://www.who.int/api/emergencies/diseaseoutbreaknews"
SOURCE_URLS = [
    "https://www.who.int/api/emergencies/diseaseoutbreaknews",
    "https://www.who.int/api/news/diseaseoutbreaknews",
    "https://www.who.int/api/hubs/diseaseoutbreaknews",
]
SOURCE_PAGE = "https://www.who.int/emergencies/disease-outbreak-news"
PROJECT_ROOT = Path(__file__).resolve().parent
RAW_JSON = PROJECT_ROOT / "data" / "raw" / "who_disease_outbreak_news.json"


DISEASE_PATTERNS = [
    ("Cholera", r"\bcholera\b"),
    ("Dengue", r"\bdengue\b"),
    ("Mpox", r"\bmpox\b|monkeypox"),
    ("Measles", r"\bmeasles\b"),
    ("Yellow fever", r"yellow fever"),
    ("Ebola", r"\bebola\b|sudan virus|bundibugyo"),
    ("Marburg virus disease", r"\bmarburg\b"),
    ("MERS", r"\bmers\b|middle east respiratory syndrome"),
    ("Avian influenza", r"avian influenza|influenza a\(h5|h5n1|h9n2|h7n9"),
    ("Influenza", r"\binfluenza\b"),
    ("Poliomyelitis", r"polio|poliovirus|poliomyelitis"),
    ("Meningitis", r"\bmeningitis\b"),
    ("Lassa fever", r"lassa fever"),
    ("Rift Valley fever", r"rift valley fever"),
    ("Zika virus disease", r"\bzika\b"),
    ("Nipah virus infection", r"\bnipah\b"),
    ("Chikungunya", r"\bchikungunya\b"),
    ("Oropouche virus disease", r"\boropouche\b"),
    ("Anthrax", r"\banthrax\b"),
    ("COVID-19", r"covid-19|sars-cov-2"),
]


def connect_db(password: str):
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=password,
        database=DB_NAME,
        charset="utf8mb4",
    )


def strip_html(value: Any) -> str:
    text = "" if value is None else str(value)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def first_value(item: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in item and item[key] not in (None, ""):
            return item[key]
    return None


def parse_date(value: Any):
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d", "%d %B %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(str(value)[:30], fmt).date()
        except ValueError:
            continue
    return None


def detect_disease(title: str, body: str) -> str:
    haystack = f"{title} {body}".lower()
    for disease, pattern in DISEASE_PATTERNS:
        if re.search(pattern, haystack, flags=re.I):
            return disease
    title_part = re.split(r"\s+[–—-]\s+|,", title, maxsplit=1)[0].strip()
    return title_part[:120] or "Other outbreak"


def detect_location(title: str) -> str:
    parts = re.split(r"\s+[–—-]\s+", title, maxsplit=1)
    if len(parts) > 1 and parts[1].strip():
        return parts[1].strip()[:255]
    bits = [b.strip() for b in title.split(",") if b.strip()]
    if len(bits) >= 2:
        return bits[-1][:255]
    return "Global / multiple locations"


def normalize_url(item: dict[str, Any]) -> str:
    don_id = first_value(item, "DonId", "UrlName")
    if don_id:
        return f"https://www.who.int/emergencies/disease-outbreak-news/item/{don_id}"
    raw = first_value(item, "Url", "url", "ItemDefaultUrl", "Link", "link")
    if not raw:
        raw = first_value(item, "RelativeUrl", "relativeUrl")
    if not raw:
        return SOURCE_PAGE
    raw = str(raw)
    if raw.startswith("http"):
        return raw
    if raw.startswith("/"):
        return f"https://www.who.int/emergencies/disease-outbreak-news/item{raw}"
    return f"https://www.who.int/{raw.lstrip('/')}"


def parse_count_near_terms(text: str, terms: list[str]) -> int | None:
    total = 0
    found = False
    for term in terms:
        pattern_before = rf"(\d[\d,\. ]*)\s+(?:suspected\s+|confirmed\s+|probable\s+)?{term}s?\b"
        pattern_after = rf"\b{term}s?\b(?:\s+\w+){{0,5}}\s+(\d[\d,\. ]*)"
        for pattern in (pattern_before, pattern_after):
            for match in re.finditer(pattern, text, flags=re.I):
                raw = match.group(1).replace(",", "").replace(".", "").replace(" ", "")
                if raw.isdigit():
                    total += int(raw)
                    found = True
    return total if found else None


def extract_numbers(text: str) -> tuple[int | None, int | None]:
    cases = parse_count_near_terms(text, ["case", "infection"])
    deaths = parse_count_near_terms(text, ["death", "fatalit"])
    return cases, deaths


def extract_items_from_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("value", "items", "Items"):
            items = payload.get(key)
            if isinstance(items, list):
                return items
    raise ValueError("WHO API response khong dung dinh dang danh sach.")


def fetch_who_items(limit: int = 500) -> list[dict[str, Any]]:
    headers = {
        "Accept": "application/json",
        "User-Agent": "covid-cloud-etl-dashboard/1.0",
    }
    param_options = [
        {"$top": limit, "$orderby": "PublicationDate desc"},
        {"$top": limit},
        {"take": limit, "sortExpression": "PublicationDate DESC"},
        {},
    ]
    errors: list[str] = []
    for url in SOURCE_URLS:
        for params in param_options:
            try:
                response = requests.get(url, params=params, headers=headers, timeout=40)
                response.raise_for_status()
                items = extract_items_from_payload(response.json())
                if items:
                    print(f"      WHO API OK: {response.url}")
                    return items[:limit]
            except requests.RequestException as exc:
                status = getattr(exc.response, "status_code", "network")
                errors.append(f"{url} params={params} -> {status}")
            except ValueError as exc:
                errors.append(f"{url} params={params} -> {exc}")
    raise RuntimeError("Khong tai duoc WHO Disease Outbreak News. Thu loi: " + " | ".join(errors[:6]))


def transform_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for item in items:
        title = strip_html(first_value(item, "Title", "title", "Name", "name"))
        if not title:
            continue
        summary = strip_html(first_value(item, "Summary", "summary", "Description", "description"))
        overview = strip_html(first_value(
            item,
            "Overview", "overview", "Response", "response", "Epidemiology", "epidemiology",
            "Assessment", "assessment", "Advice", "advice", "Body", "body", "Content", "content",
        ))
        body = f"{summary} {overview}"
        date_value = first_value(item, "PublicationDateAndTime", "publicationDateAndTime", "Date", "date")
        published = parse_date(date_value)
        if not published:
            continue
        who_id = str(first_value(item, "Id", "id", "ItemId", "itemId") or normalize_url(item))[:80]
        cases, deaths = extract_numbers(body)
        cfr = round(deaths / cases * 100, 2) if cases and deaths is not None else None
        rows.append({
            "who_id": who_id,
            "title": title[:500],
            "disease": detect_disease(title, body),
            "location_text": detect_location(title),
            "publication_date": published,
            "year": published.year,
            "month": published.month,
            "reported_cases": cases,
            "reported_deaths": deaths,
            "case_fatality_rate": cfr,
            "source_url": normalize_url(item)[:500],
            "summary": summary[:4000],
            "overview_text": overview[:16000],
        })
    return rows


def ensure_schema(conn):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS raw_who_outbreak_news (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                who_id VARCHAR(80) UNIQUE,
                title VARCHAR(500),
                disease VARCHAR(120),
                location_text VARCHAR(255),
                publication_date DATE,
                year INT,
                month INT,
                reported_cases BIGINT,
                reported_deaths BIGINT,
                case_fatality_rate DECIMAL(8,2),
                source_url VARCHAR(500),
                summary TEXT,
                overview_text MEDIUMTEXT,
                ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                KEY idx_who_disease_date (disease, publication_date),
                KEY idx_who_publication_date (publication_date)
            ) ENGINE=InnoDB
        """)
        conn.commit()


def save_raw_snapshot(items: list[dict[str, Any]]):
    RAW_JSON.parent.mkdir(parents=True, exist_ok=True)
    RAW_JSON.write_text(json.dumps(items, ensure_ascii=False, default=str, indent=2), encoding="utf-8")


def load_rows(conn, rows: list[dict[str, Any]]) -> int:
    sql = """
        INSERT INTO raw_who_outbreak_news (
            who_id, title, disease, location_text, publication_date, year, month,
            reported_cases, reported_deaths, case_fatality_rate, source_url,
            summary, overview_text
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            title = VALUES(title),
            disease = VALUES(disease),
            location_text = VALUES(location_text),
            publication_date = VALUES(publication_date),
            year = VALUES(year),
            month = VALUES(month),
            reported_cases = VALUES(reported_cases),
            reported_deaths = VALUES(reported_deaths),
            case_fatality_rate = VALUES(case_fatality_rate),
            source_url = VALUES(source_url),
            summary = VALUES(summary),
            overview_text = VALUES(overview_text),
            ingested_at = CURRENT_TIMESTAMP
    """
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE raw_who_outbreak_news")
        for row in rows:
            cur.execute(sql, (
                row["who_id"], row["title"], row["disease"], row["location_text"],
                row["publication_date"], row["year"], row["month"],
                row["reported_cases"], row["reported_deaths"], row["case_fatality_rate"],
                row["source_url"], row["summary"], row["overview_text"],
            ))
        conn.commit()
    return len(rows)


def log_job(conn, status: str, rows_processed: int, started_at: datetime, error_message: str | None = None):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO etl_job_log (job_name, status, rows_processed, started_at, finished_at, error_message)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            ("who_outbreak_load", status, rows_processed, started_at, datetime.now(), error_message),
        )
        conn.commit()


def main():
    started_at = datetime.now()
    password = get_db_password(prompt=True)
    conn = connect_db(password)
    try:
        print("[1/4] Tai ban tin dich benh tu WHO Disease Outbreak News...")
        items = fetch_who_items()
        save_raw_snapshot(items)
        print(f"      Raw items: {len(items):,}. Snapshot: {RAW_JSON}")

        print("[2/4] Transform: nhan dien dich benh, khu vuc, so ca/tu vong neu co...")
        rows = transform_items(items)
        diseases = Counter(row["disease"] for row in rows).most_common(8)
        print(f"      Rows hop le: {len(rows):,}. Top disease: {diseases}")

        print("[3/4] Load vao MySQL raw_who_outbreak_news...")
        ensure_schema(conn)
        loaded = load_rows(conn, rows)

        print("[4/4] Ghi log ETL...")
        log_job(conn, "success", loaded, started_at)
        print(f"HOAN TAT - da nap {loaded:,} ban tin WHO vao warehouse.")
    except Exception as exc:
        try:
            log_job(conn, "failed", 0, started_at, str(exc)[:1000])
        finally:
            raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
