// Build-time data access. Everything here runs on the server during `next build`.
import fs from "node:fs";
import path from "node:path";

const DIR = path.join(process.cwd(), "public", "data");

export type Family = {
  id: string; label: string; type: string; kind: string; rule_clarity: string;
  rule_note?: string | null; question?: string | null; assets: string[]; contract: string;
};
export type AuditFamily = {
  family: string; label: string; type: string; kind: string; events: number; in_session: number;
  usable: number; train: number; holdout: number; median_spread_pp: number | null;
  median_active_share: number | null; exclusions: Record<string, number>; first: string; last: string;
};
export type Meta = {
  generated_at: string; status: "results" | "awaiting_stock_data"; holdout_unsealed: boolean;
  window: { pre_min: number; post_min: number };
  quality: Record<string, number>; jump: Record<string, number>; validation: Record<string, unknown>;
  gate: { min_usable_events: number };
  audit: null | {
    families: AuditFamily[];
    totals: { events: number; in_session: number; outside_session: number; usable: number; train: number; holdout: number; stock_bars: number };
    gate: { min_usable_train_events: number; train_events: number; pass: boolean };
    exclusions: Record<string, number>;
  };
  families: Family[];
};
export type Beta = {
  family: string; asset: string; controls: string[]; n_events: number; n_obs: number;
  beta_10pp_pct: number; ci_lo: number; ci_hi: number; p_boot: number;
  raw_beta_10pp_pct: number; raw_ci_lo: number; raw_ci_hi: number; raw_p_boot: number;
  placebo_p: number | null; shuffle_p: number | null; q_value: number | null; survives: boolean;
  t_stat: number;
};
export type Lag = { k: number; coef_10pp_pct: number; ci_lo: number; ci_hi: number };
export type LeadLagCore = {
  n_events: number; lags: Lag[]; total_10pp_pct: number; total_ci: [number, number];
  lead_minus_lag_10pp_pct: number; lead_minus_lag_ci: [number, number];
  verdict: "contract_first" | "stocks_first" | "same_minute_or_unclear"; p_boot?: number; q_value?: number; uncorrected_verdict?: string;
};
export type LeadLag = LeadLagCore & { family: string; asset: string; robust_high_activity: LeadLagCore | null };
export type EventRow = {
  event_id: string; t0: string; label: string; usable: boolean; exclusion: string | null; split: string | null;
  in_session: boolean; active_share: number | null; median_spread_pp: number | null; p_start: number | null;
  dp_window_pp: number | null; jump_pp: number | null; path: { m: number; p: number }[] | null;
};
export type FamilyData = {
  family: string; events: EventRow[]; betas?: Beta[]; leadlag?: LeadLag[];
  paths?: Record<string, { event_id: string; cum_ret_pct: number[] }[]>;
  holdout_betas?: Beta[]; holdout_leadlag?: LeadLag[];
};

function read<T>(rel: string): T | null {
  const p = path.join(DIR, rel);
  if (!fs.existsSync(p)) return null;
  return JSON.parse(fs.readFileSync(p, "utf8")) as T;
}

export function meta(): Meta {
  const m = read<Meta>("meta.json");
  if (!m) throw new Error("web/public/data/meta.json missing: run `uv run pricedin export` first");
  return m;
}
export const family = (id: string) => read<FamilyData>(`families/${id}.json`);
export const allBetas = () => read<{ betas: Beta[] }>("betas.json")?.betas ?? [];
export const allLeadLag = () => read<{ leadlag: LeadLag[] }>("leadlag.json")?.leadlag ?? [];

export const VERDICT: Record<LeadLagCore["verdict"], string> = {
  contract_first: "Contract moves first",
  stocks_first: "Stocks move first",
  same_minute_or_unclear: "No clear lead",
};
export const EXCLUSION: Record<string, string> = {
  usable: "Usable",
  before_open: "Before the open",
  after_close: "After the close",
  window_crosses_open: "Window crosses the open",
  window_crosses_close: "Window crosses the close",
  weekend: "Weekend",
  no_price: "No contract price",
  wide_spread: "Spread over 5 points",
  one_sided_book: "One-sided book",
  inactive: "Fewer than 5 active minutes",
  no_next_meeting_contracts: "No next-meeting contract",
};
export const fmt = (x: number | null | undefined, d = 2, sign = false) =>
  x == null || Number.isNaN(x) ? "–" : `${sign && x > 0 ? "+" : ""}${x.toFixed(d)}`;
export const fmtP = (p: number | null | undefined) =>
  p == null ? "–" : p < 0.001 ? "<0.001" : p.toFixed(3);
