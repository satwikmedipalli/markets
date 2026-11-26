// Ticker tape: every contract's last measured odds and the move that put it there. CSS-only marquee.
export type Tick = { sym: string; val: string; chg?: number; unit?: string };

export default function Ticker({ items }: { items: Tick[] }) {
  const row = (aria: boolean) => (
    <ul className="tape-row" aria-hidden={aria || undefined}>
      {items.map((t, i) => (
        <li key={i}>
          <span className="sym">{t.sym}</span>
          <span className="val">{t.val}</span>
          {t.chg != null && (
            <span className={t.chg >= 0 ? "up" : "dn"}>{t.chg >= 0 ? "▲" : "▼"} {Math.abs(t.chg).toFixed(1)}{t.unit ?? ""}</span>
          )}
        </li>
      ))}
    </ul>
  );
  return <div className="tape" role="marquee" aria-label="Contracts and measured moves">{row(false)}{row(true)}</div>;
}
