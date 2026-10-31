"""One-off probe of the public sources for the Arauco case. Prints findings as annotations."""

import io
import re
import zipfile

import requests

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0 Safari/537.36"
)
S = requests.Session()
S.headers["User-Agent"] = UA
CMF = "https://www.cmfchile.cl/institucional/mercados/entidad.php"


def note(title, msg, level="notice"):
    print(f"::{level} title={title}::{msg[:900]}", flush=True)


def get(url, **kw):
    try:
        r = S.get(url, timeout=90, **kw)
        return r
    except requests.RequestException as e:
        note("error", f"{url[:200]} -> {e}", "warning")
        return None


def text(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


# 1. CMF: which company-page tabs mention material events (hechos esenciales) for Arauco
for rut, name in (("93458000", "Celulosa Arauco"), ("90690000", "Empresas Copec")):
    hits = []
    for tab in range(1, 61):
        url = (
            f"{CMF}?mercado=V&rut={rut}&grupo=&tipoentidad=RVEMI&row=&vig=VI&control=svs"
            f"&pestania={tab}"
        )
        r = get(url)
        if r is None or r.status_code != 200:
            continue
        r.encoding = r.apparent_encoding
        t = text(r.text)
        if re.search(r"hecho[s]? (esencial|relevante)", t, re.IGNORECASE):
            m = re.search(r"(\d{2}/\d{2}/\d{4}).{0,200}", t)
            hits.append(f"tab {tab}: {len(r.text)} bytes; {m.group(0)[:160] if m else ''}")
    note(f"CMF {name}", " || ".join(hits) or "no tab mentions hechos esenciales")

# 2. GDELT news (last month)
r = get(
    "https://api.gdeltproject.org/api/v2/doc/doc",
    params={
        "query": '"Arauco" (celulosa OR forestal OR pulp)',
        "mode": "artlist",
        "format": "json",
        "maxrecords": 250,
        "timespan": "3m",
    },
)
if r is not None:
    try:
        arts = r.json().get("articles", [])
        sample = "; ".join(
            f"{a['seendate'][:8]} {a['domain']}: {a['title'][:80]}" for a in arts[:5]
        )
        note("GDELT", f"HTTP {r.status_code}, {len(arts)} articles in 3 months. {sample}")
    except ValueError:
        note("GDELT", f"HTTP {r.status_code}: {r.text[:300]}", "warning")

# 3. FAOSTAT forestry bulk file: Chile wood pulp production and exports
for url in (
    "https://bulks-faostat.fao.org/production/Forestry_E_All_Data_(Normalized).zip",
    "https://fenixservices.fao.org/faostat/static/bulkdownloads/Forestry_E_All_Data_(Normalized).zip",
):
    r = get(url)
    if r is None or r.status_code != 200:
        note("FAOSTAT", f"{url}: HTTP {getattr(r, 'status_code', None)}", "warning")
        continue
    z = zipfile.ZipFile(io.BytesIO(r.content))
    csv = next(n for n in z.namelist() if n.endswith(".csv") and "Normalized" in n)
    import pandas as pd

    df = pd.read_csv(z.open(csv), encoding="latin-1", low_memory=False)
    cl = df[df["Area"] == "Chile"]
    pulp = cl[cl["Item"].str.contains("pulp", case=False)]
    items = sorted(pulp["Item"].unique())[:8]
    last = int(cl["Year"].max())
    rows = pulp[(pulp["Year"] == last)][["Item", "Element", "Unit", "Value"]].head(6)
    note("FAOSTAT", f"{len(r.content) / 1e6:.0f} MB; Chile last year {last}; pulp items {items}")
    note("FAOSTAT rows", rows.to_string(index=False).replace("\n", " | "))
    break

# 4. FRED: US producer price index for wood pulp (no key)
r = get("https://fred.stlouisfed.org/graph/fredgraph.csv", params={"id": "WPU0911"})
if r is not None:
    lines = r.text.strip().splitlines()
    note(
        "FRED WPU0911",
        f"HTTP {r.status_code}, {len(lines)} lines, first {lines[1:2]}, last {lines[-1:]}",
    )

# 5. OpenAlex: research on Arauco / Chilean forestry
r = get(
    "https://api.openalex.org/works",
    params={
        "filter": "title_and_abstract.search:Arauco AND (forestry OR plantation OR pulp)",
        "per-page": 5,
        "select": "display_name,publication_year,cited_by_count",
    },
)
if r is not None:
    j = r.json()
    note(
        "OpenAlex",
        f"{j.get('meta', {}).get('count')} works; "
        + "; ".join(
            f"{w['publication_year']} {w['display_name'][:70]}" for w in j.get("results", [])
        ),
    )
