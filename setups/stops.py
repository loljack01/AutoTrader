"""Stop placement (SPEC section 3.2).

- Toujours au-delà de la zone, jamais à l'intérieur.
- Marge : 8 points au-delà de la zone (fixe - la v1.0 prévoyait
  max(8, 0.15 x ATR(15m)), mais avec un ATR 15m d'environ 12
  points, le terme ATR ne dépassait jamais 8 points en pratique).
- Au contact d'un pool de liquidité (EQH/EQL), le stop se place
  au-delà du pool, pas entre le prix et le pool.
- En contexte "forte volatilité" (SPEC 8.2), marge et distance du
  stop x 1.2.
"""

DEFAULT_MARGIN = 8.0
VOLATILITY_MULTIPLIER = 1.2


def compute_stop(
    direction: str,
    zone: tuple,
    pool_level: float = None,
    margin: float = DEFAULT_MARGIN,
    high_volatility: bool = False,
) -> float:
    """direction: 'buy' (stop below the zone) or 'sell' (stop above).
    If `pool_level` is given, the stop clears that level too, not just
    the zone edge - whichever of the two is more conservative wins."""
    if direction not in ("buy", "sell"):
        raise ValueError("direction must be 'buy' or 'sell'")

    if high_volatility:
        margin *= VOLATILITY_MULTIPLIER

    zone_lower, zone_upper = zone
    if direction == "buy":
        edge = zone_lower if pool_level is None else min(zone_lower, pool_level)
        return edge - margin

    edge = zone_upper if pool_level is None else max(zone_upper, pool_level)
    return edge + margin
