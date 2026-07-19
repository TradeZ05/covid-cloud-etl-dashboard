from decimal import Decimal
from typing import Any

import pymysql
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from db_config import get_db_host, get_db_name, get_db_password, get_db_port, get_db_user

DB_HOST = get_db_host()
DB_PORT = get_db_port()
DB_USER = get_db_user()
DB_NAME = get_db_name()


app = FastAPI(title="COVID Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {"status": "ok"}


def to_json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    return value


def run_query(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    password = get_db_password()
    try:
        conn = pymysql.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=password,
            database=DB_NAME,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
        )
    except pymysql.MySQLError as exc:
        raise HTTPException(status_code=500, detail=f"Cannot connect to MySQL: {exc}") from exc

    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    except pymysql.MySQLError as exc:
        raise HTTPException(status_code=500, detail=f"MySQL query failed: {exc}") from exc
    finally:
        conn.close()

    return [{key: to_json_value(value) for key, value in row.items()} for row in rows]


class AssistantRequest(BaseModel):
    message: str


def health_assistant_reply(message: str) -> str:
    text = message.lower()
    emergency_words = ["khó thở", "dau nguc", "đau ngực", "tim tái", "ngất", "co giật", "cấp cứu"]
    if any(word in text for word in emergency_words):
        return (
            "Nếu có dấu hiệu khó thở, đau ngực, tím tái, ngất hoặc tình trạng nặng lên nhanh, "
            "hãy gọi cấp cứu 115 hoặc đến cơ sở y tế gần nhất ngay. Thông tin này chỉ để tham khảo, "
            "không thay thế chẩn đoán của bác sĩ."
        )
    if any(word in text for word in ["triệu chứng", "trieu chung", "dấu hiệu", "dau hieu"]):
        return (
            "Triệu chứng COVID-19 thường gặp gồm sốt, ho, đau họng, nghẹt mũi, mệt mỏi, đau đầu, "
            "đau cơ, mất vị giác/khứu giác và đôi khi tiêu chảy. Một số dấu hiệu cần đi khám sớm là "
            "khó thở, đau tức ngực, lơ mơ, tím môi hoặc sốt cao kéo dài. Đây là thông tin tham khảo."
        )
    if any(word in text for word in ["phòng", "phong", "ngừa", "ngua", "tránh", "tranh"]):
        return (
            "Để giảm nguy cơ lây nhiễm, nên tiêm vaccine theo khuyến cáo, đeo khẩu trang ở nơi đông người "
            "hoặc không gian kín, rửa tay thường xuyên, giữ thông khí tốt và ở nhà khi có triệu chứng hô hấp. "
            "Thông tin này không thay thế tư vấn y tế cá nhân."
        )
    if any(word in text for word in ["test", "xét nghiệm", "xet nghiem"]):
        return (
            "Bạn nên xét nghiệm khi có triệu chứng nghi COVID-19, sau tiếp xúc gần với ca bệnh, hoặc khi cần "
            "bảo vệ người có nguy cơ cao. Nếu kết quả âm tính nhưng triệu chứng vẫn rõ, có thể xét nghiệm lại "
            "sau 24-48 giờ hoặc hỏi cơ sở y tế."
        )
    if any(word in text for word in ["cách ly", "cach ly", "dương tính", "duong tinh"]):
        return (
            "Nếu dương tính, hãy hạn chế tiếp xúc, đeo khẩu trang khi ở gần người khác, nghỉ ngơi, uống đủ nước "
            "và theo dõi triệu chứng. Người có bệnh nền, người cao tuổi, phụ nữ mang thai hoặc có dấu hiệu nặng "
            "nên liên hệ nhân viên y tế."
        )
    return (
        "Mình có thể hỗ trợ thông tin tổng quát về COVID-19 như triệu chứng, phòng ngừa, xét nghiệm, cách ly "
        "và khi nào nên đi khám. Bạn mô tả rõ hơn câu hỏi nhé. Lưu ý: đây là thông tin tham khảo, không thay thế "
        "chẩn đoán hoặc điều trị từ bác sĩ."
    )


@app.get("/")
def root():
    return {
        "service": "COVID Dashboard API",
        "endpoints": [
            "/api/summary/global",
            "/api/countries/top",
            "/api/trends/global",
            "/api/summary/vietnam",
            "/api/vietnam/provinces",
            "/api/vietnam/trends",
            "/api/vietnam/cases/summary",
            "/api/vietnam/cases/trends",
            "/api/vietnam/cases/provinces",
            "/api/etl/jobs",
            "/api/assistant/health",
        ],
    }


@app.get("/api/summary/global")
def global_summary():
    rows = run_query(
        """
        SELECT
            COUNT(*) AS country_count,
            SUM(latest_total_cases) AS total_cases,
            SUM(latest_total_deaths) AS total_deaths,
            ROUND(AVG(latest_vaccination_rate), 2) AS avg_vaccination_rate,
            MAX(last_updated) AS last_updated
        FROM agg_country_summary
        """
    )
    return rows[0] if rows else {}


@app.get("/api/countries/top")
def top_countries(limit: int = Query(default=10, ge=1, le=100)):
    return run_query(
        """
        SELECT
            country_name,
            latest_total_cases,
            latest_total_deaths,
            latest_vaccination_rate,
            trend_7d_cases,
            last_updated
        FROM agg_country_summary
        ORDER BY latest_total_cases DESC
        LIMIT %s
        """,
        (limit,),
    )


@app.get("/api/trends/global")
def global_trends(days: int = Query(default=365, ge=1, le=2000)):
    return run_query(
        """
        SELECT
            d.full_date AS date,
            a.total_new_cases_global,
            a.total_new_deaths_global
        FROM agg_daily_global a
        JOIN dim_date d ON d.date_id = a.date_id
        ORDER BY a.date_id DESC
        LIMIT %s
        """,
        (days,),
    )[::-1]


@app.get("/api/etl/jobs")
def etl_jobs(limit: int = Query(default=20, ge=1, le=100)):
    return run_query(
        """
        SELECT
            job_id,
            job_name,
            status,
            rows_processed,
            started_at,
            finished_at,
            error_message
        FROM etl_job_log
        ORDER BY job_id DESC
        LIMIT %s
        """,
        (limit,),
    )


@app.get("/api/summary/vietnam")
def vietnam_summary():
    rows = run_query(
        """
        SELECT
            COUNT(*) AS province_count,
            SUM(population) AS population,
            SUM(doses_distributed) AS doses_distributed,
            SUM(doses_administered) AS doses_administered,
            ROUND(SUM(doses_administered) / NULLIF(SUM(population), 0) * 100, 2) AS doses_per_100,
            ROUND(AVG(doses_per_100), 2) AS avg_doses_per_100,
            MAX(last_updated) AS last_updated
        FROM agg_vn_vaccination_summary
        """
    )
    return rows[0] if rows else {}


@app.get("/api/vietnam/provinces")
def vietnam_provinces(limit: int = Query(default=15, ge=1, le=100)):
    return run_query(
        """
        SELECT
            province_name,
            population,
            doses_distributed,
            doses_administered,
            doses_per_100,
            last_updated
        FROM agg_vn_vaccination_summary
        ORDER BY doses_administered DESC
        LIMIT %s
        """,
        (limit,),
    )


@app.get("/api/vietnam/trends")
def vietnam_trends(days: int = Query(default=30, ge=1, le=400)):
    return run_query(
        """
        SELECT
            d.full_date AS date,
            SUM(f.doses_administered) AS doses_administered,
            ROUND(SUM(f.doses_administered) / NULLIF(SUM(f.population), 0) * 100, 2) AS doses_per_100
        FROM fact_vn_vaccination f
        JOIN dim_date d ON d.date_id = f.date_id
        GROUP BY d.full_date, f.date_id
        ORDER BY f.date_id DESC
        LIMIT %s
        """,
        (days,),
    )[::-1]


@app.get("/api/vietnam/cases/summary")
def vietnam_cases_summary():
    rows = run_query(
        """
        SELECT
            d.full_date AS latest_date,
            f.total_cases,
            f.total_deaths,
            f.new_cases,
            f.new_deaths,
            ROUND(f.total_deaths / NULLIF(f.total_cases, 0) * 100, 2) AS cfr,
            (SELECT COUNT(*) FROM agg_vn_wikipedia_province_cases WHERE province_name <> 'Cả nước') AS province_count
        FROM fact_vn_wikipedia_daily f
        JOIN dim_date d ON d.date_id = f.date_id
        ORDER BY f.date_id DESC
        LIMIT 1
        """
    )
    return rows[0] if rows else {}


@app.get("/api/vietnam/cases/trends")
def vietnam_cases_trends(days: int = Query(default=2000, ge=1, le=3000)):
    return run_query(
        """
        SELECT
            d.full_date AS date,
            f.total_cases,
            f.total_deaths,
            f.new_cases,
            f.new_deaths
        FROM fact_vn_wikipedia_daily f
        JOIN dim_date d ON d.date_id = f.date_id
        ORDER BY f.date_id DESC
        LIMIT %s
        """,
        (days,),
    )[::-1]


@app.get("/api/vietnam/cases/provinces")
def vietnam_cases_provinces(limit: int = Query(default=15, ge=1, le=100)):
    return run_query(
        """
        SELECT
            province_name,
            total_cases,
            total_deaths,
            new_cases,
            ROUND(total_deaths / NULLIF(total_cases, 0) * 100, 2) AS cfr
        FROM agg_vn_wikipedia_province_cases
        WHERE province_name <> 'Cả nước'
        ORDER BY total_cases DESC
        LIMIT %s
        """,
        (limit,),
    )


@app.post("/api/assistant/health")
def health_assistant(payload: AssistantRequest):
    return {"reply": health_assistant_reply(payload.message)}
