import pytest

from setups import net_r


def test_net_rr_matches_the_spec_worked_example():
    # SPEC section 11: sell 8113-8125 (premium), theoretical entry at
    # the near edge (8113, the side price arrives from), stop ~8135,
    # first target 8066.5, documented as "~1.8R net".
    rr = net_r.net_rr(entry=8113, stop=8135, target=8066.5, cost=3.0)
    assert rr == pytest.approx(1.8, abs=0.1)


def test_net_rr_is_lower_than_gross_rr():
    gross_reward = 100
    gross_risk = 50
    entry, stop, target = 100.0, 50.0, 200.0  # risk=50, reward=100 gross 2R
    assert gross_reward / gross_risk == 2.0
    net = net_r.net_rr(entry, stop, target, cost=3.0)
    assert net < 2.0


def test_meets_minimum_rr_true_when_above_threshold():
    assert net_r.meets_minimum_rr(entry=100, stop=90, target=150, cost=3.0, minimum=1.3)


def test_meets_minimum_rr_false_when_below_threshold():
    assert not net_r.meets_minimum_rr(
        entry=100, stop=95, target=108, cost=3.0, minimum=1.3
    )


def test_net_rr_handles_zero_net_risk_without_dividing_by_zero():
    # entry == stop and cost == 0 -> net_risk is exactly zero.
    assert net_r.net_rr(entry=100, stop=100, target=110, cost=0.0) == float("-inf")
