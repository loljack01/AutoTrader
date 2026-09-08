import numpy as np
from finta import TA
from autotrader import Order, indicators
from autotrader.strategy import Strategy


class PremiumDiscountZones(Strategy):
    """Premium/Discount Zone Strategy.

    Rules
    -----
    1. Define the current trading range from the most recent swing high and
       swing low (`indicators.find_swings`). The midpoint of this range is
       the "equilibrium".
    2. The lower half of the range is the "discount" zone (price is cheap
       relative to the range); the upper half is the "premium" zone (price
       is expensive). When `use_ote` is enabled, entries are further
       restricted to the 61.8%-79% ("optimal trade entry") pocket of each
       half, rather than the whole half.
    3. Only look for longs in the discount zone, and shorts in the premium
       zone - buying cheap and selling expensive.
    4. Require a bullish/bearish engulfing candle as the entry trigger, to
       avoid re-entering on every bar spent inside a zone.
    5. Optionally require the entry to agree with the prevailing trend, as
       per an EMA filter (longs only above the EMA, shorts only below it).
    6. Stop loss is placed beyond the swing which defines the range; take
       profit is a multiple (`RR`) of the resulting risk.
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

    def generate_features(self, data):
        """Computes the swing range, premium/discount zones and entry
        triggers from the supplied OHLC data."""
        self.data = data

        # Trend filter
        self.ema = TA.EMA(data, self.params["ema_period"])

        # Range-defining swing structure
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
            self.discount_zone = (
                swing_low + ote_low * range_size,
                swing_low + ote_high * range_size,
            )
            self.premium_zone = (
                swing_high - ote_high * range_size,
                swing_high - ote_low * range_size,
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
            return Order(direction=1, stop_loss=stop, take_profit=take)

        if in_premium and self.bearish_trigger[-1] and (not trend_filter or downtrend):
            stop, take = self.generate_exit_levels(direction=-1)
            return Order(direction=-1, stop_loss=stop, take_profit=take)

        return Order()

    def generate_exit_levels(self, direction):
        """Determines the stop loss and take profit prices for a new
        entry, based on the swing defining the current range."""
        RR = self.params["RR"]
        buffer = self.params["sl_buffer_pc"]
        close = self.data.Close.iloc[-1]

        if direction == 1:
            stop = self.swing_low.iloc[-1] * (1 - buffer)
            take = close + RR * (close - stop)
        else:
            stop = self.swing_high.iloc[-1] * (1 + buffer)
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
