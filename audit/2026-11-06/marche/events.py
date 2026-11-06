"""Annonces majeures 2012-2026 tirees du calendrier economique TradingView
(mcp__Trading_view_premium__mcp-tv-get-economic-calendar, importance haute, fichiers
eco_calendar_*.json de ce dossier) : emploi US (Non Farm Payrolls), CPI US
(Inflation Rate YoY), FOMC (US Interest Rate), BCE (ECB Interest Rate Decision)."""
import json
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
TITLES = {"Non Farm Payrolls": "NFP", "Inflation Rate YoY": "CPI", "Interest Rate": "FOMC",
          "ECB Interest Rate Decision": "BCE"}


def load_events():
    rows = []
    for f in sorted(HERE.glob("eco_calendar_*.json")):
        for x in json.load(open(f))["result"]:
            typ = TITLES.get(x["title"])
            if typ == "FOMC" and x["country"] != "US":
                continue
            if typ:
                rows.append((pd.Timestamp(x["date"]), typ))
    ev = pd.DataFrame(rows, columns=["time", "type"]).drop_duplicates().sort_values("time").reset_index(drop=True)
    return ev


if __name__ == "__main__":
    ev = load_events()
    print(ev.groupby("type").time.agg(["count", "min", "max"]))
