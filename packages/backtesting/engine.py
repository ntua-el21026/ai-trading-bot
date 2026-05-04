"""Deterministic backtest engine skeleton with explicit signal inputs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from packages.backtesting.metrics import calculate_backtest_metrics
from packages.backtesting.models import (
    BacktestInput,
    BacktestResult,
    BacktestSignal,
    BacktestTrade,
    EquityPoint,
)
from packages.data.models import AdjustedDailyBar


@dataclass
class _OpenPosition:
    symbol: str
    entry_date: date
    quantity: int
    entry_price: float
    entry_fee: float


def run_backtest(
    request: BacktestInput,
    *,
    optimistic_universe_warning: bool = False,
) -> BacktestResult:
    bar_lookup = _build_bar_lookup(request.bars_by_symbol)
    signals_by_date = _group_signals_by_date(request.signals)
    dates = sorted({bar.date for bars in request.bars_by_symbol.values() for bar in bars})

    cash = request.initial_cash
    positions: dict[str, _OpenPosition] = {}
    trades: list[BacktestTrade] = []
    equity_curve: list[EquityPoint] = []

    for current_date in dates:
        for signal in signals_by_date.get(current_date, ()):
            bar = bar_lookup.get(signal.symbol, {}).get(current_date)
            if bar is None:
                continue
            if signal.action == "buy":
                cash = _handle_buy(signal, bar, request, cash, positions)
            else:
                cash = _handle_sell(signal, bar, request, cash, positions, trades)

        equity, gross_exposure = _mark_to_market(cash, positions, bar_lookup, current_date)
        equity_curve.append(
            EquityPoint(
                date=current_date,
                equity=equity,
                cash=cash,
                gross_exposure=gross_exposure,
            )
        )

    metrics = calculate_backtest_metrics(equity_curve=equity_curve, trades=trades)
    return BacktestResult(
        name=request.name,
        trades=tuple(trades),
        equity_curve=tuple(equity_curve),
        metrics=metrics,
        validation_note=request.validation_note,
        optimistic_universe_warning=optimistic_universe_warning,
    )


def _build_bar_lookup(
    bars_by_symbol: dict[str, tuple[AdjustedDailyBar, ...]],
) -> dict[str, dict[date, AdjustedDailyBar]]:
    return {
        symbol: {bar.date: bar for bar in bars}
        for symbol, bars in bars_by_symbol.items()
    }


def _group_signals_by_date(
    signals: tuple[BacktestSignal, ...],
) -> dict[date, tuple[BacktestSignal, ...]]:
    grouped: dict[date, list[BacktestSignal]] = {}
    for signal in sorted(signals, key=lambda item: (item.date, item.symbol, item.action)):
        grouped.setdefault(signal.date, []).append(signal)
    return {signal_date: tuple(items) for signal_date, items in grouped.items()}


def _handle_buy(
    signal: BacktestSignal,
    bar: AdjustedDailyBar,
    request: BacktestInput,
    cash: float,
    positions: dict[str, _OpenPosition],
) -> float:
    if signal.symbol in positions:
        return cash
    entry_price = bar.close * (1.0 + request.slippage.entry_slippage_bps / 10_000.0)
    notional = entry_price * signal.quantity
    fee = notional * request.slippage.fee_bps_per_side / 10_000.0
    total_cost = notional + fee
    if total_cost > cash:
        return cash
    positions[signal.symbol] = _OpenPosition(
        symbol=signal.symbol,
        entry_date=signal.date,
        quantity=signal.quantity,
        entry_price=entry_price,
        entry_fee=fee,
    )
    return cash - total_cost


def _handle_sell(
    signal: BacktestSignal,
    bar: AdjustedDailyBar,
    request: BacktestInput,
    cash: float,
    positions: dict[str, _OpenPosition],
    trades: list[BacktestTrade],
) -> float:
    position = positions.pop(signal.symbol, None)
    if position is None:
        return cash

    exit_price = bar.close * (1.0 - request.slippage.exit_slippage_bps / 10_000.0)
    notional = exit_price * position.quantity
    exit_fee = notional * request.slippage.fee_bps_per_side / 10_000.0
    entry_value = position.entry_price * position.quantity
    pnl = notional - exit_fee - entry_value - position.entry_fee
    trades.append(
        BacktestTrade(
            symbol=signal.symbol,
            entry_date=position.entry_date,
            exit_date=signal.date,
            quantity=position.quantity,
            entry_price=position.entry_price,
            exit_price=exit_price,
            entry_fee=position.entry_fee,
            exit_fee=exit_fee,
            pnl=pnl,
            return_pct=pnl / entry_value,
        )
    )
    return cash + notional - exit_fee


def _mark_to_market(
    cash: float,
    positions: dict[str, _OpenPosition],
    bar_lookup: dict[str, dict[date, AdjustedDailyBar]],
    current_date: date,
) -> tuple[float, float]:
    gross_exposure = 0.0
    for symbol, position in positions.items():
        bar = bar_lookup.get(symbol, {}).get(current_date)
        if bar is None:
            gross_exposure += position.entry_price * position.quantity
        else:
            gross_exposure += bar.close * position.quantity
    return cash + gross_exposure, gross_exposure

