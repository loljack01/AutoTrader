"""Section 2 - verification du constat "57 % des balayages sur des niveaux deja casses en
cloture", avec trois definitions, et recoupement du suivi avec le CSV officiel
data/backtests/frozen_15m_calls_trend_trades.csv (sma20). Descriptif.

  A  cloture au-dela du niveau entre la confirmation du 2e membre du pool et le balayage
     (definition de main_trades.py, = option consumed_pools du moteur)
  B  idem mais depuis la confirmation du 1er membre
  C  trades de la principale qui disparaissent si le moteur tourne avec consumed_pools=True
     (option d'audit existante ; change aussi les cibles, donc indicatif)

Usage: PYTHONDONTWRITEBYTECODE=1 python3 /home/user/AutoTrader/audit/2026-11-06/marche/sweep_check.py
"""
import sys
from pathlib import Path

REPO = Path("/home/user/AutoTrader")
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))
sys.dont_write_bytecode = True
import numpy as np
import pandas as pd
from finta import TA

import backtest_liquidity_sweep_buy as bt
import frozen_15m_calls_trend as fc
from ma_grid_test import trend_up
from levels import structure, liquidity

HERE = Path(__file__).resolve().parent
NOW = pd.Timestamp("2026-11-06 07:00", tz="UTC")


def main():
    t = pd.read_csv(HERE / "trades_principale.csv", parse_dates=["entry_time", "sweep_time"])
    nB, totB, gone, tot = 0, 0, 0, 0
    for sym, (name, k) in fc.MARKETS.items():
        d = bt.cache.closed_bars(bt.cache.load(sym, "15m"), "15m", NOW)
        d.index = pd.to_datetime(d.index, utc=True)
        d = d[~d.index.duplicated(keep="last")].sort_index()
        atr = TA.ATR(d, 14)
        is_hi, is_lo = structure.find_swings(d, n=2)
        pos = {ts: i for i, ts in enumerate(d.index)}
        c = d.Close.to_numpy()
        for side, sname in ((1, "call"), (-1, "put")):
            marks = structure.confirmed_marks(is_lo if side == 1 else is_hi, d.Low if side == 1 else d.High, 2)
            pools = liquidity.find_sweeps(liquidity.find_pools(marks, atr), d, "low" if side == 1 else "high")
            mine = t[(t.symbol == sym) & (t.side == sname)]
            for s in mine.sweep_time:
                ps = [p for p in pools if p["swept_at"] is not None and p["swept_at"] == s]
                if not ps:
                    continue
                totB += 1
                ok = []
                for p in ps:
                    seg = c[pos[p["members"][0][0]] + 1:pos[s]]
                    ok.append(bool((seg < p["level"]).any() if side == 1 else (seg > p["level"]).any()))
                nB += all(ok)
        # C : moteur avec consumed_pools
        k_ = k
        bt.ROUND_TRIP_COST, bt.MIN_RISK_ATR_MULT, bt.STOP_MARGIN = 1.0 * k_, 2.0, 8.0 * k_
        bt.SWING_N, bt.MIN_NET_RR, bt.CHOCH_WINDOW = 2, 1.3, pd.Timedelta(hours=4)
        up = trend_up(sym, d, "SMA", 20)
        alt = pd.concat([bt.backtest(d, True, False, direction="buy", entry_mask=up, consumed_pools=True),
                         bt.backtest(d, True, False, direction="sell", consumed_pools=True)])
        alt = alt[alt.result != "open"]
        base = t[t.symbol == sym]
        tot += len(base)
        gone += (~base.entry_time.isin(alt.entry_time)).sum()
    a = (t.sweep_broken_all.astype(str).str.lower() == "true")
    print(f"A (depuis le 2e membre) : {a.mean():.1%} ({a.sum()}/{len(t)})")
    print(f"B (depuis le 1er membre) : {nB / totB:.1%} ({nB}/{totB})")
    print(f"C (trades absents avec consumed_pools=True) : {gone / tot:.1%} ({gone}/{tot})")
    # avant le 04/11 inclus (perimetre de l'audit du 05/11 : 333 trades)
    m = t.entry_time < pd.Timestamp("2026-11-05", tz="UTC")
    print(f"A sur les trades entres avant le 05/11 : {a[m].mean():.1%} ({a[m].sum()}/{m.sum()})")

    # recoupement du suivi avec le CSV officiel
    csv = pd.read_csv(REPO / "data/backtests/frozen_15m_calls_trend_trades.csv")
    csv = csv[(csv.version == "sma20") & (csv.resultat != "open")]
    live = t[t.live]
    key = lambda x: set(zip(x.iloc[:, 0], x.iloc[:, 1]))
    a1 = key(csv[["marche", "entree_paris"]])
    a2 = key(live.assign(e=pd.to_datetime(live.entry_paris).dt.strftime("%d/%m %H:%M"))[["market", "e"]])
    print(f"suivi : CSV officiel {len(csv)} trades clos ({csv.net_r.sum():+.1f}R) ; reproduction {len(live)} "
          f"({live.net_r.sum():+.1f}R) ; communs {len(a1 & a2)} ; seulement CSV {sorted(a1 - a2)} ; seulement reproduction {sorted(a2 - a1)}")


if __name__ == "__main__":
    main()
