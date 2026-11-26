"use client";
// Scrollytelling: one pinned figure that turns, step by step, from one event into the whole study.
import { useEffect, useRef, useState } from "react";

type Pt = { m: number; p: number };
export type StoryData = {
  title: string; asset: string; when: string; jump: number;
  odds: Pt[]; stock: { m: number; v: number }[]; pre: number; post: number;
  lags: { k: number; c: number; lo: number; hi: number }[];
  pairs: { label: string; d: number; lo: number; hi: number; kind: "o" | "s" | "n" }[];
  betas: { label: string; b: number; lo: number; hi: number; survives: boolean }[];
  nEvents: string; closest: string | null; closestLabel: string | null;
};

const W = 640, H = 460, M = { l: 16, r: 16, t: 20, b: 40 };

export default function Story({ s }: { s: StoryData }) {
  const [step, setStep] = useState(0);
  const steps = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const root = steps.current;
    if (!root) return;
    const io = new IntersectionObserver((es) => {
      for (const e of es) if (e.isIntersecting) setStep(Number((e.target as HTMLElement).dataset.step));
    }, { rootMargin: "-45% 0px -45% 0px" });
    root.querySelectorAll("[data-step]").forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, []);

  // ---- layer A: one event
  const span = s.pre + s.post;
  const X = (m: number) => M.l + ((m + s.pre) / span) * (W - M.l - M.r);
  const ext = (a: number[]) => { const lo = Math.min(...a, 0), hi = Math.max(...a, 0), p = (hi - lo || 1) * 0.15; return [lo - p, hi + p]; };
  const ps = s.odds.map((o) => o.p), [pa, pb] = [Math.min(...ps) - 3, Math.max(...ps) + 3];
  const [sa, sb] = ext(s.stock.map((x) => x.v));
  const YP = (p: number) => 200 - ((p - pa) / (pb - pa)) * 170;
  const YS = (v: number) => H - M.b - ((v - sa) / (sb - sa)) * 170;
  const line = (pts: [number, number][]) => pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`).join("");

  // ---- layer B: lag profile
  const lagMax = Math.max(...s.lags.map((l) => Math.max(Math.abs(l.lo), Math.abs(l.hi))), 0.01);
  const bw = (W - M.l - M.r) / s.lags.length;
  const BX = (i: number) => M.l + i * bw + bw / 2;
  const BY = (v: number) => 230 - (v / lagMax) * 170;

  // ---- layers C/D: forest rows
  const rows = (n: number) => (i: number) => M.t + 26 + i * ((H - M.t - M.b - 26) / Math.max(1, n - 1));
  const fx = (vals: number[]) => { const m = Math.max(...vals.map(Math.abs), 0.01) * 1.08; return (v: number) => W / 2 + (v / m) * (W / 2 - 24); };
  const PX = fx(s.pairs.flatMap((p) => [p.lo, p.hi])), PY = rows(s.pairs.length);
  const BXf = fx(s.betas.flatMap((b) => [b.lo, b.hi])), BYf = rows(s.betas.length);
  const col = (k: string) => (k === "o" ? "#ffb000" : k === "s" ? "#4fd1ff" : "#3a4248");

  const show = (on: boolean) => ({ opacity: on ? 1 : 0, transition: "opacity .6s" });
  const draw = (on: boolean) => ({ strokeDasharray: 1, strokeDashoffset: on ? 0 : 1, transition: "stroke-dashoffset 1.4s ease" });
  const nSig = s.pairs.filter((p) => p.kind !== "n").length, nSurv = s.betas.filter((b) => b.survives).length;

  return (
    <div className="story">
      <div className="story-steps" ref={steps}>
        <div className={`story-step${step === 0 ? " on" : ""}`} data-step="0">
          <div className="n">01 / 05</div>
          <h3>A contract jumps</h3>
          <p>{s.when}. Kalshi&apos;s odds on <b>{s.title.toLowerCase()}</b> move <b className="o">{s.jump > 0 ? "+" : "−"}{Math.abs(s.jump).toFixed(0)} points</b> in minutes. Something happened, and traders on the contract repriced it.</p>
          <p className="muted small">The line is the bid–ask midpoint, not the last trade. A stale trade price would fake a delay.</p>
        </div>
        <div className={`story-step${step === 1 ? " on" : ""}`} data-step="1">
          <div className="n">02 / 05</div>
          <h3>Same clock, one stock</h3>
          <p>Line up <b className="s">{s.asset}</b> on the same minutes. If the stock market cares about this event, it should move too. (The model separately nets out what the whole market and the stock&apos;s sector did.)</p>
          <p>The question is not only <b>whether</b> it moves. It&apos;s <b>who moves first</b>.</p>
        </div>
        <div className={`story-step${step === 2 ? " on" : ""}`} data-step="2">
          <div className="n">03 / 05</div>
          <h3>Slide one against the other</h3>
          <p>Shift the odds up to five minutes ahead of the stock, and five behind. Each bar is how much {s.asset} moves per 10 points of odds at that offset, pooled over {s.nEvents}.</p>
          <p>Weight on the <b className="o">right</b> means Kalshi moved first. Weight on the <b className="s">left</b> means stocks did.</p>
        </div>
        <div className={`story-step${step === 3 ? " on" : ""}`} data-step="3">
          <div className="n">04 / 05</div>
          <h3>Now all {s.pairs.length} pairs</h3>
          <p>Every contract against every stock it should touch. Each line is right-side weight minus left-side weight, with a 95% interval from resampling whole events.</p>
          <p>After correcting for testing {s.pairs.length} pairs at once, <b>{s.pairs.length - nSig} show no clear leader</b>. {nSig} do, all on one contract.</p>
        </div>
        <div className={`story-step${step === 4 ? " on" : ""}`} data-step="4">
          <div className="n">05 / 05</div>
          <h3>How much? Not proven yet</h3>
          <p>The size of each move, in % per 10 points of odds. To count, a result has to beat a time-shift placebo, a shuffled-pairs test and the multiple-testing bar.</p>
          <p><b>{nSurv} of {s.betas.length}</b> do. {s.closest}</p>
          <p className="muted small">The newest 30% of events stay sealed until the method is frozen. Then they run once.</p>
        </div>
      </div>

      <div className="story-stage">
        <figure className="story-fig">
          <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Figure that changes with each step of the story">
            {/* A: one event */}
            <g style={show(step <= 1)}>
              <text x={M.l} y={22} fontSize="10" fill="#ffb000">KALSHI ODDS ¢</text>
              <text x={M.l} y={248} fontSize="10" fill="#4fd1ff" style={show(step >= 1)}>{s.asset} %, raw</text>
              <line x1={X(0)} x2={X(0)} y1={20} y2={H - M.b} stroke="#ff5a4e" strokeDasharray="4 4" />
              <text x={X(0) + 6} y={36} fontSize="10" fill="#ff5a4e">EVENT</text>
              <line x1={M.l} x2={W - M.r} y1={YS(0)} y2={YS(0)} stroke="#2a3238" strokeDasharray="2 4" style={show(step >= 1)} />
              <path pathLength={1} d={line(s.odds.map((o) => [X(o.m), YP(o.p)]))} fill="none" stroke="#ffb000" strokeWidth="2.4" style={draw(step <= 1)} />
              <path pathLength={1} d={line(s.stock.map((o) => [X(o.m), YS(o.v)]))} fill="none" stroke="#4fd1ff" strokeWidth="2.4" style={draw(step === 1)} />
              {[-s.pre, 0, 10, 20, s.post].map((m) => <text key={m} x={X(m)} y={H - 14} fontSize="10" textAnchor="middle" fill="#6c6f6c">{m === 0 ? "T" : m > 0 ? `+${m}m` : `${m}m`}</text>)}
            </g>

            {/* B: lag profile */}
            <g style={show(step === 2)}>
              <line x1={M.l} x2={W - M.r} y1={BY(0)} y2={BY(0)} stroke="#2a3238" />
              {s.lags.map((l, i) => {
                const c = l.k > 0 ? "#ffb000" : l.k < 0 ? "#4fd1ff" : "#ece6d8";
                return (
                  <g key={l.k}>
                    <rect x={BX(i) - bw * 0.3} width={bw * 0.6} y={Math.min(BY(0), BY(l.c))} height={Math.max(1, Math.abs(BY(l.c) - BY(0)))} fill={c} opacity={0.85}
                      style={{ transformOrigin: `${BX(i)}px ${BY(0)}px`, transform: `scaleY(${step === 2 ? 1 : 0})`, transition: `transform .7s ${i * 0.04}s ease` }} />
                    <line x1={BX(i)} x2={BX(i)} y1={BY(l.lo)} y2={BY(l.hi)} stroke="#ece6d8" strokeOpacity=".45" />
                    <text x={BX(i)} y={BY(0) + 190} fontSize="10" textAnchor="middle" fill="#6c6f6c">{l.k > 0 ? `+${l.k}` : l.k}</text>
                  </g>
                );
              })}
              <text x={M.l} y={H - 14} fontSize="11" fill="#4fd1ff">← STOCKS FIRST</text>
              <text x={W - M.r} y={H - 14} fontSize="11" textAnchor="end" fill="#ffb000">KALSHI FIRST →</text>
              <text x={W / 2} y={H - 14} fontSize="11" textAnchor="middle" fill="#6c6f6c">offset, minutes</text>
            </g>

            {/* C: all pairs, lead minus lag */}
            <g style={show(step === 3)}>
              <line x1={PX(0)} x2={PX(0)} y1={M.t + 10} y2={H - M.b + 6} stroke="#2a3238" />
              {s.pairs.map((p, i) => (
                <g key={p.label}>
                  <line x1={PX(p.lo)} x2={PX(p.hi)} y1={PY(i)} y2={PY(i)} stroke={col(p.kind)} strokeWidth={p.kind === "n" ? 1.5 : 2.5} />
                  <circle cx={PX(p.d)} cy={PY(i)} r={p.kind === "n" ? 2.5 : 4} fill={p.kind === "n" ? "#6c6f6c" : col(p.kind)} />
                  {p.kind !== "n" && <text x={p.d > 0 ? PX(p.hi) + 8 : PX(p.lo) - 8} y={PY(i) + 4} fontSize="11" fill={col(p.kind)} textAnchor={p.d > 0 ? "start" : "end"}>{p.label}</text>}
                </g>
              ))}
              <text x={M.l} y={H - 14} fontSize="11" fill="#4fd1ff">← STOCKS FIRST</text>
              <text x={W - M.r} y={H - 14} fontSize="11" textAnchor="end" fill="#ffb000">KALSHI FIRST →</text>
            </g>

            {/* D: betas */}
            <g style={show(step === 4)}>
              <line x1={BXf(0)} x2={BXf(0)} y1={M.t + 10} y2={H - M.b + 6} stroke="#2a3238" />
              {s.betas.map((b, i) => (
                <g key={b.label}>
                  <line x1={BXf(b.lo)} x2={BXf(b.hi)} y1={BYf(i)} y2={BYf(i)} stroke={b.survives ? "#36d97b" : "#3a4248"} strokeWidth="1.5" />
                  <circle cx={BXf(b.b)} cy={BYf(i)} r={b.label === s.closestLabel ? 5 : 3} fill={b.survives ? "#36d97b" : b.label === s.closestLabel ? "#ffb000" : "#a9a497"} />
                  {b.label === s.closestLabel && <text x={BXf(b.hi) + 8} y={BYf(i) + 4} fontSize="11" fill="#ffb000">CLOSEST: {b.label.split("|")[1]}</text>}
                </g>
              ))}
              <text x={M.l} y={H - 14} fontSize="11" fill="#6c6f6c">stock falls when odds rise</text>
              <text x={W - M.r} y={H - 14} fontSize="11" textAnchor="end" fill="#6c6f6c">stock rises when odds rise</text>
              <text x={W - M.r} y={M.t + 4} fontSize="40" textAnchor="end" fill="#ece6d8" fontWeight="700">{nSurv}/{s.betas.length}</text>
              <text x={W - M.r} y={M.t + 24} fontSize="10" textAnchor="end" fill="#6c6f6c">SURVIVE EVERY TEST</text>
            </g>
          </svg>
          <figcaption className="cap">
            {step <= 1 ? `${s.title} · ${s.when}` : step === 2 ? `${s.title} → ${s.asset} · lead–lag coefficients, 95% event-bootstrap CIs` : step === 3 ? "Lead minus lag, % per 10 pts · 95% CIs · colored = passes Benjamini–Hochberg at q < 0.05" : "Event beta, % per 10 pts · 95% CIs · green = survives all checks"}
          </figcaption>
        </figure>
      </div>
    </div>
  );
}
