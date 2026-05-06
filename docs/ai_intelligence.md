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
- `packages/ledger/repositories.py` can persist AI research output payloads locally in repository
  tests without calling AI/news providers or managed databases.
- `apps/workers/app/activities/ledger.py` can persist AI research output payloads through a
  local/fake Temporal activity boundary without calling AI/news providers.
- Milestone 14 broker activity boundaries do not grant AI broker access. AI still has no order
  submission, order modification, stop modification, or broker credential path.
- Milestone 16 paper dry-run orchestration uses neutral/fake AI fallback output only and persists it
  through the local ledger. It does not call AI or news providers.

## Fallback Policy

Invalid or unavailable AI/news input does not create execution authority and does not trigger a
global kill switch by itself.

- No news: `ai_score=50`, `hard_block=false`, `news_state=insufficient_data`.
- Invalid JSON or schema violation: `ai_score=50`, `hard_block=false`, warning-style fallback reason.
- AI provider outage: neutral fallback and no global kill-switch trigger.
- Conflicting sources: `news_state=mixed`, `size_multiplier <= 0.75`, no hard block unless a
  high-severity blocking risk clears the configured confidence threshold.

## Deferred Work

Real news provider clients, real AI provider clients, managed database runtime integration,
production dashboard deployment, and paper/live validation remain deferred. Tests and the Milestone
16 dry run use fixtures only and require no API keys or network calls. Dashboard contracts can
display AI output read models but do not call AI providers from frontend code.

## Level 4 Readiness Evidence

`docs/level4_micro_live_readiness.md` requires AI evidence before Level 4 micro-live: deterministic
shortlist-only analysis, strict schema validation, neutral fallbacks for invalid/provider-failure
cases, no broker access, and AI valid-schema rate >= 99% during frozen paper. Current AI
implementation is fixture-only and has no real provider evidence.
