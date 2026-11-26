# Priced In: pre-registration

Committed before any stock return was loaded. Numeric parameters live in
[`config/study.yaml`](config/study.yaml); the contract list in [`config/universe.yaml`](config/universe.yaml).
`pricedin freeze` hashes all three files plus the analysis code; the held-out run refuses to start if
any of them changed after the freeze.

## Questions

1. **Event betas.** For each contract family and asset, how much does the asset move per 10-point
   change in the contract's probability, inside event windows?
2. **Who moves first.** Within those windows, does the contract reprice before the asset, after it,
   or in the same minute?

Results are described as co-movement ("moves with the odds"), never as causal effects: the same news
reaches both markets.

## Events

**Scheduled: FOMC.** t0 = 2:00pm ET on each decision day since Kalshi listed Fed contracts (May 2023).
The current-meeting contract stops trading 1–5 minutes before 2:00pm (verified on the Jan 29, 2025 and
Oct 28, 2026 meetings), so the probability series is **P(cut at the next meeting)**: the sum of the
midquotes of that meeting's cut outcomes. It trades through the statement and press conference.

**Not tested at minute resolution: CPI.** Releases are at 8:30am ET, before the stock session.

**Unscheduled.** A contract's midquote moves at least the threshold within 5 minutes. The threshold is
the 99.5th percentile of that contract's own 5-minute absolute changes over its life, and never below
5 points. t0 is the start of the 5-minute move. Crossings within 120 minutes of a previous one are the
same event. Thresholds come from contract data only.

**Session rule.** The whole window [t0 − 5, t0 + 30] must fall within 9:30–16:00 ET on a weekday.
Events outside it are counted and published, not tested.

## Contracts

Ten families (`config/universe.yaml`), chosen on 2026-11-26 by Kalshi traded volume and economic
relevance before any stock data was pulled: FOMC; Fed-chair nominee (Warsh, Hassett); Powell leaving in
2025; 2025 recession; Supreme Court tariff ruling; Jan 2026 shutdown; 2026 House and Senate control;
Bitcoin above $200k in 2026. Each family names its assets in advance.

## Quality filter (module 3)

An event is usable only if, within the window:

- the median bid–ask spread is at most 5 points (Kalshi);
- both sides of the book are quoted in at least 90% of minutes;
- at least 5 minutes have a candle or print;
- a price exists at every minute.

Two contracts are flagged as having ambiguous resolution rules (recession, tariff ruling). They are
estimated, but the flag is shown next to every result.

## Data alignment

Every series is labelled by minute **end** time in UTC. Kalshi candles are already end-stamped; Alpaca
bars are start-stamped and shifted by one minute. Contract prices are midquotes, never last trades: a
contract that hasn't traded keeps a stale last price, and that alone would make the liquid stock look
like it leads.

## Estimation

**Event beta (primary).** Pooled OLS with event fixed effects over the 35 one-minute returns of each
window, with the contract's move at every lag from −5 to +5 minutes (a Dimson 1979 beta, built for
non-synchronous prices):

r(i,t) = α(i,e) + Σₖ βₖ·Δp(t−k) + γ·r(SPY,t) + δ·r(sector,t) + ε,   event beta = Σₖ βₖ

SPY gets no controls. Single stocks get a sector ETF; ETFs get the market only. A raw beta without
controls is also reported. The 95% interval comes from an event bootstrap (2,000 resamples of whole
events). Betas are reported as % per 10 points.

**Who moves first.** A distributed-lag regression of raw returns on Δp at lags −5…+5 minutes (lag k > 0
means the contract moved first), with no controls, because controls absorb the macro timing being
measured. The statistic is lead minus lag: the sum of the k > 0 coefficients minus the sum of the k < 0
coefficients, signed by the total response, with an event-bootstrap 95% interval.

- Verdict `contract_first` if the interval is above zero.
- Verdict `stocks_first` if it is below zero.
- Otherwise `same_minute_or_unclear`.
- A directional verdict also needs a Benjamini–Hochberg q < 0.05 across all lead-lag tests (bootstrap
  p of the lead-minus-lag statistic).

A robustness re-run keeps only events with at least 50% active minutes.

## Validation

A result **survives** only if all of the following hold:

1. q < 0.05 after Benjamini–Hochberg across every (family, asset) beta;
2. **time-shift placebo** p < 0.05: the same contract moves paired with the asset's returns at the
   same clock time on a random past day 5–60 trading days away (500 draws from a fixed pool of 20 days
   per event);
3. **shuffled pairs** p < 0.05: the contract moves of one event paired with the asset's returns from a
   different event of the same family (500 random derangements).

Both compare the beta's t-statistic, not the raw beta, because event windows are more volatile than
placebo windows.

**Held-out events.** The most recent 30% of usable events in each family are sealed. They are run once,
after `pricedin freeze`, and reported next to the training results whatever they show.

**Decision gate.** At least 40 usable training events across families. If not, the contract set is
widened before any results are produced.

**Planned null.** "Contract and stocks reprice in the same minute" is a finding and will be published as
one.

## Known limitations

- Unscheduled events are defined by contract jumps, so they over-sample news the contract reacted to.
- FedWatch (fed funds futures) has no free intraday history. The comparison runs at daily resolution if
  that data is added (`data/fedwatch.csv`).
- Polymarket's price history has no bid/ask. Polymarket contracts would use print frequency only and are
  not in the launch universe.
- Minute resolution cannot separate effects faster than a minute.

## Change log

| Date | Change | Why | Stock data seen? |
| --- | --- | --- | --- |
| 2026-11-26 | Lead-lag verdicts also need BH q < 0.05 across all (family, asset) lead-lag tests | The pre-registration corrected betas for multiple testing but not lead-lag. Without it, 6 of 30 uncorrected verdicts would be published as findings when ~1.5 are expected by chance. Stricter | Yes, training output |
| 2026-11-26 | Placebo and shuffle tests compare the beta's t-statistic, not the raw beta | The raw-beta placebo was invalid: placebo returns come from calm days, so any beta from volatile event windows beat the null (FOMC: placebo p ≈ 0.002 for assets whose bootstrap CI crossed zero). The t-statistic is scale-free. This makes the test stricter | Yes, partial training output (bars had loaded for only 4 families) |
| 2026-11-26 | Placebo days restricted to dates before today | Bug fix: for recent events the 5–60 trading-day rule picked future dates, which have no data. Found when the first bar load crashed. Mechanical; it changes which pool days are drawn for the most recent events | Partial training output had been printed |
| 2026-11-26 | Event beta: from the same-minute coefficient to the Dimson sum over lags −5…+5 | The synthetic test showed that a stock responding one minute after the contract gets a same-minute beta near zero. Minute-boundary timing and quote staleness make that common in real data | No |
| 2026-11-26 | FOMC composite: spread and two-sidedness now come from the dominant cut outcome, not the worst outcome; the P(cut) sum is undefined when any outcome lacks a price (previously treated as 0) | The first audit excluded 2026 meetings with 1¢ spreads because the "cut > 25bp" tail at 1¢ has no bid. Tail books say nothing about how well the probability that matters is quoted | No |
| 2026-11-26 | Quality filter: replaced "≥ 80% of minutes with a candle" with spread ≤ 5 points, ≥ 90% two-sided, ≥ 5 active minutes; activity moved to a robustness split | Kalshi prints no candle when the book is unchanged, so a two-sided midquote is live, not stale. The 80% rule would have dropped 2025–26 FOMC meetings with 1¢ spreads | No |
