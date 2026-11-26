import Hedge from "@/components/Hedge";
import { allBetas, meta } from "@/lib/data";

export const metadata = { title: "Hedge calculator · Priced In" };

export default function HedgePage() {
  return (
    <div className="page">
      <div className="pagehead">
      <div className="kicker">Tool</div>
      <h1>Hedge <em>calculator</em></h1>
      <p className="lede">Enter positions and an event. Priced In returns the number of event contracts that offsets the portfolio's measured exposure to that event's odds.</p>
      </div>
      <Hedge families={meta().families} betas={allBetas()} />
    </div>
  );
}
