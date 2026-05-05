from packages.validation.paper import PaperDryRunInputs, evaluate_paper_dry_run


def _safe_inputs(**updates: object) -> PaperDryRunInputs:
    data: dict[str, object] = {
        "execution_intent_lifecycle_validated": True,
        "broker_snapshot_fixture_used": True,
        "reconciliation_contract_clean": True,
        "missing_stop_policy_validated": True,
        "duplicate_order_rejected": True,
        "invalid_ai_output_neutral": True,
        "control_plane_kill_switch_signal_mapped": True,
        "live_trading_enabled": False,
        "autonomous_execution_enabled": False,
        "broker_orders_submitted": False,
        "external_calls_performed": False,
    }
    data.update(updates)
    return PaperDryRunInputs.model_validate(data)


def test_paper_dry_run_contract_passes_with_fixture_only_safe_inputs() -> None:
    result = evaluate_paper_dry_run(_safe_inputs())

    assert result.passed is True
    assert "not proof of profitability" in result.validation_note
    assert {check.name for check in result.checks} == {
        "execution_intent_lifecycle_validated",
        "broker_snapshot_fixture_used",
        "reconciliation_contract_clean",
        "missing_stop_policy_validated",
        "duplicate_order_rejected",
        "invalid_ai_output_neutral",
        "control_plane_kill_switch_signal_mapped",
        "no_broker_orders_submitted",
        "no_external_calls_performed",
        "safe_runtime_flags",
    }


def test_paper_dry_run_contract_fails_if_orders_or_external_calls_occur() -> None:
    result = evaluate_paper_dry_run(
        _safe_inputs(broker_orders_submitted=True, external_calls_performed=True)
    )
    reason_codes = {check.reason_code for check in result.checks if not check.passed}

    assert result.passed is False
    assert "broker_orders_submitted" in reason_codes
    assert "external_calls_performed" in reason_codes


def test_paper_dry_run_contract_fails_if_live_or_autonomous_flags_are_enabled() -> None:
    result = evaluate_paper_dry_run(
        _safe_inputs(live_trading_enabled=True, autonomous_execution_enabled=True)
    )

    assert result.passed is False
    assert any(
        check.name == "safe_runtime_flags"
        and check.reason_code == "runtime_flags_unsafe"
        and check.details == {
            "live_trading_enabled": "True",
            "autonomous_execution_enabled": "True",
        }
        for check in result.checks
    )
