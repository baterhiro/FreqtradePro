"""
BaterHiro - Custom quantitative strategy based on MyStrategy template.

Spec:
- 5m timeframe
- Fixed stoploss: 5%
- Max 5 open trades       (configure in config.json: max_open_trades)
- $200 per trade          (configure in config.json: stake_amount)
"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone
from pandas import DataFrame
from typing import Optional, Union

from freqtrade.strategy import (
    IStrategy,
    Trade,
    Order,
    PairLocks,
    informative,
    BooleanParameter,
    CategoricalParameter,
    DecimalParameter,
    IntParameter,
    RealParameter,
    timeframe_to_minutes,
    timeframe_to_next_date,
    timeframe_to_prev_date,
    merge_informative_pair,
    stoploss_from_absolute,
    stoploss_from_open,
)

import talib.abstract as ta
from technical import qtpylib


class BaterHiro(IStrategy):
    INTERFACE_VERSION = 3

    # -- Strategy settings --
    can_short: bool = True
    timeframe = "5m"
    startup_candle_count: int = 2400
    process_only_new_candles = True
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # -- ROI table: exit at these profit targets --
    minimal_roi = {
        "60": 0.005,
        "30": 0.01,
        "0": 0.02,
    }

    # -- Fixed 3% stoploss --
    stoploss = -0.03

    # -- Trailing stop --
    trailing_stop = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.015
    trailing_only_offset_is_reached = True

    # -- Hyperoptable parameters --
    buy_ema_short = IntParameter(5, 30, default=10, space="buy", optimize=True)
    buy_ema_long = IntParameter(20, 100, default=50, space="buy", optimize=True)
    buy_rsi = IntParameter(30, 55, default=40, space="buy", optimize=True)

    sell_ema_short = IntParameter(5, 30, default=10, space="sell", optimize=True)
    sell_ema_long = IntParameter(20, 100, default=50, space="sell", optimize=True)
    sell_rsi = IntParameter(60, 90, default=70, space="sell", optimize=True)

    # -- Order types --
    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        "stoploss_on_exchange": False,
    }

    order_time_in_force = {"entry": "GTC", "exit": "GTC"}

    # -- Plot config --
    plot_config = {
        "main_plot": {
            "ema_short": {"color": "blue"},
            "ema_long": {"color": "orange"},
            "ema_200_1h": {"color": "purple", "type": "line"},
            "bb_upperband": {"color": "grey"},
            "bb_lowerband": {"color": "grey"},
        },
        "subplots": {
            "RSI": {
                "rsi": {"color": "red"},
            },
            "MACD": {
                "macd": {"color": "blue"},
                "macdsignal": {"color": "orange"},
            },
        },
    }

    @informative("1h")
    def populate_indicators_1h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema_200"] = ta.EMA(dataframe, timeperiod=200)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        for period in [10, 20, 50, 100]:
            dataframe[f"ema_{period}"] = ta.EMA(dataframe, timeperiod=period)

        dataframe["rsi"] = ta.RSI(dataframe)

        macd = ta.MACD(dataframe)
        dataframe["macd"] = macd["macd"]
        dataframe["macdsignal"] = macd["macdsignal"]
        dataframe["macdhist"] = macd["macdhist"]

        bollinger = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
        dataframe["bb_lowerband"] = bollinger["lower"]
        dataframe["bb_middleband"] = bollinger["mid"]
        dataframe["bb_upperband"] = bollinger["upper"]

        dataframe["vwap"] = (
            (dataframe["close"] * dataframe["volume"]).cumsum()
            / dataframe["volume"].cumsum()
        )

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema_short"] = ta.EMA(dataframe, timeperiod=self.buy_ema_short.value)
        dataframe["ema_long"] = ta.EMA(dataframe, timeperiod=self.buy_ema_long.value)
        vol_mean = dataframe["volume"].rolling(20).mean()

        cond_trend_pullback = (
            (dataframe["ema_short"] > dataframe["ema_long"])
            & (dataframe["close"] < dataframe["ema_short"])
            & (dataframe["rsi"] < self.buy_rsi.value)
        )

        cond_bb_bounce = (
            (dataframe["low"].shift(1) < dataframe["bb_lowerband"].shift(1))
            & (dataframe["close"] > dataframe["bb_lowerband"])
            & (dataframe["rsi"] < 45)
        )

        cond_rsi_bounce = (
            qtpylib.crossed_above(dataframe["rsi"], 30)
            & (dataframe["volume"] > vol_mean)
        )

        htf_uptrend = dataframe["close"] > dataframe["ema_200_1h"]
        htf_downtrend = dataframe["close"] < dataframe["ema_200_1h"]
        has_volume = dataframe["volume"] > 0

        dataframe.loc[
            cond_trend_pullback & htf_uptrend & has_volume,
            ["enter_long", "enter_tag"],
        ] = (1, "long_pullback")
        dataframe.loc[
            cond_bb_bounce & htf_uptrend & has_volume,
            ["enter_long", "enter_tag"],
        ] = (1, "long_bb_bounce")
        dataframe.loc[
            cond_rsi_bounce & htf_uptrend & has_volume,
            ["enter_long", "enter_tag"],
        ] = (1, "long_rsi_bounce")

        short_trend_pullback = (
            (dataframe["ema_short"] < dataframe["ema_long"])
            & (dataframe["close"] > dataframe["ema_short"])
            & (dataframe["rsi"] > self.sell_rsi.value)
        )

        short_bb_rejection = (
            (dataframe["high"].shift(1) > dataframe["bb_upperband"].shift(1))
            & (dataframe["close"] < dataframe["bb_upperband"])
            & (dataframe["rsi"] > 55)
        )

        short_rsi_rejection = (
            qtpylib.crossed_below(dataframe["rsi"], 70)
            & (dataframe["volume"] > vol_mean)
        )

        dataframe.loc[
            short_trend_pullback & htf_downtrend & has_volume,
            ["enter_short", "enter_tag"],
        ] = (1, "short_pullback")
        dataframe.loc[
            short_bb_rejection & htf_downtrend & has_volume,
            ["enter_short", "enter_tag"],
        ] = (1, "short_bb_reject")
        dataframe.loc[
            short_rsi_rejection & htf_downtrend & has_volume,
            ["enter_short", "enter_tag"],
        ] = (1, "short_rsi_reject")

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema_short"] = ta.EMA(dataframe, timeperiod=self.sell_ema_short.value)
        dataframe["ema_long"] = ta.EMA(dataframe, timeperiod=self.sell_ema_long.value)

        dataframe.loc[
            (
                (qtpylib.crossed_below(dataframe["ema_short"], dataframe["ema_long"]))
                & (dataframe["rsi"] > self.sell_rsi.value)
                & (dataframe["volume"] > 0)
            ),
            "exit_long",
        ] = 1

        dataframe.loc[
            (
                (qtpylib.crossed_above(dataframe["ema_short"], dataframe["ema_long"]))
                & (dataframe["rsi"] < self.buy_rsi.value)
                & (dataframe["volume"] > 0)
            ),
            "exit_short",
        ] = 1

        return dataframe

    def leverage(self, pair: str, current_time, current_rate: float,
                 proposed_leverage: float, max_leverage: float,
                 entry_tag: Optional[str], side: str, **kwargs) -> float:
        return 1.0
