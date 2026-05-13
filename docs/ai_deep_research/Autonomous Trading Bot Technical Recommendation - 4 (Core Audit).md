# Προ-παγώματος audit για το Autonomous AI Trading Bot v0.4

## Executive readiness judgment

Κρίση: **ready after moderate changes**.

Ο πυρήνας στρατηγικής/ρίσκου/εκτέλεσης είναι ήδη αρκετά ώριμος για να περάσει σε freeze μετά από **ένα τελικό implementation milestone**, όχι όμως ως έχει. Υπάρχουν τρία ουσιαστικά ζητήματα που πρέπει να λυθούν πριν αρχίσει το 8-week frozen paper window:  
πρώτον, το frozen validation δεν έχει ακόμη δικό του πλήρως παγωμένο policy bundle και operational schedule· δεύτερον, το M43 scale-in είναι policy-complete αλλά **όχι** real-broker-proven, ενώ η τρέχουσα τεκμηρίωση της urlAlpacaturn6view2 αφήνει ανοιχτό θέμα για πολλαπλές ανεξάρτητες conditional closing orders· τρίτον, η έναρξη με carry-in AAPL/MSFT/XLK θα μολύνει attribution, drawdown και statistics του validation window. fileciteturn10file0 fileciteturn12file1 fileciteturn12file2 fileciteturn12file0 citeturn9search0turn6view2

Η γενική αρχιτεκτονική δεν χρειάζεται άλλη proving phase. Οι M39–M42 αποδείξεις δείχνουν ότι controlled paper entry + stop placement + supervised one-shot scheduled equivalent έχουν λειτουργήσει με επιτυχημένη normal protective-stop path και clean protected holds. Αυτό αρκεί για να ειπωθεί ότι το project είναι **κοντά** σε frozen validation, αλλά όχι ότι είναι ήδη ασφαλές να παγώσει χωρίς policy-tightening. fileciteturn12file2 fileciteturn11file0

## Recommended pre-freeze changes

### must change

- **Create spec v0.5 as the frozen validation spec.**  
  Αυτό συγκρούεται με το v0.4 επειδή το v0.4 είναι execution-first και καλύπτει live-target semantics, αλλά δεν ορίζει ακόμη ένα πλήρες, validation-specific freeze bundle για carry-in policy, daily broker-write budget, max new entries/day, scale-in staging, validation-specific acceptance clock και frozen reporting schema. **Ναι, απαιτείται v0.5.** Πρέπει να μείνουν αμετάβλητα: no live trading, no autonomous live execution, no AI broker authority, reconciliation-before-new-risk, protective stop on every filled quantity, kill switch semantics. fileciteturn10file0 fileciteturn12file1

- **Start the 8-week validation flat, not with carry-in protected holds.**  
  Αυτό συγκρούεται πρακτικά με τη σημερινή M42/M43 accepted state, όπου AAPL/MSFT/XLK υπάρχουν ως protected holds και είναι δυνητικά scale-in candidates. Πρέπει να αλλάξει γιατί διαφορετικά το validation θα ξεκινήσει με προϋπάρχον PnL, pre-freeze decision history και asymmetry σε stop age / holding age / attribution. **Ναι, απαιτείται v0.5** με ρητή `flat_start_required: true` στο validation-start policy. Πρέπει να μείνει αμετάβλητο ότι risk-reducing cleanup επιτρέπεται και ότι protective-stop verification παραμένει mandatory μέχρι το cleanup. fileciteturn12file2 fileciteturn12file0

- **Disable scale-ins at validation day 1; stage-gate them later.**  
  Αυτό συγκρούεται με το v0.4/M43, όπου `enabled_for_paper_validation: true`. Πρέπει να αλλάξει επειδή το M43 είναι fake/stub-only και όχι real broker evidence, ενώ η τρέχουσα επίσημη τεκμηρίωση της urlAlpacaturn6view2 σημειώνει ότι, έξω από grouped orders, το σύστημα μπορεί να μη δεχθεί δύο conditional closing orders όπως τις περιγράφει η additive-stop λογική. **Ναι, απαιτείται v0.5.** Πρέπει να μείνουν αμετάβλητα: max 2 entries/symbol, max 1 add-on, no stop cancel/replace in scale-in path, aggregate protected-quantity rule, duplicate-intent blockers. fileciteturn12file0 fileciteturn11file0 citeturn9search0

- **Make AI/news negative-only for the first frozen window.**  
  Αυτό συγκρούεται με το v0.4 FinalScore επειδή σήμερα το AIScore συμμετέχει θετικά στο ranking. Πρέπει να αλλάξει γιατί ο στόχος του πρώτου frozen paper window πρέπει να είναι η καθαρή αξιολόγηση του deterministic core με το AI ως bounded risk overlay, όχι ως source of upside rank variability. **Ναι, απαιτείται v0.5.** Πρέπει να μείνουν αμετάβλητα: structured output, hard-blocks για high-severity adverse risk, neutral fallback, no broker write authority, no AI size increase. fileciteturn10file0

- **Require non-IEX-only primary signal data before freeze.**  
  Αυτό δεν αλλάζει την core strategy, αλλά πρέπει να γίνει explicit pre-freeze gate. Το ίδιο το spec λέει ότι production signals δεν πρέπει να βασίζονται μόνο στο Alpaca free IEX feed, και η επίσημη τεκμηρίωση της urlAlpacaturn6view4 αναφέρει ότι το default Basic plan δίνει real-time equities data μόνο από IEX. **v0.5 recommended** για να μετατρέψει αυτό το principle σε hard validation gate. Πρέπει να μείνει αμετάβλητο ότι ο broker παραμένει Alpaca paper-first. fileciteturn10file0 citeturn6view4

