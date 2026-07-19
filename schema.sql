-- ============================================================
-- File này tạo TOÀN BỘ database rỗng cho dự án COVID Dashboard.
-- Chạy 1 lần duy nhất là xong Giai đoạn 1.
-- Chưa có dữ liệu gì trong này — chỉ tạo "cái tủ trống" đúng thiết kế.
-- ============================================================

CREATE DATABASE IF NOT EXISTS covid_dashboard
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE covid_dashboard;

-- TẦNG DATA LAKE (RAW LAYER)
CREATE TABLE raw_covid_data (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    iso_code VARCHAR(10),
    continent VARCHAR(50),
    location VARCHAR(100),
    date_raw VARCHAR(20),
    new_cases VARCHAR(20),
    new_deaths VARCHAR(20),
    total_cases VARCHAR(20),
    total_deaths VARCHAR(20),
    people_vaccinated VARCHAR(20),
    population VARCHAR(20),
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source_file VARCHAR(255)
) ENGINE=InnoDB;

-- TẦNG DATA WAREHOUSE (STAR SCHEMA)
CREATE TABLE dim_country (
    country_id INT AUTO_INCREMENT PRIMARY KEY,
    iso_code VARCHAR(10) UNIQUE NOT NULL,
    country_name VARCHAR(100) NOT NULL,
    continent VARCHAR(50),
    population BIGINT
) ENGINE=InnoDB;

CREATE TABLE dim_province (
    province_id INT AUTO_INCREMENT PRIMARY KEY,
    province_name VARCHAR(100) NOT NULL,
    region VARCHAR(20),
    population BIGINT
) ENGINE=InnoDB;

CREATE TABLE dim_date (
    date_id INT PRIMARY KEY,
    full_date DATE NOT NULL,
    year INT,
    month INT,
    week INT,
    quarter INT
) ENGINE=InnoDB;

CREATE TABLE fact_covid_global_daily (
    fact_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    country_id INT,
    date_id INT,
    new_cases INT DEFAULT 0,
    new_deaths INT DEFAULT 0,
    total_cases BIGINT DEFAULT 0,
    total_deaths BIGINT DEFAULT 0,
    people_vaccinated BIGINT DEFAULT 0,
    vaccination_rate DECIMAL(5,2),
    case_fatality_rate DECIMAL(5,2),
    UNIQUE KEY uq_country_date (country_id, date_id),
    FOREIGN KEY (country_id) REFERENCES dim_country(country_id),
    FOREIGN KEY (date_id) REFERENCES dim_date(date_id)
) ENGINE=InnoDB;

CREATE TABLE fact_covid_vn_daily (
    fact_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    province_id INT,
    date_id INT,
    new_cases INT DEFAULT 0,
    new_deaths INT DEFAULT 0,
    total_cases BIGINT DEFAULT 0,
    total_deaths BIGINT DEFAULT 0,
    recovered BIGINT DEFAULT 0,
    active_cases BIGINT DEFAULT 0,
    UNIQUE KEY uq_province_date (province_id, date_id),
    FOREIGN KEY (province_id) REFERENCES dim_province(province_id),
    FOREIGN KEY (date_id) REFERENCES dim_date(date_id)
) ENGINE=InnoDB;

-- TẦNG SERVING (phục vụ web đọc nhanh)
CREATE TABLE agg_country_summary (
    country_id INT PRIMARY KEY,
    country_name VARCHAR(100),
    latest_total_cases BIGINT,
    latest_total_deaths BIGINT,
    latest_vaccination_rate DECIMAL(5,2),
    trend_7d_cases DECIMAL(6,2),
    last_updated TIMESTAMP,
    FOREIGN KEY (country_id) REFERENCES dim_country(country_id)
) ENGINE=InnoDB;

CREATE TABLE agg_vn_province_summary (
    province_id INT PRIMARY KEY,
    province_name VARCHAR(255),
    latest_total_cases BIGINT,
    latest_total_deaths BIGINT,
    latest_new_cases INT,
    active_cases BIGINT,
    last_updated TIMESTAMP,
    FOREIGN KEY (province_id) REFERENCES dim_province(province_id)
) ENGINE=InnoDB;

CREATE TABLE agg_daily_global (
    date_id INT PRIMARY KEY,
    total_new_cases_global BIGINT,
    total_new_deaths_global BIGINT,
    FOREIGN KEY (date_id) REFERENCES dim_date(date_id)
) ENGINE=InnoDB;

CREATE TABLE agg_daily_vn (
    date_id INT PRIMARY KEY,
    total_new_cases_vn BIGINT,
    total_new_deaths_vn BIGINT,
    FOREIGN KEY (date_id) REFERENCES dim_date(date_id)
) ENGINE=InnoDB;

-- GIÁM SÁT ETL PIPELINE
CREATE TABLE raw_vn_vaccination_data (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    province_name VARCHAR(100),
    population BIGINT,
    doses_distributed BIGINT,
    doses_administered BIGINT,
    doses_per_100 DECIMAL(8,2),
    snapshot_date DATE,
    source_url VARCHAR(255),
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE fact_vn_vaccination (
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
) ENGINE=InnoDB;

CREATE TABLE agg_vn_vaccination_summary (
    province_id INT PRIMARY KEY,
    province_name VARCHAR(100),
    population BIGINT,
    doses_distributed BIGINT,
    doses_administered BIGINT,
    doses_per_100 DECIMAL(8,2),
    last_updated TIMESTAMP,
    FOREIGN KEY (province_id) REFERENCES dim_province(province_id)
) ENGINE=InnoDB;

CREATE TABLE raw_vn_wikipedia_province_cases (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    province_name VARCHAR(100),
    total_cases BIGINT,
    total_deaths BIGINT,
    new_cases BIGINT,
    source_url VARCHAR(255),
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE fact_vn_wikipedia_daily (
    date_id INT PRIMARY KEY,
    total_cases BIGINT,
    total_deaths BIGINT,
    new_cases BIGINT,
    new_deaths BIGINT,
    source_url VARCHAR(255),
    FOREIGN KEY (date_id) REFERENCES dim_date(date_id)
) ENGINE=InnoDB;

CREATE TABLE agg_vn_wikipedia_province_cases (
    province_name VARCHAR(255) PRIMARY KEY,
    total_cases BIGINT,
    total_deaths BIGINT,
    new_cases BIGINT,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- WHO DISEASE OUTBREAK NEWS (nguồn chính thống, cập nhật cảnh báo dịch bệnh)
CREATE TABLE raw_who_outbreak_news (
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
) ENGINE=InnoDB;

CREATE TABLE etl_job_log (
    job_id INT AUTO_INCREMENT PRIMARY KEY,
    job_name VARCHAR(100) NOT NULL,
    status ENUM('success','failed','running') NOT NULL,
    rows_processed INT,
    started_at TIMESTAMP NULL,
    finished_at TIMESTAMP NULL,
    error_message TEXT
) ENGINE=InnoDB;

-- Kiểm tra nhanh: chạy lệnh dưới đây sau khi tạo xong,
-- phải thấy đủ 10 dòng (10 bảng) hiện ra.
SHOW TABLES;
