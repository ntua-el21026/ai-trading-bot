# Short-side design recommendation for the autonomous AI trading bot

## Decision and spec baseline

### Executive recommendation

My recommendation is: implement short-side support in M44 as a **paper-only, explicitly gated capability**, but keep it **disabled by default** for the first frozen 8-week validation window. In other words: land the signed-position architecture, risk model, order semantics, reconciliation logic, tests, and documentation now; do **not** start the first frozen validation with shorts enabled. The current source-of-truth spec is explicitly long-only, excludes shorting and margin/leverage, and the accepted M43 state only extends paper validation for long-side scale-ins with additive protective stops. fileciteturn4file0 fileciteturn4file1 fileciteturn4file14

That recommendation is driven by current broker facts. The broker’s short path is not just “sell instead of buy.” The broker ties shorting to margin-account semantics, requires at least $2,000 account equity for margin/short access in live brokerage accounts, exposes shortability and easy-to-borrow state at the asset level, performs distinct buying-power checks for opening short sells, supports only easy-to-borrow names for opening shorts, and documents real short-position close-out / buy-in risk when borrow cannot be maintained. Paper trading uses the same API surface and can exercise side/order-state logic, but it cannot fully validate live borrow, recall, or buy-in behavior. citeturn25view2turn14view0turn15search4turn24view0turn24view1turn7view3

So the right bounded decision is:

- **Implement now:** yes.
- **Enable by default before the first 8-week freeze:** no.
- **Carry the capability behind an explicit paper-only flag:** yes.
- **Allow later activation only after a short-specific rehearsal packet passes:** yes. fileciteturn4file15 fileciteturn4file17

### Required spec decision

A new **v0.5** spec is required.

That is not optional, because v0.4 directly conflicts with active short support in several places. v0.4’s first production target is “Long-only / No leverage / No shorting,” its non-goals explicitly include margin/leverage and short selling, its strategy engine is explicitly “Long-only trend-breakout continuation,” and its regime logic forbids **all** new entries in persistent `RISK_OFF`, which is exactly where a deterministic ETF short overlay would otherwise want to operate. fileciteturn4file0 fileciteturn4file3 fileciteturn4file4

v0.5 should therefore change the following:

- introduce a **paper-only short exposure** category that is explicitly distinct from live shorting or live margin approval;
- add a **signed quantity / position-side model** across intent, orders, fills, positions, reconciliation, reporting, and risk;
- add explicit short-side order roles and stop semantics;
- add a **short-eligible universe subset** separate from the long universe;
- add side-aware regime behavior if shorts are ever enabled;
- add short-specific risk caps, protection rules, and incident handling;
- define an activation rule that keeps shorts **disabled by default** until expressly approved. fileciteturn4file9 fileciteturn4file12 fileciteturn4file13

What must remain unchanged in v0.5:

- no live trading;
- no autonomous live execution;
- no AI broker authority;
- no options, futures, crypto, prediction markets, HFT/scalping;
- no frontend broker secrets;
- broker reconciliation before new-risk execution;
- protective stop required for every filled quantity;
- kill switch blocks new risk;
- no Level 4 readiness claim. fileciteturn4file3 fileciteturn4file5 fileciteturn4file8 fileciteturn4file16

The important nuance is this: **live shorting would violate the current “no leverage / no margin borrowing” invariant**; **paper-only short simulation would not**, if v0.5 defines it as a separate paper-only exposure category and keeps all live-order paths disabled. That distinction is consistent with the broker’s live account/margin rules and with the project’s existing paper-only gating model. citeturn25view2turn14view0turn7view3

## Current Alpaca and regulatory findings

### Current Alpaca / broker findings

The broker-specific findings below come primarily from the official urlAlpaca margin and short-selling docsturn14view0, urlAlpaca orders docsturn7view1, urlAlpaca paper-trading docsturn7view3, urlAlpaca working-with-orders docsturn21view0, and urlAlpaca account docsturn25view2.

Factually, the broker currently documents the following:

