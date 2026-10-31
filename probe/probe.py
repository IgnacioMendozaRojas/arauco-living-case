"""Fourth probe: the CMF material-events search for Arauco with the full form."""

import re

import requests

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0 Safari/537.36"
)
S = requests.Session()
S.headers["User-Agent"] = UA
BASE = {"mercado": "V", "rut": "93458000", "grupo": "", "tipoentidad": "RVEMI", "row": ""}
BASE |= {"vig": "VI", "control": "svs", "pestania": "25"}
URL = "https://www.cmfchile.cl/institucional/mercados/entidad.php"
QS = "&".join(f"{k}={v}" for k, v in BASE.items())


def note(title, msg, level="notice"):
    print(f"::{level} title={title}::{msg[:950]}", flush=True)


def clean(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


S.get(f"{URL}?{QS}", timeout=90)
dates = {"dd": "01", "mm": "01", "aa": "2025", "dd2": "31", "mm2": "12", "aa2": "2025"}
for label, url, data in (
    ("post to query url, base+dates", f"{URL}?{QS}", {**BASE, **dates}),
    ("post to bare url, base+dates", URL, {**BASE, **dates}),
    ("post with dias", f"{URL}?{QS}", {**BASE, **dates, "dias": "365"}),
    ("get with dates", f"{URL}?{QS}&" + "&".join(f"{k}={v}" for k, v in dates.items()), None),
):
    if data is None:
        r = S.get(url, timeout=90, headers={"Referer": f"{URL}?{QS}"})
    else:
        r = S.post(url, data=data, timeout=90, headers={"Referer": f"{URL}?{QS}"})
    r.encoding = r.apparent_encoding
    t = r.text
    rows = [clean(x)[:200] for x in re.findall(r"<tr[^>]*>(.*?)</tr>", t, re.S)]
    rows = [x for x in rows if re.search(r"\d{2}/\d{2}/\d{4}", x)]
    links = [x for x in re.findall(r'href="([^"]+)"', t) if re.search(r"hecho|pdf|doc", x, re.I)]
    note(label, f"HTTP {r.status_code}, {len(rows)} dated rows: " + " || ".join(rows[:4]))
    if rows:
        note(label + " links", " | ".join(links[:4]))
        break
