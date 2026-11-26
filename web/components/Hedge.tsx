"use client";
import { useMemo, useState } from "react";
import type { Beta, Family } from "@/lib/data";

type Line = { ticker: string; value: string };
const usd = (x: number) => x.toLocaleString("en-US", { maximumFractionDigits: 0 });

export default function Hedge({ families, betas }: { families: Family[]; betas: Beta[] }) {
  const withBetas = families.filter((f) => betas.some((b) => b.family === f.id));
  const [fam, setFam] = useState(withBetas[0]?.id ?? "");
  const [lines, setLines] = useState<Line[]>([{ ticker: "KRE", value: "250000" }, { ticker: "TLT", value: "100000" }]);
  const rows = useMemo(() => new Map(betas.filter((b) => b.family === fam).map((b) => [b.asset, b])), [betas, fam]);

  const res = useMemo(() => {
    let c = 0, lo = 0, hi = 0;
    const missing: string[] = [];
    const per = lines.map((l) => {
      const b = rows.get(l.ticker.trim().toUpperCase());
      const v = Number(l.value.replace(/[,$\s]/g, "")) || 0;
      if (!b) { if (l.ticker.trim()) missing.push(l.ticker.toUpperCase()); return null; }
      // contracts = value x (return per unit probability); beta is % per 10 points
      const k = (x: number) => (v * x) / 10;
      const [a, z] = [k(b.ci_lo), k(b.ci_hi)].sort((p, q) => p - q);
      c += k(b.beta_10pp_pct); lo += a; hi += z;
      return { t: b.asset, v, c: k(b.beta_10pp_pct), survives: b.survives };
    });
    return { c, lo, hi, per, missing };
  }, [lines, rows]);

  if (!withBetas.length) return <div className="banner">The calculator turns on once event betas are estimated.</div>;
  const side = res.c > 0 ? "Buy NO (or sell YES)" : res.c < 0 ? "Buy YES" : "No hedge needed";

  return (
    <div className="grid g2">
      <div className="panel">
        <label className="small muted">Event</label>
        <select value={fam} onChange={(e) => setFam(e.target.value)} style={{ width: "100%", margin: "6px 0 16px" }}>
          {withBetas.map((f) => <option key={f.id} value={f.id}>{f.label}</option>)}
        </select>
        <label className="small muted">Positions (dollar value, negative for short)</label>
        {lines.map((l, i) => (
          <div key={i} style={{ display: "flex", gap: 8, marginTop: 8 }}>
            <input list="tickers" value={l.ticker} placeholder="Ticker" style={{ width: 110 }}
              onChange={(e) => setLines(lines.map((x, j) => (j === i ? { ...x, ticker: e.target.value } : x)))} />
            <input value={l.value} inputMode="decimal" placeholder="Value" style={{ flex: 1, minWidth: 0 }}
              onChange={(e) => setLines(lines.map((x, j) => (j === i ? { ...x, value: e.target.value } : x)))} />
            <button className="ghost" aria-label="Remove" onClick={() => setLines(lines.filter((_, j) => j !== i))}>×</button>
          </div>
        ))}
        <datalist id="tickers">{[...rows.keys()].map((t) => <option key={t} value={t} />)}</datalist>
        <button className="ghost" style={{ marginTop: 12 }} onClick={() => setLines([...lines, { ticker: "", value: "" }])}>Add position</button>
        <p className="small muted" style={{ marginTop: 14 }}>Covered for this event: {[...rows.keys()].join(", ")}</p>
      </div>
      <div className="panel">
        <div className="kicker">Contracts to offset the exposure</div>
        <div className="num" style={{ fontSize: 40, fontWeight: 700, lineHeight: 1.1 }}>{usd(Math.abs(res.c))}</div>
        <div style={{ margin: "6px 0 14px", fontWeight: 600 }}>{side}</div>
        <div className="small muted">
          95% range: {usd(Math.min(Math.abs(res.lo), Math.abs(res.hi)) * (res.lo * res.hi > 0 ? 1 : 0))} to {usd(Math.max(Math.abs(res.lo), Math.abs(res.hi)))} contracts
        </div>
        <table style={{ marginTop: 16 }}>
          <tbody>
            {res.per.filter(Boolean).map((p) => (
              <tr key={p!.t}><td className="num">{p!.t}</td><td className="r num">${usd(p!.v)}</td>
                <td className="r num">{usd(p!.c)}</td><td>{p!.survives ? <span className="pill good">holds up</span> : <span className="pill">weak</span>}</td></tr>
            ))}
          </tbody>
        </table>
        {res.missing.length > 0 && <p className="small" style={{ color: "var(--warn)" }}>No beta for {res.missing.join(", ")} on this event.</p>}
        <p className="small muted" style={{ marginTop: 14 }}>
          A $1 contract gains 1¢ per probability point, so contracts = position × beta per point ÷ $0.01.
          This offsets co-movement measured in event windows. It is not a guarantee, and betas marked weak
          did not survive the placebo checks.
        </p>
      </div>
    </div>
  );
}