### should change

- **Freeze 20D breakout as the only active breakout for the first 8 weeks.** Το 55D να μείνει research-only, όχι active frozen variant. fileciteturn10file0
- **Use deterministic non-stop exits from day 1, but keep app-level trailing disabled initially.** Active set: fail-fast, technical EMA10 exit, time stop. Αυτό μειώνει stop-cancel/replace complexity χωρίς να αφήνει το validation stop-only. fileciteturn10file0
- **Keep the full 14-symbol universe, but split risk caps by bucket**: broad ETFs, sector ETFs, single-name mega caps, plus explicit tech-cluster cap. fileciteturn12file0
- **Skip new entries on NYSE early-close sessions during the first frozen window** για να μειωθεί operational edge-case risk. entity["organization","NYSE","us securities exchange"] core hours are 9:30 a.m.–4:00 p.m. ET and official early-close days exist in the 2026 calendar. citeturn7view0
- **Add explicit rejection reasons** for `early_close_session`, `execution_budget_exhausted`, `correlation_cluster_cap`, `same_day_reentry_forbidden`, `scale_in_stage_gate_not_met`. fileciteturn10file0

### optional

- **Add a watchlist-only reporting view** for symbols that passed filters but lost on correlation/budget caps. fileciteturn10file2
- **Add stressed risk-at-stop reporting** using a small stop-slippage buffer proxy for ETFs versus single names, without changing the actual sizing formula yet. fileciteturn12file1

### do not change

- Η regime classifier λογική 50/200 + hysteresis + RV20 state model. fileciteturn10file0  
- Τα deterministic long filters: trend, breakout, RS63, ATR band, price/liquidity, earnings blackout. fileciteturn10file0  
- Η protective-stop mandate. fileciteturn11file1  
- Το reconciliation-before-new-risk invariant. fileciteturn11file0  
- Οι kill-switch states και η αρχή “risk-reducing exits remain allowed”. fileciteturn11file1  
- Τα non-negotiables: no live trading, no autonomous live execution, no leverage, no shorts for this phase, no AI broker authority. fileciteturn10file0

## Long strategy audit

Η long-side στρατηγική είναι **αρκετή** για πρώτο frozen validation, με στοχευμένες αλλαγές μόνο στο scoring και στο ενεργό exit set.

Ως facts, το v0.4 long candidate απαιτεί regime not `RISK_OFF`, `Close > SMA50`, `SMA50 > SMA200`, breakout πάνω από prior high, `VolumeRatio20 >= 1.20`, `RS63 > 0`, ATR% μέσα στο band, price/liquidity filters, earnings blackout και duplicate-intent protection. Τα initial exits είναι ήδη deterministically defined: initial ATR stop, app-level trailing, technical EMA10 exit, time stop και fail-fast. fileciteturn10file0

**Regime classification:** adequate, δεν θα την άλλαζα πριν το πρώτο 8-week freeze. Είναι coarse, explainable και ήδη fixture-tested για `RISK_ON`, `CAUTION`, `RISK_OFF`. fileciteturn12file1

**Breakout logic:** το 20D breakout είναι σωστό ως frozen primary. Το 55D να μείνει μόνο ablation/research path, όχι active policy, ώστε το πρώτο forward window να μην γίνεται multivariant runtime experiment. fileciteturn10file0

**RS63 / relative strength:** adequate. Σε αυτό το curated liquidity-heavy universe αρκεί `RS63 > 0`; το percentile floor να μη μεταφερθεί ως active extra gate στο frozen live-universe set. fileciteturn10file0

**ATR / liquidity / volume filters:** adequate και δεν χρειάζονται softening. Το universe είναι ήδη αρκετά liquid ώστε τα `min_price`, `ADV20` και ATR band να λειτουργούν περισσότερο ως safety filters παρά ως alpha knobs. fileciteturn10file0

**Earnings blackout:** keep unchanged. Το deterministic `2 sessions before / 1 after`, με `unknown => block entries`, είναι σωστό για first validation επειδή περιορίζει γνωστό gap-risk χωρίς discretion. fileciteturn10file0 fileciteturn12file1

**Candidate scoring:** εδώ είναι η βασική προτεινόμενη αλλαγή. Για το πρώτο frozen window, το AI δεν πρέπει να προσθέτει upside score. Η recommendation είναι:  
`FinalScore = 0.70 * TechnicalScore + 0.20 * RelativeStrengthScore + 0.10 * PortfolioFitScore`, με AI μόνο ως hard-block / size-reduction / explanation layer. Αυτό κάνει το system state πιο εύκολο να ελεγχθεί και να αποδοθεί. fileciteturn10file0

**Rejection reasons:** ο υπάρχων μηχανισμός είναι καλός αλλά χρειάζονται τέσσερα νέα frozen-window reasons: `same_day_reentry_forbidden`, `early_close_session`, `execution_budget_exhausted`, `correlation_cluster_cap`. fileciteturn10file0

**Exit helper calculations:** οι φόρμουλες είναι adequate. Η σύσταση δεν είναι να αλλάξουν τα μαθηματικά, αλλά να παγώσει ρητά ποια helpers είναι active. Δηλαδή: fail-fast, technical exit, time stop active· trailing inactive στο πρώτο frozen window. fileciteturn10file0

