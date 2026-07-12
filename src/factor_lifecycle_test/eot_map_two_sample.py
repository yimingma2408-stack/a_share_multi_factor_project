from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any

import numpy as np


def _array(x: Any) -> np.ndarray:
    out = np.asarray(x, dtype=float)
    if out.ndim != 2:
        raise ValueError("samples must be two-dimensional")
    return out[np.isfinite(out).all(axis=1)]


def sample_uniform_unit_ball(n_reference: int, dimension: int, random_state: int) -> np.ndarray:
    """Draw independently from the uniform distribution on a d-dimensional unit ball."""
    if n_reference < 1 or dimension < 1:
        raise ValueError("n_reference and dimension must be positive")
    rng = np.random.default_rng(random_state)
    directions = rng.normal(size=(n_reference, dimension))
    norms = np.linalg.norm(directions, axis=1, keepdims=True)
    directions /= np.where(norms == 0, 1.0, norms)
    radii = rng.random(n_reference) ** (1.0 / dimension)
    return directions * radii[:, None]


def robust_scale_from_base(
    X_base: Any, X_recent: Any, min_scale: float = 1e-8
) -> tuple[np.ndarray, np.ndarray, dict[str, np.ndarray]]:
    """Scale both samples using median/MAD statistics estimated only from base."""
    base, recent = _array(X_base), _array(X_recent)
    if base.shape[1] != recent.shape[1]:
        raise ValueError("base and recent dimensions differ")
    center = np.median(base, axis=0)
    mad_scale = 1.4826 * np.median(np.abs(base - center), axis=0)
    std = np.std(base, axis=0, ddof=1) if len(base) > 1 else np.zeros(base.shape[1])
    fallback = mad_scale <= min_scale
    scale = np.where(fallback, std, mad_scale)
    near_zero = scale <= min_scale
    scale = np.where(near_zero, 1.0, scale)
    diagnostics = {
        "metric_center": center,
        "metric_scale": scale,
        "scaling_fallback": fallback,
        "near_zero_scale_warning": near_zero,
    }
    return (base - center) / scale, (recent - center) / scale, diagnostics


def epsilon_from_pooled(X_base: np.ndarray, X_recent: np.ndarray, epsilon_scale: float = 0.2) -> float:
    pooled = np.vstack([X_base, X_recent])
    diff = pooled[:, None, :] - pooled[None, :, :]
    squared = np.sum(diff * diff, axis=2)
    positive = squared[squared > 1e-14]
    median = float(np.median(positive)) if positive.size else 1.0
    return max(float(epsilon_scale) * median, 1e-8)


def compute_eot_barycentric_map(
    reference_points: Any,
    target_sample: Any,
    epsilon: float,
    target_weights: Any | None = None,
    method: str = "sinkhorn_log",
    num_iter_max: int = 2000,
    stop_thr: float = 1e-9,
    return_diagnostics: bool = False,
    cost_matrix: Any | None = None,
):
    """Compute an EOT barycentric map and optionally return convergence metadata."""
    import ot

    U, X = _array(reference_points), _array(target_sample)
    if len(U) == 0 or len(X) == 0 or U.shape[1] != X.shape[1]:
        raise ValueError("non-empty reference and target samples must share dimension")
    a = np.full(len(U), 1.0 / len(U))
    if target_weights is None:
        b = np.full(len(X), 1.0 / len(X))
    else:
        b = np.asarray(target_weights, dtype=float)
        if b.shape != (len(X),) or np.any(b < 0) or not np.isfinite(b).all() or b.sum() <= 0:
            raise ValueError("invalid target_weights")
        b = b / b.sum()
    cost = (0.5 * np.sum((U[:, None, :] - X[None, :, :]) ** 2, axis=2)
            if cost_matrix is None else np.asarray(cost_matrix, dtype=float))
    if cost.shape != (len(U), len(X)):
        raise ValueError("cost_matrix shape does not match reference and target samples")
    plan, log = ot.sinkhorn(
        a, b, cost, reg=max(float(epsilon), 1e-8), method=method,
        numItermax=num_iter_max, stopThr=stop_thr, log=True, warn=False,
    )
    if not np.isfinite(plan).all():
        raise FloatingPointError("non-finite Sinkhorn plan")
    mapped = (plan @ X) / a[:, None]
    err = log.get("err", [])
    residual = float(err[-1]) if len(err) else np.nan
    diagnostics = {
        "iterations": int(log.get("niter", len(err))),
        "residual": residual,
        "converged": bool(not np.isfinite(residual) or residual <= max(stop_thr * 10, 1e-7)),
        "target_weights": b,
    }
    return (mapped, plan, diagnostics) if return_diagnostics else mapped


