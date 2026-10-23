"""Small, auditable conditional-sample statistical utilities."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats


@dataclass(frozen=True)
class OLSResult:
    terms: tuple[str, ...]
    coefficients: np.ndarray
    standard_errors: np.ndarray
    ci_low: np.ndarray
    ci_high: np.ndarray
    p_values: np.ndarray
    n: int
    rank: int
    condition_number: float
    r_squared: float
    residual_abs_fitted_spearman: float


def ols_hc3(y: np.ndarray, x: np.ndarray, terms: list[str]) -> OLSResult:
    """OLS with heteroskedasticity-consistent HC3 covariance; no silent rank loss."""
    y = np.asarray(y, dtype=float)
    x = np.asarray(x, dtype=float)
    if x.ndim != 2 or y.ndim != 1 or x.shape[0] != len(y) or x.shape[1] != len(terms):
        raise ValueError("Design matrix, outcome and term names do not align")
    if not np.isfinite(x).all() or not np.isfinite(y).all() or len(y) <= x.shape[1] + 2:
        raise ValueError("OLS requires finite values and residual degrees of freedom")
    coefficient, _, rank, singular = np.linalg.lstsq(x, y, rcond=None)
    if rank != x.shape[1]:
        raise ValueError("OLS design matrix is rank deficient")
    xtx_inv = np.linalg.inv(x.T @ x)
    fitted = x @ coefficient
    residual = y - fitted
    leverage = np.einsum("ij,jk,ik->i", x, xtx_inv, x)
    if (leverage >= 1 - 1e-10).any():
        raise ValueError("OLS has unit-leverage observations; HC3 is undefined")
    scaled = x * (residual / (1 - leverage))[:, None]
    covariance = xtx_inv @ (scaled.T @ scaled) @ xtx_inv
    standard_errors = np.sqrt(np.maximum(np.diag(covariance), 0))
    if (standard_errors <= 0).any():
        raise ValueError("OLS HC3 standard error is zero or invalid")
    z = coefficient / standard_errors
    p_values = 2 * stats.norm.sf(np.abs(z))
    ci_low = coefficient - stats.norm.ppf(0.975) * standard_errors
    ci_high = coefficient + stats.norm.ppf(0.975) * standard_errors
    total = float(np.sum((y - y.mean()) ** 2))
    r2 = 1 - float(np.sum(residual**2)) / total if total > 0 else math.nan
    diagnostic = stats.spearmanr(np.abs(residual), fitted)
    return OLSResult(
        tuple(terms), coefficient, standard_errors, ci_low, ci_high, p_values,
        len(y), int(rank), float(singular[0] / singular[-1]), r2,
        float(diagnostic.statistic) if np.isfinite(diagnostic.statistic) else math.nan,
    )


def benjamini_hochberg(p_values: list[float] | np.ndarray) -> np.ndarray:
    """BH-adjusted q-values for one predeclared family of finite p-values."""
    values = np.asarray(p_values, dtype=float)
    if values.ndim != 1 or ((values < 0) | (values > 1) | ~np.isfinite(values)).any():
        raise ValueError("BH requires finite p-values in [0, 1]")
    if len(values) == 0:
        return values
    order = np.argsort(values)
    sorted_adjusted = values[order] * len(values) / np.arange(1, len(values) + 1)
    sorted_adjusted = np.minimum.accumulate(sorted_adjusted[::-1])[::-1].clip(0, 1)
    result = np.empty_like(values)
    result[order] = sorted_adjusted
    return result


def spearman_result(x: pd.Series, y: pd.Series, hypothesis: str) -> dict:
    paired = pd.DataFrame({"x": x, "y": y}).dropna()
    if len(paired) < 3:
        raise ValueError("Spearman test needs at least three complete observations")
    result = stats.spearmanr(paired["x"], paired["y"])
    if not np.isfinite(result.statistic) or not np.isfinite(result.pvalue):
        raise ValueError("Spearman result is undefined")
    return {"test": "Spearman rank correlation", "hypothesis": hypothesis,
            "null_hypothesis": "population monotonic association is zero under test assumptions",
            "n": len(paired), "statistic": float(result.statistic),
            "effect_size": float(result.statistic), "p_value": float(result.pvalue),
            "scope": "exploratory conditional-sample association; inclusion probabilities unverified"}