**Determinism / no AI authority:** ισχυρό σημείο του spec και δεν χρειάζεται weakening. fileciteturn11file0

Συμπέρασμα: **αλλαγή πριν το freeze ναι**, αλλά όχι στον πυρήνα των long entry rules. Η αλλαγή πρέπει να γίνει στο **AI contribution model** και στο **active exit set**, όχι σε regime, breakout, RS63, ATR, volume ή earnings blackout. fileciteturn10file0

## Universe audit

Η τελική recommendation είναι: **keep full universe**, όχι ETF-only reduction.

Το approved universe είναι μικρό, ρευστό και operationally manageable: broad ETFs, sector ETFs και mega-cap equities. Για daily/swing paper validation αυτό είναι επαρκές και βοηθά να δοκιμαστούν τόσο index/sector όσο και single-name stop/reconciliation paths μέσα σε ελεγχόμενο symbol count. fileciteturn10file0 fileciteturn12file0

Το πρόβλημα δεν είναι η ποιότητα των symbols αλλά η **εσωτερική συσχέτιση**. Το set συνδυάζει broad-beta ETFs με tech-heavy ETF exposure και τα ίδια mega-cap tech names. Η official holdings τεκμηρίωση δείχνει ότι το XLK έχει ως top holdings τη Microsoft, τη NVIDIA και την Apple, ενώ το QQQ είναι το Nasdaq-100 tracker, άρα το overlap/concentration risk είναι πραγματικό. citeturn3view2turn2search1

Τελική frozen policy:

- **Candidate universe:** κράτησε και τα 14 symbols.
- **Risk buckets:**  
  broad ETFs = SPY, QQQ, DIA, IWM  
  sector ETFs = XLK, XLF, XLE, XLV  
  single names = AAPL, MSFT, NVDA, AMZN, META, GOOGL
- **No symbol additions/removals before the first freeze.**
- **Separate ETF and single-stock caps:** ναι.
- **No watchlist split for trading permissions**, μόνο optional reporting split.

Για long-plus-short validation αργότερα, το ίδιο universe μπορεί να μείνει ως base, αλλά shorts δεν πρέπει να μπουν στο ίδιο first frozen window επειδή αλλάζουν margin, borrow, asymmetric stop logic και reporting semantics. fileciteturn10file0

## Risk policy audit

Το v0.4 ήδη έχει conservative live-micro caps, αλλά για το frozen paper validation λείπουν operational caps και concentration semantics που είναι πιο σημαντικά από το να γίνουν οι exposure numbers πιο “έξυπνοι”. Τα τρέχοντα live-micro values είναι 20% gross/deployable, 4% max position, 0.35% max risk per trade, 5 open positions, 10% sector cap και 1%/2.5%/5% daily/weekly/monthly loss limits. fileciteturn10file0

### Recommended frozen 8-week limits

| Policy | Recommended limit |
| --- | ---: |
| max_gross_exposure_pct | 20% |
| max_net_exposure_pct | 20% |
| max_deployable_capital_pct | 20% |
| max_open_positions | 4 |
| max_position_size_pct_etf | 4% |
| max_position_size_pct_stock | 3% |
| max_risk_per_trade_pct | 0.35% |
| max_symbol_risk_at_stop_pct_after_scalein | 0.50% |
| max_portfolio_risk_at_stop_pct | 1.00% |
| max_sector_exposure_pct | 8% |
| max_tech_complex_exposure_pct | 10% |
| max_broad_beta_overlap_pct | 8% |
| max_new_entries_per_day | 2 |
| max_scale_ins_per_day | 0 initially; 1 after stage-enable |
| max_broker_writes_per_day | 10 while scale-ins are off |
| max_unresolved_critical_incidents | 0 |
| max_unresolved_stop_or_reconciliation_incidents_overnight | 0 |
| max_warning_only incidents carried overnight | 2, with owner and ETA |
| max_daily_loss_pct | 1.0% |
| max_weekly_loss_pct | 2.0% |
| max_monthly_loss_pct | 4.0% |
| soft trailing validation drawdown pause | 4.0% |
| hard validation fail/restart drawdown | 6.0% |
| overnight carry | allowed only if fully protected and EOD/BOD reconciliation clean |
| same-day re-entry after stop/exit | forbidden |

Αυτές οι τιμές δεν χρειάζονται leverage assumptions και συνάδουν με το υπάρχον conservative envelope, αλλά προσθέτουν όσα λείπουν operationally: daily entry budget, broker-write budget, risk-at-stop aggregation και correlation bucketing. fileciteturn11file1

## Scale-in audit

Η v0.4/M43 scale-in λογική είναι **καλή ως policy design**, αλλά **όχι κατάλληλη για enablement from day 1** του frozen validation.

Τα δυνατά σημεία της πολιτικής είναι σωστά: ένα μόνο add-on, additive protection, no stop replacement, aggregate protected quantity rule, duplicate-intent blocking, pending/ambiguous-order blockers και no AI authorization of scale-ins. fileciteturn12file0

Το πρόβλημα είναι ότι δεν υπάρχει ακόμη real-broker proof ότι η additive-stop path λειτουργεί όπως περιγράφεται σε πραγματικό Alpaca paper lifecycle. Επιπλέον, η επίσημη τεκμηρίωση της urlAlpacaturn6view2 για bracket/conditional exits αναφέρει ότι γενικά δύο separate conditional closing orders δεν υποστηρίζονται εύκολα έξω από grouped order classes. Αυτό δεν αποδεικνύει ότι το M43 design είναι λάθος, αλλά είναι αρκετό για να πει κανείς ότι δεν πρέπει να ενεργοποιηθεί σε frozen window χωρίς broker-capability proof. citeturn9search0

