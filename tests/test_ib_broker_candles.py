import pandas as pd
import pytest

ib_insync = pytest.importorskip("ib_insync")

from autotrader.brokers.ib import Broker  # noqa: E402


class FakeIB:
    """Stand-in for ib_insync.IB, recording calls instead of hitting a
    real TWS/Gateway connection (none is reachable from this test)."""

    def __init__(self, bars):
        self.bars = bars
        self.calls = []

    def qualifyContracts(self, contract):
        pass

    def reqHistoricalData(
        self,
        contract,
        endDateTime,
        durationStr,
        barSizeSetting,
        whatToShow,
        useRTH,
        formatDate,
    ):
        self.calls.append(
            dict(
                contract=contract,
                endDateTime=endDateTime,
                durationStr=durationStr,
                barSizeSetting=barSizeSetting,
                whatToShow=whatToShow,
                useRTH=useRTH,
                formatDate=formatDate,
            )
        )
        return self.bars


def _bare_broker(bars):
    # Broker.__init__ immediately dials a real IB connection, which isn't
    # reachable here - build an uninitialised instance and wire up just
    # what get_candles() needs instead.
    broker = Broker.__new__(Broker)
    broker.ib = FakeIB(bars)
    broker._check_connection = lambda: None
    return broker


def _make_bars(n=2):
    base = pd.Timestamp("2024-01-01 09:00", tz="UTC")
    return [
        ib_insync.BarData(
            date=base + pd.Timedelta(minutes=i),
            open=100.0 + i,
            high=101.0 + i,
            low=99.5 + i,
            close=100.5 + i,
            volume=10 + i,
            average=100.2 + i,
            barCount=5,
        )
        for i in range(n)
    ]


@pytest.mark.parametrize(
    "granularity,expected",
    [
        ("1min", "1 min"),
        ("1m", "1 min"),
        ("5min", "5 mins"),
        ("1h", "1 hour"),
        ("4h", "4 hours"),
        ("1D", "1 day"),
    ],
)
def test_granularity_to_ib_bar_size(granularity, expected):
    assert Broker._granularity_to_ib_bar_size(granularity) == expected


def test_granularity_to_ib_bar_size_rejects_unsupported_size():
    with pytest.raises(ValueError):
        Broker._granularity_to_ib_bar_size("7min")


@pytest.mark.parametrize(
    "total_seconds,expected",
    [
        (30, "30 S"),
        (3600, "3600 S"),
        (86399, "86399 S"),
        (86400, "1 D"),
        (86401, "2 D"),
        (172800, "2 D"),
    ],
)
def test_seconds_to_ib_duration(total_seconds, expected):
    assert Broker._seconds_to_ib_duration(total_seconds) == expected


def test_get_candles_shapes_dataframe_correctly():
    bars = _make_bars(2)
    broker = _bare_broker(bars)

    df = broker.get_candles(
        "FCE",
        granularity="1min",
        count=2,
        secType="Future",
        exchange="MONEP",
        contract_month="202512",
    )

    assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert len(df) == 2
    assert df["Close"].iloc[0] == pytest.approx(100.5)
    assert df["Close"].iloc[-1] == pytest.approx(101.5)
    assert isinstance(df.index, pd.DatetimeIndex)


def test_get_candles_calls_ib_with_correct_bar_size_and_duration():
    bars = _make_bars(2)
    broker = _bare_broker(bars)

    broker.get_candles(
        "FCE",
        granularity="1min",
        count=2,
        secType="Future",
        exchange="MONEP",
        contract_month="202512",
    )

    call = broker.ib.calls[0]
    assert call["barSizeSetting"] == "1 min"
    assert call["durationStr"] == "120 S"  # 2 bars * 60s
    assert call["whatToShow"] == "TRADES"
    assert call["useRTH"] is False


def test_get_candles_uses_explicit_window_when_given():
    bars = _make_bars(2)
    broker = _bare_broker(bars)

    start = pd.Timestamp("2024-01-01 09:00", tz="UTC")
    end = pd.Timestamp("2024-01-01 11:00", tz="UTC")
    broker.get_candles(
        "FCE",
        granularity="1min",
        start_time=start,
        end_time=end,
        secType="Future",
        exchange="MONEP",
        contract_month="202512",
    )

    call = broker.ib.calls[0]
    assert call["durationStr"] == "7200 S"  # 2 hours
    assert call["endDateTime"] == end


def test_get_candles_returns_empty_dataframe_with_correct_columns_when_no_bars():
    broker = _bare_broker([])

    df = broker.get_candles(
        "FCE",
        granularity="1min",
        count=10,
        secType="Future",
        exchange="MONEP",
        contract_month="202512",
    )

    assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert len(df) == 0
