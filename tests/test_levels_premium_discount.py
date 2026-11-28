import pandas as pd

from levels import premium_discount as pd_levels


def test_equilibrium_is_the_range_midpoint():
    high = pd.Series([100.0])
    low = pd.Series([80.0])
    assert pd_levels.equilibrium(high, low).iloc[0] == 90.0


def test_ote_zones_buyer_sits_near_the_swing_low():
    high = pd.Series([100.0])
    low = pd.Series([80.0])
    buyer, seller = pd_levels.ote_zones(high, low, low=0.62, high=0.79)

    range_size = 20.0
    assert buyer[0].iloc[0] == 100.0 - 0.79 * range_size
    assert buyer[1].iloc[0] == 100.0 - 0.62 * range_size
    # Buyer OTE must sit in the lower half of the range (discount side).
    assert buyer[1].iloc[0] < 90.0


def test_ote_zones_seller_sits_near_the_swing_high():
    high = pd.Series([100.0])
    low = pd.Series([80.0])
    buyer, seller = pd_levels.ote_zones(high, low, low=0.62, high=0.79)

    range_size = 20.0
    assert seller[0].iloc[0] == 80.0 + 0.62 * range_size
    assert seller[1].iloc[0] == 80.0 + 0.79 * range_size
    # Seller OTE must sit in the upper half of the range (premium side).
    assert seller[0].iloc[0] > 90.0


def test_in_zone():
    assert pd_levels.in_zone(85.0, (80.0, 90.0)) is True
    assert pd_levels.in_zone(95.0, (80.0, 90.0)) is False
    assert pd_levels.in_zone(80.0, (80.0, 90.0)) is True  # inclusive bound
