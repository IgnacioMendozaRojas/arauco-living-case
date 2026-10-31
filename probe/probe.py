"""Second probe: CMF tab names and material events for Arauco; GDELT with a polite pause."""

import re
import time

import requests

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0 Safari/537.36"
)
S = requests.Session()
S.headers["User-Agent"] = UA
CMF = "https://www.cmfchile.cl/institucional/mercados/entidad.php"
RUT = "93458000"


def note(title, msg, level="notice"):
    print(f"::{level} title={title}::{msg[:950]}", flush=True)


def page(tab, method="get", **data):
    url = (
        f"{CMF}?mercado=V&rut={RUT}&grupo=&tipoentidad=RVEMI&row=&vig=VI&control=svs&pestania={tab}"
    )
    r = S.request(method, url, timeout=90, data=data or None)
    r.encoding = r.apparent_encoding
    return r.text


def clean(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


# 1. the menu: tab number -> label
html = page(1)
tabs = {}
for m in re.finditer(r"pestania=(\d+)[^>]*>(.*?)</a>", html, re.S):
    tabs.setdefault(int(m.group(1)), clean(m.group(2)))
note("CMF tabs", " | ".join(f"{k}: {v}" for k, v in sorted(tabs.items())))

# 2. the material-events tab: forms, date fields and the first rows
for tab, label in sorted(tabs.items()):
    if not re.search(r"hecho|esencial|relevante", label, re.I):
        continue
    h = page(tab)
    forms = re.findall(r'<input[^>]+name="([^"]+)"[^>]*?(?:value="([^"]*)")?', h)
    note(f"CMF tab {tab} form", f"{label}: inputs {forms[:15]}")
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", h, re.S)
    sample = [clean(r)[:160] for r in rows if re.search(r"\d{2}/\d{2}/\d{4}", r)][:6]
    note(f"CMF tab {tab} rows", f"{len(rows)} rows; " + " || ".join(sample))
    links = re.findall(r'href="([^"]+)"', h)
    docs = [x for x in links if re.search(r"pdf|documento|hecho", x, re.I)][:5]
    note(f"CMF tab {tab} links", " | ".join(docs))

# 3. GDELT, waiting between attempts as the service asks
for attempt in range(4):
    time.sleep(8 * (attempt + 1))
    r = S.get(
        "https://api.gdeltproject.org/api/v2/doc/doc",
        params={
            "query": "Arauco (celulosa OR forestal OR pulp)",
            "mode": "artlist",
            "format": "json",
            "maxrecords": 250,
            "timespan": "3m",
        },
        timeout=90,
    )
    if r.status_code == 200:
        try:
            arts = r.json().get("articles", [])
        except ValueError:
            note("GDELT", f"not JSON: {r.text[:300]}", "warning")
            break
        langs = {}
        for a in arts:
            langs[a.get("language")] = langs.get(a.get("language"), 0) + 1
        s = "; ".join(f"{a['seendate'][:8]} {a['domain']}: {a['title'][:70]}" for a in arts[:6])
        note("GDELT", f"{len(arts)} articles, languages {langs}. {s}")
        break
    note("GDELT", f"attempt {attempt + 1}: HTTP {r.status_code}", "warning")
