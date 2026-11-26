export const metadata = { title: "API & MCP · Priced In" };

export default function Api() {
  return (
    <div className="prose page pagehead">
      <div className="kicker">For programs and assistants</div>
      <h1>API &amp; <em>MCP</em></h1>
      <p className="lede">The same numbers as the site, served read-only as JSON and as tools an AI assistant can call.</p>

      <h2>Static JSON</h2>
      <p>Every file the site uses is public:</p>
      <pre>{`GET /data/meta.json              families, audit, study parameters
GET /data/betas.json             every event beta with CIs, placebo/shuffle p, q, survives
GET /data/leadlag.json           lead-lag coefficients and verdicts
GET /data/families/{id}.json     one family: events, quality, betas, lead-lag, paths`}</pre>

      <h2>REST API</h2>
      <pre>{`uv run uvicorn pricedin.api:app --port 8300

GET  /v1/families
GET  /v1/betas?ticker=KRE&survives_only=true
GET  /v1/leadlag/fomc
GET  /v1/quality/fomc
POST /v1/hedge   {"family": "fomc", "positions": {"KRE": 250000}}`}</pre>

      <h2>MCP server</h2>
      <p>Add it to Claude Code, then ask: <em>“What's priced in for regional banks ahead of the Fed meeting?”</em></p>
      <pre>{`claude mcp add pricedin -- uv --directory ~/pricedin run python -m pricedin.mcp_server`}</pre>
      <p>Tools: <code>list_events()</code>, <code>get_event_betas(ticker)</code>, <code>lead_lag(event)</code>, <code>hedge(portfolio, event)</code>. Every response carries the co-movement caveat.</p>
    </div>
  );
}
