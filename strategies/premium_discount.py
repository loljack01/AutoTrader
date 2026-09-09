import numpy as np
import pandas as pd
from finta import TA
from autotrader import Order, indicators
from autotrader.strategy import Strategy


def compute_market_structure(
    data: pd.DataFrame, swing_high: pd.Series, swing_low: pd.Series
):
    """Classifies each bar into a market structure trend (bullish/bearish)
    and, where applicable, a BOS or CHoCH event.

    A break of the previously-established swing high/low, by closing price,
    is a **BOS** (Break of Structure) if it continues the current trend, or
    a **CHoCH** (Change of Character) if it is the first break against the
    current trend - the classic first sign of a potential reversal. Before
    any trend has been established, the first break is labelled a BOS.

    This is intentionally close-based (not wick-based): a break is only
    counted once price *closes* beyond the reference level, which is less
    noisy than reacting to a single wick poking through it.

    Parameters
    ----------
    data : pd.DataFrame
        OHLC data.

    swing_high, swing_low : pd.Series
        The forward-filled last-confirmed swing high/low series, as
        produced by `PremiumDiscountZones.generate_features` (same index
        as `data`). NaN before any swing has been confirmed.

    Returns
    -------
    trend : pd.Series
        "bullish" / "bearish" / None, forward-filled from the last event.

    event : pd.Series
        "BOS_bullish" / "CHoCH_bullish" / "BOS_bearish" / "CHoCH_bearish"
        on the bar it occurs, None otherwise.

    Notes
    -----
    Causal by construction: only `swing_high.shift(1)` / `swing_low.shift(1)`
    (the level as it stood at the close of the PREVIOUS bar) is compared
    against the current close, so a bar can never break a level that was
    only established by itself.
    """
    close = data["Close"].to_numpy()
    ref_high = swing_high.shift(1).to_numpy()
    ref_low = swing_low.shift(1).to_numpy()

    trend = [None] * len(data)
    event = [None] * len(data)
    current_trend = None

    for i in range(len(data)):
        broke_up = not np.isnan(ref_high[i]) and close[i] > ref_high[i]
        broke_down = not np.isnan(ref_low[i]) and close[i] < ref_low[i]

        # If a single bar's close somehow breaks both levels (only possible
        # with a very small swing_n on a highly volatile bar), the upward
        # break is resolved first - an arbitrary but deterministic choice.
        if broke_up:
            event[i] = "CHoCH_bullish" if current_trend == "bearish" else "BOS_bullish"
            current_trend = "bullish"
        elif broke_down:
            event[i] = "CHoCH_bearish" if current_trend == "bullish" else "BOS_bearish"
            current_trend = "bearish"

        trend[i] = current_trend

    index = data.index
    return pd.Series(trend, index=index), pd.Series(event, index=index)


def compute_liquidity_sweeps(
    data: pd.DataFrame, swing_high: pd.Series, swing_low: pd.Series
):
    """Detects liquidity sweeps (stop hunts) of the previously-established
    swing high/low.

    A bullish sweep is a bar whose **wick** trades below the prior swing
    low (taking out the resting sell-side liquidity/stops just beyond it)
    but whose **close** comes back above it - a rejection of the break,
    rather than a genuine continuation. The symmetric bearish sweep wicks
    above the prior swing high and closes back below it.

    This is a different, complementary signal to `bullish_engulfing` /
    `bearish_engulfing`: an engulfing candle only looks at two candles'
    bodies, with no reference to any specific level, whereas a sweep is
    specifically about a level being probed and rejected within a single
    bar. A bar can be both, one, or neither.

    Parameters
    ----------
    data : pd.DataFrame
        OHLC data.

    swing_high, swing_low : pd.Series
        The forward-filled last-confirmed swing high/low series (same
        index as `data`), as produced by
        `PremiumDiscountZones.generate_features`.

    Returns
    -------
    bullish_sweep, bearish_sweep : pd.Series[bool]

    Notes
    -----
    Causal by construction: compared against `swing_high.shift(1)` /
    `swing_low.shift(1)` - the level as it stood at the close of the
    PREVIOUS bar - so a bar can never sweep a level only established by
    itself.
    """
    ref_high = swing_high.shift(1)
    ref_low = swing_low.shift(1)

    bullish_sweep = (data["Low"] < ref_low) & (data["Close"] > ref_low)
    bearish_sweep = (data["High"] > ref_high) & (data["Close"] < ref_high)

    return bullish_sweep.fillna(False), bearish_sweep.fillna(False)


