import numpy as np
from finta import TA
from autotrader import Order, indicators
from autotrader.strategy import Strategy


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
       avoid re-entering on every bar spent inside a zone.
    4. Optionally require the entry to agree with the prevailing trend, as
       per an EMA filter (longs only above the EMA, shorts only below it).
    5. Unless `one_trade_per_range` is disabled, only one entry is taken
       per (H, L) range; a new entry requires a new swing to have
       confirmed and redefined the range.
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

    def generate_signal(self, dt):
        """Fetches the latest data and checks for a premium/discount zone
        entry signal."""
        min_bars = max(self.params["ema_period"], 2 * self.params["swing_n"]) + 2
        data = self.broker.get_candles(
            self.instrument,
            granularity=self.params["granularity"],
            count=max(min_bars, self.params["lookback_candles"]),
            end_time=dt,
        )
        if len(data) < min_bars:
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

        if in_discount and self.bullish_trigger[-1] and (not trend_filter or uptrend):
            stop, take = self.generate_exit_levels(direction=1)
            self._last_entry_range = current_range
            return Order(direction=1, stop_loss=stop, take_profit=take)

        if in_premium and self.bearish_trigger[-1] and (not trend_filter or downtrend):
            stop, take = self.generate_exit_levels(direction=-1)
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
        }
