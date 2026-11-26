"use client";
// The hero: real events replayed on a phosphor screen. Kalshi's odds (amber) race a stock (cyan), minute by minute.
import { useEffect, useRef, useState } from "react";

export type RaceEvent = {
  tab: string; title: string; contract: string; t0: string; asset: string;
  odds: { m: number; p: number }[]; stock: { m: number; v: number }[];
  pre: number; post: number;
  verdict: { kind: "o" | "s" | "n"; text: string; detail: string };
};

const PLAY = 8000, HOLD = 3200;

const clockET = (t0: string, m: number) =>
  new Date(new Date(t0).getTime() + m * 60000).toLocaleTimeString("en-US", { timeZone: "America/New_York", hour: "numeric", minute: "2-digit" });

export default function Race({ events }: { events: RaceEvent[] }) {
  const [idx, setIdx] = useState(0);
  const [t, setT] = useState(1);
  const [auto, setAuto] = useState(true);
  const [narrow, setNarrow] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const start = useRef(0);

  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setNarrow(e.contentRect.width < 640));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) { setT(1); return; }
    let raf = 0;
    start.current = performance.now();
    const tick = (now: number) => {
      const e = now - start.current;
      if (e > PLAY + HOLD) {
        if (auto && events.length > 1) { setIdx((i) => (i + 1) % events.length); return; }
        start.current = now;
      }
      setT(Math.min(1, (now - start.current) / PLAY));
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [idx, auto, events.length]);

  const r = events[idx];
  const W = narrow ? 600 : 1200, H = narrow ? 360 : 340;
  const L = narrow ? 14 : 24, R = narrow ? 14 : 24, laneO: [number, number] = [narrow ? 44 : 26, H * 0.48], laneS: [number, number] = [H * 0.56, H - 34];
  const span = r.pre + r.post;
  const now = -r.pre + t * span;
  const X = (m: number) => L + ((m + r.pre) / span) * (W - L - R);
  const ext = (a: number[], zero = false) => {
    let lo = Math.min(...a, ...(zero ? [0] : [])), hi = Math.max(...a, ...(zero ? [0] : []));
    if (hi - lo < 1e-6) { lo -= 1; hi += 1; }
    const pad = (hi - lo) * 0.14;
    return [lo - pad, hi + pad];
  };
  const [p0, p1] = ext(r.odds.map((o) => o.p));
  const [s0, s1] = ext(r.stock.map((s) => s.v), true);
  const YP = (p: number) => laneO[1] - ((p - p0) / (p1 - p0)) * (laneO[1] - laneO[0]);
  const YS = (v: number) => laneS[1] - ((v - s0) / (s1 - s0)) * (laneS[1] - laneS[0]);
  const upto = <T extends { m: number }>(a: T[]) => a.filter((x) => x.m <= now);
  const d = (pts: [number, number][]) => pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`).join("");
  const o = upto(r.odds), s = upto(r.stock);
  const pStart = r.odds[0].p, pNow = o.at(-1)?.p ?? pStart, sNow = s.at(-1)?.v ?? 0;
  const dp = pNow - pStart;
  const ticks = narrow ? [-r.pre, 0, 15, r.post] : [-r.pre, 0, 5, 10, 15, 20, 25, r.post];

  return (
    <div className="race" id="race" ref={box}>
      <div className="race-bar">
        <span className="live">REPLAY · {clockET(r.t0, Math.round(now))} ET</span>
        <div className="tabs" role="tablist" aria-label="Pick an event">
          {events.map((e, i) => (
            <button key={e.tab} role="tab" aria-pressed={i === idx} aria-selected={i === idx}
              onClick={() => { setAuto(false); setIdx(i); }}>{e.tab}</button>
          ))}
        </div>
      </div>

      <div className="race-head">
        <div className="ev"><small>{r.contract} · {new Date(r.t0).toLocaleDateString("en-US", { timeZone: "America/New_York", month: "short", day: "numeric", year: "numeric" })}</small>{r.title}</div>
        <div className="readout o">
          <div className="k">Kalshi odds</div>
          <div className="v">{pNow.toFixed(0)}¢</div>
          <div className="d" style={{ color: dp >= 0 ? "var(--up)" : "var(--dn)" }}>{dp >= 0 ? "▲" : "▼"} {Math.abs(dp).toFixed(0)} pts</div>
        </div>
        <div className="readout s">
          <div className="k">{r.asset}</div>
          <div className="v">{sNow >= 0 ? "+" : "−"}{Math.abs(sNow).toFixed(2)}%</div>
          <div className="d" style={{ color: "var(--dim)" }}>since T−{r.pre}</div>
        </div>
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${r.title}: Kalshi odds and ${r.asset}, minute by minute around the event`}>
        <defs>
          <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="3.5" result="b" />
            <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
          <linearGradient id="sweep" x1="0" x2="1">
            <stop offset="0" stopColor="#ffb000" stopOpacity="0" /><stop offset="1" stopColor="#ffb000" stopOpacity=".10" />
          </linearGradient>
        </defs>
        {/* minute grid */}
        {Array.from({ length: span + 1 }, (_, i) => -r.pre + i).map((m) => (
          <line key={m} x1={X(m)} x2={X(m)} y1={laneO[0] - 8} y2={laneS[1] + 4} stroke="#12171b" />
        ))}
        <line x1={L} x2={W - R} y1={(laneO[1] + laneS[0]) / 2} y2={(laneO[1] + laneS[0]) / 2} stroke="#1d2328" />
        <line x1={L} x2={W - R} y1={YS(0)} y2={YS(0)} stroke="#2a3238" strokeDasharray="2 4" />
        <text x={L + 2} y={laneO[0] - 12} fontSize="10" fill="#ffb000" letterSpacing="1">ODDS ¢</text>
        <text x={L + 2} y={laneS[0] - 8} fontSize="10" fill="#4fd1ff" letterSpacing="1">{r.asset} %</text>

        {/* event marker */}
        <line x1={X(0)} x2={X(0)} y1={laneO[0] - 14} y2={laneS[1] + 4} stroke="#ff5a4e" strokeDasharray="4 4" opacity={now >= 0 ? 1 : 0.35} />
        <rect x={X(0) - 30} y={laneO[0] - 26} width="60" height="16" fill={now >= 0 ? "#ff5a4e" : "#000"} stroke="#ff5a4e" />
        <text x={X(0)} y={laneO[0] - 14} fontSize="10" textAnchor="middle" fill={now >= 0 ? "#000" : "#ff5a4e"} fontWeight="700">EVENT</text>

        {/* sweep */}
        <rect x={L} y={laneO[0] - 8} width={Math.max(0, X(now) - L)} height={laneS[1] - laneO[0] + 12} fill="url(#sweep)" />
        <line x1={X(now)} x2={X(now)} y1={laneO[0] - 8} y2={laneS[1] + 4} stroke="#ffcf66" strokeOpacity=".5" />

        <path d={d(o.map((x) => [X(x.m), YP(x.p)]))} fill="none" stroke="#ffb000" strokeWidth="2.4" strokeLinejoin="round" filter="url(#glow)" />
        <path d={d(s.map((x) => [X(x.m), YS(x.v)]))} fill="none" stroke="#4fd1ff" strokeWidth="2.4" strokeLinejoin="round" filter="url(#glow)" />
        {o.length > 0 && <circle cx={X(o.at(-1)!.m)} cy={YP(pNow)} r="5" fill="#ffcf66" filter="url(#glow)" />}
        {s.length > 0 && <circle cx={X(s.at(-1)!.m)} cy={YS(sNow)} r="5" fill="#a8e9ff" filter="url(#glow)" />}

        {ticks.map((m) => (
          <text key={m} x={X(m)} y={H - 10} fontSize="10" textAnchor="middle" fill="#6c6f6c">{m === 0 ? "T" : m > 0 ? `T+${m}` : `T${m}`}</text>
        ))}
      </svg>

      <div className="race-foot">
        <span>{r.asset} vs. this contract, all training events: <span className={`verdict ${r.verdict.kind}`}>{r.verdict.text}</span></span>
        <span className="muted">{r.verdict.detail}</span>
      </div>
    </div>
  );
}
