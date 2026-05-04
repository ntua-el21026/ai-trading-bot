"""Temporal query contract names required by the latest spec."""

from __future__ import annotations

from dataclasses import dataclass

GET_CURRENT_SYSTEM_STATE = "get_current_system_state"
GET_ACTIVE_WORKFLOWS = "get_active_workflows"
GET_ACTIVE_EXECUTION_INTENTS = "get_active_execution_intents"
GET_OPEN_ORDER_LIFECYCLES = "get_open_order_lifecycles"
GET_OPEN_POSITION_LIFECYCLES = "get_open_position_lifecycles"
GET_RECENT_INCIDENTS = "get_recent_incidents"
GET_LAST_RECONCILIATION_STATUS = "get_last_reconciliation_status"
GET_KILL_SWITCH_STATE = "get_kill_switch_state"

QUERY_NAMES: tuple[str, ...] = (
    GET_CURRENT_SYSTEM_STATE,
    GET_ACTIVE_WORKFLOWS,
    GET_ACTIVE_EXECUTION_INTENTS,
    GET_OPEN_ORDER_LIFECYCLES,
    GET_OPEN_POSITION_LIFECYCLES,
    GET_RECENT_INCIDENTS,
    GET_LAST_RECONCILIATION_STATUS,
    GET_KILL_SWITCH_STATE,
)


@dataclass(frozen=True)
class QueryContract:
    name: str
    purpose: str


QUERY_CONTRACTS: dict[str, QueryContract] = {
    GET_CURRENT_SYSTEM_STATE: QueryContract(
        name=GET_CURRENT_SYSTEM_STATE,
        purpose="Expose current workflow/system state to the control plane.",
    ),
    GET_ACTIVE_WORKFLOWS: QueryContract(
        name=GET_ACTIVE_WORKFLOWS,
        purpose="Expose active workflow identifiers or placeholders.",
    ),
    GET_ACTIVE_EXECUTION_INTENTS: QueryContract(
        name=GET_ACTIVE_EXECUTION_INTENTS,
        purpose="Expose active execution-intent identifiers once implemented.",
    ),
    GET_OPEN_ORDER_LIFECYCLES: QueryContract(
        name=GET_OPEN_ORDER_LIFECYCLES,
        purpose="Expose open order lifecycle identifiers once implemented.",
    ),
    GET_OPEN_POSITION_LIFECYCLES: QueryContract(
        name=GET_OPEN_POSITION_LIFECYCLES,
        purpose="Expose open position lifecycle identifiers once implemented.",
    ),
    GET_RECENT_INCIDENTS: QueryContract(
        name=GET_RECENT_INCIDENTS,
        purpose="Expose recent incident identifiers or placeholders.",
    ),
    GET_LAST_RECONCILIATION_STATUS: QueryContract(
        name=GET_LAST_RECONCILIATION_STATUS,
        purpose="Expose the last reconciliation status snapshot.",
    ),
    GET_KILL_SWITCH_STATE: QueryContract(
        name=GET_KILL_SWITCH_STATE,
        purpose="Expose kill-switch state and new-risk permission.",
    ),
}
