# AWS deployment guide

This project is designed as a cloud data pipeline and dashboard:

- Data Lake: Amazon S3 stores raw CSV snapshots.
- Data Warehouse / Serving Layer: Amazon RDS for MySQL stores dimensional, fact, and aggregate tables.
- Backend API: FastAPI runs on AWS Elastic Beanstalk or a Docker-based AWS service.
- Frontend: React/Vite runs on AWS Amplify Hosting.

## 1. Create an S3 data lake bucket

Create an S3 bucket, for example:

```text
covid-etl-datalake-yourname
```

Suggested folder layout:

```text
s3://covid-etl-datalake-yourname/raw/owid/
s3://covid-etl-datalake-yourname/raw/vietnam/
s3://covid-etl-datalake-yourname/processed/
```

Upload local raw files from `data/raw/` to S3. If you use AWS CLI:

```powershell
aws s3 sync .\data\raw s3://covid-etl-datalake-yourname/raw/
```

## 2. Create Amazon RDS MySQL

Create an RDS MySQL database:

```text
Engine: MySQL
DB identifier: covid-dashboard-db
Initial database name: covid_dashboard
Username: admin or root
Public access: Yes for a student demo, No for production
```

Security group rule for quick demo:

```text
Type: MySQL/Aurora
Port: 3306
Source: your current public IP
```

Keep these connection values:

```text
MYSQL_HOST=<rds-endpoint>
MYSQL_PORT=3306
MYSQL_USER=<rds-user>
MYSQL_PASSWORD=<rds-password>
MYSQL_DATABASE=covid_dashboard
```

## 3. Initialize schema and run ETL into RDS

Set environment variables locally:

```powershell
$env:MYSQL_HOST="<rds-endpoint>"
$env:MYSQL_PORT="3306"
$env:MYSQL_USER="<rds-user>"
$env:MYSQL_PASSWORD="<rds-password>"
$env:MYSQL_DATABASE="covid_dashboard"
```

Create tables:

```powershell
mysql -h $env:MYSQL_HOST -P $env:MYSQL_PORT -u $env:MYSQL_USER -p $env:MYSQL_DATABASE < schema.sql
```

Run ETL:

```powershell
python .\extract.py
python .\transform_load.py
python .\vn_vaccination_load.py
python .\vn_wikipedia_load.py
```

Verify:

```powershell
mysql -h $env:MYSQL_HOST -P $env:MYSQL_PORT -u $env:MYSQL_USER -p -e "USE covid_dashboard; SELECT COUNT(*) FROM fact_covid_global_daily; SELECT COUNT(*) FROM agg_country_summary;"
```

## 4. Deploy backend FastAPI

Recommended for a student project: Elastic Beanstalk with Docker or Python platform.

Backend environment variables:

```text
MYSQL_HOST=<rds-endpoint>
MYSQL_PORT=3306
MYSQL_USER=<rds-user>
MYSQL_PASSWORD=<rds-password>
MYSQL_DATABASE=covid_dashboard
```

Runtime command:

```text
uvicorn main:app --host 0.0.0.0 --port $PORT
```

After deployment, test:

```text
https://<backend-domain>/health
https://<backend-domain>/api/summary/global
```

## 5. Deploy frontend with AWS Amplify

Connect Amplify Hosting to your GitHub repo.

Build settings are already in `amplify.yml`.

Set frontend environment variable:

```text
VITE_API_BASE=https://<backend-domain>
```

After deployment, test:

```text
https://<amplify-domain>
```

## 6. Final report checklist

- S3 bucket contains raw source snapshots.
- RDS contains raw, dimension, fact, and aggregate tables.
- Backend API connects to RDS and returns JSON.
- Frontend dashboard connects to backend and shows charts.
- ETL job can be rerun and refresh the serving layer.
- Secrets are stored in AWS environment variables, not in Git.