Live brokerage accounts are opened as margin accounts, and accounts with at least $2,000 equity have access to margin trading and short selling. The account object exposes `shorting_enabled`, `multiplier`, `buying_power`, `regt_buying_power`, `daytrading_buying_power`, `long_market_value`, `short_market_value`, `initial_margin`, and `maintenance_margin`. That means real short selling at this broker is inseparable from margin-account semantics. citeturn25view2turn8view4turn8view5turn8view6

The asset model exposes `tradable`, `marginable`, `shortable`, `easy_to_borrow`, and `fractionable`. The official examples for U.S. equities show those fields present on equity assets, and the broker explicitly says to use the API to check borrow status daily because names can move ETB→HTB and back. citeturn11search1turn14view0

Order-side semantics are still just `buy` and `sell`; there is no separate retail-equity-side enum such as `sell_short` or `buy_to_cover`. The broker’s own “Submit Shorts” example shows that a short position is opened by submitting a `sell` order when there is no open long position, and the example is explicitly shown with `paper=True`. The same page then checks that the resulting position quantity is negative. The create-order reference also states that the only allowed order sides are `buy` and `sell`. citeturn21view0turn12view0

The broker’s buying-power logic is side-aware. For new short sells, the opening short value is computed as `MAX(limit_price, 3% above current ask) * quantity`; market shorts are checked against `3% above current ask * quantity`. Existing open long buys and open short sells consume buying power, while sell-long and buy-to-cover orders do not replenish buying power until execution. citeturn7view1turn15search4

Opening short positions is currently limited to **easy-to-borrow** securities. Hard-to-borrow opening shorts are not supported. If an open short order’s symbol changes from ETB to HTB overnight, the broker states that the open short order is automatically canceled before market open. The broker also states that short positions can be subject to stock-borrow fees once HTB, and separately documents that short positions can be forcibly closed out or bought in if shares cannot be borrowed, are recalled, or a fail-to-deliver occurs. citeturn14view0turn24view0turn24view1

Paper trading uses the same API specification as live and a dedicated paper base URL. The broker documents paper as a real-time simulation environment and separately provides a short-submission example that is explicitly wired with `paper=True`. That supports testing of order semantics, lifecycle handling, signed positions, and protective-stop orchestration in paper. It does **not** prove live borrow stability or live forced close-out behavior. citeturn7view3turn19search0turn21view0turn24view0

For protective stops, the broker supports both buy and sell stop orders. Its OCO examples explicitly show a `side="buy"` stop-loss leg for a buy-side exit group, which is the correct direction for protecting a short position. The same orders documentation also states that stop-loss `stop_price` thresholds are directional: for stop-loss sells the threshold must be below the base price; for stop-loss buys it must be above the base price. citeturn26view0turn12view2

Short positions must be modeled as signed positions. The broker’s websocket trading updates explicitly define `position_qty` as positive for long positions and negative for short positions, and the broker’s short-order example checks for a negative resulting position quantity. citeturn7view4turn17search5turn21view0

Fractional shorting is out of scope at the broker level. The broker explicitly states that it does not support short sales in fractional orders and that all fractional sell orders are marked long. Therefore, any short implementation here must use **whole-share quantities only**. citeturn10search4turn3search12

The paper environment simulates pattern-day-trader checks, and the broker defines a same-day short-open plus buy-to-cover round trip as a day trade. That does not stop your project from implementing paper shorts, but it is another reason the initial short strategy should not be designed around same-day in-and-out behavior. citeturn7view3turn7view8

From the regulatory side, entity["organization","SEC","us securities regulator"] Rule 201 under Regulation SHO imposes a short-sale price-test restriction after a covered security declines by 10% in one day, and entity["organization","FINRA","us self regulator"] materials continue to describe short sales as margin-account transactions with specific initial and maintenance margin treatment. That matters operationally even in paper, because the design should treat broker/exchange-side rejections and restrictions as authoritative rather than trying to out-predict them locally. citeturn7view6turn18search4turn18search15turn7view7

## Proposed short-side architecture

### Proposed short-side architecture