def compute_eot_map_test_statistic(map_base: Any, map_recent: Any, n_base: int, n_recent: int) -> float:
    base, recent = _array(map_base), _array(map_recent)
    if base.shape != recent.shape:
        raise ValueError("map shapes differ")
    effective_n = n_base * n_recent / (n_base + n_recent)
    return float(effective_n * np.mean(np.sum((recent - base) ** 2, axis=1)))


def decompose_map_statistic_by_coordinate(
    map_difference: Any, n_base: int, n_recent: int, metric_names: list[str] | tuple[str, ...]
) -> list[dict[str, float | int | str]]:
    diff = _array(map_difference)
    if diff.shape[1] != len(metric_names):
        raise ValueError("metric_names do not match map dimension")
    effective_n = n_base * n_recent / (n_base + n_recent)
    stats = effective_n * np.mean(diff * diff, axis=0)
    total = stats.sum()
    ratios = stats / total if total > 0 else np.zeros_like(stats)
    ranks = (-stats).argsort().argsort() + 1
    return [
        {"metric_name": name, "coordinate_statistic": float(stats[k]),
         "coordinate_contribution_ratio": float(ratios[k]), "coordinate_rank": int(ranks[k])}
        for k, name in enumerate(metric_names)
    ]


def signed_coordinate_diagnostics(
    map_difference: Any,
    metric_names: list[str] | tuple[str, ...],
    better_directions: dict[str, int],
) -> list[dict[str, float | str]]:
    diff = _array(map_difference)
    raw_bad = []
    for k, name in enumerate(metric_names):
        direction = int(better_directions[name])
        raw_bad.append(float(np.mean(np.maximum(-direction * diff[:, k], 0.0) ** 2)))
    denominator = sum(raw_bad) + 1e-15
    rows = []
    for k, name in enumerate(metric_names):
        displacement = float(diff[:, k].mean())
        improvement = int(better_directions[name]) * displacement
        rows.append({
            "metric_name": name,
            "signed_map_displacement": displacement,
            "signed_improvement_score": improvement,
            "deterioration_score": raw_bad[k],
            "deterioration_share": raw_bad[k] / denominator,
            "improvement_or_deterioration": "improvement" if improvement > 0 else "deterioration" if improvement < 0 else "neutral",
        })
    return rows


def _multiplier_weights(rng: np.random.Generator, n: int, method: str, block_length: int | None) -> np.ndarray:
    if method == "iid_multiplier":
        values = rng.exponential(size=n)
    elif method == "block_multiplier":
        length = int(block_length or 8)
        if length < 1:
            raise ValueError("block_length must be positive")
        values = np.repeat(rng.exponential(size=int(np.ceil(n / length))), length)[:n]
    else:
        raise ValueError(f"unknown bootstrap method: {method}")
    return values / values.sum()


