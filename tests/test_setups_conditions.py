import pytest

from setups import conditions


def test_valid_setup_when_all_four_conditions_hold():
    result = conditions.check_setup(
        price=86.0,
        zone=(84.2, 87.6),
        zone_side="discount",
        direction="buy",
        choch_confirmed=True,
        entry=87.6,
        stop=80.0,
        target=110.0,
        cost=3.0,
        min_rr=1.3,
    )
    assert result.missing == []
    assert result.valid


def test_missing_price_out_of_zone():
    result = conditions.check_setup(
        price=95.0,
        zone=(84.2, 87.6),
        zone_side="discount",
        direction="buy",
        choch_confirmed=True,
        entry=87.6,
        stop=80.0,
        target=100.0,
    )
    assert "prix_hors_zone" in result.missing
    assert not result.valid


def test_missing_wrong_side_selling_in_discount():
    result = conditions.check_setup(
        price=86.0,
        zone=(84.2, 87.6),
        zone_side="discount",
        direction="sell",  # spec: on ne vend pas en discount
        choch_confirmed=True,
        entry=87.6,
        stop=95.0,
        target=75.0,
    )
    assert "mauvais_cote_equilibre" in result.missing


def test_missing_choch_confirmation():
    result = conditions.check_setup(
        price=86.0,
        zone=(84.2, 87.6),
        zone_side="discount",
        direction="buy",
        choch_confirmed=False,
        entry=87.6,
        stop=80.0,
        target=100.0,
    )
    assert "pas_de_choch" in result.missing


def test_missing_insufficient_net_rr():
    result = conditions.check_setup(
        price=86.0,
        zone=(84.2, 87.6),
        zone_side="discount",
        direction="buy",
        choch_confirmed=True,
        entry=87.6,
        stop=85.0,  # tight risk
        target=90.0,  # small reward -> net RR well under 1.3
    )
    assert "ratio_net_insuffisant" in result.missing


def test_multiple_missing_conditions_all_named():
    result = conditions.check_setup(
        price=95.0,  # out of zone
        zone=(84.2, 87.6),
        zone_side="discount",
        direction="sell",  # wrong side
        choch_confirmed=False,  # no choch
        entry=87.6,
        stop=85.0,
        target=90.0,  # insufficient RR
    )
    assert set(result.missing) == {
        "prix_hors_zone",
        "mauvais_cote_equilibre",
        "pas_de_choch",
        "ratio_net_insuffisant",
    }
    assert not result.valid


def test_rejects_invalid_direction():
    with pytest.raises(ValueError):
        conditions.check_setup(
            price=86.0,
            zone=(84.2, 87.6),
            zone_side="discount",
            direction="sideways",
            choch_confirmed=True,
            entry=87.6,
            stop=80.0,
            target=100.0,
        )


def test_rejects_invalid_zone_side():
    with pytest.raises(ValueError):
        conditions.check_setup(
            price=86.0,
            zone=(84.2, 87.6),
            zone_side="neutral",
            direction="buy",
            choch_confirmed=True,
            entry=87.6,
            stop=80.0,
            target=100.0,
        )