The recommended architecture is to keep the existing deterministic long-side execution pattern and mirror it **structurally**, not behaviorally. Concretely, that means: do **not** switch to broker-native bracket/OCO as the primary path for shorts in v0.5. Continue using single-leg deterministic entries followed by explicit post-fill protective-stop submission and verification, because that is already how the project’s long-side paper lifecycle and additive stop policy are defined. fileciteturn4file1 fileciteturn4file12 citeturn17search4turn26view0

The side semantics should be fixed and explicit:

| Internal action | Broker side / type | Internal role |
|---|---|---|
| Long entry | `buy` entry order | `long_entry` |
| Long protective stop | `sell` `stop` | `long_protective_stop` |
| Long exit | `sell` risk-reducing order | `long_exit` |
| Short entry | `sell` entry order | `short_entry` |
| Short protective stop | `buy` `stop` | `short_protective_stop` |
| Short cover | `buy` risk-reducing order | `short_cover` |

That mapping matches the broker’s documented side model and short-order examples. citeturn12view0turn21view0turn26view0

The deterministic short lifecycle should be:

A symbol becomes a short candidate only if short-side config is enabled, the environment is paper, the symbol is in the short-eligible subset, all data are fresh, the broker snapshot is clean, the asset snapshot says `tradable=true`, `marginable=true`, `shortable=true`, `easy_to_borrow=true`, and the account snapshot says `shorting_enabled=true`, account equity is at least $2,000, and the multiplier is margin-capable. Any missing or stale borrow/account field should fail closed. citeturn11search1turn14view0turn8view4turn8view5

The strategy should **not** use a naive “inverse long” mirror. The safer deterministic rule is a separate bearish breakout rule with stricter gating than the long side. My recommendation is:

- short candidates only from the short-eligible ETF subset;
- only after a side-aware bearish regime gate is satisfied;
- require both a 20-day and 55-day downside breakout;
- require price below SMA50 and SMA50 below SMA200;
- require ATR% to remain within the existing liquid-name risk envelope;
- require no existing long or short active intent on the same symbol;
- require no same-symbol open position on the opposite side. fileciteturn4file4 fileciteturn4file8

This is intentionally stricter than the long path because shorting has asymmetric gap and borrow risk. That is a design recommendation, not a broker requirement.

After candidate selection, the decision stage should emit a side-aware decision object: `decision_side=short`, `entry_role=initial_short` or later `scale_in_short`, `risk_regime_side=short_allowed|short_forbidden`, and a deterministic reason-code bundle. The AI/news layer may still provide advisory vetoes or non-increasing size multipliers, but it must never authorize, create, or enlarge short positions. That remains unchanged from the current spec. fileciteturn4file5 fileciteturn4file10

The risk stage then approves or rejects a `NewRiskOrderInput` with signed semantics. For shorts, the sizing equation must switch to a short stop-distance convention such as `stop_distance = stop_price - entry_price`, which is the positive adverse move for a short. The current long-only sizing formula in the risk documentation uses `entry_price - stop_price`, so v0.5 must make sizing explicitly side-aware. fileciteturn4file10

If approved, execution should emit an `ExecutionIntent` with at least these extra semantics: `position_side=short`, `signed_qty=-N`, `broker_side=sell`, `role=short_entry`, `protective_role=short_protective_stop`, `stop_side=buy`, and `opening_effect=open_short`. The current project already treats idempotency and `client_order_id` root generation as first-class concerns; keep that pattern and add explicit short-side role encoding to the intent metadata. fileciteturn4file1 fileciteturn4file6

Entry submission should stay aligned with the current paper execution boundary: **DAY limit entry orders only**, no market entries, no extended-hours entries, and no autonomous schedules. That is already the current paper-entry boundary for the broker adapter and smoke harness. fileciteturn4file12 fileciteturn4file17

On fill, partial-fill logic must mirror the existing long-side protection invariant: every filled short quantity must receive a protective buy stop for the exact filled quantity, immediately, and never remain unprotected. The current spec already requires that for filled quantity in general; v0.5 should state the short-side equivalent explicitly. fileciteturn4file1

After the protective buy stop is submitted, the workflow must verify it through both stream and REST read-back before the short position is considered protected. If buy-stop verification misses the current thresholds, the existing incident ladder should remain in force: warning, then critical pause-new-risk, then flatten-if-safe recommendation. fileciteturn4file1 fileciteturn4file10

