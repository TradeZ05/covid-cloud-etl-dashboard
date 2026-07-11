# Lộ trình triển khai: Cloud Data Pipeline (ETL) & Data Lake — Dashboard COVID-19

> Tài liệu này là checklist thực thi theo từng bước, dựa trên schema và UI đã thiết kế trước đó.
> Nguyên tắc: làm từ trong ra ngoài — Database → ETL → Backend → nối Frontend → Cloud → Báo cáo.
> Đừng nhảy cóc lên cloud trước khi pipeline chạy ổn ở local.

---

## Phase 0 — Chuẩn bị môi trường (làm trong 1 buổi)

Cài đặt trên máy cá nhân trước khi đụng tới cloud:

| Công cụ | Mục đích | Cài đặt |
|---|---|---|
| Python 3.10+ | Viết script ETL | `python --version` để kiểm tra, hoặc cài từ python.org |
| MySQL | Database (Data Lake + Warehouse + Serving đều nằm chung 1 DB lúc đầu) | Bạn đã có sẵn — chỉ cần đảm bảo MySQL server đang chạy (`mysql --version` để kiểm tra, hoặc mở MySQL Workbench/XAMPP tùy cách bạn cài) |
| DBeaver hoặc MySQL Workbench | Xem dữ liệu trực quan trong lúc code | Tải bản free — DBeaver dùng được cho cả MySQL lẫn Postgres nếu sau này đổi ý |
| Node.js 18+ | Chạy backend API + frontend | `node --version` |
| Git | Quản lý code, để sau này dễ deploy | — |

✅ **Việc đầu tiên bạn nên làm ngay hôm nay:** mở terminal, chạy `mysql -u root -p` để chắc chắn đăng nhập được vào MySQL đang có sẵn, sau đó tạo database bằng lệnh `CREATE DATABASE covid_dashboard CHARACTER SET utf8mb4;`. Có database chạy được là xong Phase 0.

---

## Phase 1 — Tạo schema thật trong database (30 phút)

Lấy đúng khối lệnh `CREATE TABLE` đã có trong file `covid-dashboard-spec.md` (mục 4 — bản MySQL), lưu thành `database/schema.sql`, rồi chạy:

```bash
mysql -u root -p covid_dashboard < database/schema.sql
```

Nếu bạn chưa tạo database từ Phase 0, dòng `CREATE DATABASE IF NOT EXISTS covid_dashboard ...` ở đầu file schema sẽ tự tạo luôn, khỏi cần bước riêng.

Kiểm tra lại bằng DBeaver/Workbench: mở database, thấy đủ 10 bảng (`raw_covid_data`, `dim_country`, `dim_province`, `dim_date`, `fact_covid_global_daily`, `fact_covid_vn_daily`, `agg_country_summary`, `agg_vn_province_summary`, `agg_daily_global`, `agg_daily_vn`, `etl_job_log`) là xong.

---

## Phase 2 — Viết script Extract (1-2 buổi)

Mục tiêu: tải dữ liệu thô từ nguồn public, đổ **y nguyên** vào `raw_covid_data` — không xử lý gì cả ở bước này.

**`etl/extract.py`** — làm 2 việc:
1. Tải file CSV OWID (`https://covid.ourworldindata.org/data/owid-covid-data.csv`) bằng `pandas.read_csv()` hoặc `requests`.
2. Tải/đọc file CSV Vietnam từ Kaggle (tải thủ công 1 lần, để trong thư mục `data/raw/`).
3. Insert từng dòng vào `raw_covid_data` bằng `pymysql` hoặc SQLAlchemy — giữ nguyên kiểu string, không convert.
4. Ghi 1 dòng vào `etl_job_log` với `job_name='extract_owid'`, `status='success'`, `rows_processed=<số dòng>`.

Thư viện cần: `pip install pandas pymysql sqlalchemy requests --break-system-packages`

✅ Kiểm tra: chạy `python etl/extract.py`, mở DBeaver xem bảng `raw_covid_data` có dữ liệu, bảng `etl_job_log` có 1 dòng `success`.

---

## Phase 3 — Viết script Transform (1-2 buổi)

Mục tiêu: đọc từ `raw_covid_data`, làm sạch, tính toán, chuẩn bị dữ liệu để nạp vào Warehouse.

**`etl/transform.py`** làm:
- Convert string → đúng kiểu (int, date, decimal), xử lý giá trị rỗng/null (`COALESCE` hoặc `fillna(0)`).
- Tính `vaccination_rate = people_vaccinated / population * 100`.
- Tính `case_fatality_rate = total_deaths / total_cases * 100`.
- Loại bỏ dòng trùng lặp (`DISTINCT` theo `iso_code + date`).
- Trả về DataFrame đã sạch, sẵn sàng cho bước Load (chưa insert vội, giữ nguyên tắc tách rời 3 bước Extract–Transform–Load để dễ debug từng bước).

✅ Kiểm tra: in ra `df.head()`, `df.isnull().sum()` để chắc chắn không còn giá trị rác trước khi sang Load.

---

## Phase 4 — Viết script Load (1 buổi)

