"""Third probe: the CMF material-events form for Arauco, and Google News RSS as news source."""

import re
import xml.etree.ElementTree as ET

import requests

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0 Safari/537.36"
)
S = requests.Session()
S.headers["User-Agent"] = UA
URL = (
    "https://www.cmfchile.cl/institucional/mercados/entidad.php?mercado=V&rut=93458000&grupo="
    "&tipoentidad=RVEMI&row=&vig=VI&control=svs&pestania=25"
)


def note(title, msg, level="notice"):
    print(f"::{level} title={title}::{msg[:950]}", flush=True)


def clean(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def get_html(method="get", data=None):
    r = S.request(method, URL, data=data, timeout=90, headers={"Referer": URL})
    r.encoding = r.apparent_encoding
    return r.text


h = get_html()
# the content area: everything after the tab menu
body = h[h.find("Hechos") :]
selects = {
    m.group(1): re.findall(r'<option[^>]*value="([^"]*)"', m.group(2))[:8]
    for m in re.finditer(r'<select[^>]+name="([^"]+)"(.*?)</select>', body, re.S)
}
forms = re.findall(r"<form[^>]*>", body)
inputs = re.findall(r'<input[^>]+name="([^"]+)"', body)
note("CMF form", f"forms {forms[:3]} | selects {selects} | inputs {inputs[:25]}")
i = body.find("<table")
note("CMF content", clean(body[: i if i > 0 else 1500])[:900])
note("CMF table", clean(body[i : i + 3000])[:900] if i > 0 else "no table")

for data in (
    {"dd": "01", "mm": "01", "aa": "2024", "dd2": "31", "mm2": "12", "aa2": "2025"},
    {"txt_inicio": "01/01/2024", "txt_termino": "31/12/2025"},
    {"aa": "2025", "mm": "12"},
):
    t = get_html("post", {"pestania": "25", **data})
    dates = re.findall(r"\d{2}/\d{2}/\d{4}", t)
    rows = [clean(r)[:170] for r in re.findall(r"<tr[^>]*>(.*?)</tr>", t, re.S)]
    rows = [r for r in rows if re.search(r"\d{2}/\d{2}/\d{4}", r)]
    note(f"CMF post {list(data)[:2]}", f"{len(dates)} dates; " + " || ".join(rows[:5]))

for q in ("Arauco celulosa", "Arauco forestal", "Celulosa Arauco"):
    r = S.get(
        "https://news.google.com/rss/search",
        params={"q": q, "hl": "es-419", "gl": "CL", "ceid": "CL:es-419"},
        timeout=60,
    )
    try:
        items = ET.fromstring(r.content).findall(".//item")
    except ET.ParseError:
        note("Google News", f"{q}: HTTP {r.status_code}, not XML", "warning")
        continue
    s = "; ".join(
        f"{(i.findtext('pubDate') or '')[5:16]} {i.findtext('source')}: {i.findtext('title')[:70]}"
        for i in items[:5]
    )
    note(f"Google News {q}", f"HTTP {r.status_code}, {len(items)} items. {s}")
