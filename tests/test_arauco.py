from datetime import date

import pandas as pd
import yaml

from arauco import report
from arauco import sources as src

RSS = b"""<?xml version="1.0"?><rss><channel>
<item><title>Arauco anuncia inversion en Brasil - Diario Financiero</title>
<link>https://x/1</link><pubDate>Sat, 22 Aug 2026 10:00:00 GMT</pubDate>
<source url="https://df.cl">Diario Financiero</source></item>
<item><title>Incendio en la provincia de Arauco - BioBioChile</title>
<link>https://x/2</link><pubDate>Mon, 08 Jun 2026 10:00:00 GMT</pubDate>
<source url="https://biobiochile.cl">BioBioChile</source></item>
</channel></rss>"""
CFG = yaml.safe_load(open("config/sources.yaml"))


def test_parse_rss_strips_source_and_dates():
    rows = src.parse_rss(RSS, "q")
    assert rows[0]["title"] == "Arauco anuncia inversion en Brasil"
    assert rows[0]["date"] == "2026-08-22" and rows[0]["source"] == "Diario Financiero"


def test_relevance_and_themes_ignore_accents():
    assert src.relevant("Arauco anuncia inversión", CFG["news"])
    assert not src.relevant("Incendio en la provincia de Arauco", CFG["news"])
    assert src.tag(
        "Celulosa Arauco: bono sostenible y certificación FSC", CFG["news"]["themes"]
    ) == ("legitimacy")
    assert "group" in src.tag("Copec respalda inversión de Arauco", CFG["news"]["themes"])


def test_merge_news_keeps_history_and_flags_new():
    a = pd.DataFrame(
        [
            {
                "date": "2026-08-01",
                "source": "s",
                "title": "Arauco A",
                "link": "l",
                "themes": "",
                "query": "q",
            }
        ]
    )
    b = pd.DataFrame(
        [
            {
                "date": "2026-09-01",
                "source": "s",
                "title": "Arauco  a.",
                "link": "l",
                "themes": "",
                "query": "q",
            },
            {
                "date": "2026-09-02",
                "source": "s",
                "title": "Arauco B",
                "link": "l",
                "themes": "market",
                "query": "q",
            },
        ]
    )
    full, fresh = src.merge_news(a, b)
    assert list(fresh["title"]) == ["Arauco B"] and len(full) == 2
    assert full.iloc[0]["date"] == "2026-09-02"


def fao():
    rows = []
    for y in range(1961, 2025):
        cl = 0.2e6 + (y - 1961) * 0.09e6
        rows += [
            {"area": "Chile", "element": "Production", "unit": "t", "year": y, "value": cl},
            {
                "area": "Chile",
                "element": "Export Quantity",
                "unit": "t",
                "year": y,
                "value": cl * 0.8,
            },
            {
                "area": "Chile",
                "element": "Export Value",
                "unit": "1000 USD",
                "year": y,
                "value": cl * 0.8 * (0.5 + (y % 5) / 10),
            },
            {"area": "Brazil", "element": "Production", "unit": "t", "year": y, "value": cl * 2},
            {"area": "Finland", "element": "Production", "unit": "t", "year": y, "value": 5e6},
            {"area": "World", "element": "Production", "unit": "t", "year": y, "value": 1.2e8},
        ]
    return pd.DataFrame(rows)


def test_report_end_to_end(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "README.md").write_text("<!-- latest:start -->\nold\n<!-- latest:end -->\n")
    fao().to_csv(tmp_path / "data" / "faostat_pulp.csv", index=False)
    news = pd.DataFrame(
        [
            {
                "date": "2026-10-20",
                "source": "s",
                "title": "Arauco y Copec invierten",
                "link": "l",
                "themes": "group",
                "query": "q",
            },
            {
                "date": "2026-10-25",
                "source": "s",
                "title": "Arauco precio celulosa",
                "link": "l",
                "themes": "market",
                "query": "q",
            },
        ]
    )
    news.to_csv(tmp_path / "data" / "news.csv", index=False)
    news.head(1).to_csv(tmp_path / "data" / "news_new.csv", index=False)
    pd.DataFrame(
        [{"id": "W1", "year": 2018, "title": "Valdivia mill", "source": "J", "cited": 3}]
    ).to_csv(tmp_path / "data" / "research.csv", index=False)
    timeline = yaml.safe_load(open("config/timeline.yaml"))
    cfg = {**CFG, "faostat": {**CFG["faostat"], "peers": ["Brazil", "Finland"]}}
    out = report.main(tmp_path, cfg, timeline, today=date(2026, 11, 1))
    assert out["notes"][0].startswith("Pulp production in 2024: 5.9 million tonnes")
    assert "(a record)" in out["notes"][0]
    assert "US$" in out["notes"][1]
    assert out["latest"]["metrics"][2]["value"] == 2
    log = (tmp_path / "docs" / "log.md").read_text()
    assert log.count("## 2026-11-01") == 1
    report.main(tmp_path, cfg, timeline, today=date(2026, 11, 1))  # rerun the same day
    assert (tmp_path / "docs" / "log.md").read_text().count("## 2026-11-01") == 1
    for name in ("arc", "share", "news"):
        assert (tmp_path / "docs" / "figures" / f"{name}-dark.png").exists()
