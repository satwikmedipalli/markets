import Link from "next/link";
import Race, { type RaceEvent } from "@/components/Race";
import Story, { type StoryData } from "@/components/Story";
import Ticker, { type Tick } from "@/components/fx/Ticker";
import Spark from "@/components/fx/Spark";
import { allBetas, allLeadLag, family, fmt, meta, type EventRow, type LeadLag } from "@/lib/data";

const SHORT: Record<string, string> = {
  fomc: "FOMC", "fedchair-warsh": "WARSH", "fedchair-hassett": "HASSETT", "powell-leaves-2025": "POWELL",
  "recession-2025": "RECESSION", "scotus-tariffs": "TARIFFS", "shutdown-jan-2026": "SHUTDOWN",
  "house-2026": "HOUSE", "senate-2026": "SENATE", "btc-200k-2026": "BTC200K",
};
const short = (id: string) => SHORT[id] ?? id.toUpperCase();
const day = (iso: string) => new Date(iso).toLocaleDateString("en-US", { timeZone: "America/New_York", month: "short", day: "numeric", year: "numeric" });
const tm = (iso: string) => new Date(iso).toLocaleTimeString("en-US", { timeZone: "America/New_York", hour: "numeric", minute: "2-digit" });
const sym = (contract: string, kind: string) => (kind === "fomc" ? "KXFEDDECISION" : contract.split(" ")[0]);

function verdictOf(r: LeadLag | undefined): RaceEvent["verdict"] {
  if (!r) return { kind: "n", text: "NOT TESTED", detail: "too few events" };
  const q = r.q_value != null ? `q ${r.q_value.toFixed(3)}` : "";
  if (r.verdict === "contract_first") return { kind: "o", text: "KALSHI MOVED FIRST", detail: `${r.n_events} events · ${q}` };
  if (r.verdict === "stocks_first") return { kind: "s", text: `${r.asset} MOVED FIRST`, detail: `${r.n_events} events · ${q}` };
  return { kind: "n", text: "NO CLEAR LEADER", detail: `${r.n_events} events · ${q}` };
}

// Biggest usable training move for a family that has a stock path for `asset`.
function bigEvent(fam: string, asset: string) {
  const d = family(fam);
  const paths = d?.paths?.[asset];
  if (!d || !paths) return null;
  const byId = new Map(paths.map((p) => [p.event_id, p.cum_ret_pct]));
  const ev = d.events.filter((e) => e.usable && e.split === "train" && e.path?.length && byId.has(e.event_id))
    .sort((a, b) => Math.abs(b.dp_window_pp ?? 0) - Math.abs(a.dp_window_pp ?? 0))[0];
  return ev ? { ev, ret: byId.get(ev.event_id)! } : null;
}

function biggest(id: string): EventRow | undefined {
  return family(id)?.events.filter((e) => e.usable && e.path?.length)
    .sort((a, b) => Math.abs(b.dp_window_pp ?? 0) - Math.abs(a.dp_window_pp ?? 0))[0];
}