For exits, do **not** permit implicit side flips. In v0.5, a symbol may be long, or short, or flat, but never long and short simultaneously in the internal model. A short cover is a risk-reducing `buy`. A long-to-short or short-to-long reversal must be modeled as two phases: fully close the existing side, reconcile, then only later open the opposite side if a separate fresh signal still exists. That is the safest deterministic policy even apart from broker quirks, and it avoids same-symbol wash-trade or opposing-order ambiguity.

### Protective stop policy for shorts

The short-side protective-stop rule should be as strict as the existing long rule:

**Every filled short quantity must have a verified protective buy stop.** There should be no exception for paper short positions. This preserves the current non-negotiable invariant that every filled quantity is protected. fileciteturn4file1 fileciteturn4file8

The stop quantity rule should be:

- initial short fill of `q` shares → submit one `buy` stop with quantity `q`;
- add-on short fill of `q_add` shares → submit one additional `buy` stop with quantity `q_add`;
- aggregate verified protected quantity must satisfy `sum(open_verified_short_buy_stop_qty) >= abs(open_short_qty)`. That is the natural signed extension of the current M43 aggregate protection rule. fileciteturn4file14

The short-side stop policy should remain **additive only** in the initial version. No stop replacement. No cancel/replace during short scale-in. No trailing-stop migration as a primary broker-native mechanism. That is fully aligned with the current paper scale-in safety posture. fileciteturn4file1 fileciteturn4file12

If protective buy-stop submission fails, the incident policy should mirror the existing spec thresholds:

- warning incident after the warning threshold;
- critical incident and `PAUSED_NEW_RISK` after the critical threshold;
- flatten-if-safe recommendation after the flatten threshold. fileciteturn4file1 fileciteturn4file10

The most important short-specific addition is this: **never allow a non-stop discretionary cover while protective buy stops remain live for the same quantity**. Otherwise a buy-to-cover plus a later triggered buy stop could flip the account unintentionally long. Therefore, v0.5 should initially support only:

- stop-triggered partial/full covers; and
- explicit **full** discretionary covers, but only after all symbol-level short protective buy stops are canceled and verified canceled first.

I recommend forbidding discretionary **partial** short covers in the first active short version for exactly this reason. That is a design recommendation, not a broker rule, but it materially reduces accidental-long-flip risk.

### Scale-in policy for shorts

The architecture can support a short-side equivalent of M43, but the first frozen default should **not** activate it.

So the right split is:

- **Implement capability** in M44: yes.
- **Enable in frozen validation**: no, keep `max_short_add_entries_per_symbol = 0` by default.

The equivalent rules, once later enabled, should be:

A short scale-in candidate must already have a short paper position with `abs(qty) > 0` and below the configured cap. Existing verified protective buy-stop coverage must be present and sufficient before a short add-on can even be considered. A pending entry order, ambiguous order, stale order, pending exit, unresolved incident, duplicate active intent, or missing prior add-on stop verification must all block the short add-on. Those are direct short-side mirrors of the current long-side M43 rules. fileciteturn4file2 fileciteturn4file14

The short add-on entry order is another `sell` entry. After that additional quantity fills, the workflow submits a **new** protective buy stop only for the newly filled add-on quantity and then verifies that the summed open short-protective quantity covers the absolute open short position. fileciteturn4file12 fileciteturn4file14

My recommendation is that v0.5 define the symmetry, but M45 frozen config keep short scale-ins disabled.

### Execution / reconciliation impact

Reconciliation has to become fully signed and side-aware.

The broker/adapter normalization layer should produce `signed_qty`, `position_side`, `signed_market_value`, `gross_market_value_abs`, `net_market_value_signed`, and role-classified open orders. The broker already documents negative short quantities in trade updates, and the account snapshot already exposes separate long and short market value fields, so the system should stop treating quantity and exposure as implicitly long-only. citeturn7view4turn8view4turn8view6

The rules should be:

