# AI Intelligence

The latest source of truth is `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.3.md`.

Milestone 07 implements bounded AI/news intelligence contracts only. AI is advisory and may analyze
deterministic shortlist candidates, summarize candidate-specific news, extract events, classify
risk/catalyst context, return schema-validated JSON, and produce explanations.

AI cannot:

- scan the full universe for trade ideas;
- create or modify orders;
- change stops;
- modify strategy rules;
- modify risk limits;
- access broker credentials;
- call broker APIs;
- disable or override kill switches.

## Implemented Contracts

- `packages/ai/news.py` defines deterministic-shortlist news provider boundaries.
- `packages/ai/models.py` defines strict news, citation, event, output, fallback, and provider-failure models.
- `packages/ai/dedupe.py` normalizes and deduplicates ticker-tagged articles.
- `packages/ai/prompts/ai_trade_research_v0_3.md` is the versioned prompt template.
- `packages/ai/parser.py` parses strict JSON and returns neutral fallbacks for invalid JSON or schema violations.
- `packages/ai/fallback.py` defines neutral no-news, provider-outage, and conflicting-source fallback contracts.
- `packages/ai/scoring.py` implements deterministic recency/source/event scoring, hard-block classification, and non-increasing size multipliers.
- `packages/ai/persistence.py` defines raw prompt/output persistence payload contracts with audit hashes.

## Fallback Policy

Invalid or unavailable AI/news input does not create execution authority and does not trigger a
global kill switch by itself.

- No news: `ai_score=50`, `hard_block=false`, `news_state=insufficient_data`.
- Invalid JSON or schema violation: `ai_score=50`, `hard_block=false`, warning-style fallback reason.
- AI provider outage: neutral fallback and no global kill-switch trigger.
- Conflicting sources: `news_state=mixed`, `size_multiplier <= 0.75`, no hard block unless a
  high-severity blocking risk clears the configured confidence threshold.

## Deferred Work

Real news provider clients, real AI provider clients, database persistence/migrations, production
dashboard deployment, and paper/live validation remain deferred. Tests use fixtures only and require
no API keys or network calls. Milestone 08 dashboard contracts can display AI output read models but
do not call AI providers from frontend code.

## Level 4 Readiness Evidence

`docs/level4_micro_live_readiness.md` requires AI evidence before Level 4 micro-live: deterministic
shortlist-only analysis, strict schema validation, neutral fallbacks for invalid/provider-failure
cases, no broker access, and AI valid-schema rate >= 99% during frozen paper. Current AI
implementation is fixture-only and has no real provider evidence.
