from __future__ import annotations

from typing import Final

from investlab.technical_timing import momentum, trend, volatility, volume
from investlab.technical_timing.models import IndicatorSpec


_SPECS: Final[tuple[IndicatorSpec, ...]] = (
    IndicatorSpec("SMA", "trend", "N1=5,N2=20", "short MA crosses long MA", trend.sma),
    IndicatorSpec(
        "EMA", "trend", "N1=10,N2=20", "short EMA crosses long EMA", trend.ema_cross
    ),
    IndicatorSpec(
        "KAMA", "trend", "N1=10,N2=20", "short KAMA crosses long KAMA", trend.kama_cross
    ),
    IndicatorSpec(
        "MACD",
        "trend",
        "N1=12,N2=26,N3=9",
        "MACD histogram above/below zero",
        trend.macd,
    ),
    IndicatorSpec(
        "AROON",
        "trend",
        "N=20,H=70",
        "Aroon up/down threshold confirmation",
        trend.aroon,
    ),
    IndicatorSpec("ADX", "trend", "N=14", "+DI crosses -DI", trend.adx),
    IndicatorSpec("DPO", "trend", "N=20", "DPO crosses zero", trend.dpo),
    IndicatorSpec(
        "SAR", "trend", "N=0.02,M=0.2", "SAR below/above close", trend.sar_proxy
    ),
    IndicatorSpec("MOM", "momentum", "N=10", "MOM above/below zero", momentum.mom),
    IndicatorSpec("BIAS", "momentum", "N=26,H=5", "BIAS threshold", momentum.bias),
    IndicatorSpec(
        "RSI",
        "momentum",
        "N=14,H=70,L=30",
        "RSI re-enters from oversold/overbought",
        momentum.rsi,
    ),
    IndicatorSpec("ROC", "momentum", "N=20", "ROC above/below zero", momentum.roc),
    IndicatorSpec(
        "KDJ",
        "momentum",
        "N=9,M=3,H=80,L=20",
        "K crosses D in extreme zone",
        momentum.kdj,
    ),
    IndicatorSpec(
        "WR", "momentum", "N=6,H=-20,L=-80", "WR threshold cross", momentum.wr
    ),
    IndicatorSpec(
        "CCI", "momentum", "N=14,H=100,L=-100", "CCI threshold", momentum.cci
    ),
    IndicatorSpec("CMO", "momentum", "N=25", "CMO above/below zero", momentum.cmo),
    IndicatorSpec(
        "UO", "momentum", "N1=7,N2=14,N3=28", "UO threshold cross", momentum.uo
    ),
    IndicatorSpec(
        "TRIX", "momentum", "N1=12,N2=20", "TRIX crosses trigger", momentum.trix
    ),
    IndicatorSpec(
        "POS", "momentum", "N=20,H=80,L=20", "position threshold cross", momentum.pos
    ),
    IndicatorSpec(
        "ATR/KC",
        "volatility",
        "N=14,M=2",
        "close breaks Keltner channel",
        volatility.atr_kc,
    ),
    IndicatorSpec(
        "BBANDS",
        "volatility",
        "N=20,M=2",
        "close breaks Bollinger band",
        volatility.bbands,
    ),
    IndicatorSpec(
        "DC", "volatility", "N=20", "close breaks Donchian channel", volatility.dc
    ),
    IndicatorSpec(
        "ACCBANDS",
        "volatility",
        "N=20,M=4",
        "close breaks acceleration bands",
        volatility.accbands,
    ),
    IndicatorSpec(
        "MASSI",
        "volatility",
        "N1=9,N2=25",
        "mass-index reversal setup",
        volatility.massi,
    ),
    IndicatorSpec(
        "RVI", "volatility", "N=14,H=70,L=30", "RVI threshold cross", volatility.rvi
    ),
    IndicatorSpec(
        "UDVD", "volatility", "N=20", "up/down volatility difference", volatility.udvd
    ),
    IndicatorSpec(
        "AD", "volume", "N1=3,N2=10", "ADOSC with 90-day trend filter", volume.ad
    ),
    IndicatorSpec(
        "OBV", "volume", "N1=10,N2=20", "OBV short MA minus long MA", volume.obv
    ),
    IndicatorSpec("MFI", "volume", "N=14,H=80,L=20", "MFI threshold cross", volume.mfi),
    IndicatorSpec("EOM", "volume", "N=20", "EOM above/below zero", volume.eom),
    IndicatorSpec(
        "MAAMT", "volume", "N=30", "volume crosses its moving average", volume.maamt
    ),
    IndicatorSpec("FI", "volume", "N=13", "force index above/below zero", volume.fi),
)


def default_indicator_specs() -> tuple[IndicatorSpec, ...]:
    return _SPECS
