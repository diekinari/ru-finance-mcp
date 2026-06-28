"""Обёртки над cbrapi -> JSON-дружелюбные структуры.

cbrapi возвращает pandas Series/DataFrame с Period/Timestamp-индексом; здесь
приводим к спискам записей со строковыми датами и достаём «последнее значение».
"""
from __future__ import annotations

import cbrapi
import pandas as pd


def _ser(s: pd.Series, tail: int) -> dict:
    s = s.dropna()
    if s.empty:
        return {"latest": None, "latest_date": None, "series": []}
    series = [{"date": str(getattr(i, "date", lambda: i)()), "value": float(v)}
              for i, v in s.tail(tail).items()]
    return {"latest": float(s.iloc[-1]),
            "latest_date": str(getattr(s.index[-1], "date", lambda: s.index[-1])()),
            "series": series}


def _df(df: pd.DataFrame, tail: int) -> dict:
    df = df.tail(tail).copy()
    df.index = [str(getattr(i, "date", lambda: i)()) for i in df.index]
    df.columns = [str(c) for c in df.columns]
    latest = {k: v for k, v in df.iloc[-1].to_dict().items() if pd.notna(v)} if len(df) else {}
    return {"latest": latest,
            "latest_date": df.index[-1] if len(df) else None,
            "rows": df.reset_index(names="date").to_dict("records")}


def key_rate(first_date: str | None = None, last_date: str | None = None,
             tail: int = 30) -> dict:
    """Ключевая ставка ЦБ РФ (главный драйвер рынка облигаций и рубля)."""
    return _ser(cbrapi.get_key_rate(first_date, last_date), tail)


def ruonia(first_date: str | None = None, last_date: str | None = None,
           tail: int = 30) -> dict:
    """RUONIA overnight (% годовых) — ставка денежного рынка.

    cbrapi отдаёт overnight долей (0.1412) — приводим к процентам (×100),
    чтобы единицы совпадали с key_rate.
    """
    return _ser(cbrapi.get_ruonia_overnight(first_date, last_date) * 100, tail)


def ruonia_index(first_date: str | None = None, last_date: str | None = None,
                 tail: int = 12) -> dict:
    """RUONIA-индекс + срочные средние RUONIA_AVG_1M/3M/6M (% годовых).

    Короткая кривая ставок денежного рынка (живая замена прекращённому ROISfix).
    AVG-колонки уже в процентах; RUONIA_INDEX — уровень индекса (не ставка).
    """
    return _df(cbrapi.get_ruonia_index(first_date, last_date), tail)


def ibor(first_date: str | None = None, last_date: str | None = None,
         tail: int = 12) -> dict:
    """MIACR — фактические средневзвешенные ставки межбанка (MBK).

    MosPrime/MIBOR/MIBID прекращены (пустые колонки отфильтрованы);
    актуальны MIACR по срокам D1/D7/...
    """
    df = cbrapi.get_ibor(first_date, last_date).dropna(axis=1, how="all")
    return _df(df, tail)


def currency(symbol: str, first_date: str, last_date: str, tail: int = 30) -> dict:
    """Курс валюты ЦБ к рублю. symbol — тикер валюты, напр. 'USD', 'EUR', 'CNY'."""
    return _ser(cbrapi.get_time_series(symbol, first_date, last_date), tail)


def metals(first_date: str | None = None, last_date: str | None = None,
           tail: int = 12) -> dict:
    """Учётные цены ЦБ на драгметаллы (золото/серебро/платина/палладий)."""
    return _df(cbrapi.get_metals_prices(first_date, last_date), tail)


def reserves(first_date: str | None = None, last_date: str | None = None,
             tail: int = 12) -> dict:
    """Международные (золотовалютные) резервы РФ (ЗВР)."""
    return _df(cbrapi.get_mrrf(first_date, last_date), tail)
