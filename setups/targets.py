"""Targets (SPEC section 3.3).

    Dans l'ordre : bord opposé de la zone -> pool de liquidité le plus
    proche -> extrême de la structure. Un niveau sans source ne peut pas
    servir de cible.

This module never invents a level - it only orders and returns what the
caller already sourced from real data (a pool from levels/liquidity.py,
a structure extreme from levels/structure.py).
"""


def target_waterfall(
    direction: str, zone: tuple, pools: list = None, structure_extreme: float = None
):
    """direction: 'buy' or 'sell'. `pools`: liquidity pool levels reachable
    in the trade's direction, already sorted nearest-first by the caller.
    Returns an ordered list of candidate targets, opposite zone edge first."""
    if direction not in ("buy", "sell"):
        raise ValueError("direction must be 'buy' or 'sell'")

    zone_lower, zone_upper = zone
    targets = [zone_upper if direction == "buy" else zone_lower]
    if pools:
        targets.extend(pools)
    if structure_extreme is not None:
        targets.append(structure_extreme)
    return targets
