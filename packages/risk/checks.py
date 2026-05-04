"""Config-driven deterministic risk checks for new-risk entry eligibility."""

from __future__ import annotations

from packages.core.config import ExecutionConfig, LiveUniverseConfig, RiskLevelConfig, SystemConfig
from packages.risk.kill_switch import new_risk_allowed
from packages.risk.models import NewRiskOrderInput, RiskAssessment, RiskCheckResult

ALLOWED_NEW_RISK_ASSET_CLASSES = {"equity", "etf"}


def evaluate_new_risk_order(
    order_input: NewRiskOrderInput,
    *,
    system_config: SystemConfig,
    execution_config: ExecutionConfig,
    risk_config: RiskLevelConfig,
    live_universe_config: LiveUniverseConfig,
) -> RiskAssessment:
    checks = (
        _environment_check(system_config),
        _paper_live_mode_check(system_config, execution_config),
        _autonomy_check(system_config, execution_config),
        _approved_symbol_check(order_input, live_universe_config),
        _asset_class_check(order_input, live_universe_config),
        _market_session_check(order_input),
        _data_freshness_check(order_input),
        _broker_reconciliation_check(order_input, execution_config),
        _kill_switch_check(order_input),
        _loss_limit_check(
            "daily_loss_limit",
            order_input.daily_loss_pct,
            risk_config.max_daily_loss_pct,
        ),
        _loss_limit_check(
            "weekly_loss_limit",
            order_input.weekly_loss_pct,
            risk_config.max_weekly_loss_pct,
        ),
        _loss_limit_check(
            "monthly_loss_limit",
            order_input.monthly_loss_pct,
            risk_config.max_monthly_loss_pct,
        ),
        _position_size_check(order_input, risk_config),
        _gross_exposure_check(order_input, risk_config),
        _deployable_capital_check(order_input, risk_config),
        _open_positions_check(order_input, risk_config),
        _sector_exposure_check(order_input, risk_config),
        _cash_buffer_check(order_input, risk_config),
        _protective_stop_check(order_input, execution_config, risk_config),
        _risk_per_trade_check(order_input, risk_config),
        _duplicate_intent_check(order_input),
        _broker_account_mode_check(order_input, system_config),
        _system_health_check(order_input),
        _temporal_workflow_check(order_input),
    )
    return RiskAssessment(
        symbol=order_input.symbol,
        approved=all(check.passed for check in checks),
        checks=checks,
    )


def _pass(name: str, reason_code: str, details: dict[str, str] | None = None) -> RiskCheckResult:
    return RiskCheckResult(
        name=name,
        passed=True,
        severity="info",
        reason_code=reason_code,
        details=details or {},
    )


def _fail(
    name: str,
    reason_code: str,
    details: dict[str, str] | None = None,
) -> RiskCheckResult:
    return RiskCheckResult(
        name=name,
        passed=False,
        severity="critical",
        reason_code=reason_code,
        details=details or {},
    )


def _environment_check(system_config: SystemConfig) -> RiskCheckResult:
    if system_config.environment not in {"paper", "live"}:
        return _fail("environment_validity", "invalid_environment")
    return _pass("environment_validity", "environment_valid")


def _paper_live_mode_check(
    system_config: SystemConfig,
    execution_config: ExecutionConfig,
) -> RiskCheckResult:
    if system_config.environment == "paper":
        if system_config.live_trading_enabled or execution_config.allow_live_orders:
            return _fail("paper_live_mode", "paper_mode_live_orders_enabled")
        return _pass("paper_live_mode", "paper_mode_safe")
    if not system_config.live_trading_enabled or not execution_config.allow_live_orders:
        return _fail("paper_live_mode", "live_mode_not_enabled")
    if system_config.dry_run:
        return _fail("paper_live_mode", "live_mode_dry_run_enabled")
    return _pass("paper_live_mode", "live_mode_consistent")


def _autonomy_check(
    system_config: SystemConfig,
    execution_config: ExecutionConfig,
) -> RiskCheckResult:
    if not system_config.autonomous_execution_enabled:
        return _fail("autonomous_execution", "system_autonomous_execution_disabled")
    if not execution_config.autonomous_execution_enabled:
        return _fail("autonomous_execution", "execution_autonomous_execution_disabled")
    return _pass("autonomous_execution", "autonomous_execution_enabled")


