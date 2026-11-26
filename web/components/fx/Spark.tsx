// Tiny odds path for one event, server-rendered.
export default function Spark({ path, w = 120, h = 34 }: { path: { m: number; p: number }[]; w?: number; h?: number }) {
  if (!path?.length) return <svg width={w} height={h} aria-hidden="true" />;
  const ms = path.map((x) => x.m), ps = path.map((x) => x.p);
  const [m0, m1, p0, p1] = [Math.min(...ms), Math.max(...ms), Math.min(...ps), Math.max(...ps)];
  const X = (m: number) => 2 + ((m - m0) / (m1 - m0 || 1)) * (w - 4);
  const Y = (p: number) => h - 3 - ((p - p0) / (p1 - p0 || 1)) * (h - 6);
  const d = path.map((x, i) => `${i ? "L" : "M"}${X(x.m).toFixed(1)} ${Y(x.p).toFixed(1)}`).join("");
  const zero = X(0);
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} className="spark" aria-hidden="true">
      <line x1={zero} x2={zero} y1={0} y2={h} />
      <path d={d} />
      <circle cx={X(path.at(-1)!.m)} cy={Y(path.at(-1)!.p)} r="2.5" />
    </svg>
  );
}
