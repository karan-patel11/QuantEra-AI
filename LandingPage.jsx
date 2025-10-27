import React, { useState } from "react";

// --- Fancy, Simple QE Logo (Header) ---
function QuantEraLogo({ size = 90 }) {
  return (
    <div
      className="rounded-full flex items-center justify-center mx-auto shadow-lg"
      style={{
        width: size,
        height: size,
        background: "linear-gradient(135deg,#06b6d4 40%,#0ea5e9 90%,#10b981 100%)",
        boxShadow: "0 6px 36px #06b6d4aa, 0 2px 14px #0ea5e9bb",
      }}
    >
      <span
        style={{
          fontWeight: 900,
          fontSize: size * 0.48,
          color: "#fff",
          letterSpacing: "0.07em",
          fontFamily: "Inter,ui-sans-serif,sans-serif",
        }}
      >
        QE
      </span>
    </div>
  );
}

// --- Sparkle Icon, animates on hover ---
function Sparkle({ animate }) {
  return (
    <svg
      width="38"
      height="38"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden
      className={animate ? "animate-spin-slow" : ""}
    >
      <path
        d="M12 2l1.8 4.4L18 8l-4.2 1.6L12 14l-1.8-4.4L6 8l4.2-1.6L12 2z"
        fill="#06b6d4"
        opacity="0.95"
      />
    </svg>
  );
}

// --- Statement Section ---
function ChatGPTStatement() {
  return (
    <div className="mt-7 max-w-3xl mx-auto text-center text-slate-200">
      <h3 className="text-xl font-semibold mb-2">LLMs & QuantEra — Changing the game</h3>
      <ul className="text-left inline-block text-sm leading-relaxed">
        <li>— Multi-agent collaboration for holistic market insight</li>
        <li>— Natural-language explanations for transparency</li>
        <li>— Continuous learning from streaming market data</li>
        <li>— Instant scenario simulations and risk previews</li>
      </ul>
    </div>
  );
}

