import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Priced In · Who knew first?",
  description: "Kalshi odds against minute-by-minute stock prices: which stocks move with the odds, by how much, and which market moves first.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,400..900&family=JetBrains+Mono:wght@400;500;600;700&display=swap"
        />
      </head>
      <body>
        <header className="top">
          <div className="wrap">
            <Link href="/" className="brand" aria-label="Priced In, home">
              <b>Priced<i>In</i></b><span className="cur" aria-hidden="true" />
              <small>by Satwik Medipalli</small>
            </Link>
            <nav className="links">
              <Link href="/#race"><span className="fk">F1</span>Race</Link>
              <Link href="/#story"><span className="fk">F2</span>How</Link>
              <Link href="/#board"><span className="fk">F3</span>Board</Link>
              <Link href="/hedge/"><span className="fk">F4</span>Hedge</Link>
              <Link href="/methods/"><span className="fk">F5</span>Method</Link>
              <Link href="/api/"><span className="fk">F6</span>API</Link>
            </nav>
          </div>
        </header>
        <main><div className="wrap">{children}</div></main>
        <footer>
          <div className="wrap">
            <span>Computed statistics only. Co-movement, not causation. Not investment advice.</span>
            <span>Data: Kalshi · Alpaca SIP</span>
            <span className="me">
              Satwik Medipalli: <a href="https://satwikmedipalli.dev">Portfolio</a> · <a href="https://github.com/satwikmedipalli">GitHub</a> · <a href="https://linkedin.com/in/medipalli-satwik">LinkedIn</a>
            </span>
          </div>
        </footer>
      </body>
    </html>
  );
}
