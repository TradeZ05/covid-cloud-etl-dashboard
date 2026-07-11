# Data folder

`raw/` stores local source snapshots used by ETL scripts.

Large source files such as `owid-covid-data.csv` are intentionally ignored by Git. If the file is missing, `extract.py` can download the OWID CSV from the source URL.
