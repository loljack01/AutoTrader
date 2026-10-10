"""Order blocks (SPEC section 2.4).

    OB baissier : dernière bougie haussière avant une impulsion baissière
    qui casse la structure.
    OB haussier : dernière bougie baissière avant une impulsion haussière
    qui casse la structure.

Zone = from that candle's low wick to its high wick. Order blocks are
anchored on BOS events (levels/structure.py's bos_events), so this
module takes those as input rather than recomputing structure itself.
"""

import pandas as pd


def find_order_blocks(
    data: pd.DataFrame, bullish_bos: pd.Series, bearish_bos: pd.Series
):
    """For each BOS bar, walks backward to the last candle of the
    opposite colour and records its full wick-to-wick range. A BOS with
    no opposite-coloured candle before it (e.g. right at the start of
    the data) is skipped rather than guessed at."""
    is_bullish_candle = data.Close > data.Open
    obs = []
    for i in range(len(data)):
        if bearish_bos.iloc[i]:
            j = i
            while j >= 0 and not is_bullish_candle.iloc[j]:
                j -= 1
            if j >= 0:
                obs.append(
                    {
                        "type": "bearish",
                        "top": data.High.iloc[j],
                        "bottom": data.Low.iloc[j],
                        "candle_at": data.index[j],
                        "confirmed_at": data.index[i],
                    }
                )
        elif bullish_bos.iloc[i]:
            j = i
            while j >= 0 and is_bullish_candle.iloc[j]:
                j -= 1
            if j >= 0:
                obs.append(
                    {
                        "type": "bullish",
                        "top": data.High.iloc[j],
                        "bottom": data.Low.iloc[j],
                        "candle_at": data.index[j],
                        "confirmed_at": data.index[i],
                    }
                )
    return obs
