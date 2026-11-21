"""Gymnasium-compatible trading environment for reinforcement learning.

This module is deliberately decoupled from AutoTrader's live/paper trading
stack (:mod:`autotrader.brokers.virtual`, :class:`~autotrader.autobot.AutoTraderBot`,
etc). Those classes model order books, fills and account state for driving a
strategy bar-by-bar in real time, which is a poor fit for the fast, vectorised
reset/step loop reinforcement learning training requires. Instead,
:class:`TradingEnv` works directly off a price history DataFrame, so it can be
fed data from any AutoTrader feed (OANDA, CCXT, yfinance, ...), or from a
plain CSV file, without needing broker credentials or a running bot.
"""

from __future__ import annotations

from typing import Callable, Optional

import numpy as np
import pandas as pd

try:
    import gymnasium as gym
    from gymnasium import spaces
except ImportError as exc:  # pragma: no cover - exercised via ImportError path
    raise ImportError(
        "The 'gymnasium' package is required to use autotrader.rl. "
        "Install it with `pip install autotrader[rl]`."
    ) from exc


class TradingEnv(gym.Env):
    """A single-asset trading environment following the Gymnasium API.

    The agent controls a target position weight in the asset, in the range
    ``[-1, 1]`` (or ``[0, 1]`` when ``allow_short`` is False), where -1/1
    mean fully short/long and 0 means flat. Each step, the environment moves
    one bar forward, marks the portfolio to the resulting price return, and
    charges a proportional commission on any change in position (turnover).

    Parameters
    ----------
    data : pandas.DataFrame
        Historical price data with, at minimum, ``Open``, ``High``, ``Low``
        and ``Close`` columns (case-insensitive). A ``Volume`` column is
        used as an extra feature when present. The DataFrame should be
        sorted chronologically.

    window_size : int, optional
        The number of trailing bars included in each observation. The
        default is 10.

    initial_balance : float, optional
        The starting net worth of the account. The default is 1000.0.

    commission : float, optional
        Proportional commission charged on position turnover (eg. 0.001 for
        0.1%). The default is 0.001.

    continuous_actions : bool, optional
        If True, the action space is a ``Box`` giving the target position
        weight directly. If False (default), the action space is
        ``Discrete`` with actions for flat/long (and short, when
        ``allow_short`` is True).

    allow_short : bool, optional
        Whether the agent is allowed to hold a short position. The default
        is True.

    reward_function : Callable[[TradingEnv], float], optional
        A custom function computing the reward after each step, given the
        environment instance. Defaults to the log return of net worth.

    price_column : str, optional
        The column used to mark the position to market and compute returns.
        The default is 'Close'.

    Examples
    --------
    >>> import pandas as pd
    >>> from autotrader.rl import TradingEnv
    >>> data = pd.read_csv("EUR_USD.csv")
    >>> env = TradingEnv(data, window_size=20)
    >>> obs, info = env.reset()
    >>> obs, reward, terminated, truncated, info = env.step(env.action_space.sample())
    """

    metadata = {"render_modes": ["human"]}

    def __init__(
        self,
        data: pd.DataFrame,
        window_size: int = 10,
        initial_balance: float = 1000.0,
        commission: float = 0.001,
        continuous_actions: bool = False,
        allow_short: bool = True,
        reward_function: Optional[Callable[["TradingEnv"], float]] = None,
        price_column: str = "Close",
    ) -> None:
        super().__init__()

        if window_size < 1:
            raise ValueError("window_size must be >= 1")

        columns = {c.lower(): c for c in data.columns}
        required = ["open", "high", "low", "close"]
        missing = [c for c in required if c not in columns]
        if missing:
            raise ValueError(
                f"data is missing required column(s): {missing}. "
                "Expected OHLC(V) columns."
            )

        self._data = data.reset_index(drop=True)
        self._price_col = columns[price_column.lower()]
        self._feature_cols = [columns[c] for c in required] + (
            [columns["volume"]] if "volume" in columns else []
        )

        self.window_size = window_size
        self.initial_balance = initial_balance
        self.commission = commission
        self.continuous_actions = continuous_actions
        self.allow_short = allow_short
        self.reward_function = reward_function or self._default_reward

        self._max_step = len(self._data) - 1
        if self._max_step <= window_size:
            raise ValueError(
                "data does not contain enough rows for the requested window_size"
            )

        n_features = len(self._feature_cols) + 2  # + position, + net worth change
        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(window_size, n_features),
            dtype=np.float32,
        )

        if continuous_actions:
            low = -1.0 if allow_short else 0.0
            self.action_space = spaces.Box(
                low=low, high=1.0, shape=(1,), dtype=np.float32
            )
        else:
            # 0: flat, 1: long, 2: short (short only available if allow_short)
            self.action_space = spaces.Discrete(3 if allow_short else 2)

        self.reset()

    def reset(
        self, *, seed: Optional[int] = None, options: Optional[dict] = None
    ) -> tuple[np.ndarray, dict]:
        super().reset(seed=seed)

        self._step = self.window_size
        self.position = 0.0
        self.net_worth = self.initial_balance
        self.history = {
            "net_worth": [self.net_worth],
            "position": [self.position],
        }

        return self._get_observation(), self._get_info()

    def step(self, action) -> tuple[np.ndarray, float, bool, bool, dict]:
        target_position = self._action_to_position(action)

        price_now = self._data.loc[self._step, self._price_col]
        price_next = self._data.loc[self._step + 1, self._price_col]
        asset_return = (price_next - price_now) / price_now

        turnover = abs(target_position - self.position)
        cost = turnover * self.commission
        portfolio_return = self.position * asset_return - cost

        self.net_worth = max(self.net_worth * (1 + portfolio_return), 0.0)
        self.position = target_position
        self._step += 1

        self.history["net_worth"].append(self.net_worth)
        self.history["position"].append(self.position)

        terminated = self._step >= self._max_step
        truncated = self.net_worth <= 0

        reward = self.reward_function(self)
        return self._get_observation(), reward, terminated, truncated, self._get_info()

    def render(self) -> None:
        print(
            f"step={self._step} position={self.position:+.2f} "
            f"net_worth={self.net_worth:.2f}"
        )

    def _action_to_position(self, action) -> float:
        if self.continuous_actions:
            value = np.clip(action, self.action_space.low, self.action_space.high)
            return float(np.asarray(value).reshape(-1)[0])

        action = int(action)
        if action == 0:
            return 0.0
        if action == 1:
            return 1.0
        if action == 2 and self.allow_short:
            return -1.0
        raise ValueError(f"Invalid action: {action!r}")

    def _get_observation(self) -> np.ndarray:
        window = self._data.loc[
            self._step - self.window_size : self._step - 1, self._feature_cols
        ].to_numpy(dtype=np.float64)

        # Express each feature as a fractional change from the start of the
        # window, rather than an absolute price/volume level.
        base = window[0].copy()
        base[base == 0] = 1.0
        normalised = window / base - 1.0

        position_col = np.full((self.window_size, 1), self.position)
        net_worth_col = np.full(
            (self.window_size, 1), self.net_worth / self.initial_balance - 1.0
        )
        obs = np.hstack([normalised, position_col, net_worth_col])
        return obs.astype(np.float32)

    def _get_info(self) -> dict:
        return {
            "step": self._step,
            "net_worth": self.net_worth,
            "position": self.position,
        }

    @staticmethod
    def _default_reward(env: "TradingEnv") -> float:
        prev_net_worth = env.history["net_worth"][-2]
        curr_net_worth = env.history["net_worth"][-1]
        if prev_net_worth <= 0:
            return -1.0
        return float(np.log(curr_net_worth / prev_net_worth))
