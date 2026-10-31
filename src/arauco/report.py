"""Figures, the case log, the timeline page, latest.json and the README block, all computed from
data/. The 'comments' are rules applied to the data, so every sentence can be traced back."""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

import pandas as pd

from .figstyle import charts

REPO = "github.com/IgnacioMendozaRojas/arauco-living-case"
FAO_SOURCE = f"Source: FAOSTAT, Forestry production and trade (chemical wood pulp). {REPO}"
NEWS_SOURCE = f"Source: Google News headlines (Chile, Spanish), tagged by keyword rules. {REPO}"
THEME_LABEL = {
    "territory": "Territory and environment",
    "group": "Group, ownership and investment",
    "legitimacy": "Sustainability and legitimacy",
    "market": "Pulp market and results",
    "state": "State and regulation",
}


def element(fao: pd.DataFrame, area: str, name: str) -> pd.Series:
    d = fao[(fao["area"] == area) & (fao["element"].str.lower() == name.lower())]
    return d.set_index("year")["value"].sort_index()


# --- figures --------------------------------------------------------------------------------------


def fig_arc(fao: pd.DataFrame, timeline: dict, country: str, fig: Path) -> str:
    prod = element(fao, country, "Production") / 1e6
    y1 = int(prod.index.max())
    base = 1979 if 1979 in prod.index else int(prod.index.min())
    title = (
        f"{country}'s pulp output: {prod[base]:.1f} Mt at privatisation ({base}), "
        f"{prod[y1]:.1f} Mt in {y1}"
    )
    sub = "Chemical wood pulp production, million tonnes (Mt); shaded: the phases of the case"
    for c in charts(title, sub, FAO_SOURCE):
        for i, ph in enumerate(timeline["phases"]):
            if i % 2 == 0:
                c.span(ph["start"], ph["end"] or y1, ph["name"])
            else:
                c.ax.text(
                    ph["start"],
                    0.98,
                    f" {ph['name']}",
                    transform=c.ax.get_xaxis_transform(),
                    fontsize=8,
                    color=c.t["muted"],
                    va="top",
                )
        c.line(list(prod.index), list(prod.values), 0, country, end_label=False)
        marked = [e for e in timeline["events"] if e.get("label") and e["year"] in prod.index]
        for i, e in enumerate(marked):
            yr = e["year"]
            # alternate above and below the line so that neighbouring labels do not collide
            off = (-30, 40) if i % 2 == 0 else (10, -40)
            c.note((yr, prod[yr]), e["label"], xytext=off)
        c.yaxis("Million tonnes")
        c.ax.set_xlim(prod.index.min(), y1 + 1)
        c.ax.set_ylim(0, prod.max() * 1.25)
        c.save(fig, "arc")
    return title


def world_shares(fao: pd.DataFrame, areas: list[str]) -> pd.DataFrame:
    world = element(fao, "World", "Production")
    out = {a: element(fao, a, "Production") / world for a in areas}
    return pd.DataFrame(out).dropna(how="all")


def fig_share(fao: pd.DataFrame, country: str, peers: list[str], fig: Path) -> str:
    sh = world_shares(fao, [country, *peers]).dropna(subset=[country])
    y1 = int(sh.index.max())
    peak_year = int(sh[country].idxmax())
    title = (
        f"{country} produced {sh[country][y1]:.1%} of the world's chemical pulp in {y1} "
        f"(peak {sh[country][peak_year]:.1%} in {peak_year})"
    )
    top_peers = sh[peers].iloc[-1].sort_values(ascending=False).index[:3].tolist()
    sub = f"Share of world production: {country} and the three largest of the peers in {y1}"
    for c in charts(title, sub, FAO_SOURCE):
        c.line(list(sh.index), list(sh[country]), 0, country)
        for i, p in enumerate(top_peers, start=1):
            s = sh[p].dropna()
            c.line(list(s.index), list(s.values), i, p.replace("United States of America", "USA"))
        c.yaxis(pct=True)
        c.save(fig, "share")
    return title


def theme_counts(news: pd.DataFrame) -> pd.Series:
    tags = news["themes"].fillna("").str.split(";").explode()
    tags = tags[tags != ""]
    return tags.map(THEME_LABEL).value_counts()


