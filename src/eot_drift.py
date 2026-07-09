from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class EOTDriftResult:
    drift: float
    epsilon: float
    status: str
    notes: str
    mean_shift_norm: float
    covariance_shift_norm: float
    n_base: int
    n_recent: int
    n_reference: int


def _as_2d_float_array(X: Any) -> np.ndarray:
    arr = np.asarray(X, dtype=float)
    if arr.ndim != 2:
        raise ValueError("X must be a 2D array")
    mask = np.isfinite(arr).all(axis=1)
    return arr[mask]


def _standardize_pair(X_base: np.ndarray, X_recent: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    pooled = np.vstack([X_base, X_recent])
    mean = pooled.mean(axis=0)
    std = pooled.std(axis=0, ddof=0)
    std = np.where(std <= 1e-12, 1.0, std)
    return (X_base - mean) / std, (X_recent - mean) / std


def _pairwise_half_squared(U: np.ndarray, X: np.ndarray) -> np.ndarray:
    diff = U[:, None, :] - X[None, :, :]
    return 0.5 * np.sum(diff * diff, axis=2)


def compute_reference_points(
    X_base: Any,
    X_recent: Any,
    n_reference: int = 100,
    random_state: int = 42,
) -> np.ndarray:
    """
    Compute shared reference points for EOT barycentric maps.

    The MVP samples from the pooled empirical distribution after standardizing
    the base and recent observations together.
    """
    X_base = _as_2d_float_array(X_base)
    X_recent = _as_2d_float_array(X_recent)
    X_base_s, X_recent_s = _standardize_pair(X_base, X_recent)
    pooled = np.vstack([X_base_s, X_recent_s])
    if len(pooled) == 0:
        raise ValueError("No finite observations are available")

    rng = np.random.default_rng(random_state)
    replace = len(pooled) < n_reference
    idx = rng.choice(len(pooled), size=n_reference, replace=replace)
    return pooled[idx]


def eot_barycentric_map(U: Any, X: Any, epsilon: float) -> tuple[np.ndarray, np.ndarray]:
    """
    Compute entropic OT barycentric map from reference points U to sample X.

    Uniform weights are used and the cost is 0.5 * squared Euclidean distance.
    """
    try:
        import ot
    except Exception as exc:  # pragma: no cover - environment dependent
        raise ImportError("POT is required for EOT barycentric maps") from exc

    U = _as_2d_float_array(U)
    X = _as_2d_float_array(X)
    if len(U) == 0 or len(X) == 0:
        raise ValueError("U and X must contain finite observations")

    a = np.full(len(U), 1.0 / len(U))
    b = np.full(len(X), 1.0 / len(X))
    C = _pairwise_half_squared(U, X)
    epsilon = float(max(epsilon, 1e-8))

    plan = ot.sinkhorn(a, b, C, reg=epsilon, method="sinkhorn_log", numItermax=2000)
    if not np.isfinite(plan).all():
        raise FloatingPointError("Sinkhorn returned non-finite transport weights")
    T = (plan @ X) / a[:, None]
    return T, plan


def compute_eot_drift(
    X_base: Any,
    X_recent: Any,
    n_reference: int = 100,
    epsilon_scale: float = 0.1,
    random_state: int = 42,
) -> EOTDriftResult:
    """
    Compute EOT map distance between base and recent empirical distributions.

    If POT/Sinkhorn fails, the function returns a finite fallback score based on
    mean and covariance shift, with the failure reason in diagnostics.
    """
    X_base = _as_2d_float_array(X_base)
    X_recent = _as_2d_float_array(X_recent)
    if len(X_base) < 3 or len(X_recent) < 3:
        raise ValueError("At least 3 finite observations are required in each window")

    X_base_s, X_recent_s = _standardize_pair(X_base, X_recent)
    mean_shift = float(np.linalg.norm(X_base_s.mean(axis=0) - X_recent_s.mean(axis=0)))
    cov_base = np.cov(X_base_s, rowvar=False)
    cov_recent = np.cov(X_recent_s, rowvar=False)
    covariance_shift = float(np.linalg.norm(np.atleast_2d(cov_base) - np.atleast_2d(cov_recent), ord="fro"))

    U = compute_reference_points(X_base, X_recent, n_reference=n_reference, random_state=random_state)
    pooled = np.vstack([X_base_s, X_recent_s])
    C_pooled = _pairwise_half_squared(pooled, pooled)
    positive_costs = C_pooled[C_pooled > 0]
    median_cost = float(np.median(positive_costs)) if len(positive_costs) else 1.0
    epsilon = max(float(epsilon_scale) * median_cost, 1e-8)

    try:
        T_base, _ = eot_barycentric_map(U, X_base_s, epsilon)
        T_recent, _ = eot_barycentric_map(U, X_recent_s, epsilon)
        drift = float(np.mean(np.sum((T_base - T_recent) ** 2, axis=1)))
        status = "ok"
        notes = ""
    except Exception as exc:  # pragma: no cover - numerical/environment fallback
        drift = float(mean_shift**2 + covariance_shift)
        status = "fallback"
        notes = f"{type(exc).__name__}: {exc}"

    return EOTDriftResult(
        drift=drift,
        epsilon=epsilon,
        status=status,
        notes=notes,
        mean_shift_norm=mean_shift,
        covariance_shift_norm=covariance_shift,
        n_base=len(X_base),
        n_recent=len(X_recent),
        n_reference=n_reference,
    )
