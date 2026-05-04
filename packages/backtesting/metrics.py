"""Deterministic backtest metric calculations."""

from __future__ import annotations

import math
import statistics
from collections.abc import Sequence

from packages.backtesting.models import BacktestMetrics, BacktestTrade, EquityPoint

TRADING_DAYS_PER_YEAR = 252


def total_return(equity_curve: Sequence[EquityPoint]) -> float | None:
    if len(equity_curve) < 2:
        return None
    first = equity_curve[0].equity
    last = equity_curve[-1].equity
    if first == 0:
        return None
    return (last / first) - 1.0


def max_drawdown(equity_curve: Sequence[EquityPoint]) -> float | None:
    if not equity_curve:
        return None
    peak = equity_curve[0].equity
    worst = 0.0
    for point in equity_curve:
        peak = max(peak, point.equity)
        if peak == 0:
            continue
        drawdown = (point.equity / peak) - 1.0
        worst = min(worst, drawdown)
    return worst


def average_exposure(equity_curve: Sequence[EquityPoint]) -> float | None:
    exposures: list[float] = []
    for point in equity_curve:
        if point.equity == 0:
            continue
        exposures.append(point.gross_exposure / point.equity)
    if not exposures:
        return None
    return statistics.fmean(exposures)


def win_rate(trades: Sequence[BacktestTrade]) -> float | None:
    if not trades:
        return None
    wins = sum(1 for trade in trades if trade.pnl > 0)
    return wins / len(trades)


def average_win(trades: Sequence[BacktestTrade]) -> float | None:
    wins = [trade.pnl for trade in trades if trade.pnl > 0]
    return statistics.fmean(wins) if wins else None


def average_loss(trades: Sequence[BacktestTrade]) -> float | None:
    losses = [trade.pnl for trade in trades if trade.pnl < 0]
    return statistics.fmean(losses) if losses else None


def profit_factor(trades: Sequence[BacktestTrade]) -> float | None:
    gross_profit = sum(trade.pnl for trade in trades if trade.pnl > 0)
    gross_loss = abs(sum(trade.pnl for trade in trades if trade.pnl < 0))
    if gross_loss == 0:
        return None
    return gross_profit / gross_loss


def equity_returns(equity_curve: Sequence[EquityPoint]) -> list[float]:
    returns: list[float] = []
    for index in range(1, len(equity_curve)):
        previous = equity_curve[index - 1].equity
        current = equity_curve[index].equity
        if previous == 0:
            continue
        returns.append((current / previous) - 1.0)
    return returns


def sharpe_ratio(returns: Sequence[float]) -> float | None:
    if len(returns) < 2:
        return None
    standard_deviation = statistics.pstdev(returns)
    if standard_deviation == 0:
        return None
    return statistics.fmean(returns) / standard_deviation * math.sqrt(TRADING_DAYS_PER_YEAR)


def sortino_ratio(returns: Sequence[float], target_return: float = 0.0) -> float | None:
    if len(returns) < 2:
        return None
    downside = [min(0.0, item - target_return) for item in returns]
    downside_deviation = statistics.pstdev(downside)
    if downside_deviation == 0:
        return None
    excess_return = statistics.fmean(item - target_return for item in returns)
    return excess_return / downside_deviation * math.sqrt(TRADING_DAYS_PER_YEAR)


def calculate_backtest_metrics(
    *,
    equity_curve: Sequence[EquityPoint],
    trades: Sequence[BacktestTrade],
) -> BacktestMetrics:
    returns = equity_returns(equity_curve)
    return BacktestMetrics(
        total_return=total_return(equity_curve),
        max_drawdown=max_drawdown(equity_curve),
        average_exposure=average_exposure(equity_curve),
        trade_count=len(trades),
        win_rate=win_rate(trades),
        average_win=average_win(trades),
        average_loss=average_loss(trades),
        profit_factor=profit_factor(trades),
        sharpe=sharpe_ratio(returns),
        sortino=sortino_ratio(returns),
    )