def weighted_eot_map_bootstrap(
    reference_points: Any, X_base: Any, X_recent: Any, map_base: Any, map_recent: Any,
    epsilon: float, n_bootstrap: int, random_state: int,
    bootstrap_method: str = "iid_multiplier", block_length: int | None = None,
) -> dict[str, Any]:
    """Centered weighted map bootstrap; block multipliers are an exploratory extension."""
    U, base, recent = _array(reference_points), _array(X_base), _array(X_recent)
    base_map, recent_map = _array(map_base), _array(map_recent)
    rng = np.random.default_rng(random_state)
    scale = np.sqrt(len(base) * len(recent) / (len(base) + len(recent)))
    # Target locations do not change across multiplier draws, so cache both costs.
    base_cost = 0.5 * np.sum((U[:, None, :] - base[None, :, :]) ** 2, axis=2)
    recent_cost = 0.5 * np.sum((U[:, None, :] - recent[None, :, :]) ** 2, axis=2)
    statistics, failures, iterations = [], 0, []
    for _ in range(int(n_bootstrap)):
        try:
            wb = _multiplier_weights(rng, len(base), bootstrap_method, block_length)
            wr = _multiplier_weights(rng, len(recent), bootstrap_method, block_length)
            mb, _, db = compute_eot_barycentric_map(U, base, epsilon, wb, return_diagnostics=True, cost_matrix=base_cost)
            mr, _, dr = compute_eot_barycentric_map(U, recent, epsilon, wr, return_diagnostics=True, cost_matrix=recent_cost)
            centered = scale * ((mb - base_map) - (mr - recent_map))
            statistics.append(float(np.mean(np.sum(centered * centered, axis=1))))
            iterations.extend([db["iterations"], dr["iterations"]])
        except Exception:
            failures += 1
    return {"bootstrap_statistics": np.asarray(statistics), "bootstrap_failures": failures,
            "mean_iterations": float(np.mean(iterations)) if iterations else np.nan,
            "max_iterations": int(max(iterations)) if iterations else 0}


def run_eot_map_two_sample_test(
    X_base: Any, X_recent: Any, n_reference: int = 100, epsilon_scale: float = 0.2,
    n_bootstrap: int = 300, alpha: float = 0.05, random_state: int = 42,
    bootstrap_method: str = "iid_multiplier", block_length: int | None = None,
) -> dict[str, Any]:
    start = perf_counter()
    base, recent, scaling = robust_scale_from_base(X_base, X_recent)
    if len(base) < 3 or len(recent) < 3:
        raise ValueError("each sample needs at least three finite rows")
    U = sample_uniform_unit_ball(n_reference, base.shape[1], random_state)
    epsilon = epsilon_from_pooled(base, recent, epsilon_scale)
    map_base, _, diag_base = compute_eot_barycentric_map(U, base, epsilon, return_diagnostics=True)
    map_recent, _, diag_recent = compute_eot_barycentric_map(U, recent, epsilon, return_diagnostics=True)
    difference = map_recent - map_base
    unscaled = float(np.mean(np.sum(difference * difference, axis=1)))
    statistic = compute_eot_map_test_statistic(map_base, map_recent, len(base), len(recent))
    boot = weighted_eot_map_bootstrap(
        U, base, recent, map_base, map_recent, epsilon, n_bootstrap,
        random_state + 1, bootstrap_method, block_length,
    )
    values = boot["bootstrap_statistics"]
    if not len(values):
        raise RuntimeError("all bootstrap repetitions failed")
    critical = float(np.quantile(values, 1 - alpha))
    p_value = float((1 + np.count_nonzero(values >= statistic)) / (len(values) + 1))
    return {
        "test_statistic": statistic, "unscaled_map_distance": unscaled,
        "effective_sample_size": len(base) * len(recent) / (len(base) + len(recent)),
        "n_base": len(base), "n_recent": len(recent), "n_reference": len(U),
        "epsilon": epsilon, "epsilon_scale": epsilon_scale,
        "map_base": map_base, "map_recent": map_recent, "map_difference": difference,
        "reference_points": U, "reference_seed": random_state,
        "bootstrap_critical_value": critical, "p_value": p_value,
        "reject_raw": p_value <= alpha, "bootstrap_statistics": values,
        "bootstrap_method": bootstrap_method, "n_bootstrap": n_bootstrap,
        "block_length": block_length, "scaling_diagnostics": scaling,
        "sinkhorn_status": "ok" if diag_base["converged"] and diag_recent["converged"] else "warning",
        "bootstrap_status": "ok" if boot["bootstrap_failures"] == 0 else "partial_failure",
        "bootstrap_failures": boot["bootstrap_failures"], "mean_iterations": boot["mean_iterations"],
        "max_iterations": boot["max_iterations"], "runtime_seconds": perf_counter() - start,
    }