export default function QuantEraLanding() {
  const [active, setActive] = useState(null);
  const [hovered, setHovered] = useState(null);

  const agents = [
    {
      id: 'news',
      title: 'News Oracle',
      short: 'Curates headlines & macro signals',
      long:
        'Scans global news, earnings, and filings in real-time. Extracts actionable events, ranks by impact, and routes to fusion engine for fast, proven insights.',
      colors: 'from-cyan-400 to-indigo-500',
    },
    {
      id: 'charts',
      title: 'Chart Sage',
      short: 'Finds structure in price action',
      long:
        'Identifies breakouts, momentum shifts, and technical anomalies using multi-horizon chart analysis. Gives traders probabilistic timing context.',
      colors: 'from-emerald-400 to-cyan-500',
    },
    {
      id: 'fund',
      title: 'Value Alchemist',
      short: 'Anchors decisions with fundamentals',
      long:
        'Evaluates earnings, cash flows, leverage, and growth metrics. Signals divergence from intrinsic value to combine short and long-term perspectives.',
      colors: 'from-indigo-400 to-purple-500',
    },
    {
      id: 'sentiment',
      title: 'Sentiment Whisperer',
      short: 'Quantifies crowd psychology',
      long:
        'Analyzes social streams and market commentary to detect mania or fear. Adjusts signals when crowd behavior skews market probabilities.',
      colors: 'from-pink-400 to-yellow-400',
    },
    {
      id: 'risk',
      title: 'Risk Sentinel',
      short: 'Protects capital and enforces constraints',
      long:
        'Monitors volatility, liquidity, and correlations. Implements dynamic position sizing, stop rules, and portfolio-level checks for sustainable decisions.',
      colors: 'from-yellow-300 to-orange-500',
    },
  ];

  return (
    <div className="min-h-screen bg-black text-white font-sans relative">
      <header className="max-w-7xl mx-auto px-6 pt-14 pb-8 text-center relative">
        <QuantEraLogo size={90} />
        <div className="mt-7 text-5xl md:text-7xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 via-emerald-400 to-fuchsia-400 drop-shadow-xl">
          QuantEra AI
        </div>
        <h1 className="mt-7 text-3xl md:text-5xl font-extrabold leading-tight shadow-xl">
          Transform trading with human-level AI insights
        </h1>
        <p className="mt-6 max-w-2xl mx-auto text-lg text-slate-300">
          Interactive agents analyze news, charts, fundamentals, sentiment, and risk. Explore their unique contributions and see how multi-agent fusion amplifies trading intelligence.
        </p>
        <div className="mt-8 flex items-center justify-center gap-5">
          <a href="#agents" className="rounded-full px-7 py-4 bg-gradient-to-r from-cyan-500 to-emerald-400 text-black font-bold shadow-xl text-lg hover:scale-105 transition">Meet the Agents</a>
          <a href="#demo" className="px-6 py-4 border border-white/10 rounded-full text-md text-slate-300 hover:bg-white/5">Request a Demo</a>
        </div>
        <ChatGPTStatement />
      </header>

      <section id="agents" className="max-w-7xl mx-auto px-6 pb-14 pt-3">
        <h2 className="text-3xl md:text-4xl font-extrabold mb-7 text-white">Interactive Agent Flow</h2>
        <p className="text-slate-400 mb-10 max-w-3xl mx-auto">
          Click each agent to see how its insights impact trading and why it's essential for market intelligence.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-7">
          {agents.map((a) => (
            <article
              key={a.id}
              tabIndex={0}
              aria-expanded={active === a.id}
              className={`relative rounded-2xl overflow-hidden shadow-2xl transform transition-all focus:ring-2 ring-cyan-400 ring-offset-2
                ${active === a.id ? "scale-105 z-10" : "hover:scale-104"}
              `}
              onMouseEnter={() => setHovered(a.id)}
              onMouseLeave={() => setHovered(null)}
              onClick={() => setActive(active === a.id ? null : a.id)}
              onKeyPress={e => { if (e.key === 'Enter' || e.key === ' ') setActive(active === a.id ? null : a.id); }}
            >
              <div className={`p-6 cursor-pointer bg-gradient-to-br ${a.colors}`}>
                <div className="flex items-center gap-4">
                  <div className="w-14 h-14 flex items-center justify-center">
                    <Sparkle animate={hovered === a.id}/>
                  </div>
                  <div>
                    <h3 className="text-lg font-bold text-white">{a.title}</h3>
                    <p className="text-sm text-white/90 mt-1">{a.short}</p>
                  </div>
                </div>
                <div className={`mt-4 text-sm text-white/90 transition-all duration-300 ease-in
                  ${active === a.id ? "max-h-44 opacity-100" : "max-h-0 opacity-0 overflow-hidden"}
                `}>
                  <p>{a.long}</p>
                </div>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section id="demo" className="max-w-4xl mx-auto px-6 py-14 text-center">
  <h3 className="text-2xl font-extrabold mb-3">Want to collaborate?</h3>
  <p className="text-slate-300 mb-8">
    Have an idea, a project, or just want to chat about AI in finance? <br />
    Reach out—let’s build the future, together.
  </p>
  <a
    href="mailto:hello@quanterai.example"
    className="inline-block rounded-full bg-gradient-to-r from-cyan-500 to-emerald-400 px-7 py-4 font-bold text-black shadow-xl text-lg hover:scale-105 transition"
  >
    Reach Out
  </a>
</section>


      <footer className="mt-14 border-t border-white/8 py-7 text-center text-slate-400">
        <div>© {new Date().getFullYear()} QuantEra AI — Concept & in development</div>
        <div className="text-sm mt-1">For analysts, PMs, and teams who demand speed, transparency, and auditable insights.</div>
      </footer>

      {/* Fancy slow spin animation for sparkle */}
      <style>{`
        .animate-spin-slow {
          animation: spin 2.8s linear infinite;
        }
        @keyframes spin { 100% { transform: rotate(360deg); } }
        .hover\\:scale-104:hover { transform: scale(1.04); }
      `}</style>
    </div>
  );
}
