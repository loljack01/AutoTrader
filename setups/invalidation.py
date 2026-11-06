"""Invalidation (SPEC section 3.4).

Uniquement sur clôture d'une bougie, jamais sur une mèche, et
toujours vérifiée sur les données (pas à l'œil). Unité de temps de
référence : 15 minutes en intraday, 4 heures pour le biais. Une
clôture d'invalidation survenue hors séance comptant (avant 09h00 ou
après 17h30) est signalée comme "à confirmer en séance comptant".

Unité de temps 1 minute : elle sert uniquement à déclencher les
alertes de zone et à horodater précisément un contact. Elle ne sert
jamais à valider une clôture, une confirmation (CHoCH) ou une
invalidation.
"""

from datetime import time


def check_invalidation(
    direction: str, level: float, close: float, close_time, interval: str
) -> dict:
    """direction: the trade's direction - 'buy' is invalidated by a
    close below `level`, 'sell' by a close above it. `close_time`: a
    datetime (or bare time) in Europe/Paris. `interval` must not be
    '1m' - the SPEC forbids using the 1-minute timeframe to validate an
    invalidation."""
    if direction not in ("buy", "sell"):
        raise ValueError("direction must be 'buy' or 'sell'")
    if interval == "1m":
        raise ValueError(
            "1-minute closes must never validate an invalidation (SPEC 3.4)"
        )

    invalidated = (direction == "buy" and close < level) or (
        direction == "sell" and close > level
    )
    if not invalidated:
        return {"invalidated": False, "needs_cash_session_confirmation": False}

    t = close_time.time() if hasattr(close_time, "time") else close_time
    outside_cash_session = t < time(9, 0) or t > time(17, 30)
    return {
        "invalidated": True,
        "needs_cash_session_confirmation": outside_cash_session,
    }
