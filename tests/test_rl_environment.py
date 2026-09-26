import numpy as np
import pandas as pd
import pytest

from autotrader.rl import TradingEnv


def _make_data(n=100, seed=1):
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 1, n))
    high = close + rng.random(n)
    low = close - rng.random(n)
    open_ = close + rng.normal(0, 0.1, n)
    volume = rng.integers(100, 1000, n)
    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume}
    )


def test_missing_columns_raises():
    with pytest.raises(ValueError):
        TradingEnv(pd.DataFrame({"Close": [1, 2, 3]}), window_size=2)


def test_insufficient_data_raises():
    with pytest.raises(ValueError):
        TradingEnv(_make_data(n=5), window_size=10)


def test_reset_returns_valid_observation():
    env = TradingEnv(_make_data(), window_size=10)
    obs, info = env.reset()
    assert obs.shape == env.observation_space.shape
    assert env.observation_space.contains(obs)
    assert info["step"] == 10
    assert info["position"] == 0.0


def test_discrete_step_updates_state():
    env = TradingEnv(_make_data(), window_size=10, allow_short=True)
    env.reset()
    obs, reward, terminated, truncated, info = env.step(1)
    assert env.position == 1.0
    assert env.observation_space.contains(obs)
    assert isinstance(reward, float)
    assert not terminated
    assert not truncated

    obs, reward, terminated, truncated, info = env.step(2)
    assert env.position == -1.0


def test_discrete_without_short_has_two_actions():
    env = TradingEnv(_make_data(), window_size=10, allow_short=False)
    assert env.action_space.n == 2
    env.reset()
    with pytest.raises(ValueError):
        env.step(2)


def test_continuous_actions():
    env = TradingEnv(_make_data(), window_size=10, continuous_actions=True)
    env.reset()
    obs, reward, terminated, truncated, info = env.step(np.array([0.5]))
    assert env.position == pytest.approx(0.5)


def test_commission_reduces_net_worth_on_turnover():
    env = TradingEnv(_make_data(), window_size=10, commission=0.5)
    env.reset()
    env.step(1)
    assert env.net_worth < env.initial_balance


def test_episode_terminates_at_end_of_data():
    n = 30
    window = 10
    env = TradingEnv(_make_data(n=n), window_size=window)
    env.reset()
    terminated = False
    steps = 0
    while not terminated:
        _, _, terminated, truncated, _ = env.step(0)
        steps += 1
        if truncated:
            break
    assert steps == (n - 1) - window