**`etl/load.py`** làm:
1. Upsert vào `dim_country` / `dim_province` / `dim_date` (dùng `INSERT IGNORE INTO ...` hoặc `INSERT INTO ... ON DUPLICATE KEY UPDATE` — tương đương `ON CONFLICT` bên Postgres — vì các bảng dimension không đổi thường xuyên).
2. Insert vào `fact_covid_global_daily` / `fact_covid_vn_daily`.
3. Tính lại và ghi đè vào các bảng `agg_*` (Serving Layer) — đây là bước biến dữ liệu chi tiết thành số liệu tổng hợp nhanh cho web đọc.
4. Ghi log vào `etl_job_log` cho từng bước con (`transform_global`, `load_vn_provinces`, `refresh_agg_summary`...) — đúng như dữ liệu mẫu bạn đã thấy ở trang ETL Monitoring.

**`etl/run_pipeline.py`** — file điều phối, gọi lần lượt `extract → transform → load`, bọc mỗi bước trong `try/except` để nếu 1 bước lỗi, vẫn ghi log `status='failed'` kèm `error_message` thay vì crash toàn bộ.

✅ Kiểm tra: chạy `python etl/run_pipeline.py`, mở trang ETL Monitoring demo (hoặc query trực tiếp `SELECT * FROM etl_job_log ORDER BY started_at DESC`) — thấy đủ các dòng log đúng như wireframe.

---

## Phase 5 — Viết Backend API (2-3 buổi)

Dùng FastAPI (khuyến nghị vì đồng bộ Python với ETL) hoặc Node/Express.

Thực hiện đúng danh sách endpoint đã liệt kê trong file spec (mục 6):
- `/api/summary/global`, `/api/countries/top`, `/api/trends/global`
- `/api/vietnam/provinces`, `/api/vietnam/trends`
- `/api/etl/jobs`

Mỗi endpoint chỉ cần 1 câu `SELECT` vào bảng `agg_*` hoặc `etl_job_log` — không cần logic phức tạp vì dữ liệu đã được ETL xử lý sẵn.

```bash
pip install fastapi uvicorn psycopg2-binary --break-system-packages
uvicorn main:app --reload --port 8000
```

✅ Kiểm tra: mở `http://localhost:8000/api/summary/global` trên trình duyệt, thấy JSON trả về đúng số liệu thật (không còn là data mẫu).

---

## Phase 6 — Nối Frontend thật với Backend (1 buổi)

Lấy đúng file React demo đã có (`covid-dashboard-demo-v2.jsx`), thay các khối `GLOBAL_SUMMARY`, `TOP_COUNTRIES`, `CASES_TREND_30D`... bằng `fetch("http://localhost:8000/api/...")` trong `useEffect`. UI giữ nguyên 100%, chỉ đổi nguồn dữ liệu — đây là lý do trước đó mình tách rõ data mẫu ra đầu file, để bước này chỉ cần sửa 1 chỗ.

✅ Kiểm tra: mở web, số liệu hiển thị khớp với dữ liệu thật trong database, không còn số cố định.

---

## Phase 7 — Tự động hóa lịch chạy ETL (1 buổi)

Ở local: dùng `cron` (Linux/Mac) hoặc Task Scheduler (Windows) chạy `run_pipeline.py` mỗi ngày 1 lần.
```
0 2 * * * /usr/bin/python3 /path/to/etl/run_pipeline.py
```
Đây là bước giúp bảng `etl_job_log` có nhiều dòng lịch sử thật để demo trang ETL Monitoring thuyết phục hơn (thay vì chỉ có 1 lần chạy).

---

## Phase 8 — Đưa lên Cloud (đây là phần lõi môn học, làm sau khi mọi thứ chạy ổn ở local)

Ánh xạ từng tầng đã có sang dịch vụ cloud cụ thể (ví dụ dùng AWS — có thể đổi sang GCP/Azure tương đương):

| Tầng | Local hiện tại | Dịch vụ Cloud gợi ý |
|---|---|---|
| Data Lake | `raw_covid_data` trong Postgres | Amazon S3 (lưu file CSV thô trước khi vào DB) |
| ETL | Script Python chạy local | AWS Lambda (chạy theo lịch) hoặc AWS Glue Job |
| Lên lịch | cron | Amazon EventBridge Scheduler |
| Data Warehouse + Serving | Postgres local | Amazon RDS for PostgreSQL |
| Backend API | uvicorn local | AWS Elastic Beanstalk / ECS / Lambda + API Gateway |
| Frontend | React chạy local | Vercel hoặc AWS Amplify / S3 + CloudFront |
| Giám sát | `etl_job_log` | Có thể bổ sung CloudWatch Logs để đối chiếu |

✅ Đây là phần bạn sẽ vẽ thành sơ đồ kiến trúc cho báo cáo — mình có thể giúp vẽ khi bạn tới bước này.

---

## Phase 9 — Chuẩn bị báo cáo/slide (song song làm trong lúc code)

Chụp lại: sơ đồ ERD, sơ đồ luồng Data Lake → ETL → Warehouse → Serving → Web (đã có ở phần trước), ảnh chụp trang ETL Monitoring có dữ liệu log thật, sơ đồ kiến trúc cloud ở Phase 8.

---

## Bạn nên bắt đầu từ đâu — ngay bây giờ

1. Chạy Docker Postgres (Phase 0) — 10 phút.
2. Chạy schema.sql tạo bảng (Phase 1) — 10 phút.
3. Viết `extract.py` tải OWID CSV và insert vào `raw_covid_data` (Phase 2) — đây là **việc cụ thể đầu tiên nên code**.

Nếu bạn muốn, mình có thể viết luôn code `extract.py` hoàn chỉnh ngay bây giờ để bạn chạy thử, thay vì chỉ mô tả — bạn muốn vậy không?
