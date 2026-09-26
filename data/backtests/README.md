# Backtest data

Real market data fetched via the TradingView Premium MCP tools, kept here
(rather than the session scratchpad) so it survives across sessions and
can be accumulated over time.

## cac40_1m_accum.csv

1-minute OHLCV bars for `TVC:CAC40`. The TradingView `get-ohlcv` tool has
no pagination or end-date parameter - each call returns only the most
recent 5000 bars (~13 calendar days for this symbol, given its trading
session gaps). To build a longer 1-minute history than a single call
allows, this file is grown incrementally: a daily job fetches the latest
5000 bars, merges them into this file by timestamp (deduplicating
overlapping rows), and commits the result. Each day typically adds only
the newly-traded minutes since the previous fetch (session gaps mean this
is well under 1440 rows/day), so building up a multi-week window takes
real calendar time, not a single run.

Columns: `Date` (index, UTC), `Open`, `High`, `Low`, `Close`, `Volume`.
