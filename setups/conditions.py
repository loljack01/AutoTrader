"""Entry conditions (SPEC section 3.1): a setup is valid only if all
four hold - missing even one means "attente" (waiting), with the exact
missing condition(s) named, never a partial or best-guess signal.

    1. Le prix entre dans une zone identifiée (OB, FVG, demande, offre, OTE).
    2. La zone est du bon côté de l'équilibre (vente en premium, achat en discount).
    3. Une confirmation apparaît : CHoCH en 5 ou 15 minutes dans le sens du trade.
    4. Le ratio rendement/risque de la première cible, net de coûts, est >= 1.3R.
"""

from dataclasses import dataclass, field

from setups.net_r import DEFAULT_ROUND_TRIP_COST, MIN_NET_RR, net_rr


@dataclass
class SetupCheck:
    valid: bool
    missing: list = field(default_factory=list)
    net_rr: float = None


def check_setup(
    price: float,
    zone: tuple,
    zone_side: str,
    direction: str,
    choch_confirmed: bool,
    entry: float,
    stop: float,
    target: float,
    cost: float = DEFAULT_ROUND_TRIP_COST,
    min_rr: float = MIN_NET_RR,
) -> SetupCheck:
    """direction: 'buy' or 'sell'. zone_side: 'discount' or 'premium' -
    the zone's side relative to the range equilibrium."""
    if direction not in ("buy", "sell"):
        raise ValueError("direction must be 'buy' or 'sell'")
    if zone_side not in ("discount", "premium"):
        raise ValueError("zone_side must be 'discount' or 'premium'")

    missing = []

    if not (zone[0] <= price <= zone[1]):
        missing.append("prix_hors_zone")

    correct_side = (direction == "buy" and zone_side == "discount") or (
        direction == "sell" and zone_side == "premium"
    )
    if not correct_side:
        missing.append("mauvais_cote_equilibre")

    if not choch_confirmed:
        missing.append("pas_de_choch")

    rr = net_rr(entry, stop, target, cost)
    if rr < min_rr:
        missing.append("ratio_net_insuffisant")

    return SetupCheck(valid=len(missing) == 0, missing=missing, net_rr=rr)