export default function Home() {
  const m = meta();
  const betas = allBetas();
  const ll = allLeadLag();
  const audit = m.audit;
  const fam = (id: string) => m.families.find((f) => f.id === id)!;
  const pre = m.window.pre_min, post = m.window.post_min;
  const stockPts = (ret: number[]) => [{ m: -pre, v: 0 }, ...ret.map((v, i) => ({ m: -pre + 1 + i, v }))];

  const sig = ll.filter((r) => r.verdict !== "same_minute_or_unclear").sort((a, b) => (a.q_value ?? 1) - (b.q_value ?? 1));
  const survivors = betas.filter((b) => b.survives);
  const closest = [...betas].filter((b) => (b.placebo_p ?? 1) < 0.05 && (b.shuffle_p ?? 1) < 0.05).sort((a, b) => (a.q_value ?? 1) - (b.q_value ?? 1))[0];

  // ---- race: the significant pairs first, then the big scheduled and unscheduled stories
  const wanted: { fam: string; asset: string }[] = [
    ...sig.map((r) => ({ fam: r.family, asset: r.asset })),
    { fam: "fomc", asset: "KRE" }, { fam: "scotus-tariffs", asset: "AAPL" }, { fam: "shutdown-jan-2026", asset: "SPY" },
  ];
  const race: RaceEvent[] = [];
  const used = new Set<string>();
  for (const w of wanted) {
    if (race.length >= 4) break;
    const key = `${w.fam}|${w.asset}`;
    if (used.has(key)) continue;
    const b = bigEvent(w.fam, w.asset);
    if (!b) continue;
    used.add(key);
    const f = fam(w.fam);
    race.push({
      tab: `${short(w.fam)}·${w.asset}`, title: f.label, contract: sym(f.contract, f.kind), t0: b.ev.t0, asset: w.asset,
      odds: b.ev.path!, stock: stockPts(b.ret), pre, post,
      verdict: verdictOf(ll.find((r) => r.family === w.fam && r.asset === w.asset)),
    });
  }

  // ---- story: the top significant pair
  const top = sig[0] ?? ll[0];
  const tb = top && bigEvent(top.family, top.asset);
  const story: StoryData | null = top && tb ? {
    title: fam(top.family).label, asset: top.asset, when: `${day(tb.ev.t0)}, ${tm(tb.ev.t0)} ET`, jump: tb.ev.dp_window_pp ?? 0,
    odds: tb.ev.path!, stock: stockPts(tb.ret), pre, post,
    lags: top.lags.map((l) => ({ k: l.k, c: l.coef_10pp_pct, lo: l.ci_lo, hi: l.ci_hi })),
    pairs: [...ll].sort((a, b) => a.lead_minus_lag_10pp_pct - b.lead_minus_lag_10pp_pct).map((r) => ({
      label: `${short(r.family)} → ${r.asset}`, d: r.lead_minus_lag_10pp_pct, lo: r.lead_minus_lag_ci[0], hi: r.lead_minus_lag_ci[1],
      kind: r.verdict === "contract_first" ? "o" : r.verdict === "stocks_first" ? "s" : "n",
    })),
    betas: [...betas].sort((a, b) => a.beta_10pp_pct - b.beta_10pp_pct).map((b) => ({
      label: `${b.family}|${b.asset}`, b: b.beta_10pp_pct, lo: b.ci_lo, hi: b.ci_hi, survives: b.survives,
    })),
    nEvents: `${top.n_events} events`,
    closestLabel: closest ? `${closest.family}|${closest.asset}` : null,
    closest: closest ? `Closest: ${fam(closest.family).label} → ${closest.asset}, ${fmt(closest.beta_10pp_pct, 2, true)}% per 10 points. It beats both placebos but misses the multiple-testing bar (q ${fmt(closest.q_value, 2)}).` : null,
  } : null;

  // ---- tape
  const tape: Tick[] = [];
  for (const f of m.families) {
    const e = biggest(f.id);
    if (e?.path) tape.push({ sym: short(f.id), val: `${e.path.at(-1)!.p.toFixed(0)}¢`, chg: e.dp_window_pp ?? undefined, unit: " pts" });
  }
  for (const b of [...betas].sort((a, c) => Math.abs(c.t_stat ?? 0) - Math.abs(a.t_stat ?? 0)).slice(0, 8))
    tape.push({ sym: `${short(b.family)}→${b.asset}`, val: `β ${fmt(b.beta_10pp_pct, 2, true)}%` });

  const auditBy = new Map(audit?.families.map((f) => [f.family, f]) ?? []);
  const nPairs = ll.length;

  return (
    <>
      <div className="bleed"><Ticker items={tape} /></div>

      <section className="hero">
        <div>
          <div className="kicker">Prediction markets × the stock market</div>
          <h1>Who knew<span className="l2">first?</span></h1>
        </div>
        <div className="side">
          <p>
            When the odds on Kalshi jump, does Wall Street already know? I lined up <b>{audit?.totals.events ?? ""} sudden
            moves in event contracts</b> against <b>minute-by-minute stock prices</b> to measure who reprices first, and by how much.
          </p>
          <div className="acts">
            <a className="cta" href="#answer">Get the answer ↓</a>
            <a className="cta ghost" href="#story">How it works</a>
          </div>
        </div>
      </section>

      {race.length > 0 && <Race events={race} />}

      <section className="block" id="answer">
        <div className="section-head">
          <div className="kicker">The answer, so far</div>
          <h2>Mostly, <em>nobody</em> wins the race.</h2>
          <p className="lede">Training events only. The newest 30% are sealed until the method is frozen, then run once and published whatever they show.</p>
        </div>
        <div className="board">
          <div>
            <div className="k">No clear leader</div>
            <div className="v">{nPairs - sig.length}<small>/{nPairs}</small></div>
            <div className="t">Pairs where neither side measurably moves first</div>
            <p>At this sample size, most also show no measurable co-movement at all.</p>
          </div>
          <div className="o">
            <div className="k">Exceptions</div>
            <div className="v">{sig.length}</div>
            <div className="t">{sig.length ? `${sig.length > 1 ? "Both" : "Only"} on the ${short(sig[0].family).charAt(0) + short(sig[0].family).slice(1).toLowerCase()} contract` : "No market moves first"}</div>
            <p>{sig.map((r) => `${r.asset}: ${r.verdict === "contract_first" ? "Kalshi first" : "stocks first"} (q ${fmt(r.q_value, 3)})`).join(" · ")}{sig.length ? `. Only ${sig[0].n_events} events: a lead to follow, not a law.` : ""}</p>
          </div>
          <div className="s">
            <div className="k">Effects that survive</div>
            <div className="v">{survivors.length}<small>/{betas.length}</small></div>
            <div className="t">{survivors.length ? "Event betas that hold up" : "No event beta holds up yet"}</div>
            <p>{closest ? `Closest: ${fam(closest.family).label} → ${closest.asset}, ${fmt(closest.beta_10pp_pct, 2, true)}% per 10 pts (q ${fmt(closest.q_value, 2)}).` : "Intervals are wide with this many events."}</p>
          </div>
        </div>
        {audit && (
          <div className="counts">
            <span><b>{audit.totals.events}</b>contract moves found</span>
            <span><b>{audit.totals.in_session}</b>during market hours</span>
            <span><b>{audit.totals.usable}</b>pass the quality filter</span>
            <span><b>{audit.totals.train}</b>in training · {audit.totals.holdout} sealed</span>
            <span><b>{Math.round(audit.totals.stock_bars / 1000)}k</b>stock minute bars</span>
          </div>
        )}
      </section>

      {story && (
        <section className="block" id="story">
          <div className="section-head">
            <div className="kicker">How you catch who moved first</div>
            <h2>One event, then <em>all of them.</em></h2>
          </div>
          <Story s={story} />
        </section>
      )}

      <section className="block" id="board">
        <div className="section-head">
          <div className="kicker">The board</div>
          <h2>Ten contracts. <em>One clock.</em></h2>
          <p className="lede">Each line is the contract&apos;s biggest usable move. Click through for every event, every stock and every test.</p>
        </div>
        <div className="quotes">
          <div className="qhead"><span>Contract</span><span>Event</span><span className="r">Last</span><span className="r">Move</span><span>T−5 → T+30</span><span className="r">Signal</span></div>
          {m.families.map((f) => {
            const e = biggest(f.id);
            const a = auditBy.get(f.id);
            const tested = betas.some((b) => b.family === f.id);
            const v = sig.filter((r) => r.family === f.id);
            const ch = e?.dp_window_pp ?? null;
            return (
              <Link key={f.id} href={`/events/${f.id}/`} className={`qrow${tested ? "" : " dim"}`}>
                <span className="sym">{sym(f.contract, f.kind)}</span>
                <span className="nm">{f.label}<small>{f.type} · {a ? `${a.usable}/${a.events} usable` : "–"}</small></span>
                <span className="px">{e?.path ? `${e.path.at(-1)!.p.toFixed(0)}¢` : "—"}</span>
                <span className={`ch ${ch != null && ch >= 0 ? "up" : "dn"}`}>{ch != null ? `${ch >= 0 ? "▲" : "▼"} ${Math.abs(ch).toFixed(0)}` : "—"}</span>
                <Spark path={e?.path ?? []} w={130} h={30} />
                <span className="sig">
                  {!tested && <span className="pill">thin data</span>}
                  {tested && !v.length && <span className="pill">no leader</span>}
                  {v.map((r) => <span key={r.asset} className={`pill ${r.verdict === "contract_first" ? "odds" : "stock"}`}>{r.verdict === "contract_first" ? `Kalshi→${r.asset}` : `${r.asset} first`}</span>)}
                  {f.rule_clarity === "ambiguous" && <span className="pill warn">fuzzy rules</span>}
                </span>
              </Link>
            );
          })}
        </div>
      </section>

      <section className="block">
        <div className="section-head">
          <div className="kicker">Why believe it</div>
          <h2>Built to <em>say no.</em></h2>
          <p className="lede">Every result above had to get through all of this. Most didn&apos;t, and the site says so.</p>
        </div>
        <div className="log">
          {[
            ["Pre-registered", "Windows, thresholds and contracts were committed before any stock data loaded. Every later change is logged with whether results had been seen."],
            ["Midquotes, not trades", "A contract that hasn't traded keeps a stale price, which would make stocks look like they lead. The bid–ask midpoint doesn't."],
            ["Time-shift placebo", "Same contract moves, paired with the stock at the same clock time on random other days. Real effects have to beat it."],
            ["Shuffled pairs", "Odds from one event, stock returns from another. If that looks as strong, it's noise."],
            ["Many-tests correction", `Benjamini–Hochberg across all ${nPairs} pairs, for effect sizes and for who moves first.`],
            ["Sealed holdout", "The newest 30% of events are locked behind a hash until the method is frozen."],
          ].map(([t, d], i) => (
            <div className="log-line" key={t}><span className="i">[{String(i + 1).padStart(2, "0")}]</span><b>{t}</b><span>{d}</span></div>
          ))}
        </div>
        <p style={{ marginTop: 28 }}><Link className="cta ghost" href="/methods/">Read the full method →</Link></p>
      </section>
    </>
  );
}
