# AI Intelligence

The latest source of truth is `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.5.md`.

Milestone 22 implements provider-first news and OpenAI structured-analysis boundaries while
preserving offline defaults. AI is advisory and may analyze deterministic shortlist candidates,
summarize candidate-specific news, extract events, classify risk/catalyst context, return
schema-validated JSON, produce explanations, and generate automated calibration reports that can
only reduce/neutralize/escalate AI influence.

Milestone 23 can route AI/news warnings and AI quality degradation events to Telegram alerts through
the alerting boundary. Those alerts are operator-facing only and do not grant AI broker access,
order authority, strategy mutation, risk mutation, or stop-policy mutation.

Milestone 25 surfaces AI/news outputs, provider budget status, and AI quality state in the
dashboard/control-plane read model. These dashboard sections are read-only, may be unavailable-safe
when local records are absent, and do not call AI/news providers or give AI any broker authority.

Milestone 27 readiness aggregation treats AI/news implementation and prior gated smoke evidence as
read-only status inputs. It does not call Marketaux, Alpha Vantage, OpenAI structured analysis, or
OpenAI web fallback by default.

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
- `packages/ai/providers.py` implements Marketaux-first and Alpha Vantage fallback/cross-check
  retrieval behind explicit provider clients, per-provider request budgets, per-run symbol/article
  caps, lookback limits, normalization, deduplication, and raw payload hashing/persistence
  boundaries.
- `packages/ai/budget.py` defines in-memory request-budget enforcement for providers, OpenAI
  structured analysis, and OpenAI web fallback.
- `packages/ai/models.py` defines strict news, citation, event, output, fallback, and provider-failure models.
- `packages/ai/dedupe.py` normalizes and deduplicates ticker-tagged articles.
- `packages/ai/prompts/ai_trade_research_v0_3.md` is the versioned prompt template.
- `packages/ai/openai.py` implements fake/default and explicitly gated OpenAI client boundaries,
  strict Responses-API JSON schema generation, optional model-list validation, structured-output
  analysis over already-normalized shortlist articles, neutral fallbacks, prompt/output hashes, and
  disabled-by-default web-search fallback.
- `packages/ai/feedback.py` implements autonomous historical feedback/calibration reports and AI
  safety-state recommendations: `AI_NORMAL`, `AI_REDUCED_INFLUENCE`, `AI_NEUTRAL_ONLY`, and
  `AI_ESCALATION_REQUIRED`.
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
- Milestone 22 integration smoke tests for providers/OpenAI are skipped by default and require
  explicit gates. Default unit tests use fakes/fixtures only and do not call Marketaux, Alpha
  Vantage, OpenAI, broker APIs, alert services, or managed databases.
- Milestone 23 alert templates include AI/news warning summaries. Default tests still use fake
  alert clients and do not call AI/news providers or Telegram.
- Milestone 25 dashboard/control-plane runtime tests validate read-only AI quality and provider
  budget sections without calling Marketaux, Alpha Vantage, OpenAI, broker APIs, or alert services.

## Provider-First News Policy

- Marketaux is the primary ticker-tagged news provider.
- Alpha Vantage is the fallback/cross-check provider.
- News is fetched only for caller-supplied deterministic shortlist symbols.
- Full-universe AI/news scanning is forbidden.
- `NEWS_MAX_SYMBOLS_PER_RUN` and `NEWS_MAX_ARTICLES_PER_SYMBOL` cap each run.
- `NEWS_MARKETAUX_DAILY_REQUEST_LIMIT` and `NEWS_ALPHA_VANTAGE_DAILY_REQUEST_LIMIT` are checked
  before any real provider request.
- Default lookback is 7 calendar days; event/risk lookups may extend to 14 calendar days.
- Articles preserve provider, endpoint, symbol, title, summary/content, canonical URL, source,
  publication timestamp, language/sentiment when supplied, and raw payload hash.
- Raw provider payload persistence uses the existing ledger boundary; no schema change is required.

## OpenAI Structured Analysis

- OpenAI analysis runs only on normalized provider-fetched shortlist articles.
- `AI_REQUIRE_STRUCTURED_OUTPUT=true` and neutral fallback on error are required.
- Configured model names are read from env/config; default tests do not require valid OpenAI model
  IDs or API keys.
- Real model-list validation is allowed only with
  `RUN_OPENAI_MODEL_LIST_SMOKE=1` and
  `OPENAI_MODEL_LIST_CONFIRM=LIST_AVAILABLE_MODELS_ONLY`.
- Parsed output records prompt version, schema version, model version, raw prompt hash, and raw
  output hash.
- AI output may set `hard_block` and `size_multiplier <= 1.0`; it may not increase deterministic
  position caps or create execution intents/orders.

## OpenAI Web Fallback

OpenAI web fallback is disabled by default with `NEWS_ENABLE_OPENAI_WEB_FALLBACK=false`.
Even when enabled, runtime policy must explicitly allow it. It is exception-only for no provider
articles, conflicting providers, incomplete high-severity legal/regulatory/accounting/FDA-style
context, low-confidence trade-pass cases, or hard-block decisions that depend on missing context.
`NEWS_OPENAI_WEB_DAILY_REQUEST_LIMIT` is checked before any web-search request.

Real web fallback smoke is skipped/refused unless:

- `RUN_OPENAI_WEB_FALLBACK_SMOKE=1`
- `OPENAI_WEB_FALLBACK_CONFIRM=AUDITED_EXCEPTION_ONLY_WEB_SEARCH`

Web fallback output is advisory only and cannot create orders or modify broker state.

## Feedback And Calibration

Autonomous feedback/calibration may evaluate historical AI outputs against later outcomes, produce
calibration metrics, generate reports, recommend warnings/incidents, and reduce or neutralize AI
influence when quality degrades.

It may not:

- mutate strategy rules;
- change risk limits;
- change stop policy;
- change execution policy;
- increase position size;
- expand the universe;
- enable live trading;
- override kill switches;
- call broker APIs.

Under v0.5 frozen-validation readiness, AI/news is negative-only for the first frozen window. AI
may hard-block, reduce size, explain risk, and report evidence. It may not positively increase
ranking, increase size, authorize entries, authorize scale-ins, authorize shorts, mutate strategy or
risk policy, or gain broker authority.

## Fallback Policy

Invalid or unavailable AI/news input does not create execution authority and does not trigger a
global kill switch by itself.

- No news: `ai_score=50`, `hard_block=false`, `news_state=insufficient_data`.
- Invalid JSON or schema violation: `ai_score=50`, `hard_block=false`, warning-style fallback reason.
- AI provider outage: neutral fallback and no global kill-switch trigger.
- Conflicting sources: `news_state=mixed`, `size_multiplier <= 0.75`, no hard block unless a
  high-severity blocking risk clears the configured confidence threshold.

## Deferred Work

Managed database production activity wiring, production dashboard deployment, frozen paper
evidence, and paper/live validation remain deferred. Tests and the Milestone 16 dry run use
fixtures only and require no API keys or network calls. Dashboard contracts can display AI output,
budget, and quality read models but do not call AI providers from frontend code.

## Level 4 Readiness Evidence

`docs/level4_micro_live_readiness.md` requires AI evidence before Level 4 micro-live: deterministic
shortlist-only analysis, strict schema validation, neutral fallbacks for invalid/provider-failure
cases, no broker access, provider coverage/fallback calibration, and AI valid-schema rate >= 99%
during frozen paper. Milestone 22 adds the provider/OpenAI/calibration implementation, but it is not
frozen paper evidence and does not satisfy Level 4 readiness.