- `signed_qty > 0` means long;
- `signed_qty < 0` means short;
- `gross_exposure = Σ abs(position_market_value)`;
- `net_exposure = Σ signed_position_market_value`;
- `short_exposure = Σ abs(short_position_market_value)` over short positions only.

Open-order role classification must also become side-aware:

- `sell stop` protecting a long position → `long_protective_stop`;
- `buy stop` protecting a short position → `short_protective_stop`;
- `sell` order with no open long and short intent metadata → opening short;
- `buy` order against an open short, after stop-cancel verification → short cover;
- any same-symbol opposing order mix that cannot be explained deterministically → `unknown_or_ambiguous` and blocks new risk. fileciteturn4file2 fileciteturn4file17 citeturn21view0turn26view0

The system must additionally check:

- negative-quantity broker positions with no matching internal short intent/position ledger → critical incident;
- open short position with verified buy-stop quantity below `abs(open_short_qty)` → critical incident;
- full cover completed but one or more buy stops still open → critical incident and immediate risk-reducing cleanup;
- existing long position in symbol blocks new short entry unless and until full flat reconciliation has been reached;
- existing short position blocks new long entry unless and until full flat reconciliation has been reached.

That is the minimum deterministic reconciliation envelope needed to keep shorts safe.

## Risk envelope and eligible universe

### Risk policy for shorts

The correct short policy for v0.5 is **intentionally tighter than the current long policy**. My recommendation is to separate **implementation capability** from **frozen default activation**.

If shorts are ever enabled in paper, the active caps should be:

- environment: `paper` only;
- explicit feature flag: required;
- whole-share quantities only;
- shortable asset required;
- `easy_to_borrow=true` required;
- `marginable=true` required;
- account snapshot must show `shorting_enabled=true`;
- account equity must be at least `$2,000`;
- broker/account state must be unambiguous and reconciliation-clean;
- one concurrent open short symbol maximum;
- broad-ETF-only short universe;
- one initial short entry maximum per symbol;
- no short scale-in in the first frozen config;
- max total short quantity per symbol: `1` share;
- max per-symbol short notional: `$1,000`;
- max total portfolio short notional: `$1,000`;
- max portfolio short exposure: `1%` of equity;
- max net short exposure: `1%` of equity;
- max risk at stop per short trade: `min(existing_long_max_risk_per_trade, 0.25% of equity)`;
- max aggregate portfolio short risk at stop: `0.50% of equity`.  

Those are recommendations, not broker limits. They are deliberately small because this project is still in paper validation and because broker-documented shorting introduces ETB status changes, buy-in/close-out risk, and distinct buying-power handling. citeturn14view0turn15search4turn24view0

In addition, the short policy should hard-forbid:

- leveraged ETFs;
- inverse ETFs;
- individual stocks;
- sector ETFs in the first activation phase;
- fractional shorts;
- HTB names;
- symbols whose borrow/shortability snapshot is stale or missing;
- shorting under any ambiguous broker state;
- shorting when the account snapshot cannot safely support margin/short semantics. fileciteturn4file8 citeturn10search4turn14view0

### Universe recommendation

The full current universe should **not** be eligible for initial short candidates.

My recommendation is: **only broad ETFs initially** — `SPY`, `QQQ`, `DIA`, and `IWM` — and keep shorts disabled for individual stocks and sector ETFs until a separate validation cycle is accepted. The current configured paper universe is broader, but that does not mean the short universe should be equally broad. fileciteturn4file2

This is an inference-based design recommendation supported by the broker facts above. The broker updates ETB/borrow status daily, may cancel open short orders when ETB turns to HTB overnight, and documents buy-in / close-out scenarios when borrow cannot be maintained. Broad ETFs are typically the most liquid, most consistently ETB, and least exposed to single-name earnings and idiosyncratic gap risk. Individual stocks introduce exactly the event-risk and locate/borrow fragility that the first short validation should avoid. citeturn14view0turn24view0turn24view1

So the recommended short universe policy is:

- long universe: unchanged from v0.4 / current accepted state;
- short universe in v0.5: `SPY`, `QQQ`, `DIA`, `IWM` only;
- no individual-stock shorts in the first short-capable release;
- no sector ETF shorts in the first short-capable release;
- no leveraged or inverse ETF shorts at all unless separately spec-approved.

