"""Облигационная математика: цена из денежных потоков, дюрация, сценарии по ставке.

Считаем то, чего нет в либах: реакцию цены/полного дохода на сдвиг доходности
и реальную доходность к погашению при разной инфляции. Полугодовые купоны ОФЗ.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta


def _to_date(d) -> date:
    if isinstance(d, date):
        return d
    return datetime.strptime(str(d)[:10], "%Y-%m-%d").date()


def _coupon_dates(valdate: date, maturity: date, freq: int = 2) -> list[date]:
    step = round(365 / freq)
    out, d = [], maturity
    while d > valdate:
        out.append(d)
        d = d - timedelta(days=step)
    return sorted(out)


def dirty_price(valdate: date, maturity: date, coupon_rate: float,
                ytm: float, face: float = 1000.0, freq: int = 2) -> float:
    """Грязная цена облигации (в рублях номинала) при заданной YTM, %."""
    c = coupon_rate / freq / 100 * face
    p = 0.0
    for d in _coupon_dates(valdate, maturity, freq):
        t = (d - valdate).days / 365
        cf = c + (face if d == maturity else 0)
        p += cf / (1 + ytm / 100 / freq) ** (freq * t)
    return p


def macaulay_duration(valdate: date, maturity: date, coupon_rate: float,
                      ytm: float, face: float = 1000.0, freq: int = 2) -> float:
    """Дюрация Маколея в годах (из денежных потоков)."""
    c = coupon_rate / freq / 100 * face
    pv_tot = w_tot = 0.0
    for d in _coupon_dates(valdate, maturity, freq):
        t = (d - valdate).days / 365
        cf = c + (face if d == maturity else 0)
        pv = cf / (1 + ytm / 100 / freq) ** (freq * t)
        pv_tot += pv
        w_tot += t * pv
    return round(w_tot / pv_tot, 2) if pv_tot else 0.0


def rate_scenarios(maturity, coupon_rate: float, ytm: float,
                   horizon_days: int = 365, face: float = 1000.0,
                   deltas=(-3, -2, -1, 0, 1, 2, 3), today: str | None = None) -> dict:
    """Полный доход за горизонт при сдвиге доходности на delta п.п.

    Возвращает по каждому delta: total_return_pct = (цена_конца + купоны - цена_старта)/старт.
    Плюс точку безубытка по росту доходности.
    """
    t0 = _to_date(today) if today else date.today()
    mat = _to_date(maturity)
    t1 = t0 + timedelta(days=horizon_days)
    d0 = dirty_price(t0, mat, coupon_rate, ytm, face)
    annual_coupon = coupon_rate / 100 * face * (horizon_days / 365)
    out = []
    for dy in deltas:
        d1 = dirty_price(t1, mat, coupon_rate, ytm + dy, face)
        tr = (d1 + annual_coupon - d0) / d0 * 100
        out.append({"delta_pp": dy, "total_return_pct": round(tr, 1)})
    # безубыток: какой рост доходности обнуляет годовой доход
    lo, hi = 0.0, 10.0
    for _ in range(40):
        mid = (lo + hi) / 2
        tr = (dirty_price(t1, mat, coupon_rate, ytm + mid, face) + annual_coupon - d0) / d0
        if tr > 0:
            lo = mid
        else:
            hi = mid
    return {
        "ytm": ytm, "coupon_pct": coupon_rate, "maturity": str(mat),
        "horizon_days": horizon_days,
        "macaulay_years": macaulay_duration(t0, mat, coupon_rate, ytm, face),
        "scenarios": out,
        "breakeven_yield_rise_pp": round(lo, 2),
    }


def real_return(ytm: float, inflations=(4, 6, 8, 10, 12, 14, 16)) -> list[dict]:
    """Реальная доходность к погашению (номинал YTM зафиксирован) при разной инфляции."""
    return [{"inflation_pct": i,
             "real_return_pct": round(((1 + ytm / 100) / (1 + i / 100) - 1) * 100, 1)}
            for i in inflations]
