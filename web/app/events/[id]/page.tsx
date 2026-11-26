import Link from "next/link";
import { notFound } from "next/navigation";
import { Forest, LagProfile } from "@/components/charts";
import EventStudy from "@/components/EventStudy";
import { EXCLUSION, family, fmt, fmtP, meta, VERDICT, type Beta, type LeadLag } from "@/lib/data";

export function generateStaticParams() {
  return meta().families.map((f) => ({ id: f.id }));
}

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const f = meta().families.find((x) => x.id === id);
  return { title: f ? `${f.label} · Priced In` : "Priced In" };
}

const et = (iso: string) =>
  new Date(iso).toLocaleString("en-US", { timeZone: "America/New_York", month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" });

function BetaTable({ rows }: { rows: Beta[] }) {
  return (
    <div className="tablewrap">
      <table>
        <thead>
          <tr>
            <th>Asset</th><th className="r">Per 10 pts</th><th className="r">95% CI</th><th className="r">Raw</th>
            <th className="r">Placebo p</th><th className="r">Shuffle p</th><th className="r">q</th><th className="r">Events</th><th>Holds up</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((b) => (
            <tr key={b.asset}>
              <td className="num">{b.asset}<div className="small muted">{b.controls.length ? `vs ${b.controls.join(", ")}` : "no controls"}</div></td>
              <td className="r num">{fmt(b.beta_10pp_pct, 3, true)}%</td>
              <td className="r num muted">[{fmt(b.ci_lo, 3, true)}, {fmt(b.ci_hi, 3, true)}]</td>
              <td className="r num muted">{fmt(b.raw_beta_10pp_pct, 3, true)}%</td>
              <td className="r num">{fmtP(b.placebo_p)}</td>
              <td className="r num">{fmtP(b.shuffle_p)}</td>
              <td className="r num">{fmtP(b.q_value)}</td>
              <td className="r num">{b.n_events}</td>
              <td>{b.survives ? <span className="pill good">yes</span> : <span className="pill">no</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function LeadTable({ rows }: { rows: LeadLag[] }) {
  return (
    <div className="tablewrap">
      <table>
        <thead><tr><th>Asset</th><th>Verdict</th><th className="r">Lead − lag</th><th className="r">95% CI</th><th className="r">q</th><th>High-activity events only</th></tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.asset}>
              <td className="num">{r.asset}</td>
              <td>{VERDICT[r.verdict]}</td>
              <td className="r num">{fmt(r.lead_minus_lag_10pp_pct, 3, true)}</td>
              <td className="r num muted">[{fmt(r.lead_minus_lag_ci[0], 3, true)}, {fmt(r.lead_minus_lag_ci[1], 3, true)}]</td>
              <td className="r num">{fmtP(r.q_value)}</td>
              <td className="small">{r.robust_high_activity ? `${VERDICT[r.robust_high_activity.verdict]} (${r.robust_high_activity.n_events} events)` : "too few events"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default async function EventPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const m = meta();
  const f = m.families.find((x) => x.id === id);
  const d = family(id);
  if (!f || !d) notFound();
  const a = m.audit?.families.find((x) => x.family === id);
  const betas = d.betas ?? [];
  const ll = d.leadlag ?? [];
  const lead = [...ll].sort((x, y) => Math.abs(y.total_10pp_pct) - Math.abs(x.total_10pp_pct))[0];
  const usable = d.events.filter((e) => e.usable);

  return (
    <div className="page">
      <div className="pagehead">
        <div className="kicker"><Link href="/#events">Events</Link> / {f.type}</div>
        <h1>{f.label}</h1>
        <p className="lede">
          {f.question ?? `How do stocks move when the odds on "${f.label}" jump?`}{" "}
          <span className="muted">Contract: <span className="num">{f.contract}</span>.</span>
        </p>
      </div>
      {f.rule_clarity === "ambiguous" && (
        <div className="banner"><strong>Resolution rules flagged as ambiguous.</strong> {f.rule_note}</div>
      )}

      {a && (
        <div className="grid g4">
          <div className="panel stat"><div className="v">{a.events}</div><div className="l">{f.kind === "fomc" ? "meetings" : "jumps detected"}</div></div>
          <div className="panel stat"><div className="v">{a.in_session}</div><div className="l">inside market hours</div></div>
          <div className="panel stat"><div className="v">{a.usable}</div><div className="l">usable ({a.train} train / {a.holdout} sealed)</div></div>
          <div className="panel stat"><div className="v">{a.median_spread_pp == null ? "–" : `${fmt(a.median_spread_pp, 1)}¢`}</div><div className="l">median spread, usable events</div></div>
        </div>
      )}

      {betas.length > 0 ? (
        <>
          <h2>Event betas</h2>
          <p className="muted small">Return per 10-point rise in the odds, inside [−{m.window.pre_min}, +{m.window.post_min}] minutes, after market and sector moves. Filled dots hold up under every check.</p>
          <div className="panel">
            <Forest unit="% per 10 pts" rows={betas.map((b) => ({ label: b.asset, sub: `${b.n_events} events`, est: b.beta_10pp_pct, lo: b.ci_lo, hi: b.ci_hi, strong: b.survives }))} />
          </div>
          <div className="panel" style={{ marginTop: 16, padding: 0 }}><BetaTable rows={betas} /></div>

          <h2>Who moves first</h2>
          {lead && (
            <>
              <p className="muted small">
                Coefficient on the contract's move k minutes earlier, for <span className="num">{lead.asset}</span> (the asset with the clearest response).
                Bars right of zero mean the contract moved first.
              </p>
              <div className="panel"><LagProfile lags={lead.lags} /></div>
            </>
          )}
          <div className="panel" style={{ marginTop: 16, padding: 0 }}><LeadTable rows={ll} /></div>
          <p className="small muted">A direction is called only when the interval excludes zero and q &lt; 0.05 across all lead-lag tests; otherwise it reads as no clear lead.</p>

          {d.paths && Object.keys(d.paths).length > 0 && (
            <>
              <h2>Every event on one clock</h2>
              <div className="panel">
                <EventStudy events={usable.filter((e) => e.split === "train")} stock={d.paths} pre={m.window.pre_min} post={m.window.post_min} />
              </div>
            </>
          )}

          {d.holdout_betas && d.holdout_betas.length > 0 && (
            <>
              <h2>Held-out check</h2>
              <p className="muted small">The same estimates including the sealed, most recent 30% of events, run once after the method was frozen.</p>
              <div className="panel" style={{ padding: 0 }}><BetaTable rows={d.holdout_betas} /></div>
            </>
          )}
        </>
      ) : (
        <div className="banner" style={{ marginTop: 28 }}>Stock results for this event appear once minute bars are loaded. The contract-side events are below.</div>
      )}

      <h2>Events</h2>
      <div className="panel tablewrap" style={{ padding: 0 }}>
        <table>
          <thead><tr><th>When (ET)</th><th>Status</th><th className="r">Odds at start</th><th className="r">Odds change</th><th className="r">Spread</th><th className="r">Active min.</th></tr></thead>
          <tbody>
            {[...d.events].reverse().map((e) => (
              <tr key={e.event_id}>
                <td className="num small" style={{ whiteSpace: "nowrap" }}>{et(e.t0)}</td>
                <td className="small">
                  {e.usable ? <span className={`pill ${e.split === "holdout" ? "warn" : "good"}`}>{e.split === "holdout" ? "sealed" : "used"}</span>
                    : <span className="muted">{EXCLUSION[e.exclusion ?? ""] ?? e.exclusion}</span>}
                </td>
                <td className="r num">{e.p_start == null ? "–" : `${fmt(e.p_start * 100, 0)}%`}</td>
                <td className="r num">{fmt(e.dp_window_pp, 1, true)}</td>
                <td className="r num">{e.median_spread_pp == null ? "–" : `${fmt(e.median_spread_pp, 1)}¢`}</td>
                <td className="r num">{e.active_share == null ? "–" : `${Math.round(e.active_share * 100)}%`}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