**Recommendation:**  
**enable scale-ins only after 10 clean scheduled runs** και μόνο αν περάσουν όλα τα παρακάτω:

1. 10 consecutive clean scheduled runs χωρίς missing-stop, duplicate-order ή unresolved mismatch incident.  
2. Flat-start validation baseline έχει ήδη κλειδώσει.  
3. Real Alpaca paper proof ότι second protective stop για added quantity γίνεται accepted/verified ενώ η πρώτη stop παραμένει ανοικτή και το summed protected quantity ισούται με τη θέση.  
4. Reconciliation and reporting prove correct role attribution: `initial_entry`, `scale_in_entry`, `initial_protective_stop`, `add_on_protective_stop`. fileciteturn12file0 fileciteturn11file0

Αν αυτό δεν αποδειχθεί μέχρι τη 10η clean run, η σωστή πολιτική είναι **keep implemented but disabled during the first 8-week validation**. Δεν υπάρχει λόγος να ρισκαριστεί το frozen window για ένα feature που δεν είναι απαραίτητο για να αξιολογηθεί ο deterministic core. fileciteturn12file1

## Existing protected positions policy

**Recommendation: B. flat broker state before validation start.**

Η σημερινή accepted state μετά το M42 είναι τρεις protected holds: AAPL, MSFT, XLK. Αυτό είναι χρήσιμο ως proof of working paper paths, αλλά **όχι** ως validation baseline. fileciteturn12file2

| Criterion | Carry-in protected positions | Flat broker state |
| --- | --- | --- |
| PnL attribution | contaminated | clean |
| Drawdown calculation | ambiguous starting equity-to-position mapping | clean |
| Win/loss stats | contaminated by pre-freeze trades | clean |
| Scale-in eligibility | complex and path-dependent | clean |
| Reporting complexity | high | low |
| Safety | acceptable if protected, but operationally noisy | best |

Αν ξεκινούσε το validation με carry-in, θα έπρεπε να γίνει separation μεταξύ `carry_in_trade`, `validation_start_trade`, carry-in unrealized PnL, carry-in stop age, carry-in holding age και carry-in exits. Αυτό αυξάνει σημαντικά το reporting complexity και θολώνει το audit. fileciteturn12file0

### Required cleanup milestone behavior

Πριν το validation clock:

1. Εκτελείται **operator-approved risk-reducing cleanup** για AAPL/MSFT/XLK.  
2. Μετά από κάθε exit, γίνεται verification ότι δεν υπάρχει residual position quantity.  
3. Ακυρώνονται ή καθαρίζονται τα πλέον orphaned protective stops.  
4. Εκτελείται full reconciliation μέχρι να επιστρέψει `zero positions / zero open orders / clean reconciliation`.  
5. Δημιουργείται **validation baseline packet** με broker equity, zero-position baseline, config/spec hashes, carry-in policy = `none`, validation start timestamp.  
6. Το frozen clock αρχίζει **την επόμενη market session**, όχι την ίδια μέρα του cleanup. fileciteturn12file2 fileciteturn11file1

## Execution and stop policy audit

Η execution path χρειάζεται tightening, όχι redesign.

**ExecutionIntent requirement:** keep unchanged. Κάθε submit πρέπει να περνά από valid decision → passed risk check → clean reconciliation → ExecutionIntent → broker submit. fileciteturn11file0

**Idempotency:** keep the current deterministic client-order root, αλλά πρόσθεσε μία frozen rule: **σε timeout ή ambiguous submit δεν γίνεται resubmit μέχρι να ολοκληρωθεί lookup by `client_order_id` και broker reconciliation**. Η current Alpaca documentation είναι σαφής ότι ένα timed-out order μπορεί ήδη να έχει σταλεί στην αγορά και να μη γίνει blind resend. fileciteturn11file0 citeturn6view5

**Order role classification:** freeze explicit roles: `entry`, `protective_stop`, `strategy_exit`, `cleanup`, `incident_repair`, `cancel`, `noop`. Το reporting και το reconciliation πρέπει να τα βλέπουν ως first-class fields. fileciteturn12file0

**Paper endpoint proof / live endpoint rejection:** keep unchanged. Η evidence βάση το έχει ήδη αποδείξει ως policy boundary. fileciteturn12file2 fileciteturn11file0

**Protective-stop verification:** keep stream-first / REST-fallback verification, με 5s warning, 30s critical pause-new-risk, 60s flatten-if-safe recommendation. Αυτό είναι σωστό και δεν πρέπει να χαλαρώσει. fileciteturn10file0 fileciteturn10file2

**Partial fills:** keep the rule that only filled quantity gets protected, unfilled remainder survives only μέχρι το expiry/cancel point, και ποτέ δεν αφήνεται filled quantity unprotected. fileciteturn10file0

**No-fill behavior:** παγώνει ως deterministic: cancel at 11:00 ET, mark `no_fill`, no same-day re-entry on the same symbol. fileciteturn10file0

**Ambiguous broker state:** πρέπει να μείνει hard blocker για new risk, με incident, reconciliation και manual review if unresolved. fileciteturn11file1

### Recommended stop policy for the first 8-week validation

