"""Рыночные ожидания по ключевой ставке из G-кривой ОФЗ (КБД / zcyc).

Только числовой расчёт — интерпретация под портфель остаётся в плейбуке агента
(news.md). Источник: ISS zcyc (template 417), блок `yearyields` (точки кривой).

ВАЖНО (терм-премия): доходность ОФЗ = безрисковая ставка + срочная премия +
ожидания. Поэтому спреды к ключевой ставке — БРУТТО (с премией), а не «чистое
ожидание». Чистый прогноз короткой ставки точнее читается по форвардам и якорю к
RUONIA. Это отражено в полях и в `note`.
"""
from __future__ import annotations

import math

from . import cbr
from .session import exec_template, records

T_ZCYC = 417  # /engines/{engine}/zcyc

# Узлы и масштабы гауссовых поправок КБД MOEX (фиксированы методикой; k=1.6).
# a_i = a_{i-1}+0.6*k^(i-1), b_i = 0.6*k^(i-1). Воспроизводит yearyields с точностью 0.0000 пп.
_K = 1.6
_A = [0.0, 0.6]
_B = [0.6]
for _i in range(2, 9):
    _A.append(_A[-1] + 0.6 * _K ** (_i - 1))
for _i in range(1, 9):
    _B.append(_B[-1] * _K)


def _curve(engine: str = "stock"):
    raw = exec_template(T_ZCYC, {"engine": engine})
    yy = records(raw, "yearyields")
    params = (records(raw, "params") or [{}])[0]
    pts = sorted(({"years": r["period"], "yield": r["value"]} for r in yy),
                 key=lambda x: x["years"])
    as_of = yy[0]["tradedate"] if yy else None
    return pts, params, as_of


def _nss(p: dict, t: float) -> float:
    """Доходность КБД MOEX на сроке t (годы), % годовых — модель Нельсона-Сигеля + 9 поправок.

    Параметры B1..B3,G1..G9 даны в б.п. (÷10000); GT — непрерывная ставка,
    КБД = 100*(e^GT − 1). Работает на любом сроке t>0 (вкл. экстраполяцию за 20 лет).
    """
    b0, b1, b2 = p["B1"] / 10000, p["B2"] / 10000, p["B3"] / 10000
    tau = p["T1"]
    g = [p[f"G{i}"] / 10000 for i in range(1, 10)]
    e = math.exp(-t / tau)
    gt = b0 + b1 * tau * (1 - e) / t + b2 * ((1 - e) * tau / t - e)
    gt += sum(g[i] * math.exp(-((t - _A[i]) ** 2) / (_B[i] ** 2)) for i in range(9))
    return 100 * (math.exp(gt) - 1)


def _y(pts: list, params: dict, years: float) -> float:
    """Доходность на сроке: по NSS-модели MOEX (если есть params), иначе интерполяция узлов."""
    if params:
        return _nss(params, years)
    for p in pts:
        if abs(p["years"] - years) < 1e-9:
            return p["yield"]
    xs = [p["years"] for p in pts]
    ys = [p["yield"] for p in pts]
    if years <= xs[0]:
        return ys[0]
    if years >= xs[-1]:
        return ys[-1]
    for i in range(1, len(xs)):
        if years <= xs[i]:
            t = (years - xs[i - 1]) / (xs[i] - xs[i - 1])
            return ys[i - 1] + t * (ys[i] - ys[i - 1])
    return ys[-1]


def _fwd(pts, params, t1: float, t2: float) -> float:
    """Форвардная ставка f(t1,t2), % годовых (effective), из zero-доходностей."""
    z1 = _y(pts, params, t1) / 100
    z2 = _y(pts, params, t2) / 100
    f = ((1 + z2) ** t2 / (1 + z1) ** t1) ** (1 / (t2 - t1)) - 1
    return round(f * 100, 2)


def rate_expectations(key_rate: float | None = None, engine: str = "stock") -> dict:
    """Сигналы рыночных ожиданий по ставке из G-кривой ОФЗ (числа, без интерпретации)."""
    pts, params, as_of = _curve(engine)
    key = key_rate if key_rate is not None else (cbr.key_rate(tail=1).get("latest") or 0)
    ruo = cbr.ruonia(tail=1).get("latest")

    y025, y05, y1, y2, y10 = (_y(pts, params, t) for t in (0.25, 0.5, 1, 2, 10))
    short_vs_key_1y = round(y1 - key, 2)

    # машинная метка с деадбендом (±0.25 пп), чтобы не дёргалась на шуме
    if short_vs_key_1y < -0.25:
        read = "cuts_priced"
    elif short_vs_key_1y > 0.25:
        read = "hikes_priced"
    else:
        read = "flat"

    signals = {
        "slope_10y_1y": round(y10 - y1, 2),
        "slope_2y_3m": round(y2 - y025, 2),
        # БРУТТО-спреды (вкл. срочную премию) — не чистое ожидание:
        "short_vs_key_1y": short_vs_key_1y,
        "short_vs_key_05y": round(y05 - key, 2),
        "priced_cut_1y_pp_gross": round(key - y1, 2),
        # якорь к деньгам сейчас (money rate), ближе к «ожидаемому изменению ставки»:
        "short_vs_ruonia_1y": round(y1 - ruo, 2) if ruo is not None else None,
        # форварды — рыночный путь короткой ставки (чище спреда уровней):
        "fwd_1y_in_1y": _fwd(pts, params, 1, 2),
        "fwd_1y_in_2y": _fwd(pts, params, 2, 3),
        "fwd_3m_in_1y": _fwd(pts, params, 1, 1.25),
        "inverted": y2 < y025,  # значимый участок, не микрогорб короткого конца
        "read": read,
    }
    return {
        "as_of": as_of,
        "key_rate": key,
        "ruonia": ruo,
        "curve": pts,
        "signals": signals,
        "note": ("Спреды к ставке — БРУТТО (включают срочную премию), не чистое "
                 "ожидание. Чистый путь короткой ставки точнее по форвардам / якорю "
                 "к RUONIA. Интерпретация под портфель — на стороне агента."),
    }


def curve_yield(years: float, engine: str = "stock") -> dict:
    """Доходность G-кривой ОФЗ на произвольном сроке (% годовых) — привязка к дюрации бумаги.

    По точной NSS-модели MOEX (Нельсон-Сигель + 9 поправок) из блока params: гладко
    на изгибах и умеет экстраполировать за пределы узлов (0.25–20 лет). Сверено с
    yearyields до 0.0000 пп. Фоллбэк на интерполяцию узлов, если params недоступны.
    """
    pts, params, as_of = _curve(engine)
    method = "NSS" if params else "interp"
    return {"years": years, "yield": round(_y(pts, params, years), 3),
            "as_of": as_of, "method": method}
