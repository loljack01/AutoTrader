"""TEST 3 of docs/tests_figes_2026-11-06.md (frozen on 2026-11-06 BEFORE
running, at the user's request): half size when the VIX is high (R2).

Data: TVC:VIX daily (data/cache/TVC_VIX_1D.csv, fetched on 06/11/2026).
Rule evaluated: half size on a swing trade if the VIX close of the day before
the entry (last VIX session dated before the entry date, J-1) is > 30.
ADOPTED only if the trades of the reference swing (5-position cap,
test_swing_rsi2_cap5.py) entered with VIX(J-1) > 30 are at least 50 and have
a net R <= 0 at 0.05 %, on the development period (2012-2021) AND on the
reserved period (2022 -> last day). Otherwise normal size whatever the VIX.
Multiple-testing budget: 4 tests (tests 1-4).

Usage: python scripts/test_swing_vix.py dev|reserved
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

import swing_portfolio as sp
from data import cache

LEVEL, MIN_N = 30.0, 50


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "dev"
    period = sp.DEV if which == "dev" else sp.RESERVED
    data = sp.load_all()
    print(f"Reference identique a test_swing_rsi2_cap5 : {'OK' if sp.check_reference(data) else 'DIFFERENT'}")
    v = cache.load("TVC:VIX", "1D")
    v.index = pd.to_datetime(v.index, utc=True)
    v = v[~v.index.duplicated(keep="last")].sort_index()
    vdate = v.index.tz_convert(None).normalize()
    t = sp.select_book(sp.rsi2_candidates(data, period), 5)
    edate = t.entry.dt.tz_convert(None).dt.normalize().to_numpy()
    k = np.searchsorted(vdate.to_numpy(), edate, side="left") - 1
    t["vix_prev"] = np.where(k >= 0, v.Close.to_numpy()[np.clip(k, 0, None)], np.nan)
    hi = t[t.vix_prev > LEVEL]
    lo = t[t.vix_prev <= LEVEL]
    print(f"Periode {which} : {len(t)} trades du swing (5 places)")
    print(f"  VIX veille > {LEVEL:.0f} : {len(hi)} trades, net {hi.r.sum():+.1f}R ({hi.r.mean() if len(hi) else 0:+.3f}R/trade)")
    print(f"  VIX veille <= {LEVEL:.0f} : {len(lo)} trades, net {lo.r.sum():+.1f}R ({lo.r.mean():+.3f}R/trade)")
    ok = len(hi) >= MIN_N and hi.r.sum() <= 0
    print(f"Regle fixee avant ({which}) : demi-taille si VIX > 30 "
          f"{'PASSE' if ok else 'NON ADOPTEE'} (il faut au moins {MIN_N} trades et un net <= 0)")


if __name__ == "__main__":
    main()