## Data model, reconciliation, reporting, and testing

### Database / ledger impact

The current ledger already has the core tables needed — candidates, decisions, risk checks, execution intents, orders, fills, positions, reconciliations, incidents, and reports — but v0.5 must make those models signed and side-aware. fileciteturn4file9 fileciteturn4file6

The minimum schema/model additions are:

- `trade_candidates`: add `candidate_side` and side-aware signal metadata;
- `trade_decisions`: add `decision_side`, short-specific reason codes, and side-aware regime result;
- `risk_checks`: add `position_side`, `signed_qty`, `shortable_snapshot`, `easy_to_borrow_snapshot`, `marginable_snapshot`, `account_shorting_enabled_snapshot`, account multiplier/equity snapshot, `short_exposure_before_after`, `gross_exposure_before_after`, `net_exposure_before_after`, and side-aware risk-at-stop fields;
- `execution_intents`: add `position_side`, `signed_qty`, `broker_side`, `opening_effect`, `closing_effect`, `protective_side`, and explicit roles such as `short_entry`, `short_scale_in`, `short_protective_stop`, `short_cover`;
- `orders`: add role classification, signed intended quantity, side-at-submission context, and protective linkage fields;
- `fills`: add signed fill quantity and resulting signed position quantity;
- `positions`: add `signed_qty`, `position_side`, `protected_qty_abs`, `short_exposure_notional`, and separate long/short realized/unrealized PnL rollups;
- `broker_reconciliations`: add signed exposure, gross/net exposure, short exposure, side-aware order matching, and ambiguity classification;
- `system_events`: add short-specific incident codes such as `short_non_shortable`, `short_etb_missing`, `short_buy_stop_missing`, `unexpected_long_flip`, `cover_without_stop_cancel`, `broker_short_closeout_detected`, and `borrow_state_ambiguous`;
- `reports`: add side-separated counts, PnL, stop coverage, and incident rollups. fileciteturn4file9

I also recommend one integrity rule at the repository/model layer: **one open symbol position, one side only**. The current ledger already enforces one open position per symbol; v0.5 should preserve that and make side/sign consistency explicit. fileciteturn4file6

### Reporting / dashboard impact

Reporting must distinguish action roles and exposure side.

Daily and weekly outputs should separately report:

- `long_initial_entry`;
- `long_scale_in`;
- `short_initial_entry`;
- `short_scale_in`;
- `long_exit`;
- `short_cover`;
- `long_protective_stop`;
- `short_protective_buy_stop`;
- long exposure;
- short exposure;
- gross exposure;
- net exposure;
- long realized/unrealized PnL;
- short realized/unrealized PnL;
- risk-at-stop, split by long and short. fileciteturn4file11 fileciteturn4file14

The dashboard should make signed state visually obvious. At minimum, every position row should show `side`, `abs qty`, `signed qty`, `avg entry`, `stop price`, `protected qty`, and `risk at stop`. Every open order should show both broker `side` and internal `role`, because `buy` can mean either long entry or short cover, and `sell` can mean either long exit or short entry. That distinction becomes operationally critical once short support exists.

### Testing plan

The implementation test plan should be expanded substantially. The following checklist is the minimum viable coverage.

**Unit and model tests**

- short support disabled by default;
- short support enabled only when both config and spec version allow it;
- signed quantity validation and side/sign consistency;
- short sizing uses `stop_price - entry_price` adverse-distance semantics;
- shortability / ETB / marginable flags required;
- non-shortable asset rejected;
- ETB missing or stale rejected;
- account `shorting_enabled=false` rejected;
- account equity `< 2000` rejected;
- whole-share-only short quantity validation;
- fractional or notional short rejected;
- broad-ETF-only short universe enforcement;
- individual-stock short rejected;
- sector-ETF short rejected in first version;
- kill switch blocks short;
- AI cannot authorize short, increase short size, or relax short rules. fileciteturn4file8 citeturn10search4turn14view0

**Execution and lifecycle tests**