def _approved_symbol_check(
    order_input: NewRiskOrderInput,
    live_universe_config: LiveUniverseConfig,
) -> RiskCheckResult:
    if order_input.symbol not in live_universe_config.symbols:
        return _fail("approved_symbol", "symbol_not_approved")
    return _pass("approved_symbol", "symbol_approved")


def _asset_class_check(
    order_input: NewRiskOrderInput,
    live_universe_config: LiveUniverseConfig,
) -> RiskCheckResult:
    if order_input.asset_class not in ALLOWED_NEW_RISK_ASSET_CLASSES:
        return _fail("asset_class", f"disallowed_asset_class:{order_input.asset_class}")
    if order_input.asset_class == "equity" and not live_universe_config.allow_common_stocks:
        return _fail("asset_class", "common_stocks_disabled")
    if order_input.asset_class == "etf" and not live_universe_config.allow_etfs:
        return _fail("asset_class", "etfs_disabled")
    return _pass("asset_class", "asset_class_allowed")


def _market_session_check(order_input: NewRiskOrderInput) -> RiskCheckResult:
    if order_input.market_session_valid is None:
        return _fail("market_session", "market_session_unknown")
    if not order_input.market_session_valid:
        return _fail("market_session", "market_session_invalid")
    return _pass("market_session", "market_session_valid")


def _data_freshness_check(order_input: NewRiskOrderInput) -> RiskCheckResult:
    if not order_input.data_is_fresh:
        return _fail("data_freshness", "stale_market_data")
    return _pass("data_freshness", "market_data_fresh")


def _broker_reconciliation_check(
    order_input: NewRiskOrderInput,
    execution_config: ExecutionConfig,
) -> RiskCheckResult:
    if not execution_config.require_broker_reconciliation_before_order:
        return _fail("broker_reconciliation", "broker_reconciliation_not_required_by_config")
    if order_input.broker_reconciliation_clean is None:
        return _fail("broker_reconciliation", "broker_reconciliation_unknown")
    if not order_input.broker_reconciliation_clean:
        return _fail("broker_reconciliation", "broker_reconciliation_not_clean")
    return _pass("broker_reconciliation", "broker_reconciliation_clean")


def _kill_switch_check(order_input: NewRiskOrderInput) -> RiskCheckResult:
    if not new_risk_allowed(order_input.kill_switch):
        return _fail("kill_switch", f"kill_switch_{order_input.kill_switch.state.lower()}")
    return _pass("kill_switch", "kill_switch_running")


def _loss_limit_check(name: str, loss_pct: float, limit_pct: float) -> RiskCheckResult:
    if loss_pct >= limit_pct:
        return _fail(name, f"{name}_breached")
    return _pass(name, f"{name}_not_breached")


def _position_size_check(
    order_input: NewRiskOrderInput,
    risk_config: RiskLevelConfig,
) -> RiskCheckResult:
    proposed_pct = order_input.proposed_order_value / order_input.account_equity
    if proposed_pct > risk_config.max_position_size_pct:
        return _fail(
            "max_position_size",
            "max_position_size_exceeded",
            {"proposed_pct": f"{proposed_pct:.6f}"},
        )
    return _pass("max_position_size", "max_position_size_ok")


def _gross_exposure_check(
    order_input: NewRiskOrderInput,
    risk_config: RiskLevelConfig,
) -> RiskCheckResult:
    proposed_pct = (
        order_input.current_gross_exposure + order_input.proposed_order_value
    ) / order_input.account_equity
    if proposed_pct > risk_config.max_gross_exposure_pct:
        return _fail(
            "max_gross_exposure",
            "max_gross_exposure_exceeded",
            {"proposed_pct": f"{proposed_pct:.6f}"},
        )
    return _pass("max_gross_exposure", "max_gross_exposure_ok")


def _deployable_capital_check(
    order_input: NewRiskOrderInput,
    risk_config: RiskLevelConfig,
) -> RiskCheckResult:
    proposed_pct = (
        order_input.current_deployable_capital + order_input.proposed_order_value
    ) / order_input.account_equity
    if proposed_pct > risk_config.max_deployable_capital_pct:
        return _fail(
            "max_deployable_capital",
            "max_deployable_capital_exceeded",
            {"proposed_pct": f"{proposed_pct:.6f}"},
        )
    return _pass("max_deployable_capital", "max_deployable_capital_ok")