- **Protective stop order type:** plain broker stop, όχι stop-limit, για primary downside protection.  
  Η ίδια η urlAlpacaturn6view0 γράφει ότι το stop order γίνεται market order όταν εκλεγεί και ότι το stop-limit μπορεί να παραμείνει ενεργό χωρίς execution σε gap. Η guidance της entity["organization","FINRA","us self regulator"] και του entity["organization","Investor.gov","sec investor portal"] λέει επίσης ότι τα stop-limit orders προστατεύουν την τιμή αλλά ενδέχεται να μην εκτελεστούν σε γρήγορη αγορά. Για safety-first validation, η προτεραιότητα πρέπει να είναι η **εκτέλεση**, όχι η price perfection. citeturn6view0turn8view0turn8view2
- **Stop pricing basis:** deterministic ATR-based μόνο, με initial stop στο `entry - 2.0 * ATR14`. Όχι support/resistance discretion, όχι percentage overrides. fileciteturn10file0
- **Stop persistence:** broker-supported persistent stop for overnight carry. Αν persistent stop δεν επιβεβαιώνεται καθαρά από τον broker path, τότε no overnight carry. fileciteturn11file0
- **Multiple stops per symbol:** forbidden at validation start unless scale-in stage gate has passed and broker proof exists. fileciteturn12file0
- **Stop rejected / stop unconfirmed:** critical incident, pause new risk, immediate review path. fileciteturn10file2
- **Stop filled:** mark as risk-reducing exit, reconcile, and forbid same-day re-entry on the same symbol. fileciteturn11file1

## Exit policy audit

Το πρώτο 8-week validation **δεν** πρέπει να είναι stop-only.

Το ίδιο το spec έχει ήδη deterministic exit helpers, και το validation plan λέει ότι αυτά είναι fixture-tested. Αν τρέξει stop-only, το forward window δεν θα δοκιμάσει την πραγματική intended strategy αλλά μια αλλοιωμένη stop-only approximation. fileciteturn10file0 fileciteturn12file1

### Exact recommendation

Active from day 1:

- **Protective stop** as catastrophe / downside protection.
- **Fail-fast exit** if η θέση χάσει το breakout level μέσα στα πρώτα 5 bars.
- **Technical exit** after 2 consecutive closes below EMA10.
- **Time stop** after 20 trading days if unrealized PnL < +0.5R.

Inactive in the first frozen window:

- **App-level trailing stop**.  
  Δεν την απορρίπτω συνολικά, αλλά η trailing path σημαίνει repeat cancel/replace behavior, άρα μεγαλώνει materially η operatorless execution complexity. Για το πρώτο frozen operational window, προτιμάται να μείνει off. fileciteturn10file0

Not recommended for this window:

- end-of-week forced exit,
- regime-flip emergency flattening outside the existing kill-switch/stop/technical-exit logic.

Η regime turn σε `RISK_OFF` πρέπει να συνεχίσει να **μπλοκάρει νέα entries**, όχι να εισαγάγει νέο forced-liquidation engine στο πρώτο freeze. fileciteturn10file0

## Scheduling/orchestration audit

Η σημερινή schedule scaffold θέλει frozen execution schedule, όχι άλλη θεωρία. Το v0.4 already defines durable schedules for data refresh, EOD signals, shortlist AI research, trade plan snapshot and sanity reconciliation, αλλά το frozen validation χρειάζεται και explicit BOD/execution workflow cadence. fileciteturn10file0

### Concrete 8-week schedule

Όλες οι ώρες σε **America/New_York**.

1. **08:25 ET — DailyDataRefresh**  
   Corporate actions, adjusted OHLCV, earnings calendar, provider health, raw payload hashes. fileciteturn10file0
2. **09:20 ET — BOD reconciliation / preflight**  
   Broker mode, account reachability, open orders, positions, data freshness, kill switch, incident count. fileciteturn10file0 fileciteturn11file1
3. **09:35 ET — Validation execution plan build**  
   Prior-day exits first, then new-entry shortlist under current caps.
4. **09:45–10:30 ET — Entry/exit execution window**  
   DAY limit or marketable-limit orders only, no extended-hours entries. Alpaca day orders είναι by default regular-hours only unless marked extended-hours. fileciteturn10file0 citeturn6view6
5. **11:00 ET — Unfilled-entry cancel checkpoint**  
   Cancel remainder, verify stop coverage, close open execution workflows cleanly. fileciteturn10file0
6. **Every 30 seconds while orders are open — active reconciliation**  
   Stream primary, REST fallback. fileciteturn10file0
7. **16:10 ET — EOD signal generation**  
   Final daily bars, feature recompute, regime, deterministic shortlist. fileciteturn10file0
8. **16:30 ET — AI/news shortlist research**  
   Blocking-only / risk-only mode. fileciteturn10file0
9. **17:00 ET — Trade plan snapshot**  
   Freeze next-session plan and decision evidence hashes. fileciteturn10file0
10. **20:00 ET — EOD reconciliation**  
    Account/orders/positions/fills/stop coverage. fileciteturn10file0
11. **20:10 ET — Daily report**  
12. **Friday 20:20 ET — Weekly report**

### Market-open / market-closed / holiday policy

Η official entity["organization","NYSE","us securities exchange"] calendar δίνει core session 9:30 a.m.–4:00 p.m. ET, με συγκεκριμένες holidays και early-close sessions. Για το πρώτο frozen window:  
- no new entries pre-market,  
- no new entries post-market,  
- no new entries on weekends or official exchange holidays,  
- **skip all early-close days for new entries**. citeturn7view0