def fig_news(news: pd.DataFrame, fig: Path) -> str:
    counts = theme_counts(news)
    d0, d1 = news["date"].min(), news["date"].max()
    lead = counts.index[0]
    title = f"Arauco in the news: {lead.lower()} leads the headlines"
    sub = (
        f"{len(news)} headlines from {d0} to {d1}, by theme of the case "
        f"({(news['themes'].fillna('') == '').sum()} without a theme are left out)"
    )
    for c in charts(title, sub, NEWS_SOURCE):
        c.hbars(list(counts.index), list(counts.values), highlight={lead})
        c.xlabel("Headlines")
        c.fig.subplots_adjust(left=0.3, right=0.92)
        c.save(fig, "news")
    return title


# --- the comments -------------------------------------------------------------------------------


def pct(a: float, b: float) -> str:
    return f"{(a / b - 1):+.0%}"


def data_notes(fao: pd.DataFrame, country: str) -> list[str]:
    """One sentence per indicator for the latest year, each computed from the data."""
    prod = element(fao, country, "Production")
    qty = element(fao, country, "Export quantity")
    val = element(fao, country, "Export value")
    y1 = int(prod.index.max())
    notes = [
        f"Pulp production in {y1}: {prod[y1] / 1e6:.1f} million tonnes, "
        f"{pct(prod[y1], prod[y1 - 1])} on {y1 - 1}"
        + (
            " (a record)"
            if prod[y1] >= prod.max()
            else f" ({prod[y1] / prod.max():.0%} of the {int(prod.idxmax())} peak)"
        )
        + "."
    ]
    if y1 in qty.index and y1 in val.index and y1 - 1 in qty.index:
        uv1 = val[y1] * 1000 / qty[y1]
        uv0 = val[y1 - 1] * 1000 / qty[y1 - 1]
        notes.append(
            f"Export unit value, a proxy for the price received: US${uv1:,.0f} a tonne in {y1}, "
            f"{pct(uv1, uv0)} on {y1 - 1}."
        )
        notes.append(f"Share of production exported in {y1}: {qty[y1] / prod[y1]:.0%}.")
    return notes


def news_notes(fresh: pd.DataFrame, n: int = 5) -> list[str]:
    if fresh.empty:
        return ["No new headlines this month."]
    counts = theme_counts(fresh)
    lines = [
        f"{len(fresh)} new headlines; by theme: "
        + ", ".join(f"{k.lower()} {v}" for k, v in counts.items())
        + "."
    ]
    for r in fresh.head(n).itertuples():
        themes = ", ".join(THEME_LABEL[t].lower() for t in r.themes.split(";") if t) or "no theme"
        lines.append(f"[{r.title}]({r.link}) ({r.source}, {r.date}; {themes})")
    return lines


def write_log(path: Path, today: date, notes: list[str], heads: list[str]) -> None:
    """docs/log.md: one dated entry per run, newest first; the 'living' part of the case."""
    entry = (
        f"## {today.isoformat()}\n\n"
        + "\n".join(f"- {x}" for x in notes)
        + "\n\n**News.** "
        + heads[0]
        + "\n\n"
        + "\n".join(f"- {x}" for x in heads[1:])
        + "\n"
    )
    head = (
        "# Case log\n\nWritten by the monthly update, newest first. "
        "Every sentence is computed from the data.\n\n"
    )
    old = path.read_text() if path.exists() else head
    body = old[len(head) :] if old.startswith(head) else old
    body = re.sub(rf"## {today.isoformat()}\n.*?(?=\n## |\Z)", "", body, flags=re.S).lstrip()
    path.write_text(head + entry + ("\n" + body if body else ""))


def timeline_page(timeline: dict, research: pd.DataFrame) -> str:
    rows = "\n".join(
        f"| {e['year']} | {THEME_LABEL.get(e['theme'], e['theme'])} | "
        f"{' '.join(e['event'].split())} |"
        for e in timeline["events"]
    )
    qs = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(timeline["questions"]))
    top = research.sort_values("cited", ascending=False).head(8)
    papers = "\n".join(
        f"- {r.year}. [{r.title}](https://openalex.org/{r.id}) "
        f"({r.source or 'n/a'}; {r.cited} citations)"
        for r in top.itertuples()
    )
    return f"""# Timeline and research on the case

## Questions

{qs}

**Working hypothesis.** {timeline["hypothesis"]}

## Base timeline (from the essay)

| Year | Theme | Event |
|---|---|---|
{rows}

New events after the essay are recorded in the [case log](log.md).

## Research on Arauco and Chilean forestry

{len(research)} articles in OpenAlex; the most cited:

{papers}
"""


# --- latest.json and README -----------------------------------------------------------------------


