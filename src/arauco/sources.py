"""Download the public sources: Google News headlines, FAOSTAT forestry statistics and OpenAlex
research on the case."""

from __future__ import annotations

import io
import re
import time
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from email.utils import parsedate_to_datetime

import pandas as pd
import requests

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0 Safari/537.36"
)
NEWS_COLS = ["date", "source", "title", "link", "themes", "query"]


def plain(text: str) -> str:
    """Lower case without accents, for keyword rules."""
    t = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = UA
    return s


# --- news -----------------------------------------------------------------------------------------


def parse_rss(xml: bytes, query: str) -> list[dict]:
    out = []
    for item in ET.fromstring(xml).findall(".//item"):
        title = " ".join((item.findtext("title") or "").split())
        source = item.findtext("source") or ""
        # Google News appends " - Source" to the title
        if source and title.endswith(f" - {source}"):
            title = title[: -len(source) - 3]
        try:
            date = parsedate_to_datetime(item.findtext("pubDate") or "").date().isoformat()
        except (TypeError, ValueError):
            date = ""
        out.append(
            {
                "date": date,
                "source": source,
                "title": title,
                "link": item.findtext("link") or "",
                "query": query,
            }
        )
    return out


def tag(title: str, rules: dict[str, str]) -> str:
    t = plain(title)
    return ";".join(name for name, rx in rules.items() if re.search(rx, t))


def relevant(title: str, cfg: dict) -> bool:
    t = plain(title)
    return bool(re.search(cfg["require"], t)) and not re.search(cfg["exclude"], t)


def news(s: requests.Session, cfg: dict, pause: float = 2.0) -> pd.DataFrame:
    rows = []
    for q in cfg["queries"]:
        r = s.get(
            "https://news.google.com/rss/search",
            params={"q": q, "hl": "es-419", "gl": "CL", "ceid": "CL:es-419"},
            timeout=60,
        )
        r.raise_for_status()
        rows += parse_rss(r.content, q)
        time.sleep(pause)
    df = pd.DataFrame(rows, columns=[c for c in NEWS_COLS if c != "themes"])
    df = df[df["title"].map(lambda t: relevant(t, cfg))].copy()
    df["themes"] = df["title"].map(lambda t: tag(t, cfg["themes"]))
    return df[NEWS_COLS]


def merge_news(old: pd.DataFrame, new: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Accumulate headlines across runs (the feed only shows recent ones). Returns the full
    history and the headlines that are new this run."""
    key = lambda df: df["title"].map(lambda t: re.sub(r"[^a-z0-9]", "", plain(t))[:90])  # noqa: E731
    new = new.assign(_k=key(new)).drop_duplicates("_k")
    seen = set(key(old)) if not old.empty else set()
    fresh = new[~new["_k"].isin(seen)].drop(columns="_k")
    full = pd.concat([old, fresh], ignore_index=True).sort_values("date", ascending=False)
    return full[NEWS_COLS].reset_index(drop=True), fresh[NEWS_COLS].reset_index(drop=True)


# --- FAOSTAT --------------------------------------------------------------------------------------


def faostat(s: requests.Session, cfg: dict) -> pd.DataFrame:
    """Chemical wood pulp: production, export quantity and export value, for Chile, its peers
    and the world, from the FAOSTAT forestry bulk file."""
    r = s.get(cfg["url"], timeout=300)
    r.raise_for_status()
    z = zipfile.ZipFile(io.BytesIO(r.content))
    name = next(n for n in z.namelist() if n.endswith(".csv") and "Normalized" in n)
    df = pd.read_csv(z.open(name), encoding="latin-1", low_memory=False)
    return tidy_faostat(df, cfg)


def tidy_faostat(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    areas = [cfg["country"], *cfg["peers"], "World"]
    d = df[(df["Item"] == cfg["item"]) & (df["Area"].isin(areas))]
    d = d[["Area", "Element", "Unit", "Year", "Value"]].rename(columns=str.lower)
    return d.sort_values(["area", "element", "year"]).reset_index(drop=True)


# --- OpenAlex ------------------------------------------------------------------------------------


def research(s: requests.Session, query: str) -> pd.DataFrame:
    """Research articles on the case (numbered pages, which need no API key)."""
    rows, page = [], 1
    while True:
        r = s.get(
            "https://api.openalex.org/works",
            params={
                "filter": f"title_and_abstract.search:{query}",
                "select": "id,display_name,publication_year,cited_by_count,primary_location",
                "per-page": 100,
                "page": page,
            },
            timeout=60,
        )
        r.raise_for_status()
        j = r.json()
        for w in j["results"]:
            src = ((w.get("primary_location") or {}).get("source") or {}).get("display_name")
            rows.append(
                {
                    "id": w["id"].rsplit("/", 1)[-1],
                    "year": w.get("publication_year"),
                    "title": " ".join((w.get("display_name") or "").split()),
                    "source": src or "",
                    "cited": w.get("cited_by_count") or 0,
                }
            )
        if not j["results"] or len(rows) >= j["meta"]["count"] or page >= 10:
            break
        page += 1
    return pd.DataFrame(rows, columns=["id", "year", "title", "source", "cited"])