### Dashboard and alerts

- **Dashboard updates:** event-driven plus 5-minute health heartbeat during market hours.  
- **Critical alerts:** immediate.  
- **Warning alerts:** batched into daily report unless affecting active execution.  
- **Validation-clock status:** must be visible on dashboard after every run. fileciteturn10file2

## AI/news audit

Η recommendation είναι: **AI/news enabled, but advisory-negative-only**.

Το σύστημα ήδη ορίζει ότι το AI είναι bounded shortlist analysis, structured-output only, with neutral fallback on error and no broker/API authority. Αυτά πρέπει να μείνουν αυτούσια. fileciteturn10file0 fileciteturn11file1

### Frozen validation behavior

- **Enabled:** yes.  
- **Advisory only:** yes.  
- **May hard-block:** yes, αλλά μόνο για high-severity adverse-risk με confidence ≥ 0.70. fileciteturn10file0
- **Neutral fallback:** yes, always on provider failure / invalid schema / no-news. fileciteturn10file0
- **Affect position sizing:** only neutral or reduce; never increase. fileciteturn11file1
- **Affect candidate ranking positively:** no, όχι στο πρώτο frozen window.
- **Block new trades:** yes, μόνο μέσα από explicit hard-block policy.
- **Affect scale-in:** no.
- **Broker write authority:** never. fileciteturn11file0

### Recommended budgets

- max AI runs/day: **2**
- max AI calls/day: **10**
- max symbols/run: **5**
- max articles/symbol: **3**
- provider failure outcome: **neutral + outage evidence + continue deterministic path if other safety-critical data exist**

Το v0.4 έχει μεγαλύτερα budgets, αλλά για το πρώτο validation δεν υπάρχει operational benefit στο να είναι υψηλότερα. Η μείωση βοηθά reproducibility και cost discipline. fileciteturn10file0

## Data/reconciliation/evidence audit

### Data quality gates

Πριν από το freeze χρειάζονται οι εξής hard gates:

- **Primary signal data not IEX-only.** Το spec το απαιτεί και το official Alpaca data documentation εξηγεί ότι το default real-time equities feed στο Basic plan είναι μόνο IEX. fileciteturn10file0 citeturn6view4
- **Adjusted OHLCV complete** for the latest completed session before EODSignalWorkflow. fileciteturn10file0
- **Quote freshness at execution** ≤ 5 seconds for order placement; αλλιώς pause new risk.  
- **Earnings calendar completeness**: `unknown => block entries`. fileciteturn12file1
- **Corporate-action ambiguity => block entries**. fileciteturn10file0
- **Raw provider payload hashing** for every market/news payload and deterministic feature recomputation hash. fileciteturn12file1
- **Universe availability rule**: αν δεν υπάρχει data για held/open-position symbol, pause new risk and investigate; για non-held candidate, symbol skip + warning.

### Missing reconciliation checks to add

Τα σημερινά checks είναι καλά, αλλά λείπουν τέσσερα frozen-critical cases:

1. **Oversubscribed exit quantity / stop-reserved quantity** ανά symbol.  
2. **Orphan protective stop** χωρίς αντίστοιχη broker position.  
3. **Fill-mapping completeness** by broker order ID when `client_order_id` is absent, για να κλειδώσει μόνιμα το lesson του M35C/M35D. fileciteturn10file2
4. **Stream-vs-REST divergence timer** ως first-class incident input.  

Επίσης χρειάζεται explicit check ότι `protected_quantity_sum == open_position_quantity` για scale-in-enabled periods και όχι μόνο `>=`, ώστε να εντοπίζεται oversubscription ή stale extra stop. fileciteturn12file0

### Required evidence fields

Το frozen validation evidence schema πρέπει να περιλαμβάνει τουλάχιστον:

- spec version,
- git commit / build artifact version,
- config hash,
- universe hash,
- schedule hash,
- strategy policy hash,
- risk policy hash,
- execution policy hash,
- reconciliation policy hash,
- AI/news policy hash,
- prompt version, schema version, model version,
- data provider set and provider hash summary,
- broker baseline,
- position baseline,
- open-order baseline,
- carry-in policy,
- validation start timestamp,
- per-run decision set hash,
- per-run execution-intent set,
- per-run order/fill/stop verification evidence,
- reconciliation snapshot hashes,
- incident records,
- manual control actions,
- daily/weekly report artifact hashes,
- validation-clock valid/invalid state.

Αυτό δεν είναι fully explicit στο v0.4, άρα πρέπει να μπει στο v0.5 freeze packet. fileciteturn10file0 fileciteturn12file1

## Reporting/dashboard audit

Το reporting πρέπει να γίνει **validation-native**, όχι απλώς extension των smoke reports.

### Daily report

Required daily sections:

- workflow summary,
- data freshness summary,
- deterministic candidates and rejection reasons,
- AI summary and schema validity,
- execution intents,
- orders/fills/open orders,
- open/closed positions,
- protective-stop status and placement timing,
- reconciliation status,
- incidents,
- kill-switch state,
- exposure / cash / loss-limit status,
- slippage and fill diagnostics,
- dashboard/control-plane health,
- validation-clock status. fileciteturn10file2

### Weekly report

Required weekly sections:

- closed trades summary,
- open positions,
- stop-placement success rate,
- mismatch rate,
- AI schema-validity rate,
- incident distribution,
- failed checks,
- stale data/provider outage summary,
- control-plane audit summary,
- unresolved problems,
- whether the frozen clock remains valid. fileciteturn10file2

