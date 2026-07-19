import io
import urllib.request

import pandas as pd


URL = "https://vi.wikipedia.org/wiki/%C4%90%E1%BA%A1i_d%E1%BB%8Bch_COVID-19_t%E1%BA%A1i_Vi%E1%BB%87t_Nam"


req = urllib.request.Request(
    URL,
    headers={"User-Agent": "Mozilla/5.0 ETL student project"},
)
html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
tables = pd.read_html(io.StringIO(html))

print("tables", len(tables))
for i, table in enumerate(tables):
    print("\nTABLE", i, table.shape)
    print(list(map(str, table.columns))[:10])
    print(table.head(5).to_string())
