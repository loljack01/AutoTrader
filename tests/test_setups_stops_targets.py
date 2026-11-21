import pytest

from setups import stops, targets


def test_buy_stop_is_below_zone_by_the_margin():
    stop = stops.compute_stop("buy", zone=(84.2, 87.6))
    assert stop == 84.2 - 8.0


def test_sell_stop_is_above_zone_by_the_margin():
    stop = stops.compute_stop("sell", zone=(84.2, 87.6))
    assert stop == 87.6 + 8.0


def test_buy_stop_clears_a_pool_below_the_zone_not_just_the_zone():
    stop = stops.compute_stop("buy", zone=(84.2, 87.6), pool_level=82.0)
    assert stop == 82.0 - 8.0


def test_buy_stop_ignores_a_pool_above_the_zone_edge():
    # A pool level ABOVE the zone's own lower edge is less conservative -
    # the zone edge itself still governs.
    stop = stops.compute_stop("buy", zone=(84.2, 87.6), pool_level=86.0)
    assert stop == 84.2 - 8.0


def test_high_volatility_scales_margin_by_1_2():
    stop = stops.compute_stop("buy", zone=(84.2, 87.6), high_volatility=True)
    assert stop == pytest.approx(84.2 - 8.0 * 1.2)


def test_stops_rejects_invalid_direction():
    with pytest.raises(ValueError):
        stops.compute_stop("sideways", zone=(84.2, 87.6))


def test_target_waterfall_buy_starts_with_opposite_zone_edge():
    result = targets.target_waterfall("buy", zone=(84.2, 87.6))
    assert result == [87.6]


def test_target_waterfall_sell_starts_with_opposite_zone_edge():
    result = targets.target_waterfall("sell", zone=(84.2, 87.6))
    assert result == [84.2]


def test_target_waterfall_orders_pools_then_structure_extreme():
    result = targets.target_waterfall(
        "buy", zone=(84.2, 87.6), pools=[92.0, 98.0], structure_extreme=105.0
    )
    assert result == [87.6, 92.0, 98.0, 105.0]


def test_target_waterfall_rejects_invalid_direction():
    with pytest.raises(ValueError):
        targets.target_waterfall("sideways", zone=(84.2, 87.6))
