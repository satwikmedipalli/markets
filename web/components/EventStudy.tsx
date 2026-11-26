"use client";
// Aligned event study: every usable event on one clock (minute 0 = event time), signed so the
// odds rise. Top: change in odds. Bottom: the chosen asset's cumulative return, same sign flip.
import { useMemo, useState } from "react";

type Path = { m: number; p: number }[];
type Ev = { event_id: string; label: string; dp_window_pp: number | null; path: Path | null };

export default function EventStudy({ events, stock, pre, post }: {
  events: Ev[]; stock: Record<string, { event_id: string; cum_ret_pct: number[] }[]>; pre: number; post: number;
}) {
  const assets = Object.keys(stock);
  const [asset, setAsset] = useState(assets[0]);
  const [hover, setHover] = useState<string | null>(null);

  const rows = useMemo(() => {
    const byId = new Map((stock[asset] ?? []).map((s) => [s.event_id, s.cum_ret_pct]));
    return events.filter((e) => e.path && e.path.length > 1 && byId.has(e.event_id)).map((e) => {
      const sign = (e.dp_window_pp ?? 0) < 0 ? -1 : 1;
      const p0 = e.path![0].p;
      const odds = e.path!.map((x) => ({ m: x.m, v: sign * (x.p - p0) }));
      const r = byId.get(e.event_id)!;
      const stockPath = [{ m: -pre, v: 0 }, ...r.map((v, i) => ({ m: -pre + 1 + i, v: sign * v }))];
      return { id: e.event_id, label: e.label, odds, stock: stockPath };
    });
  }, [events, stock, asset, pre]);

  const mean = (key: "odds" | "stock") => {
    const out: { m: number; v: number }[] = [];
    for (let m = -pre; m <= post; m++) {
      const vs = rows.map((r) => r[key].find((x) => x.m === m)?.v).filter((v): v is number => v != null);
      if (vs.length) out.push({ m, v: vs.reduce((a, b) => a + b, 0) / vs.length });
    }
    return out;
  };
  const mo = mean("odds"), ms = mean("stock");

  const W = 720, left = 52, right = 16, h = 170, gap = 34;
  const X = (m: number) => left + ((m + pre) / (pre + post)) * (W - left - right);
  const panel = (key: "odds" | "stock", m: { m: number; v: number }[], y0: number, color: string, unit: string, title: string) => {
    const all = rows.flatMap((r) => r[key].map((x) => x.v));
    const q = (p: number) => { const s = [...all].sort((a, b) => a - b); return s[Math.floor(p * (s.length - 1))] ?? 0; };
    let lo = Math.min(0, q(0.02), ...m.map((x) => x.v)), hi = Math.max(0, q(0.98), ...m.map((x) => x.v));
    if (hi - lo < 1e-9) { lo -= 1; hi += 1; }
    const Y = (v: number) => y0 + (1 - (Math.max(lo, Math.min(hi, v)) - lo) / (hi - lo)) * h;
    const d = (pts: { m: number; v: number }[]) => pts.map((p, i) => `${i ? "L" : "M"}${X(p.m).toFixed(1)} ${Y(p.v).toFixed(1)}`).join("");
    return (
      <g>
        <text x={left} y={y0 - 8} fontSize="11" fill={color} fontWeight="600">{title}</text>
        {Y(0) - Y(hi) > 14 && <text x={left - 6} y={Y(hi) + 4} fontSize="10" textAnchor="end" fill="var(--ink-3)">{hi.toFixed(unit === "pp" ? 0 : 2)}</text>}
        {Y(lo) - Y(0) > 14 && <text x={left - 6} y={Y(lo) + 4} fontSize="10" textAnchor="end" fill="var(--ink-3)">{lo.toFixed(unit === "pp" ? 0 : 2)}</text>}
        <text x={left - 6} y={Y(0) + 4} fontSize="10" textAnchor="end" fill="var(--ink-3)">0</text>
        <line x1={left} x2={W - right} y1={Y(0)} y2={Y(0)} stroke="var(--grid)" />
        {rows.map((r) => (
          <path key={r.id} d={d(r[key])} fill="none" stroke={color} strokeWidth={hover === r.id ? 2 : 1}
            opacity={hover ? (hover === r.id ? 0.95 : 0.08) : 0.18}
            onMouseEnter={() => setHover(r.id)} onMouseLeave={() => setHover(null)} />
        ))}
        <path d={d(m)} fill="none" stroke={color} strokeWidth="3" />
        <text x={W - right} y={y0 - 8} fontSize="10" textAnchor="end" fill="var(--ink-3)">{unit}</text>
      </g>
    );
  };

  if (!rows.length) return <p className="muted">No events with both contract and stock data yet.</p>;
  const hovered = rows.find((r) => r.id === hover);
  return (
    <div>
      <div className="chips" style={{ marginBottom: 12 }}>
        {assets.map((a) => (
          <button key={a} className="chip" aria-pressed={a === asset} onClick={() => setAsset(a)}>{a}</button>
        ))}
      </div>
      <svg viewBox={`0 0 ${W} ${2 * h + gap + 60}`} width="100%" role="img" aria-label="Aligned event study">
        <line x1={X(0)} x2={X(0)} y1={14} y2={2 * h + gap + 30} stroke="var(--ink-3)" strokeDasharray="3 3" />
        {panel("odds", mo, 22, "var(--odds)", "pp", "Contract odds, change since window start")}
        {panel("stock", ms, 22 + h + gap, "var(--stock)", "%", `${asset}, cumulative return`)}
        {[-pre, 0, 10, 20, post].map((m) => (
          <text key={m} x={X(m)} y={2 * h + gap + 46} fontSize="11" textAnchor="middle" fill="var(--ink-3)">
            {m === 0 ? "event" : m > 0 ? `+${m}m` : `${m}m`}
          </text>
        ))}
      </svg>
      <p className="small muted" style={{ marginTop: 4 }}>
        {hovered ? hovered.label : `${rows.length} events. Thin lines are single events, the bold line is the average. Events where the odds fell are flipped so every event reads as odds rising.`}
      </p>
    </div>
  );
}
