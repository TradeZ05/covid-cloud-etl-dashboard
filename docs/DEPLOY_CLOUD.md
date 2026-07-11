# Deploy cloud nhanh cho COVID ETL/Data Lake Dashboard

Khuyen nghi dung Railway cho MySQL + FastAPI backend, va Vercel hoac Railway cho frontend Vite.

## 1. Tao MySQL tren Railway

1. Tao project moi tren Railway.
2. Add service `MySQL`.
3. Ghi lai cac bien ket noi Railway cung cap:
   - `MYSQLHOST`
   - `MYSQLPORT`
   - `MYSQLUSER`
   - `MYSQLPASSWORD`
   - `MYSQLDATABASE`

Backend va cac script ETL trong project nay da ho tro ca kieu bien `MYSQL_*` va `MYSQLHOST/MYSQLPASSWORD` cua Railway.

## 2. Nap schema va du lieu len cloud database

Chay tren may local, thay gia tri bang thong tin MySQL cua Railway:

```powershell
$env:MYSQL_HOST="your-railway-mysql-host"
$env:MYSQL_PORT="your-railway-mysql-port"
$env:MYSQL_USER="your-railway-mysql-user"
$env:MYSQL_PASSWORD="your-railway-mysql-password"
$env:MYSQL_DATABASE="your-railway-mysql-database"
```

Tao bang:

```powershell
mysql -h $env:MYSQL_HOST -P $env:MYSQL_PORT -u $env:MYSQL_USER -p $env:MYSQL_DATABASE < schema.sql
```

Nap du lieu:

```powershell
python .\extract.py
python .\transform_load.py
python .\vn_vaccination_load.py
python .\vn_wikipedia_load.py
```

## 3. Deploy backend FastAPI

Tao service backend tren Railway tu thu muc goc project nay.

Bien moi truong backend can co:

```text
MYSQL_HOST=...
MYSQL_PORT=...
MYSQL_USER=...
MYSQL_PASSWORD=...
MYSQL_DATABASE=...
```

Start command da co trong `railway.json`:

```text
uvicorn main:app --host 0.0.0.0 --port $PORT
```

Sau khi deploy, test:

```text
https://your-backend-domain/health
https://your-backend-domain/api/summary/global
```

## 4. Deploy frontend

Trong service frontend, root directory la:

```text
covid-frontend
```

Bien moi truong frontend:

```text
VITE_API_BASE=https://your-backend-domain
```

Build command:

```text
npm ci && npm run build
```

Start command neu dung Railway:

```text
npm run preview -- --host 0.0.0.0 --port $PORT
```

Neu dung Vercel:

```text
Framework: Vite
Root Directory: covid-frontend
Build Command: npm run build
Output Directory: dist
Environment Variable: VITE_API_BASE=https://your-backend-domain
```

## 5. Checklist truoc khi nop bai

- Backend `/health` tra ve `{"status":"ok"}`.
- Backend `/api/summary/global` tra ve JSON, khong loi 500.
- Frontend mo duoc trang Global, Viet Nam, Nhat ky ETL.
- Tab Viet Nam hien thi heatmap, vaccine, va bieu do ca nhiem tu Wikipedia.
- Chat tro ly y te tra loi duoc.
- Khong commit file `.mysql_password`.
