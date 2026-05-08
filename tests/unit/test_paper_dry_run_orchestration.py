from __future__ import annotations

import pytest

from packages.ledger.connection import connect_in_memory_sqlite
from packages.ledger.repositories import SQLiteLedgerRepository
from packages.paper import default_dry_run_input, run_paper_dry_run


def _repository() -> SQLiteLedgerRepository:
    return SQLiteLedgerRepository(connect_in_memory_sqlite())


def test_happy_path_dry_run_persists_full_fake_evidence_chain() -> None:
    repository = _repository()

    result = run_paper_dry_run(default_dry_run_input("happy_path"), repository=repository)

    assert result.passed is True
    assert result.safety_flags.safe is True
    assert result.safety_flags.external_calls_performed is False
    assert result.safety_flags.real_broker_calls_performed is False
    assert result.safety_flags.real_orders_submitted is False
    assert result.evidence.execution_intent_id == "intent-happy_path"
    assert result.evidence.client_order_id is not None
    assert result.evidence.fake_broker_order_id == "paper-order-1"
    assert result.evidence.fake_broker_order_status == "filled"
    assert result.evidence.fake_broker_order_request_count == 2
    assert result.evidence.fake_fill_status == "filled"
    assert result.evidence.protective_stop_verified is True
    assert result.evidence.reconciliation_status == "clean"
    assert result.evidence.report_id is not None
    assert result.evidence.dashboard_snapshot_status == "database_read_model"
    assert "Dry-run fake protective stop verified" in result.evidence.alert_titles
    assert result.dashboard_snapshot is not None
    assert result.dashboard_snapshot.system_state.data_source == "database_read_model"

    assert len(repository.list_trade_candidates()) == 1
    assert len(repository.list_ai_research_outputs()) == 1
    assert len(repository.list_trade_decisions()) == 1
    assert len(repository.list_recent_risk_checks()) == 1
    assert len(repository.list_active_execution_intents()) == 1
    assert len(repository.list_orders()) == 2
    assert len(repository.list_fills()) == 1
    assert len(repository.list_open_positions()) == 1
    assert len(repository.list_broker_reconciliations()) == 1
    assert len(repository.list_reports()) == 1
    assert repository.get_report(result.evidence.report_id) is not None


def test_dry_run_requires_no_credentials_or_managed_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    repository = _repository()

    result = run_paper_dry_run(default_dry_run_input("happy_path"), repository=repository)

    assert result.passed is True
    assert result.safety_flags.local_ledger_used is True
    assert result.safety_flags.managed_database_used is False
    assert result.safety_flags.real_ai_news_calls_performed is False
    assert result.safety_flags.real_alerts_sent is False


def test_risk_rejection_blocks_before_execution_intent_or_fake_submit() -> None:
    repository = _repository()

    result = run_paper_dry_run(default_dry_run_input("risk_rejection"), repository=repository)

    assert result.passed is False
    assert result.evidence.execution_intent_id is None
    assert result.evidence.fake_broker_order_request_count == 0
    assert "daily_loss_limit_breached" in result.failure_reasons
    assert repository.list_active_execution_intents() == ()
    assert repository.list_orders() == ()
    assert len(repository.list_reports()) == 1


def test_duplicate_active_intent_scenario_rejects_new_risk() -> None:
    repository = _repository()

    result = run_paper_dry_run(
        default_dry_run_input("duplicate_active_intent"),
        repository=repository,
    )

    assert result.passed is False
    assert "active_duplicate_intent" in result.failure_reasons
    assert result.evidence.fake_broker_order_request_count == 0
    assert len(repository.list_active_execution_intents()) == 1
    assert repository.list_orders() == ()


def test_broker_ambiguity_scenario_records_incident_without_real_order() -> None:
    repository = _repository()

    result = run_paper_dry_run(default_dry_run_input("broker_ambiguity"), repository=repository)

    assert result.passed is False
    assert result.evidence.execution_intent_id == "intent-broker_ambiguity"
    assert result.evidence.fake_broker_order_request_count == 0
    assert result.evidence.fake_broker_order_id is None
    assert "broker_ambiguity" in result.failure_reasons
    assert repository.list_orders() == ()
    assert any(
        "Broker ambiguous" in title or "safety event" in title
        for title in result.evidence.alert_titles
    )


@pytest.mark.parametrize(
    ("scenario_id", "expected_mismatch"),
    (
        ("missing_protective_stop", "missing_protective_stop"),
        ("reconciliation_mismatch", "internal_position_without_broker_position"),
    ),
)
def test_reconciliation_failure_scenarios_create_incident_evidence(
    scenario_id: str,
    expected_mismatch: str,
) -> None:
    repository = _repository()

    result = run_paper_dry_run(default_dry_run_input(scenario_id), repository=repository)

    assert result.passed is False
    assert expected_mismatch in result.evidence.reconciliation_mismatch_types
    assert result.evidence.reconciliation_status == "mismatched"
    assert len(repository.list_recent_incidents()) >= 1
    if scenario_id == "missing_protective_stop":
        assert result.evidence.protective_stop_verified is False
        assert result.evidence.fake_broker_order_request_count == 1


def test_partial_fill_requires_matching_fake_protective_stop_quantity() -> None:
    repository = _repository()

    result = run_paper_dry_run(default_dry_run_input("partial_fill"), repository=repository)

    assert result.passed is True
    assert result.evidence.fake_fill_status == "partial"
    assert result.evidence.filled_quantity == 4.0
    assert result.evidence.protective_stop_verified is True
    assert result.evidence.reconciliation_status == "clean"
    stop_orders = [
        order for order in repository.list_orders() if order.client_order_id.endswith("-stop")
    ]
    assert len(stop_orders) == 1
    assert stop_orders[0].quantity == 4.0
    assert stop_orders[0].stop_price == 174.20


def test_invalid_ai_output_uses_neutral_fallback_without_external_call() -> None:
    repository = _repository()

    result = run_paper_dry_run(
        default_dry_run_input("invalid_ai_output_neutral"),
        repository=repository,
    )

    assert result.passed is True
    assert result.safety_flags.real_ai_news_calls_performed is False
    ai_outputs = repository.list_ai_research_outputs()
    assert len(ai_outputs) == 1
    assert ai_outputs[0].fallback_reason == "schema_violation"
    assert ai_outputs[0].ai_score == 50
