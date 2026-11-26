import { EXCLUSION, fmt, meta } from "@/lib/data";

export const metadata = { title: "Methods · Priced In" };

export default function Methods() {
  const m = meta();
  const a = m.audit;
  return (
    <div className="prose page pagehead">
      <div className="kicker">Methods</div>
      <h1>How Priced In <em>measures it</em></h1>
      <p className="lede">
        An event study around jumps in contract odds. The method, thresholds and contract list were
        committed before any stock data was loaded. The held-out run is blocked in code until the method is frozen.
      </p>

      <h2>Events</h2>
      <p>
        <strong>FOMC days.</strong> The event time is 2:00pm ET. Kalshi's current-meeting contract stops trading 1–5
        minutes before the statement, so Priced In uses the <em>next</em> meeting's contract. It keeps trading through
        the statement and the press conference, with a 1–2¢ spread in 2025–26. The probability is the sum of the
        next meeting's cut outcomes.
      </p>
      <p>
        <strong>Unscheduled jumps.</strong> A contract's midquote moves at least the {m.jump.quantile * 100}th
        percentile of its own 5-minute changes, and never less than {m.jump.min_abs_pp} points. The move's start is
        the event time. These thresholds come from contract data only.
      </p>
      <p>
        <strong>Market hours.</strong> The window from {m.window.pre_min} minutes before to {m.window.post_min}{" "}
        minutes after must fall inside 9:30–4:00 ET. Contracts trade around the clock, so many jumps happen
        overnight or on weekends. Those are counted and listed, not tested. CPI is released at 8:30am, so it can't
        be tested at minute resolution.
      </p>

      <h2>Quality filter</h2>
      <p>
        Prices are midquotes, never last trades. A contract that hasn't traded keeps a stale last price, and
        that alone would make the liquid stock look like it leads. An event is used only if, in its window, the
        median spread is at most {m.quality.max_median_spread_pp}¢, both sides of the book are quoted in at least{" "}
        {m.quality.min_two_sided_share * 100}% of minutes, and at least {m.quality.min_active_minutes} minutes show activity.
      </p>
      {a && (
        <div className="panel tablewrap" style={{ padding: 0, margin: "16px 0" }}>
          <table>
            <thead><tr><th>Outcome</th><th className="r">Events</th></tr></thead>
            <tbody>
              {Object.entries(a.exclusions).sort((x, y) => y[1] - x[1]).map(([k, v]) => (
                <tr key={k}><td>{EXCLUSION[k] ?? k}</td><td className="r num">{v}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h2>Event betas</h2>
      <p>
        Pooled regression with event fixed effects over the one-minute returns in each window. It includes the
        contract's move at every lag from 5 minutes before to 5 minutes after, and the event beta is their sum
        (a Dimson beta), so a response that lands a minute early or late still counts. The controls are the
        market (SPY) and, for single stocks, a sector ETF:
      </p>
      <pre>r(i,t) = α(i,e) + Σk βk·Δp(t−k) + γ·r(SPY,t) + δ·r(sector,t) + ε      event beta = Σk βk</pre>
      <p>
        β is reported as % per 10 points, with a 95% interval from 2,000 bootstrap resamples of whole events. A raw beta without controls is shown alongside.
      </p>

      <h2>Who moves first</h2>
      <p>
        A distributed-lag regression of raw returns on Δp from 5 minutes before to 5 minutes after (raw because
        controls would absorb the macro timing being measured). The statistic is the sum of the coefficients where
        the contract moved first minus the sum where stocks moved first. An interval above zero means the contract
        moves first; below zero means stocks do. Otherwise it's the same minute, which is a result, not a failure.
        A robustness run keeps only events with at least {m.quality.robustness_active_share * 100}% active minutes.
      </p>

      <h2>When a result holds up</h2>
      <ul>
        <li><strong>Many tests:</strong> Benjamini–Hochberg q &lt; {String(m.validation.fdr_q)} across every event–asset pair.</li>
        <li><strong>Time-shift placebo:</strong> the same contract moves paired with the stock's returns at the same clock time on a random day 5–60 trading days away.</li>
        <li><strong>Shuffled pairs:</strong> contract moves from one event paired with stock returns from another event of the same kind.</li>
        <li><strong>Held out:</strong> the most recent {Number(m.validation.holdout_share) * 100}% of events stay sealed until the method is frozen, then are run once and published whatever they show.</li>
      </ul>

      <h2>Limits</h2>
      <ul>
        <li>Co-movement is not causation: the same news reaches both markets.</li>
        <li>Unscheduled events are defined by contract jumps, so they favour news the contract reacted to.</li>
        <li>Minute data can't separate effects faster than a minute.</li>
        <li>Fed funds futures (CME FedWatch) have no free intraday history, so that comparison isn't part of the minute-level study.</li>
      </ul>
      <p className="small muted">Data generated {new Date(m.generated_at).toUTCString()}. Training events: {fmt(a?.totals.train ?? 0, 0)}.</p>
    </div>
  );
}