### Trade-by-trade schema

Κάθε trade row πρέπει να έχει:

- symbol,
- entry role,
- exit role,
- carry-in flag,
- validation-start flag,
- decision ID,
- execution-intent ID,
- initial/added quantity,
- initial/added stop,
- realized PnL,
- realized R,
- MAE/MFE if available,
- stop verification latency,
- strategy exit reason,
- incident linkage.

### Carry-in vs validation separation

Ακόμη και αν γίνει flat-start, το schema πρέπει να κρατήσει fields για carry-in separation. Στο frozen window απλώς θα είναι `carry_in=false` everywhere.

### Scale-in metrics

Αν ενεργοποιηθεί αργότερα στο ίδιο window, το weekly report πρέπει να δείχνει ξεχωριστά:

- initial-entry count,
- scale-in-entry count,
- scale-in acceptance rate,
- scale-in incident count,
- protected quantity after add,
- PnL attribution with and without add-on. fileciteturn12file0

## 8-week validation acceptance criteria

Πρέπει να διαχωριστούν τα **operational pass/fail** από τα **longer-horizon strategy / Level-4 gates**.

### Operational pass for the first frozen window

- **Minimum runtime:** 8 συνεχόμενες ημερολογιακές εβδομάδες μετά από flat-start baseline.
- **Minimum sessions:** όλες οι intended regular-session runs του παραθύρου, με επιτρεπτά skips μόνο για official holidays και την προτεινόμενη early-close skip policy.
- **Maximum unresolved incidents:** 0 critical unresolved incidents at any day close.
- **Maximum reconciliation mismatches:** 0 critical unresolved mismatches; any warning mismatch must close by next BOD.
- **Protective-stop requirement:** 100% of filled quantity protected; 0 missing-stop incidents.
- **Stop verification timing:** 100% verified within 60 seconds; any >30 seconds is critical and pauses new risk for review.
- **Duplicate-order incidents:** 0.
- **Allowed manual interventions:** only kill switch, pause/resume-after-review, stop repair, risk-reducing cleanup, schedule disable, incident acknowledgement.
- **Operational uptime:** ≥ 99% for required workers/scheduler during execution windows.
- **Schedule reliability:** ≥ 98% of intended runs complete or explicitly no-trade-close cleanly.
- **Evidence completeness:** 100% daily and weekly report generation; no missing baseline or incident packet.
- **Drawdown:** soft review at 4%; hard fail/restart if validation drawdown exceeds 6%.

### Strategy evidence for the first frozen window

- If **closed validation-start trades < 15**, το strategy αποτέλεσμα είναι **inconclusive**, όχι automatic fail.
- If **closed trades ≥ 15**, provisional strategy success may be recorded only if:
  - Profit Factor ≥ 0.90,
  - expectancy ≥ 0R,
  - no single safety breach invalidated the clock,
  - performance is not catastrophically worse than the exposure-adjusted SPY reference.

### What remains stricter and unchanged for any later Level 4 discussion

Το current validation/Level-4 scaffold παραμένει αυστηρότερο: at least 8 weeks frozen paper **and** at least 30 closed trades or 2 quarters of forward paper, PF ≥ 1.10, Sharpe ≥ 0.75 or Sortino ≥ 1.00, max drawdown ≤ 10%, 100% stop placement success, broker/internal mismatch rate < 0.1%, AI valid-schema rate ≥ 99%, zero Sev-1 control incidents in the last 20 sessions. Αυτά **δεν** τα χαλαρώνω. fileciteturn12file1

## Freeze scope

Στο validation start πρέπει να παγώσουν όλα τα παρακάτω:

- spec version,
- all config files,
- active strategy parameters,
- active regime parameters,
- active risk parameters,
- active execution parameters,
- universe,
- schedule,
- AI/news prompts,
- AI/news schemas,
- AI/news model identifiers,
- execution role taxonomy,
- reconciliation mismatch taxonomy,
- reporting schema,
- dashboard validation views,
- incident severity rules,
- operator intervention rules,
- carry-in policy,
- data provider list,
- market calendar source,
- acceptance criteria,
- benchmark definitions,
- alert cadence,
- code commit/build artifact.

Οποιαδήποτε material αλλαγή σε αυτά κατά τη διάρκεια του 8-week window πρέπει να **ακυρώνει ή επανεκκινεί** το validation clock. fileciteturn10file2

## Operator intervention policy

### Allowed

- activate kill switch,
- pause new risk,
- disable schedule,
- approve restart after review,
- run forced reconciliation,
- run forced report generation,
- perform documented risk-reducing cleanup,
- perform documented stop repair when policy explicitly allows it,
- acknowledge incident,
- annotate evidence.

### Forbidden

- manual trade selection,
- manual signal override,
- manual parameter optimization,
- ad hoc universe change,
- AI prompt/schema/model change mid-window,
- broker writes outside approved workflows,
- manual re-entry after stop,
- manual scale-in authorization,
- deletion or silent editing of ledger evidence.

No parameter optimization πρέπει να επιτρέπεται unless the validation restarts from a new baseline. fileciteturn11file1 fileciteturn10file2

## Short-side interaction note

Με βάση μόνο αυτό το general audit, η προσθήκη shorts **πριν** από το πρώτο frozen validation είναι πιθανότερο να προσθέσει υπερβολική πολυπλοκότητα παρά καθαρή ερευνητική αξία.