def _open_positions_check(
    order_input: NewRiskOrderInput,
    risk_config: RiskLevelConfig,
) -> RiskCheckResult:
    if order_input.current_open_positions + 1 > risk_config.max_open_positions:
        return _fail("max_open_positions", "max_open_positions_exceeded")
    return _pass("max_open_positions", "max_open_positions_ok")


def _sector_exposure_check(
    order_input: NewRiskOrderInput,
    risk_config: RiskLevelConfig,
) -> RiskCheckResult:
    proposed_sector_pct = (
        order_input.current_sector_exposure_pct
        + (order_input.proposed_order_value / order_input.account_equity)
    )
    if proposed_sector_pct > risk_config.max_sector_exposure_pct:
        return _fail(
            "max_sector_exposure",
            "max_sector_exposure_exceeded",
            {"proposed_pct": f"{proposed_sector_pct:.6f}"},
        )
    return _pass("max_sector_exposure", "max_sector_exposure_ok")


def _cash_buffer_check(
    order_input: NewRiskOrderInput,
    risk_config: RiskLevelConfig,
) -> RiskCheckResult:
    post_trade_cash_pct = (order_input.cash - order_input.proposed_order_value) / (
        order_input.account_equity
    )
    if post_trade_cash_pct < risk_config.min_cash_buffer_pct:
        return _fail(
            "min_cash_buffer",
            "min_cash_buffer_breached",
            {"post_trade_cash_pct": f"{post_trade_cash_pct:.6f}"},
        )
    return _pass("min_cash_buffer", "min_cash_buffer_ok")


def _protective_stop_check(
    order_input: NewRiskOrderInput,
    execution_config: ExecutionConfig,
    risk_config: RiskLevelConfig,
) -> RiskCheckResult:
    if not execution_config.require_protective_stop or not risk_config.require_protective_stop:
        return _fail("protective_stop", "protective_stop_not_required_by_config")
    if order_input.stop_loss_price is None:
        return _fail("protective_stop", "missing_protective_stop")
    if order_input.stop_loss_price >= order_input.entry_price:
        return _fail("protective_stop", "invalid_stop_distance")
    return _pass("protective_stop", "protective_stop_available")


def _risk_per_trade_check(
    order_input: NewRiskOrderInput,
    risk_config: RiskLevelConfig,
) -> RiskCheckResult:
    proposed_risk = order_input.proposed_risk_amount
    if proposed_risk is None:
        return _fail("max_risk_per_trade", "invalid_stop_distance")
    risk_pct = proposed_risk / order_input.account_equity
    if risk_pct > risk_config.max_risk_per_trade_pct:
        return _fail(
            "max_risk_per_trade",
            "max_risk_per_trade_exceeded",
            {"risk_pct": f"{risk_pct:.6f}"},
        )
    return _pass("max_risk_per_trade", "max_risk_per_trade_ok")


def _duplicate_intent_check(order_input: NewRiskOrderInput) -> RiskCheckResult:
    if order_input.active_duplicate_intent:
        return _fail("duplicate_intent", "active_duplicate_intent")
    return _pass("duplicate_intent", "no_active_duplicate_intent")


def _broker_account_mode_check(
    order_input: NewRiskOrderInput,
    system_config: SystemConfig,
) -> RiskCheckResult:
    if order_input.broker_account_environment is None:
        return _fail("broker_account_mode", "broker_account_mode_unknown")
    if order_input.broker_account_environment != system_config.environment:
        return _fail("broker_account_mode", "broker_account_mode_mismatch")
    return _pass("broker_account_mode", "broker_account_mode_ok")


def _system_health_check(order_input: NewRiskOrderInput) -> RiskCheckResult:
    if not order_input.system_health_ok:
        return _fail("system_health", "system_health_check_failed")
    return _pass("system_health", "system_health_ok")


def _temporal_workflow_check(order_input: NewRiskOrderInput) -> RiskCheckResult:
    if order_input.temporal_workflow_consistent is None:
        return _fail("temporal_workflow_consistency", "temporal_workflow_state_unknown")
    if not order_input.temporal_workflow_consistent:
        return _fail("temporal_workflow_consistency", "temporal_workflow_state_inconsistent")
    return _pass("temporal_workflow_consistency", "temporal_workflow_state_consistent")
