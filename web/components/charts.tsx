// Server-rendered SVG charts. No chart library: every mark is explicit.
import type { Lag } from "@/lib/data";

const niceStep = (span: number) => {
  const raw = span / 5;
  const p = 10 ** Math.floor(Math.log10(raw));
  return [1, 2, 2.5, 5, 10].map((m) => m * p).find((s) => s >= raw) ?? raw;
};
function ticks(lo: number, hi: number) {
  const s = niceStep(hi - lo || 1);
  const out: number[] = [];
  for (let v = Math.ceil(lo / s) * s; v <= hi + 1e-12; v += s) out.push(+v.toFixed(10));
  return out;
}

export type ForestRow = { label: string; sub?: string; est: number; lo: number; hi: number; strong: boolean };

/** Point + 95% interval per row on a shared axis, zero line marked. */
export function Forest({ rows, unit }: { rows: ForestRow[]; unit: string }) {
  const W = 720, left = 150, right = 24, rowH = 34, top = 30, H = top + rows.length * rowH + 34;
  const lo = Math.min(0, ...rows.map((r) => r.lo)), hi = Math.max(0, ...rows.map((r) => r.hi));
  const pad = (hi - lo) * 0.08 || 0.1;
  const a = lo - pad, b = hi + pad;
  const X = (v: number) => left + ((v - a) / (b - a)) * (W - left - right);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label={`Event betas, ${unit}`}>
      {ticks(a, b).map((t) => (
        <g key={t}>
          <line x1={X(t)} x2={X(t)} y1={top - 8} y2={H - 28} stroke="var(--grid)" />
          <text x={X(t)} y={H - 10} fontSize="11" textAnchor="middle" fill="var(--ink-3)">{t}</text>
        </g>
      ))}
      <line x1={X(0)} x2={X(0)} y1={top - 8} y2={H - 28} stroke="var(--ink-3)" strokeDasharray="3 3" />
      <text x={W - right} y={14} fontSize="11" textAnchor="end" fill="var(--ink-3)">{unit}</text>
      {rows.map((r, i) => {
        const y = top + i * rowH + rowH / 2;
        const c = r.strong ? "var(--stock)" : "var(--ink-3)";
        return (
          <g key={r.label}>
            <text x={0} y={y + 1} fontSize="13" fill="var(--ink)" fontWeight={r.strong ? 700 : 400}>{r.label}</text>
            {r.sub && <text x={0} y={y + 14} fontSize="10" fill="var(--ink-3)">{r.sub}</text>}
            <line x1={X(r.lo)} x2={X(r.hi)} y1={y} y2={y} stroke={c} strokeWidth="2" />
            <line x1={X(r.lo)} x2={X(r.lo)} y1={y - 5} y2={y + 5} stroke={c} strokeWidth="1.5" />
            <line x1={X(r.hi)} x2={X(r.hi)} y1={y - 5} y2={y + 5} stroke={c} strokeWidth="1.5" />
            <circle cx={X(r.est)} cy={y} r={r.strong ? 5 : 4} fill={r.strong ? c : "var(--panel)"} stroke={c} strokeWidth="2" />
          </g>
        );
      })}
    </svg>
  );
}

/** Lead-lag profile: coefficient at each lag with its interval. Right of zero = contract first. */
export function LagProfile({ lags, height = 220 }: { lags: Lag[]; height?: number }) {
  const W = 720, left = 46, right = 16, top = 34, bottom = 40, H = height;
  const lo = Math.min(0, ...lags.map((l) => l.ci_lo)), hi = Math.max(0, ...lags.map((l) => l.ci_hi));
  const pad = (hi - lo) * 0.1 || 0.1;
  const a = lo - pad, b = hi + pad;
  const n = lags.length;
  const bw = (W - left - right) / n;
  const X = (i: number) => left + bw * (i + 0.5);
  const Y = (v: number) => top + (1 - (v - a) / (b - a)) * (H - top - bottom);
  const zeroI = lags.findIndex((l) => l.k === 0);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Lead-lag profile">
      <rect x={left} y={top} width={bw * zeroI} height={H - top - bottom} fill="var(--stock-soft)" opacity="0.5" />
      <rect x={left + bw * (zeroI + 1)} y={top} width={bw * (n - zeroI - 1)} height={H - top - bottom} fill="var(--odds-soft)" opacity="0.5" />
      <text x={left + 6} y={top - 10} fontSize="11" fill="var(--stock)">← stocks moved first</text>
      <text x={W - right - 6} y={top - 10} fontSize="11" textAnchor="end" fill="var(--odds)">contract moved first →</text>
      {ticks(a, b).map((t) => (
        <g key={t}>
          <line x1={left} x2={W - right} y1={Y(t)} y2={Y(t)} stroke="var(--grid)" />
          <text x={left - 6} y={Y(t) + 4} fontSize="10" textAnchor="end" fill="var(--ink-3)">{t}</text>
        </g>
      ))}
      <line x1={left} x2={W - right} y1={Y(0)} y2={Y(0)} stroke="var(--ink-3)" />
      {lags.map((l, i) => {
        const sig = l.ci_lo > 0 || l.ci_hi < 0;
        const c = l.k === 0 ? "var(--ink)" : l.k > 0 ? "var(--odds)" : "var(--stock)";
        return (
          <g key={l.k}>
            <rect x={X(i) - bw * 0.28} width={bw * 0.56} y={Math.min(Y(0), Y(l.coef_10pp_pct))}
              height={Math.abs(Y(0) - Y(l.coef_10pp_pct))} fill={c} opacity={sig ? 0.85 : 0.3} rx="2" />
            <line x1={X(i)} x2={X(i)} y1={Y(l.ci_lo)} y2={Y(l.ci_hi)} stroke="var(--ink-2)" strokeWidth="1.2" />
            <text x={X(i)} y={H - bottom + 16} fontSize="11" textAnchor="middle" fill="var(--ink-2)">
              {l.k > 0 ? `+${l.k}` : l.k}
            </text>
          </g>
        );
      })}
      <text x={(left + W - right) / 2} y={H - 6} fontSize="11" textAnchor="middle" fill="var(--ink-3)">
        minutes the contract move precedes the stock return
      </text>
    </svg>
  );
}