Ο λόγος δεν είναι ότι τα shorts είναι “κακή ιδέα” στρατηγικά, αλλά ότι ανοίγουν νέα state spaces: short borrow/margin behavior, asymmetric stop logic, different gap/slippage behavior, intraday margin rule interactions, διαφορετική incident taxonomy και διαφορετικό reporting attribution. Ακόμη και η κανονιστική εικόνα για active margin trading έχει αλλάξει το 2026 μέσω των νέων intraday margin standards της entity["organization","FINRA","us self regulator"], ενώ η τρέχουσα documentation της urlAlpacaturn6view2 ακόμη αναφέρει PDT/DTMC protections και στο paper environment, άρα το operational behavior during transition δεν πρέπει να θεωρηθεί “αόρατο” ή trivial. citeturn11view0turn11view1turn9search1

Η σωστή στάση είναι: **μην μπουν τα shorts στο M45 frozen long-side window**, εκτός αν το separate short-side research προτείνει ρητά bounded, independently staged shadow mode με default `off`.

## M44 implementation plan

Ο M44 πρέπει να είναι **freeze-readiness milestone**, όχι feature-sprawl milestone.

1. **Create v0.5 frozen validation spec**  
   - flat-start policy,  
   - AI negative-only policy,  
   - validation-specific risk caps,  
   - active exit set,  
   - frozen schedule,  
   - evidence schema,  
   - acceptance criteria.

2. **Flat-start cleanup and baseline**  
   - operator-approved flatten of AAPL/MSFT/XLK,  
   - verify zero positions / zero open orders,  
   - clean reconciliation baseline packet.

3. **Execution hardening**  
   - no blind retry after timeout,  
   - required lookup by client order ID,  
   - explicit order-role taxonomy,  
   - same-day re-entry blocker,  
   - unfilled-entry 11:00 cancel rule harden.

4. **Stop-policy freeze**  
   - plain protective stop as primary protective exit,  
   - trailing disabled for frozen window,  
   - stop verification SLA evidence.

5. **Scale-in staging**  
   - keep implementation present,  
   - set frozen-start scale-in = disabled,  
   - add stage-gate checks and broker-capability proof test,  
   - if short-side package also wants pyramiding/averaging behavior, keep it separate and off.

6. **Data and reconciliation gates**  
   - non-IEX-only primary signal requirement,  
   - earnings/corporate-action completeness gate,  
   - oversubscribed-exit/orphan-stop checks,  
   - stream-vs-REST divergence incident.

7. **Reporting and dashboard freeze**  
   - baseline packet,  
   - per-run packet,  
   - incident packet,  
   - daily/weekly reports,  
   - validation-clock visible state.

8. **M45 go/no-go checklist**  
   - all hashes frozen,  
   - all gates pass,  
   - paper mode proven, live disabled proven,  
   - schedule dry-smoke clean,  
   - no unresolved incidents,  
   - operator approval recorded.

## M45 readiness judgment

**Ναι — το M45 μπορεί να είναι το 8-week validation start**, αν και μόνο αν ο M44 παραδώσει όλα τα παρακάτω επιτυχώς:

- v0.5 freeze spec approved,
- flat broker state baseline achieved,
- validation-specific schedule frozen,
- AI positive scoring removed for the first window,
- scale-in disabled at T0 or broker-proven and still stage-gated,
- non-IEX-only primary signal data gate satisfied,
- evidence/reporting schema frozen,
- all unresolved critical incidents = 0,
- final go/no-go checklist signed.

Αν κάποιο από αυτά αποτύχει, δεν χρειάζεται “άλλη proving phase”, αλλά χρειάζεται **ένα readiness-fix milestone πριν το validation start**. Η απουσία αυτών των πραγμάτων θα έκανε το M45 premature, όχι conceptually impossible. fileciteturn12file0 fileciteturn12file1

## Risks and open questions

- **Scale-in / additive stop broker semantics:** το μεγαλύτερο μη λυμένο ρίσκο. Η M43 policy είναι σωστή, αλλά η πραγματική συμβατότητα με Alpaca paper για multiple independent protective stops πρέπει να αποδειχθεί. citeturn9search0
- **Broker-side intraday margin / PDT transition behavior:** η κανονιστική βάση στην αγορά άλλαξε το 2026, αλλά η current Alpaca documentation δεν είναι πλήρως ευθυγραμμισμένη στην ορολογία. Το validation πρέπει να μη βασιστεί σε assumptions περί intraday churn permissions. citeturn11view0turn11view1turn9search1
- **Primary signal data source readiness:** αν το frozen window βασιστεί τελικά μόνο σε IEX-quality real-time feed για signal/execution-quality logic, το data gate δεν έχει πραγματικά περάσει. citeturn6view4
- **Production paper operations wiring:** το validation scaffold δηλώνει ακόμη ότι production managed DB activity wiring, production operational dashboard/backend integration και actual paper operations evidence δεν έχουν ολοκληρωθεί ως frozen-paper evidence. Ο M44 πρέπει να τα κλείσει operationally, όχι μόνο να τα αφήσει documented. fileciteturn12file1
- **Statistical sufficiency in 8 weeks:** με τόσο μικρό universe και conservative caps, το πρώτο 8-week window μπορεί να δώσει operationally valid αλλά statistically inconclusive strategy evidence. Αυτό δεν είναι failure, αλλά πρέπει να ειπωθεί καθαρά στο post-window judgment. fileciteturn12file1