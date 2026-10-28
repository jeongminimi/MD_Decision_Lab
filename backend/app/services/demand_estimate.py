"""Transparent demand estimates from observed sales known on the judgment date, checked against later days.

Two estimates for the days after the judgment date:
- velocity: the last 14 days' daily rate held flat.
- seasonal: velocity × last year's whole-sample ratio of (daily rate in the same later days) ÷ (daily rate in the
  same last 14 days). Only last year's sales are used, so the factor was knowable on the judgment date.
"""

from datetime import date, timedelta

METHOD_LABELS = {"velocity": "최근 14일 속도 유지", "seasonal": "작년 계절 보정"}
MIN_REFERENCE_UNITS = 100  # below this, last year's pooled ratio is too thin to use


def previous_year(day: date) -> date:
    try:
        return day.replace(year=day.year - 1)
    except ValueError:
        return day.replace(year=day.year - 1, day=28)


def windows(as_of: date, horizon: int) -> dict:
    last_year = previous_year(as_of)
    return {"recent": (as_of - timedelta(13), as_of), "after": (as_of + timedelta(1), as_of + timedelta(horizon)),
            "base_last_year": (last_year - timedelta(13), last_year),
            "after_last_year": (last_year + timedelta(1), last_year + timedelta(horizon))}


def seasonal_factor(base_units: int, after_units: int, horizon: int) -> float | None:
    """Last year's later-days daily rate ÷ last-14-days daily rate, pooled over every product."""
    if base_units < MIN_REFERENCE_UNITS:
        return None
    return round((after_units / horizon) / (base_units / 14), 3)


def estimate(recent_units: int, horizon: int, factor: float | None) -> dict:
    velocity = recent_units / 14 * horizon
    return {"velocity": round(velocity, 1), "seasonal": round(velocity * factor, 1) if factor is not None else None}


def error_summary(pairs: list[tuple[float, int]]) -> dict:
    """WAPE = Σ|estimate − actual| ÷ Σ actual; bias = (Σ estimate − Σ actual) ÷ Σ actual."""
    actual = sum(a for _, a in pairs)
    estimated = sum(e for e, _ in pairs)
    if not actual:
        return {"estimated_units": round(estimated), "actual_units": 0, "wape_pct": None, "bias_pct": None}
    return {"estimated_units": round(estimated), "actual_units": actual,
            "wape_pct": round(sum(abs(e - a) for e, a in pairs) / actual * 100, 1),
            "bias_pct": round((estimated - actual) / actual * 100, 1)}
