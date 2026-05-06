-- Initial Postgres/Supabase audit-ledger schema for the spec-governed trading system.
-- This migration defines durable business/audit tables only. It does not enable paper or live
-- trading and does not call broker, AI/news, or managed database APIs.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS symbols (
    symbol TEXT PRIMARY KEY,
    asset_class TEXT NOT NULL CHECK (asset_class IN ('equity', 'etf')),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    approved_live BOOLEAN NOT NULL DEFAULT FALSE,
    approved_research BOOLEAN NOT NULL DEFAULT FALSE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS raw_provider_payloads (
    raw_provider_payload_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    symbol TEXT,
    payload_hash TEXT NOT NULL,
    raw_payload JSONB NOT NULL,
    content_type TEXT NOT NULL DEFAULT 'application/json',
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (provider, endpoint, payload_hash)
);

CREATE TABLE IF NOT EXISTS ohlcv_daily (
    ohlcv_daily_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol TEXT NOT NULL,
    trading_date DATE NOT NULL,
    open NUMERIC NOT NULL CHECK (open > 0),
    high NUMERIC NOT NULL CHECK (high > 0),
    low NUMERIC NOT NULL CHECK (low > 0),
    close NUMERIC NOT NULL CHECK (close > 0),
    volume BIGINT NOT NULL CHECK (volume >= 0),
    adjusted BOOLEAN NOT NULL DEFAULT TRUE,
    provider TEXT NOT NULL,
    raw_provider_payload_id UUID REFERENCES raw_provider_payloads(raw_provider_payload_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (symbol, trading_date, provider)
);

CREATE TABLE IF NOT EXISTS features_daily (
    features_daily_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol TEXT NOT NULL,
    trading_date DATE NOT NULL,
    feature_version TEXT NOT NULL,
    close NUMERIC,
    feature_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    source_ohlcv_daily_id UUID REFERENCES ohlcv_daily(ohlcv_daily_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (symbol, trading_date, feature_version)
);

CREATE TABLE IF NOT EXISTS regimes (
    regime_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trading_date DATE NOT NULL,
    regime_state TEXT NOT NULL CHECK (regime_state IN ('RISK_ON', 'CAUTION', 'RISK_OFF')),
    model_version TEXT NOT NULL,
    proxy_symbol TEXT NOT NULL,
    diagnostic_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (trading_date, model_version)
);

CREATE TABLE IF NOT EXISTS trade_candidates (
    candidate_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol TEXT NOT NULL,
    trading_date DATE NOT NULL,
    strategy_version TEXT NOT NULL,
    candidate_status TEXT NOT NULL,
    technical_score NUMERIC,
    relative_strength_score NUMERIC,
    score_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    reason_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    rejection_reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
    source_features_daily_id UUID REFERENCES features_daily(features_daily_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ai_research_outputs (
    output_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    model_version TEXT NOT NULL,
    raw_prompt TEXT NOT NULL,
    raw_prompt_hash TEXT NOT NULL,
    raw_output TEXT,
    raw_output_hash TEXT,
    parsed_output JSONB NOT NULL,
    ai_score INTEGER NOT NULL CHECK (ai_score BETWEEN 10 AND 90),
    hard_block BOOLEAN NOT NULL,
    fallback_reason TEXT NOT NULL,
    citations JSONB NOT NULL DEFAULT '[]'::jsonb,
    canonical_urls JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS trade_decisions (
    decision_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_id UUID REFERENCES trade_candidates(candidate_id),
    symbol TEXT NOT NULL,
    decision_status TEXT NOT NULL,
    final_score NUMERIC,
    deterministic_decision_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    ai_output_id UUID REFERENCES ai_research_outputs(output_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS execution_intents (
    execution_intent_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    temporal_workflow_id TEXT,
    decision_id UUID,
    client_order_id_root TEXT NOT NULL UNIQUE,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
    asset_class TEXT NOT NULL CHECK (asset_class IN ('equity', 'etf')),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    entry_order_type TEXT NOT NULL CHECK (entry_order_type = 'limit'),
    limit_price NUMERIC NOT NULL CHECK (limit_price > 0),
    stop_loss_price NUMERIC CHECK (stop_loss_price > 0),
    time_in_force TEXT NOT NULL CHECK (time_in_force = 'day'),
    strategy_version TEXT NOT NULL,
    risk_config_version TEXT NOT NULL,
    autonomy_level INTEGER NOT NULL CHECK (autonomy_level BETWEEN 0 AND 5),
    requires_protective_stop BOOLEAN NOT NULL,
    max_acceptable_slippage_bps INTEGER NOT NULL CHECK (max_acceptable_slippage_bps >= 0),
    status TEXT NOT NULL,
    payload JSONB NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS risk_checks (
    risk_check_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_id UUID REFERENCES trade_decisions(decision_id),
    execution_intent_id UUID REFERENCES execution_intents(execution_intent_id),
    symbol TEXT NOT NULL,
    passed BOOLEAN NOT NULL,
    reason_codes JSONB NOT NULL DEFAULT '[]'::jsonb,
    risk_config_version TEXT NOT NULL,
    input_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    result_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS orders (
    order_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_intent_id UUID REFERENCES execution_intents(execution_intent_id),
    broker_order_id TEXT UNIQUE,
    client_order_id TEXT NOT NULL UNIQUE,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
    order_type TEXT NOT NULL,
    time_in_force TEXT NOT NULL,
    quantity NUMERIC NOT NULL CHECK (quantity > 0),
    limit_price NUMERIC CHECK (limit_price > 0),
    stop_price NUMERIC CHECK (stop_price > 0),
    status TEXT NOT NULL,
    raw_broker_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS fills (
    fill_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES orders(order_id),
    broker_order_id TEXT,
    broker_fill_id TEXT UNIQUE,
    symbol TEXT NOT NULL,
    quantity NUMERIC NOT NULL CHECK (quantity > 0),
    price NUMERIC NOT NULL CHECK (price > 0),
    filled_at TIMESTAMPTZ NOT NULL,
    raw_broker_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS positions (
    position_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol TEXT NOT NULL,
    quantity NUMERIC NOT NULL,
    average_entry_price NUMERIC NOT NULL CHECK (average_entry_price > 0),
    status TEXT NOT NULL,
    protective_stop_order_id UUID REFERENCES orders(order_id),
    opened_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ,
    raw_source_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS positions_one_open_per_symbol
    ON positions(symbol)
    WHERE status = 'open';

CREATE TABLE IF NOT EXISTS broker_reconciliations (
    reconciliation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    temporal_workflow_id TEXT,
    account_snapshot JSONB NOT NULL,
    broker_positions JSONB NOT NULL DEFAULT '[]'::jsonb,
    internal_positions JSONB NOT NULL DEFAULT '[]'::jsonb,
    broker_orders JSONB NOT NULL DEFAULT '[]'::jsonb,
    internal_orders JSONB NOT NULL DEFAULT '[]'::jsonb,
    mismatches JSONB NOT NULL DEFAULT '[]'::jsonb,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS system_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('info', 'warning', 'critical')),
    source_component TEXT NOT NULL,
    related_entity_type TEXT,
    related_entity_id TEXT,
    message TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    acknowledged_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS reports (
    report_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_type TEXT NOT NULL,
    report_date DATE,
    period_start DATE,
    period_end DATE,
    status TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    markdown TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