- short entry creates correct side/order semantics;
- short `ExecutionIntent` contains signed negative quantity;
- short entry submits broker `sell`;
- filled short requires buy-stop;
- partial short fill requires buy-stop for filled quantity only;
- missing buy-stop creates incident;
- buy-stop verification failure escalates per thresholds;
- no accidental long flip on full cover path;
- full discretionary cover requires prior stop cancel verification;
- cover quantity cannot exceed absolute short quantity;
- opposite-side reversal refused without flat reconcile;
- pending short entry blocks duplicate;
- ambiguous open order blocks new short risk;
- existing long blocks short in same symbol;
- existing short blocks long in same symbol. fileciteturn4file1 fileciteturn4file12

**Scale-in tests**

- short scale-in disabled by frozen default;
- if enabled later, one short add-on maximum;
- existing buy-stop coverage required before short add-on;
- additive buy-stop for added short quantity;
- aggregate protected quantity must cover `abs(open_short_qty)`;
- duplicate short scale-in signal blocked;
- previous add-on stop unverified blocks next add-on;
- pending entry or pending exit blocks short add-on. fileciteturn4file2 fileciteturn4file14

**Broker adapter and fake-broker tests**

- short order request construction uses `sell`;
- buy-stop request construction uses `buy` stop semantics;
- open-order role classification recognizes short protective buy stops;
- trade-update mapping supports negative resulting position quantity;
- read-only paper mode remains read-only by default;
- live endpoint refusal still passes;
- no secret leakage in logs, summaries, or evidence;
- no SDK/client use without explicit injected paper client;
- all smoke harnesses still refuse by default unless every short write gate is present. fileciteturn4file13 fileciteturn4file17

**Reconciliation tests**

- negative quantity reconciliation;
- long vs short side-aware position matching;
- long and short protective order matching;
- signed gross exposure calculation;
- signed net exposure calculation;
- short exposure calculation;
- side-separated realized/unrealized PnL reporting;
- critical incident on negative broker qty with no internal short intent;
- critical incident on residual buy stop after full cover;
- ambiguity handling when broker state is inconsistent. fileciteturn4file8

**CLI / smoke / evidence tests**

- short-support code path still performs no real broker writes by default;
- optional short smoke harness refuses without explicit paper-write confirmations;
- no live endpoint usage;
- no secrets in generated evidence;
- sanitized result packet includes side, signed qty, stop role, exposure, reconciliation summary, and cleanup summary.

## M44 implementation and M45 readiness

### M44 implementation recommendation

M44 should be a **spec + architecture + test** milestone, not a “turn shorts on” milestone.

The concise engineering plan is:

First, write and approve **Spec v0.5**. It should add paper-only short exposure, side-aware regime/strategy/risk/execution/reconciliation language, a short-eligible universe subset, short-specific protective stop rules, signed quantities, and explicit default-disabled activation. It must preserve all current non-negotiable safety invariants. fileciteturn4file0 fileciteturn4file3

Second, add config blocks in the project’s typed configuration layer for:

- `shorts.enabled`;
- `shorts.paper_only_short_exposure`;
- `shorts.eligible_symbols`;
- `shorts.require_shortable`;
- `shorts.require_easy_to_borrow`;
- `shorts.require_marginable`;
- `shorts.require_account_shorting_enabled`;
- `shorts.max_open_symbols`;
- `shorts.max_entries_per_symbol`;
- `shorts.max_add_entries_per_symbol`;
- `shorts.max_total_symbol_qty`;
- `shorts.max_symbol_notional_usd`;
- `shorts.max_portfolio_short_notional_usd`;
- `shorts.max_short_risk_per_trade_pct`;
- `shorts.max_portfolio_short_risk_at_stop_pct`;
- `shorts.allow_partial_discretionary_cover=false`;
- `shorts.allow_stop_replacement=false`.  

Third, modify the deterministic code modules that currently assume long-only semantics: strategy candidate generation, side-aware sizing, risk checks, execution-intent construction, order-role classification, broker request builders, partial-fill stop logic, reconciliation service, ledger models/repositories, reporting read models, and dashboard views. The safest concrete module targets are the existing strategy, risk, execution, broker, reconciliation, ledger, reporting, and control-plane packages already documented in the project docs. fileciteturn4file8 fileciteturn4file12 fileciteturn4file13 fileciteturn4file9

