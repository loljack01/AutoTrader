"""Risk guard-rails, fixed on 2026-11-05 after the quantitative audit, at the
user's request, BEFORE any real trade; updated on 2026-11-06 after the full
audit (capital 10 000 EUR, user's tolerance 500 EUR over 3 months, counters
on REAL money, year-safe dates). Shown every evening.

MAIN strategy (sma20 live tracking, WITHOUT money):
  daily stop       once the day's realised result reaches -3R, no new trade
                   that day (orders already open keep their stop)
  pause            if the live cumulative result falls 15R below its best
                   level, stop and review before any restart
  size if ever     8-10 EUR per trade at most (audit of 06/11: at 25 EUR, one
  traded with      3-month window in four would reach -500 EUR together with
  money            the swing)

REAL MONEY (swing journal data/journal_swing.csv + out-of-system journal
data/journal_hors_systeme.csv), user's rules of 06/11:
  global stop      if the TOTAL real result since the first trade reaches
                   -500 EUR, everything stops and is reviewed before any
                   restart (user's correction of 07/11: 500 EUR is the minimum
                   order per trade; the loss limit is -500 EUR in total, chosen
                   on 07/11, not over a 3-month window)
  daily stop       -3R realised on a day (25 EUR per R) -> no new order that day
  no revenge       after a stop, no order in the opposite direction without a
                   signal of the system (anything else goes to the
                   out-of-system journal and counts in the -500 EUR)

Real results in EUR: the journal's resultat_eur when filled, otherwise
(exit - entry) / (entry - stop) x 25 EUR with the model's stop
(frozen_swing_rsi2_trades.csv; the journal holds INDEX levels).

Usage: python scripts/risk_guard.py
"""

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
TRADES = ROOT / "data" / "backtests" / "frozen_15m_calls_trend_trades.csv"
SWING = ROOT / "data" / "backtests" / "frozen_swing_rsi2_trades.csv"
JOURNAL = ROOT / "data" / "journal_swing.csv"
OUTSIDE = ROOT / "data" / "journal_hors_systeme.csv"
DAILY_STOP, PAUSE = -3.0, -15.0
CAPITAL, RISK_EUR, GLOBAL_STOP_EUR = 10000.0, 45.0, -500.0  # 1R ~45 EUR since 07/11 (500 EUR orders); -500 EUR = total real loss (user, 07/11)


def read_csv(path, **kw):
    try:
        return pd.read_csv(path, **kw)
    except Exception:
        return pd.DataFrame()


def with_year(ddmm_hhmm, now):
    """'dd/mm HH:MM' (no year) -> Timestamp, taking the latest year that is not in the future."""
    out = []
    for s in ddmm_hhmm:
        ts = pd.to_datetime(f"{now.year}/{s[3:5]}/{s[:2]} {s[6:]}", format="%Y/%m/%d %H:%M")
        if ts > now + pd.Timedelta(days=1):
            ts = ts.replace(year=now.year - 1)
        out.append(ts)
    return pd.Series(out, index=ddmm_hhmm.index)


def main_strategy(now):
    t = read_csv(TRADES)
    if not len(t):
        print("Garde-fous (principale) : aucun trade")
        return
    t = t[(t.version == "sma20") & (t.resultat != "open")].copy()
    t["order"] = with_year(t.sortie_paris, now)
    t = t.sort_values("order")
    t["day"] = t.order.dt.strftime("%d/%m/%Y")
    eq = t.net_r.cumsum().to_numpy()
    dd = eq - np.maximum.accumulate(np.r_[0.0, eq])[1:]
    day = t.groupby("day", sort=False).net_r.sum()
    bad = day[day <= DAILY_STOP]
    print(f"Garde-fous (principale, sans argent, suivi depuis le 28/10) : cumul {eq[-1] if len(eq) else 0:+.2f}R, "
          f"ecart au plus haut {dd[-1] if len(dd) else 0:+.2f}R (pause a {PAUSE:+.0f}R), pire ecart {dd.min() if len(dd) else 0:+.2f}R")
    print(f"  journees a {DAILY_STOP:+.0f}R ou pire (arret du jour) : "
          f"{', '.join(f'{d[:5]} {v:+.1f}R' for d, v in bad.items()) if len(bad) else 'aucune'}")
    if len(dd) and dd[-1] <= PAUSE:
        print("  PAUSE : ecart de -15R atteint, pas d'argent avant revision")


def real_money(now):
    rows = []
    j = read_csv(JOURNAL)
    s = read_csv(SWING)
    if len(j):
        j = j[j.prix_sortie.notna()].copy()
        if len(s):
            j = j.merge(s[["marche", "entree", "stop"]], on=["marche", "entree"], how="left")
        else:
            j["stop"] = np.nan
        for x in j.itertuples():
            eur = getattr(x, "resultat_eur", np.nan)
            if pd.isna(eur) and pd.notna(x.stop) and x.prix_entree > x.stop:
                eur = (x.prix_sortie - x.prix_entree) / (x.prix_entree - x.stop) * RISK_EUR
            rows.append((pd.Timestamp(x.sortie), "swing", eur))
    o = read_csv(OUTSIDE)
    for x in o.itertuples() if len(o) else []:
        rows.append((pd.Timestamp(x.date), "hors systeme", x.resultat_eur))
    r = pd.DataFrame(rows, columns=["date", "source", "eur"])
    win = r  # total since the first real trade (user's correction of 07/11: no 3-month window)
    missing = int(win.eur.isna().sum())
    total = win.eur.sum()
    today = r[r.date == now.normalize()].eur.sum()
    print(f"Argent reel (capital {CAPITAL:,.0f} EUR) : total depuis le debut {total:+.0f} EUR "
          f"(arret global a {GLOBAL_STOP_EUR:+.0f} EUR) | aujourd'hui {today:+.0f} EUR soit {today / RISK_EUR:+.1f}R "
          f"(arret du jour a {DAILY_STOP:+.0f}R) | trades reels : {len(r)}"
          + (f" | {missing} sans resultat calculable (stop du modele introuvable : remplir resultat_eur)" if missing else ""))
    if total <= GLOBAL_STOP_EUR:
        print("  ARRET GLOBAL : perte totale de 500 EUR atteinte, tout s'arrete, revision avant toute reprise")
    if today / RISK_EUR <= DAILY_STOP:
        print("  ARRET DU JOUR : -3R realises aujourd'hui, plus aucun nouvel ordre")
    if len(o):
        print(f"  dont hors systeme : {len(o)} ordre(s), {o.resultat_eur.sum():+.0f} EUR (objectif : 0 ordre)")


def main():
    now = pd.Timestamp.now(tz="Europe/Paris").tz_localize(None)
    main_strategy(now)
    real_money(now)


if __name__ == "__main__":
    main()
