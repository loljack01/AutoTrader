"""Premium/discount range and OTE pockets (SPEC section 2.5).

    range      = [dernier swing low confirmé 4h, dernier swing high confirmé 4h]
    equilibre  = (high_range + low_range) / 2
    OTE vendeur  = retracement 62%-79% de la dernière jambe baissière
    OTE acheteur = retracement 62%-79% de la dernière jambe haussière

    Règle : on ne vend pas en discount, on n'achète pas en premium.

IMPORTANT - a documented conflict with this session's own empirical
findings. The existing `strategies/premium_discount.py` AutoTrader
strategy tested an equivalent mechanism (a `zone_resample='4h'` option,
anchoring the range on 4h swings instead of the execution timeframe)
against 2 real FCE1!/CAC40 datasets. Anchoring on 4h made results WORSE,
not better: on the one dataset long enough to judge it, trade count went
up (5 -> 12) but win rate collapsed (60% -> 33%) and the net result
flipped from positive to negative - see that file's docstring and
config/premium_discount.yaml for the numbers. A stale 4h swing goes out
of date as real support/resistance faster than it gets replaced.

This module still implements the range exactly as the SPEC specifies it
(anchored on 4h swings) because that's what building /levels to this
document means. But per the SPEC's own section 7 ("aucune règle ne doit
être considérée comme validée sans test"), that specific choice should
be treated as UNVALIDATED here too, not as proven better just because
it is written down - the same backtest discipline that demoted it in
the other strategy applies to this one.
"""

import pandas as pd


def equilibrium(swing_high_level: pd.Series, swing_low_level: pd.Series) -> pd.Series:
    return (swing_high_level + swing_low_level) / 2


def ote_zones(
    swing_high_level: pd.Series,
    swing_low_level: pd.Series,
    low: float = 0.62,
    high: float = 0.79,
):
    """Returns (buyer_ote, seller_ote), each a (lower_bound, upper_bound)
    pair of Series. Buyer OTE = discount pocket, the 62%-79% retracement
    of the last bullish leg (low -> high), landing just above the swing
    low. Seller OTE = premium pocket, the 62%-79% retracement of the
    last bearish leg (high -> low), landing just below the swing high."""
    range_size = swing_high_level - swing_low_level
    # Buyer OTE (discount, near the swing low): retracement of the
    # H->L leg, measured back DOWN from the high.
    buyer_ote = (
        swing_high_level - high * range_size,
        swing_high_level - low * range_size,
    )
    # Seller OTE (premium, near the swing high): retracement of the
    # L->H leg, measured back UP from the low.
    seller_ote = (
        swing_low_level + low * range_size,
        swing_low_level + high * range_size,
    )
    return buyer_ote, seller_ote


def in_zone(price: float, zone: tuple) -> bool:
    lower, upper = zone
    return lower <= price <= upper