Fourth, update the operational docs:

- main spec v0.5;
- risk policy;
- execution policy;
- broker integration notes;
- paper trading runbook;
- validation plan;
- scale-in policy appendix or replacement section for short symmetry. fileciteturn4file7 fileciteturn4file8 fileciteturn4file11

Fifth, create an M44 evidence packet containing:

- v0.5 spec diff;
- frozen config snapshot;
- full unit/temporal/fake-broker/reconciliation test results;
- signed-quantity and short-protective-stop fake traces;
- reconciliation examples for negative positions;
- sanitized incident examples;
- explicit statement that live trading remains disabled and that short support is default-disabled.

Sixth, keep **real broker writes forbidden by default** in M44. If you want a short-specific paper smoke path, make it a separately gated operator action, not an automatic part of the milestone. That is consistent with the project’s existing smoke philosophy. fileciteturn4file7 fileciteturn4file13 fileciteturn4file18

### M45 readiness judgment

**Yes, M45 can safely be the 8-week paper validation start after M44 — but only if M45 starts with shorts still disabled by default.**

**No, M45 should not start the first frozen 8-week validation with shorts enabled.**

That is the clean answer.

The exact M44 acceptance gates I would require before allowing M45 to start are:

- Spec v0.5 approved and merged;
- all existing long-side invariants still passing unchanged;
- short support default-disabled in frozen config;
- signed quantity / side-aware reconciliation tests all green;
- shortability / ETB / account-shorting-enabled gates fully tested;
- buy-stop protection path fully tested for short fills and partial fills;
- no partial discretionary short-cover support in the first version;
- no same-symbol reversal path allowed;
- reporting/dashboard side separation implemented and tested;
- no live endpoint, no live credentials, no autonomous live execution, and no secret leakage;
- read-only and fake/broker smoke harnesses still fail closed by default;
- if an optional short paper smoke harness exists, it must remain out of the M45 frozen scope unless separately approved. fileciteturn4file7 fileciteturn4file13 fileciteturn4file14

If you insist on starting a frozen validation **with shorts enabled**, then I would add a mandatory intermediate milestone — effectively an **M44A / short controlled paper rehearsal** — before M45. That intermediate milestone would need a tiny broad-ETF-only paper short smoke packet showing: entry submit, fill, protective buy-stop verify, reconciliation clean, full cover without long flip, and zero unresolved incidents. Without that intermediate rehearsal, enabling shorts in the first frozen window is not the safer choice.

## Risks and open questions

### Risks and open questions

The largest unresolved risk is not code complexity; it is **broker reality mismatch**. Paper can validate signed positions, side-aware orders, and stop orchestration, but it cannot fully validate real borrow recalls, close-outs, buy-ins, or live HTB transitions. The broker explicitly documents those risks for real short positions. citeturn24view0turn24view1

A second unresolved issue is regime semantics. v0.4 currently forbids new entries in `RISK_OFF`, while a deterministic short overlay would most naturally want short entries only in bearish risk regimes. That requires a deliberate v0.5 design choice rather than a coding patch. fileciteturn4file4

A third risk is stop/cover interaction. Buy stops protecting shorts can become long-creating orders if the cover workflow is not strictly cancel-first and verify-first. That is exactly why I recommend no discretionary partial short covers in the first version.

A fourth risk is scope creep. Adding short-side support **and** enabling it **and** starting the first frozen 8-week validation at the same time is too much change in one state transition. Implementing it now but leaving it disabled is the better bounded move.

A fifth open question is whether you want short strategy activation to be tied only to `RISK_OFF`, or whether you want a narrower “bearish broad-index breakdown” gate that is separate from the long-side market regime gate. I recommend the former for clarity in v0.5, but that is still a spec decision.

The final open implementation question is operational, not conceptual: whether M45 should begin from a deliberately flat paper account or from a fully reconciled carried state. Given the introduction of dormant short-side code, my preference is to start the frozen window from a **flat and reconciled** paper baseline if operationally feasible.