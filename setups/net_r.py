"""Net-of-cost reward:risk (SPEC section 3.1, point 4).

    Entrée théorique = bord de la zone côté prix.
    Coûts par défaut : 3 points aller-retour (écart, commissions,
    glissement), soustraits du gain et ajoutés au risque.

This is a direct application of the cost-netting correction this
session already applied to the PremiumDiscountZones backtests: gross R
routinely looked positive while net-of-cost R was flat or negative.
"""

DEFAULT_ROUND_TRIP_COST = 3.0
MIN_NET_RR = 1.3


def net_rr(
    entry: float, stop: float, target: float, cost: float = DEFAULT_ROUND_TRIP_COST
) -> float:
    """Net reward:risk to `target`: cost is subtracted from the gross
    gain and added to the risk, per SPEC section 3.1."""
    risk = abs(entry - stop)
    reward = abs(target - entry)
    net_risk = risk + cost
    if net_risk <= 0:
        return float("-inf")
    return (reward - cost) / net_risk


def meets_minimum_rr(
    entry: float,
    stop: float,
    target: float,
    cost: float = DEFAULT_ROUND_TRIP_COST,
    minimum: float = MIN_NET_RR,
) -> bool:
    return net_rr(entry, stop, target, cost) >= minimum
