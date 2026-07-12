from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd


@dataclass(frozen=True)
class FactorSpec:
    factor_name: str
    factor_family: str
    description: str
    formula: str
    direction: int
    lookback_window: int | None
    required_fields: str
    financial_or_market: str
    point_in_time_required: bool
    neutralization_required: bool
    expected_sign: str
    implementation_function: str
    enabled: bool
    lifecycle_enabled: bool
    notes: str = ""


def _spec(name: str, family: str, description: str, formula: str, direction: int,
          lookback: int | None, fields: str, kind: str, function: str,
          enabled: bool = True, lifecycle: bool = False, notes: str = "") -> FactorSpec:
    return FactorSpec(
        factor_name=name,
        factor_family=family,
        description=description,
        formula=formula,
        direction=direction,
        lookback_window=lookback,
        required_fields=fields,
        financial_or_market=kind,
        point_in_time_required=kind == "financial",
        neutralization_required=name != "size",
        expected_sign="positive after direction unification",
        implementation_function=function,
        enabled=enabled,
        lifecycle_enabled=lifecycle,
        notes=notes,
    )


FACTOR_REGISTRY: tuple[FactorSpec, ...] = (
    _spec("reversal_1m", "price_volume", "One-month reversal", "-P_t/P_{t-20}+1", 1, 20, "qfq_close", "market", "src.factors.price_volume.add_reversal", lifecycle=True),
    _spec("momentum_1m", "price_volume", "One-month momentum", "P_t/P_{t-20}-1", 1, 20, "qfq_close", "market", "src.factors.price_volume.add_momentum", lifecycle=True),
    _spec("momentum_3m", "price_volume", "Three-month momentum", "P_t/P_{t-60}-1", 1, 60, "qfq_close", "market", "src.factors.price_volume.add_momentum", lifecycle=True),
    _spec("momentum_6m", "price_volume", "Six-month momentum", "P_t/P_{t-120}-1", 1, 120, "qfq_close", "market", "src.factors.price_volume.add_momentum", lifecycle=True),
    _spec("momentum_12m", "price_volume", "Twelve-month momentum", "P_t/P_{t-250}-1", 1, 250, "qfq_close", "market", "src.factors.price_volume.add_momentum", lifecycle=True),
    _spec("volatility_1m", "risk", "Low one-month realized volatility", "-std(ret,20)", 1, 20, "return_1d", "market", "src.factors.price_volume.add_low_volatility", lifecycle=True),
    _spec("volatility_3m", "risk", "Low three-month realized volatility", "-std(ret,60)", 1, 60, "return_1d", "market", "src.factors.price_volume.add_low_volatility", lifecycle=True),
    _spec("turnover_1m", "price_volume", "Low one-month turnover", "-mean(turnover,20)", 1, 20, "turnover", "market", "src.factors.price_volume.add_turnover_factors", lifecycle=True),
    _spec("turnover_3m", "price_volume", "Low three-month turnover", "-mean(turnover,60)", 1, 60, "turnover", "market", "src.factors.price_volume.add_turnover_factors", lifecycle=True),
    _spec("liquidity_1m", "price_volume", "One-month trading amount liquidity", "log(1+mean(amount,20))", 1, 20, "amount", "market", "src.factors.price_volume.add_liquidity_factor", lifecycle=True),
    _spec("mom_60_20d", "price_volume", "Skip-month three-month momentum", "P_{t-20}/P_{t-60}-1", 1, 60, "qfq_close", "market", "src.factors.price_volume.add_momentum", notes="Implemented library variant; excluded from lifecycle to limit near-duplicate horizons."),
    _spec("mom_120_20d", "price_volume", "Skip-month six-month momentum", "P_{t-20}/P_{t-120}-1", 1, 120, "qfq_close", "market", "src.factors.price_volume.add_momentum", notes="Implemented library variant; excluded from lifecycle to limit near-duplicate horizons."),
    _spec("mom_250_20d", "price_volume", "Skip-month twelve-month momentum", "P_{t-20}/P_{t-250}-1", 1, 250, "qfq_close", "market", "src.factors.price_volume.add_momentum", notes="Implemented library variant; excluded from lifecycle to limit near-duplicate horizons."),
    _spec("lowvol_120d", "risk", "Low 120-day volatility", "-std(ret,120)", 1, 120, "return_1d", "market", "src.factors.price_volume.add_low_volatility", notes="Implemented; watch-only because lifecycle set already contains two volatility horizons."),
    _spec("lowvol_250d", "risk", "Low 250-day volatility", "-std(ret,250)", 1, 250, "return_1d", "market", "src.factors.price_volume.add_low_volatility", notes="Implemented; watch-only because lifecycle set already contains two volatility horizons."),
    _spec("lowturn_20d", "price_volume", "Log low-turnover transform", "-log(1+mean(turnover,20))", 1, 20, "turnover", "market", "src.factors.price_volume.add_turnover_factors", notes="Monotonic duplicate of turnover_1m under rank-based evaluation."),
    _spec("lowturn_60d", "price_volume", "Log low-turnover transform", "-log(1+mean(turnover,60))", 1, 60, "turnover", "market", "src.factors.price_volume.add_turnover_factors", notes="Monotonic duplicate of turnover_3m under rank-based evaluation."),
    _spec("bp", "value", "Book-to-price", "book_equity/market_cap", 1, None, "book_equity;market_cap;announcement_date", "financial", "src.factors.value.build_value_factors", notes="PIT framework exists; current financial panel covers only five tickers."),
    _spec("ep", "value", "Earnings yield", "net_profit/market_cap", 1, None, "net_profit;market_cap;announcement_date", "financial", "src.factors.value.build_value_factors", notes="PIT framework exists; current financial panel covers only five tickers."),
    _spec("sp", "value", "Sales yield", "revenue/market_cap", 1, None, "revenue;market_cap;announcement_date", "financial", "src.factors.value.build_value_factors", notes="PIT framework exists; current financial panel covers only five tickers."),
    _spec("cfp", "value", "Operating cash-flow yield", "operating_cash_flow/market_cap", 1, None, "operating_cash_flow;market_cap;announcement_date", "financial", "src.factors.value.build_value_factors", notes="PIT framework exists; current financial panel covers only five tickers."),
    _spec("value_composite_raw", "value", "Mean value yield", "mean(bp,ep,sp,cfp)", 1, None, "bp;ep;sp;cfp", "financial", "src.factors.value.build_value_factors", notes="Composite of four value yields; current coverage is insufficient."),
    _spec("size", "size", "Log market capitalization", "log(market_cap)", -1, 0, "market_cap", "market", "src.factors.quality_growth_risk.build_quality_growth_factors", notes="Market cap is available but size is reserved as a neutralization exposure in this run."),
    _spec("roe", "quality", "Return on equity", "net_profit/book_equity", 1, None, "net_profit;book_equity;announcement_date", "financial", "src.factors.quality_growth_risk.build_quality_growth_factors", notes="Current financial panel covers only five tickers."),
    _spec("gross_profitability", "quality", "Gross profitability", "gross_profit/total_assets", 1, None, "gross_profit;total_assets;announcement_date", "financial", "src.factors.quality_growth_risk.build_quality_growth_factors", notes="Current financial panel covers only five tickers."),
    _spec("ocf_to_assets", "quality", "Operating cash-flow quality", "operating_cash_flow/total_assets", 1, None, "operating_cash_flow;total_assets;announcement_date", "financial", "src.factors.quality_growth_risk.build_quality_growth_factors", notes="Current financial panel covers only five tickers."),
    _spec("revenue_growth", "growth", "Year-on-year revenue growth", "revenue_t/revenue_{t-4}-1", 1, 4, "revenue;announcement_date", "financial", "src.factors.quality_growth_risk.build_quality_growth_factors", notes="Current financial panel covers only five tickers; revision history is unavailable."),
    _spec("earnings_growth", "growth", "Year-on-year earnings growth", "profit_t/profit_{t-4}-1", 1, 4, "net_profit;announcement_date", "financial", "src.factors.quality_growth_risk.build_quality_growth_factors", notes="Current financial panel covers only five tickers; revision history is unavailable."),
    _spec("rolling_beta", "risk", "Rolling market beta", "cov(r_i,r_m)/var(r_m)", -1, 252, "return_1d", "market", "src.factors.quality_growth_risk.build_rolling_risk_factors", notes="Implemented but not included in the lifecycle run because the equal-weight proxy is not an investable benchmark."),
    _spec("idiosyncratic_volatility", "risk", "Market-model residual volatility", "std(r_i-beta*r_m)", -1, 252, "return_1d", "market", "src.factors.quality_growth_risk.build_rolling_risk_factors", notes="Implemented; watch-only pending benchmark and exposure validation."),
    _spec("downside_beta", "risk", "Beta on negative market days", "beta(r_m<0)", -1, 252, "return_1d", "market", "src.factors.quality_growth_risk.build_rolling_risk_factors", notes="Implemented; watch-only pending benchmark and exposure validation."),
)


def registry_frame() -> pd.DataFrame:
    return pd.DataFrame([asdict(spec) for spec in FACTOR_REGISTRY])


def lifecycle_factor_names() -> list[str]:
    return [spec.factor_name for spec in FACTOR_REGISTRY if spec.lifecycle_enabled]