def resample_ohlc(data: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Resamples OHLC(V) data to a coarser timeframe, dropping the final
    bar if it is still in progress (its period hasn't fully elapsed as of
    the last timestamp in `data`) so a higher-timeframe read never relies
    on an incomplete candle."""
    agg = {"Open": "first", "High": "max", "Low": "min", "Close": "last"}
    if "Volume" in data.columns:
        agg["Volume"] = "sum"
    resampled = data.resample(rule).agg(agg).dropna(how="any")

    if len(resampled) == 0:
        return resampled

    # `data` is indexed by each bar's OPEN time, so its last timestamp
    # covers price action through (last timestamp + one base-bar period),
    # not just up to that timestamp itself.
    base_period = (
        data.index[1] - data.index[0] if len(data.index) >= 2 else pd.Timedelta(0)
    )
    offset = pd.tseries.frequencies.to_offset(rule)
    last_bin_end = resampled.index[-1] + offset
    if data.index[-1] + base_period < last_bin_end:
        resampled = resampled.iloc[:-1]

    return resampled


class PremiumDiscountZones(Strategy):
    """Premium/Discount Zone Strategy.

    Rules
    -----
    1. Define the current trading range from the most recent CONFIRMED swing
       high (H) and swing low (L) (`indicators.find_swings`). The midpoint
       of this range is the "equilibrium": EQ = (H + L) / 2.
    2. [L, EQ] is the "discount" zone (price is cheap relative to the
       range) - longs only. [EQ, H] is the "premium" zone (price is
       expensive) - shorts only. When `use_ote` is enabled, entries are
       further restricted to the classic 61.8%-79% Fibonacci retracement
       pocket of the H->L leg (for the discount zone) and the L->H leg
       (for the premium zone), rather than the whole half.
    3. Require a bullish/bearish engulfing candle as the entry trigger, to
       avoid re-entering on every bar spent inside a zone. If
       `use_liquidity_sweep` is enabled, a liquidity sweep of the swing
       (see `compute_liquidity_sweeps`) is also accepted as a trigger in
       its own right - a wick through the swing that gets rejected back
       inside is often a cleaner, earlier confirmation than waiting for a
       full engulfing candle to print.
    4. Optionally require the entry to agree with the prevailing trend, as
       per an EMA filter (longs only above the EMA, shorts only below it)
       and/or a market structure filter (`use_structure_filter`): longs
       only while the last BOS/CHoCH left structure bullish, shorts only
       while it left structure bearish. See `compute_market_structure` for
       exactly how BOS/CHoCH are defined here. `use_htf_filter` applies
       the same structure check on a higher timeframe (`htf_resample`,
       eg. '1h' while trading '1m'): this specifically guards against
       buying a discount zone that keeps redefining itself lower, because
       the *larger* structure is still bearish even though a local swing
       low just triggered an entry on the execution timeframe.
    5. Unless `one_trade_per_range` is disabled, only one entry is taken
       per (H, L) range; a new entry requires a new swing to have
       confirmed and redefined the range. Independently of that, unless
       `allow_pyramiding` is enabled, no new entry is taken while a
       position is already open on the instrument (checked against the
       broker directly, not just in-memory state - this also stops a
       restarted strategy from re-entering a position that survived the
       restart).
    6. Stop loss is placed beyond the swing which defines the range, offset
       by a buffer (a fixed percentage, or a multiple of ATR - see
       `sl_buffer_mode`) so that a liquidity sweep of the swing does not
       trivially stop the trade out. Take profit is a multiple (`RR`) of
       the resulting risk.

    Notes on look-ahead bias
    ------------------------
    `find_swings` is causal: it is built from a standard recursive
    (backward-looking) EMA, and the swing extreme recorded at bar i is the
    max/min of the trailing `swing_n`-bar window ending at i - it never
    reads bars after i. Because `generate_signal` re-fetches data through
    `self.broker.get_candles(...)` (which, when backtesting, is clipped by
    AutoTrader's virtual broker to bars strictly before the current time -
    see `Broker.get_candles` in `autotrader/brokers/virtual.py`) and
    recomputes the swing/zone features from scratch on that slice, no bar
    beyond `dt` can influence the signal generated at `dt`. What IS
    inherent to this method (and to any swing-based tool) is confirmation
    lag: a swing at bar k is only recognised once price reverses for
    `swing_n` bars, i.e. at some bar i > k. That lag is real and
    unavoidable in live trading too, and is not the same thing as
    look-ahead bias.
    """

    def __init__(
        self, parameters, instrument, broker, notifier, logger_kwargs, **kwargs
    ):
        self.name = "Premium/Discount Zone Strategy"
        self.params = parameters
        self.instrument = instrument
        self.broker = broker
        self.notifier = notifier
        self.logger_kwargs = logger_kwargs

        self.indicators = {}
        self._last_entry_range = None

    def generate_features(self, data):
        """Computes the swing range, premium/discount zones and entry
        triggers from the supplied OHLC data."""
        self.data = data

        # Trend filter
        self.ema = TA.EMA(data, self.params["ema_period"])

        # Range-defining swing structure. Highs/Lows are forward-filled so
        # that, at any bar, they hold the most recently CONFIRMED swing
        # extreme (0 before any swing has been confirmed).
        self.swings = indicators.find_swings(data, n=self.params["swing_n"])
        swing_high = self.swings.Highs.replace(0, np.nan).ffill()
        swing_low = self.swings.Lows.replace(0, np.nan).ffill()
        range_size = swing_high - swing_low

        self.swing_high = swing_high
        self.swing_low = swing_low
        self.equilibrium = swing_low + 0.5 * range_size

        if self.params["use_ote"]:
            ote_low = self.params["ote_low"]
            ote_high = self.params["ote_high"]
            # Discount OTE = 61.8%-79% retracement of the H->L leg, ie.
            # measured back DOWN from the swing high - lands just above L.
            self.discount_zone = (
                swing_high - ote_high * range_size,
                swing_high - ote_low * range_size,
            )
            # Premium OTE = 61.8%-79% retracement of the L->H leg, ie.
            # measured back UP from the swing low - lands just below H.
            self.premium_zone = (
                swing_low + ote_low * range_size,
                swing_low + ote_high * range_size,
            )
        else:
            self.discount_zone = (swing_low, self.equilibrium)
            self.premium_zone = (self.equilibrium, swing_high)

        # Entry triggers
        self.bullish_trigger = indicators.bullish_engulfing(data)
        self.bearish_trigger = indicators.bearish_engulfing(data)
        self.bullish_sweep, self.bearish_sweep = compute_liquidity_sweeps(
            data, swing_high, swing_low
        )

        # Market structure (BOS/CHoCH), built on the same swing levels
        self.structure_trend, self.structure_event = compute_market_structure(
            data, swing_high, swing_low
        )

        # Higher-timeframe structure, used as a veto on top of the above
        self.htf_trend = None
        if self.params["use_htf_filter"]:
            htf_data = resample_ohlc(data, self.params["htf_resample"])
            if len(htf_data) >= 2 * self.params["swing_n"] + 2:
                htf_swings = indicators.find_swings(htf_data, n=self.params["swing_n"])
                htf_swing_high = htf_swings.Highs.replace(0, np.nan).ffill()
                htf_swing_low = htf_swings.Lows.replace(0, np.nan).ffill()
                self.htf_trend, _ = compute_market_structure(
                    htf_data, htf_swing_high, htf_swing_low
                )

    def generate_signal(self, dt):
        """Fetches the latest data and checks for a premium/discount zone
        entry signal."""
        atr_warmup = (
            self.params["atr_period"] if self.params["sl_buffer_mode"] == "atr" else 0
        )
        min_bars = (
            max(self.params["ema_period"], 2 * self.params["swing_n"], atr_warmup) + 2
        )
        data = self.broker.get_candles(
            self.instrument,
            granularity=self.params["granularity"],
            count=max(min_bars, self.params["lookback_candles"]),
            end_time=dt,
        )
        if len(data) < min_bars:
            return Order()

        if not self.params["allow_pyramiding"] and self.broker.get_positions(
            self.instrument
        ):
            # Don't open a second position on top of one already open. This
            # also protects against a strategy restart re-entering a
            # position that is still open from before the restart, since
            # `_last_entry_range` only lives in memory.
            return Order()

        self.generate_features(data)

        swing_high = self.swing_high.iloc[-1]
        swing_low = self.swing_low.iloc[-1]
        if np.isnan(swing_high) or np.isnan(swing_low) or swing_high <= swing_low:
            # Not enough swing history yet to define a range
            return Order()

        current_range = (swing_high, swing_low)
        if (
            self.params["one_trade_per_range"]
            and current_range == self._last_entry_range
        ):
            # Already traded this range; wait for a new confirmed swing
            return Order()

        close = self.data.Close.iloc[-1]
        in_discount = (
            self.discount_zone[0].iloc[-1] <= close <= self.discount_zone[1].iloc[-1]
        )
        in_premium = (
            self.premium_zone[0].iloc[-1] <= close <= self.premium_zone[1].iloc[-1]
        )

        trend_filter = self.params["use_trend_filter"]
        uptrend = close > self.ema.iloc[-1]
        downtrend = close < self.ema.iloc[-1]

        structure_filter = self.params["use_structure_filter"]
        current_structure = self.structure_trend.iloc[-1]
        bullish_structure = current_structure == "bullish"
        bearish_structure = current_structure == "bearish"

        htf_filter = self.params["use_htf_filter"]
        htf_structure = self.htf_trend.iloc[-1] if self.htf_trend is not None else None
        htf_bullish = htf_structure == "bullish"
        htf_bearish = htf_structure == "bearish"

        use_sweep = self.params["use_liquidity_sweep"]
        long_trigger = self.bullish_trigger[-1] or (
            use_sweep and bool(self.bullish_sweep.iloc[-1])
        )
        short_trigger = self.bearish_trigger[-1] or (
            use_sweep and bool(self.bearish_sweep.iloc[-1])
        )

        long_ok = (
            in_discount
            and long_trigger
            and (not trend_filter or uptrend)
            and (not structure_filter or bullish_structure)
            and (not htf_filter or htf_bullish)
        )
        short_ok = (
            in_premium
            and short_trigger
            and (not trend_filter or downtrend)
            and (not structure_filter or bearish_structure)
            and (not htf_filter or htf_bearish)
        )

        if long_ok:
            stop, take = self.generate_exit_levels(direction=1)
            if np.isnan(stop) or np.isnan(take):
                return Order()
            self._last_entry_range = current_range
            return Order(direction=1, stop_loss=stop, take_profit=take)

        if short_ok:
            stop, take = self.generate_exit_levels(direction=-1)
            if np.isnan(stop) or np.isnan(take):
                return Order()
            self._last_entry_range = current_range
            return Order(direction=-1, stop_loss=stop, take_profit=take)

        return Order()

    def generate_exit_levels(self, direction):
        """Determines the stop loss and take profit prices for a new
        entry, based on the swing defining the current range."""
        RR = self.params["RR"]
        close = self.data.Close.iloc[-1]

        if self.params["sl_buffer_mode"] == "atr":
            atr = indicators.atr(self.data, self.params["atr_period"]).iloc[-1]
            buffer_amount = self.params["sl_atr_mult"] * atr
        else:
            buffer_amount = self.params["sl_buffer_pc"] * close

        if direction == 1:
            stop = self.swing_low.iloc[-1] - buffer_amount
            take = close + RR * (close - stop)
        else:
            stop = self.swing_high.iloc[-1] + buffer_amount
            take = close - RR * (stop - close)

        return stop, take

    def create_plotting_indicators(self, data):
        """Builds the indicators dict used by AutoPlot, over the full
        backtest dataset."""
        self.generate_features(data)

        self.indicators = {
            "EMA": {"type": "MA", "data": self.ema},
            "Equilibrium": {"type": "MA", "data": self.equilibrium},
            "Discount zone": {
                "type": "bands",
                "lower": self.discount_zone[0],
                "upper": self.discount_zone[1],
                "fill_color": "green",
                "fill_alpha": 0.15,
            },
            "Premium zone": {
                "type": "bands",
                "lower": self.premium_zone[0],
                "upper": self.premium_zone[1],
                "fill_color": "red",
                "fill_alpha": 0.15,
            },
            # +1 while structure is bullish, -1 while bearish, NaN before
            # the first BOS/CHoCH. Plotted as a plain line via the 'MA'
            # type - AutoPlot has no dedicated BOS/CHoCH marker type.
            "Market structure": {
                "type": "MA",
                "data": self.structure_trend.map({"bullish": 1, "bearish": -1}).astype(
                    float
                ),
            },
        }