def latest(
    fao: pd.DataFrame, news: pd.DataFrame, fresh: pd.DataFrame, country: str, today: date
) -> dict:
    prod = element(fao, country, "Production")
    y1 = int(prod.index.max())
    sh = world_shares(fao, [country])[country]
    month = news[news["date"] >= (pd.Timestamp(today) - pd.Timedelta(days=31)).date().isoformat()]
    counts = theme_counts(month) if not month.empty else pd.Series(dtype=int)
    metrics = [
        {
            "id": "pulp_production",
            "label": f"{country}: chemical pulp production",
            "value": round(prod[y1] / 1e6, 2),
            "unit": "million tonnes",
            "period": str(y1),
            "previous": round(prod[y1 - 1] / 1e6, 2),
            "change": round((prod[y1] - prod[y1 - 1]) / 1e6, 2),
            "change_type": "absolute",
        },
        {
            "id": "world_share",
            "label": f"{country}: share of world production",
            "value": round(float(sh[y1]), 4),
            "unit": "share",
            "period": str(y1),
            "previous": round(float(sh[y1 - 1]), 4),
            "change": round(float(sh[y1] - sh[y1 - 1]), 4),
            "change_type": "absolute",
        },
        {
            "id": "headlines_month",
            "label": "Headlines in the last 31 days",
            "value": int(len(month)),
            "unit": "headlines",
            "period": today.isoformat(),
        },
    ]
    lead = counts.index[0].lower() if len(counts) else "no theme"
    headline = (
        f"{country} produced {prod[y1] / 1e6:.1f} million tonnes of chemical pulp in {y1} "
        f"({sh[y1]:.1%} of world output); in the last month, {len(month)} headlines on Arauco, "
        f"led by {lead}."
    )
    return {
        "schema": 1,
        "id": "arauco-living-case",
        "repo": "arauco-living-case",
        "title": "Arauco: a living business-history case",
        "question": (
            "How does a business group sustain an extractive-export model, and how does that "
            "show up in the data and the news?"
        ),
        "as_of": today.isoformat(),
        "frequency": "monthly",
        "updated": today.isoformat(),
        "source": "FAOSTAT; Google News; OpenAlex",
        "headline": headline,
        "metrics": metrics,
        "new_headlines": int(len(fresh)),
    }


def readme_block(doc: dict, notes: list[str]) -> str:
    return (
        f"**Latest reading: {doc['as_of']}.** {doc['headline']}\n\n"
        + "\n".join(f"- {x}" for x in notes)
        + "\n\n*Full monthly entries in the [case log](docs/log.md).*"
    )


def write_readme(block: str, path: Path) -> None:
    text = path.read_text()
    new = f"<!-- latest:start -->\n{block}\n<!-- latest:end -->"
    path.write_text(re.sub(r"<!-- latest:start -->.*?<!-- latest:end -->", new, text, flags=re.S))


def main(root: Path, cfg: dict, timeline: dict, today: date | None = None) -> dict:
    today = today or date.today()
    data, fig, docs = root / "data", root / "docs" / "figures", root / "docs"
    fao = pd.read_csv(data / "faostat_pulp.csv")
    news = pd.read_csv(data / "news.csv", keep_default_na=False)
    fresh = (
        pd.read_csv(data / "news_new.csv", keep_default_na=False)
        if (data / "news_new.csv").exists()
        else news.head(0)
    )
    research = pd.read_csv(data / "research.csv", keep_default_na=False)
    country = cfg["faostat"]["country"]
    titles = {
        "arc": fig_arc(fao, timeline, country, fig),
        "share": fig_share(fao, country, cfg["faostat"]["peers"], fig),
        "news": fig_news(news, fig) if len(theme_counts(news)) else "",
    }
    notes = data_notes(fao, country)
    heads = news_notes(fresh)
    docs.mkdir(parents=True, exist_ok=True)
    write_log(docs / "log.md", today, notes, heads)
    (docs / "timeline.md").write_text(timeline_page(timeline, research))
    doc = latest(fao, news, fresh, country, today)
    (root / "latest.json").write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    write_readme(readme_block(doc, notes + [heads[0]]), root / "README.md")
    for k, t in titles.items():
        if t:
            print(f"::notice title=figure {k}::{t}")
    print(f"::notice title=latest::{doc['headline']}")
    print(f"::notice title=notes::{' '.join(notes)} {heads[0]}")
    return {"titles": titles, "latest": doc, "notes": notes}
