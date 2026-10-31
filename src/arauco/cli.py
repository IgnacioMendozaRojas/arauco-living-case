"""Command line: `arauco fetch` collects the sources, `arauco report` rebuilds the outputs."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(os.environ.get("ARAUCO_ROOT", "."))


def notice(title: str, msg: str, level: str = "notice") -> None:
    print(f"::{level} title={title}::{msg}", flush=True)


def fetch(cfg: dict) -> None:
    from . import sources as src

    data = ROOT / "data"
    data.mkdir(parents=True, exist_ok=True)
    s = src.session()
    # each source is independent: one failing does not stop the others
    try:
        path = data / "news.csv"
        old = pd.read_csv(path, keep_default_na=False) if path.exists() else pd.DataFrame()
        full, fresh = src.merge_news(old, src.news(s, cfg["news"]))
        full.to_csv(path, index=False)
        fresh.to_csv(data / "news_new.csv", index=False)
        notice("news", f"{len(fresh)} new headlines, {len(full)} in the history")
    except Exception as e:  # noqa: BLE001
        notice("news", f"failed: {e}", "warning")
    try:
        fao = src.faostat(s, cfg["faostat"])
        fao.to_csv(data / "faostat_pulp.csv", index=False)
        elements = sorted(fao["element"].unique())
        notice("faostat", f"{len(fao)} rows, last year {fao['year'].max()}, elements {elements}")
    except Exception as e:  # noqa: BLE001
        notice("faostat", f"failed: {e}", "warning")
    try:
        res = src.research(s, cfg["openalex"]["query"])
        res.to_csv(data / "research.csv", index=False)
        notice("openalex", f"{len(res)} articles")
    except Exception as e:  # noqa: BLE001
        notice("openalex", f"failed: {e}", "warning")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="arauco")
    ap.add_argument("command", choices=["fetch", "report"])
    args = ap.parse_args(argv)
    cfg = yaml.safe_load((ROOT / "config" / "sources.yaml").read_text())
    if args.command == "fetch":
        fetch(cfg)
        return 0
    from . import report

    timeline = yaml.safe_load((ROOT / "config" / "timeline.yaml").read_text())
    report.main(ROOT, cfg, timeline)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
