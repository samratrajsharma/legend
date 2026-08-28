import React, { useState, useEffect } from 'react';
import Navbar from './Navbar';
import Footer from './Footer';
import { DOCS_URL, GITHUB_URL } from './links';
import './Legend.css';

type Line = [string, string?][];

// ── Per-file source shown on screen — each graph below is derived from it ──
const CODE_REFUNDS: Line[] = [
  [['# api/refunds.py', 'com']],
  [['from ', 'kw'], ['ledger', 'mod'], [' import ', 'kw'], ['post_entry', 'fn']],
  [['from ', 'kw'], ['auth', 'mod'], [' import ', 'kw'], ['require_scope', 'fn']],
  [['']],
  [['class ', 'kw'], ['RefundService', 'cls'], [':']],
  [['    @', 'deco'], ['require_scope', 'deco'], ['("refunds")', 'punct']],
  [['    def ', 'kw'], ['refund', 'fn'], ['(self, pid, amount):', 'self']],
  [['        p = self.db.', 'self'], ['get', 'fn'], ['(pid)', 'punct']],
  [['        if ', 'kw'], ['amount > p.total', 'punct'], [':']],
  [['            raise ', 'kw'], ['ValueError', 'cls'], ['("over-refund")', 'str']],
  [['        post_entry', 'fn'], ['(p.account, -amount)', 'punct']],
  [['        return ', 'kw'], ['Refund', 'cls'], ['(pid, amount)', 'punct']],
];
const CODE_LEDGER: Line[] = [
  [['# services/ledger.py', 'com']],
  [['from ', 'kw'], ['db', 'mod'], [' import ', 'kw'], ['session', 'fn']],
  [['from ', 'kw'], ['models', 'mod'], [' import ', 'kw'], ['Entry', 'cls']],
  [['']],
  [['def ', 'kw'], ['post_entry', 'fn'], ['(account, amount):', 'self']],
  [['    e = ', 'self'], ['Entry', 'cls'], ['(account, amount)', 'punct']],
  [['    session.', 'self'], ['add', 'fn'], ['(e)', 'punct']],
  [['    session.', 'self'], ['commit', 'fn'], ['()', 'punct']],
  [['    return ', 'kw'], ['e.id', 'punct']],
  [['']],
  [['def ', 'kw'], ['balance', 'fn'], ['(account):', 'self']],
  [['    return ', 'kw'], ['query', 'fn'], ['(account).sum()', 'punct']],
];
const CODE_AUTH: Line[] = [
  [['# services/auth.py', 'com']],
  [['import ', 'kw'], ['jwt', 'mod']],
  [['from ', 'kw'], ['config', 'mod'], [' import ', 'kw'], ['SECRET', 'cls']],
  [['']],
  [['def ', 'kw'], ['require_scope', 'fn'], ['(scope):', 'self']],
  [['    def ', 'kw'], ['wrap', 'fn'], ['(fn):', 'self']],
  [['        claims = ', 'self'], ['verify', 'fn'], ['(token)', 'punct']],
  [['        if ', 'kw'], ['scope not in claims', 'punct'], [':']],
  [['            raise ', 'kw'], ['PermissionError', 'cls'], ['(scope)', 'punct']],
  [['        return ', 'kw'], ['fn', 'fn']],
  [['    return ', 'kw'], ['wrap', 'fn']],
];
const CODE_USER: Line[] = [
  [['# models/user.py', 'com']],
  [['from ', 'kw'], ['db', 'mod'], [' import ', 'kw'], ['Base', 'cls']],
  [['']],
  [['class ', 'kw'], ['User', 'cls'], ['(', 'punct'], ['Base', 'cls'], ['):', 'punct']],
  [['    __tablename__ = ', 'self'], ['"users"', 'str']],
  [['    id = ', 'self'], ['Column', 'fn'], ['(Integer, pk=True)', 'punct']],
  [['    email = ', 'self'], ['Column', 'fn'], ['(String)', 'punct']],
  [['    name = ', 'self'], ['Column', 'fn'], ['(String)', 'punct']],
  [['']],
  [['    def ', 'kw'], ['display', 'fn'], ['(self):', 'self']],
  [['        return ', 'kw'], ['self.name or self.email', 'self']],
];

const FILES = [
  'src/', 'api/refunds.py', 'services/ledger.py', 'services/auth.py',
  'models/user.py', 'utils/cache.py', 'main.py', 'tests/test_api.py',
];

interface FileSet { name: string; tab: string; active: string; step: string; stat: string; code: Line[]; detects: string[]; }
const FILESETS: FileSet[] = [
  { name: 'dependency graph', tab: 'api/refunds.py', active: 'api/refunds.py', step: 'Resolving imports of refunds.py', stat: '4 deps', code: CODE_REFUNDS, detects: ['import · ledger.post_entry', 'import · auth.require_scope', 'raise · ValueError'] },
  { name: 'call flow', tab: 'services/ledger.py', active: 'services/ledger.py', step: 'Tracing calls in ledger.py', stat: '6 calls', code: CODE_LEDGER, detects: ['fn · post_entry', 'call · session.commit', 'fn · balance'] },
  { name: 'file tree', tab: 'services/auth.py', active: 'services/auth.py', step: 'Walking the repository tree', stat: '42 files', code: CODE_AUTH, detects: ['import · jwt', 'fn · require_scope', 'raise · PermissionError'] },
  { name: 'code health', tab: 'models/user.py', active: 'models/user.py', step: 'Scoring complexity per module', stat: 'avg cx 3.4', code: CODE_USER, detects: ['class · User', 'column · email', 'method · display'] },
];

// mode 0 — dependency graph of refunds.py (its real imports / uses)
interface GNode { id: string; x: number; y: number; }
const NODES: GNode[] = [
  { id: 'refunds', x: 86, y: 32 },
  { id: 'ledger', x: 34, y: 118 }, { id: 'auth', x: 138, y: 118 },
  { id: 'Refund', x: 56, y: 210 }, { id: 'ValueError', x: 120, y: 210 },
];
const EDGES: [string, string][] = [
  ['refunds', 'ledger'], ['refunds', 'auth'], ['refunds', 'Refund'], ['refunds', 'ValueError'],
];
const nodeOf = (id: string) => NODES.find((n) => n.id === id) as GNode;
function edgePath(aId: string, bId: string): string {
  const a = nodeOf(aId), b = nodeOf(bId);
  const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
  const dx = b.x - a.x, dy = b.y - a.y;
  const len = Math.hypot(dx, dy) || 1;
  const off = 10;
  return 'M' + a.x + ',' + a.y + ' Q' + (mx + (-dy / len) * off) + ',' + (my + (dx / len) * off) + ' ' + b.x + ',' + b.y;
}
// mode 1 — call flow of ledger.py: post_entry() -> Entry -> session.add -> session.commit
const CALL = ['post_entry()', 'Entry()', 'session.add()', 'session.commit()'];
// mode 2 — repo file tree (matches the sidebar folders)
const TREE_N = [
  { x: 90, y: 22, l: 'src' },
  { x: 40, y: 94, l: 'api' }, { x: 92, y: 94, l: 'services' }, { x: 144, y: 94, l: 'models' },
  { x: 30, y: 168, l: 'refunds' }, { x: 74, y: 168, l: 'ledger' }, { x: 114, y: 168, l: 'auth' }, { x: 152, y: 168, l: 'user' },
];
const TREE_E: [number, number][] = [[0, 1], [0, 2], [0, 3], [1, 4], [2, 5], [2, 6], [3, 7]];
// mode 3 — health by module (the scanned files)
const BARS: { l: string; h: number; c: string }[] = [
  { l: 'refunds', h: 150, c: 'hot' }, { l: 'ledger', h: 96, c: 'ok' }, { l: 'auth', h: 120, c: 'warn' },
  { l: 'user', h: 58, c: 'ok' }, { l: 'cache', h: 74, c: 'ok' }, { l: 'main', h: 88, c: 'ok' },
];

function renderViz(mode: number) {
  if (mode === 0) {
    return (
      <svg viewBox="0 0 172 250" className="viz" preserveAspectRatio="xMidYMid meet">
        <defs>
          <marker id="kyc-arrow" viewBox="0 0 8 8" refX="6.4" refY="4" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
            <path d="M1 1 L6.4 4 L1 7" fill="none" stroke="#1DB954" strokeWidth="1.2" />
          </marker>
        </defs>
        {EDGES.map(([a, b], i) => (
          <path key={i} className="viz-edge" d={edgePath(a, b)} markerEnd="url(#kyc-arrow)" style={{ animationDelay: (0.6 + i * 0.32) + 's' }} />
        ))}
        {NODES.map((n, i) => { const w = n.id.length * 5.2 + 16; return (
          <g key={n.id} className="viz-gnode" style={{ animationDelay: (i * 0.34) + 's' }}>
            <rect x={n.x - w / 2} y={n.y - 9} width={w} height={18} rx={5} />
            <text x={n.x} y={n.y + 0.5} textAnchor="middle" dominantBaseline="central">{n.id}</text>
          </g>
        ); })}
      </svg>
    );
  }
  if (mode === 1) {
    const cy = (i: number) => 34 + i * 62;
    return (
      <svg viewBox="0 0 160 250" className="viz" preserveAspectRatio="xMidYMid meet">
        <defs>
          <marker id="viz-arr" viewBox="0 0 8 8" refX="6.4" refY="4" markerWidth="5" markerHeight="5" orient="auto">
            <path d="M1 1 L6.4 4 L1 7" fill="none" stroke="#1DB954" strokeWidth="1.2" />
          </marker>
        </defs>
        {[0, 1, 2].map((i) => (
          <line key={i} className="viz-edge" x1="80" y1={cy(i) + 11} x2="80" y2={cy(i + 1) - 11} markerEnd="url(#viz-arr)" style={{ animationDelay: (0.6 + i * 0.34) + 's' }} />
        ))}
        {CALL.map((c, i) => (
          <g key={i} className="viz-gnode" style={{ animationDelay: (i * 0.38) + 's' }}>
            <rect x="19" y={cy(i) - 11} width="122" height="22" rx="11" />
            <text x="80" y={cy(i) + 0.5} textAnchor="middle" dominantBaseline="central">{c}</text>
          </g>
        ))}
      </svg>
    );
  }
  if (mode === 2) {
    return (
      <svg viewBox="0 0 184 226" className="viz" preserveAspectRatio="xMidYMid meet">
        {TREE_E.map(([a, b], i) => { const A = TREE_N[a], B = TREE_N[b]; return (
          <line key={i} className="viz-edge" x1={A.x} y1={A.y + 8} x2={B.x} y2={B.y - 8} style={{ animationDelay: (0.4 + i * 0.2) + 's' }} />
        ); })}
        {TREE_N.map((n, i) => { const w = n.l.length * 5 + 13; return (
          <g key={i} className="viz-gnode" style={{ animationDelay: (i * 0.22) + 's' }}>
            <rect x={n.x - w / 2} y={n.y - 8} width={w} height={16} rx={4} />
            <text x={n.x} y={n.y + 0.5} textAnchor="middle" dominantBaseline="central">{n.l}</text>
          </g>
        ); })}
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 184 224" className="viz" preserveAspectRatio="xMidYMid meet">
      <line className="viz-axis" x1="12" y1="188" x2="176" y2="188" />
      {BARS.map((b, i) => { const x = 18 + i * 27; return (
        <g key={i}>
          <rect className={'viz-bar viz-bar--' + b.c} x={x} y={188 - b.h} width="17" height={b.h} rx="3" style={{ animationDelay: (i * 0.28) + 's' }} />
          <text className="viz-blabel" x={x + 9} y="204" textAnchor="end" transform={'rotate(-42 ' + (x + 9) + ' 204)'} style={{ animationDelay: (0.2 + i * 0.28) + 's' }}>{b.l}</text>
        </g>
      ); })}
    </svg>
  );
}

// ── Final output — Overview of THIS repo (payments-service) ──
const STATS: { n: string; l: string; c?: string }[] = [
  { n: '42', l: 'files', c: 'g' }, { n: '168', l: 'symbols' }, { n: '311', l: 'edges' },
  { n: '214', l: 'chunks' }, { n: '6,420', l: 'LOC', c: 'g' }, { n: '3.4', l: 'avg cx', c: 'a' },
];
const LANGS: { name: string; pct: number }[] = [
  { name: 'python', pct: 92 }, { name: 'sql', pct: 26 }, { name: 'markdown', pct: 22 }, { name: 'yaml', pct: 16 },
];
const HUB: { f: string; v: number }[] = [
  { f: 'core/db.py', v: 18 }, { f: 'core/config.py', v: 16 },
  { f: 'services/ledger.py', v: 14 }, { f: 'models/user.py', v: 11 }, { f: 'services/auth.py', v: 9 },
];
const COMPLEX: { s: string; v: number }[] = [
  { s: 'RefundService.refund', v: 31 }, { s: 'require_scope', v: 22 },
  { s: 'post_entry', v: 18 }, { s: 'verify', v: 14 }, { s: 'balance', v: 11 },
];
const UNUSED: { s: string; f: string }[] = [
  { s: 'legacy_charge', f: 'services/ledger.py' }, { s: '_debug_dump', f: 'utils/cache.py' },
  { s: 'old_balance', f: 'services/ledger.py' }, { s: 'upgrade', f: 'alembic/env.py' }, { s: 'downgrade', f: 'alembic/env.py' },
];

const STAGE_MS = [4200, 4200, 4200, 4200, 5800];

const STEPS = [
  { n: '01', title: 'Connect a repo', body: 'Point it at any local folder or Git URL. It clones, walks the tree, and works out what is actually source — no config, no project file.' },
  { n: '02', title: 'Parse & map', body: 'Every file is parsed into symbols, and imports and call sites are resolved into one dependency graph of the whole project.' },
  { n: '03', title: 'Index & embed', body: 'Symbols and code chunks are indexed for both keyword and semantic search, so the right code can be retrieved for any question.' },
  { n: '04', title: 'Understand & track', body: 'Ask questions, read per-file explanations, take a guided tour — then capture the repo over time to see exactly what changed.' },
];

interface Feature { title: string; desc: string; }
const FEATURES: Feature[] = [
  { title: 'Codebase Mapping', desc: 'Maps modules, files, symbols, and the dependency graph that ties them together.' },
  { title: 'Per-File Explanations', desc: 'Clear, sectioned explanations of what each file and module actually does.' },
  { title: 'Ask Your Codebase', desc: 'Plain-English answers grounded in your code, powered by your own LLM.' },
  { title: 'Living Timeline', desc: 'An append-only log of what was added, removed, or refactored since you last looked.' },
  { title: 'Trends & Health', desc: 'Watch complexity, dead code, and coupling drift up or down over weeks.' },
  { title: 'AI Narration', desc: 'Raw diffs become a plain-English “what changed” story — multi-repo, fully local.' },
];

function letters(text: string, base: number, green: boolean) {
  return text.split('').map((ch, i) => (
    <span key={i} className={'kyc-ltr' + (green ? ' kyc-ltr--g' : '')} style={{ animationDelay: (base + i * 0.04) + 's' }}>
      {ch === ' ' ? ' ' : ch}
    </span>
  ));
}

const Legend: React.FC = () => {
  const [stage, setStage] = useState(0);
  const [copied, setCopied] = useState(false);
  const copyInstall = () => {
    try {
      navigator.clipboard.writeText('uvx legend-lens .');
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch { /* clipboard unavailable on non-HTTPS hosts */ }
  };
  useEffect(() => {
    const id = window.setTimeout(() => setStage((s) => (s + 1) % 5), STAGE_MS[stage]);
    return () => window.clearTimeout(id);
  }, [stage]);

  const scanning = stage < 4;
  const fs = FILESETS[scanning ? stage : 0];

  return (
    <div className="app kyc-page">
      <Navbar />
      <main>
        {/* ── Hero — scanning laptop ── */}
        <section className="kyc-hero" id="kyc-top">
          <div className="kyc-hero__bg" aria-hidden="true" />
          <div className="container kyc-hero__inner">
            <h1 className="kyc-hero__title" aria-label="Open a repo you have never seen. Understand it in minutes.">
              <span className="kyc-hero__line" aria-hidden="true">{letters('Open a repo you have never seen.', 0, false)}</span>
              <span className="kyc-hero__line" aria-hidden="true">{letters('Understand it in minutes.', 1.45, true)}</span>
            </h1>

            <div className={'kyc-laptop' + (scanning ? '' : ' kyc-laptop--done')} aria-hidden="true">
              <div className="kyc-laptop__screen">
                <div className="kyc-ide">
                  {scanning ? (
                    <>
                      <div className="kyc-ide__chrome">
                        <span className="kyc-ide__dots"><i /><i /><i /></span>
                        <span className="kyc-ide__tab">{fs.tab}</span>
                        <span className="kyc-ide__live"><span className="kyc-ide__pulse" /> scan · {fs.name}</span>
                      </div>

                      <div className="kyc-ide__main" key={stage}>
                        <aside className="kyc-tree">
                          {FILES.map((f, i) => (
                            <div className={'kyc-tree__row' + (f === fs.active ? ' kyc-tree__row--active' : '')} key={f} style={{ animationDelay: i * 0.12 + 's' }}>
                              <span className="kyc-tree__check" style={{ animationDelay: i * 0.12 + 's' }} />
                              <span className="kyc-tree__name">{f}</span>
                            </div>
                          ))}
                        </aside>

                        <div className="kyc-code">
                          <div className="kyc-code__scroll">
                            {fs.code.map((line, i) => (
                              <div className="kyc-code__row" key={i}>
                                <span className="kyc-code__ln">{i + 1}</span>
                                <span className="kyc-code__txt">
                                  {line.map((tok, j) => (
                                    <span key={j} className={tok[1] ? 't-' + tok[1] : ''}>{tok[0]}</span>
                                  ))}
                                </span>
                              </div>
                            ))}
                          </div>
                          <div className="kyc-scan" />
                          <div className="kyc-scan__line"><span className="kyc-scan__tag">scanning…</span></div>
                          {fs.detects.map((d, i) => (
                            <span key={i} className={'kyc-detect kyc-detect--' + (i + 1)}>{d}</span>
                          ))}
                        </div>

                        <div className="kyc-graph">{renderViz(stage)}</div>
                      </div>

                      <div className="kyc-ide__hud" key={'h' + stage}>
                        <div className="kyc-hud__bar"><span className="kyc-hud__fill" /></div>
                        <span className="kyc-hud__pct" />
                        <span className="kyc-hud__step">{fs.step}…</span>
                        <span className="kyc-hud__stat">{fs.stat}</span>
                      </div>
                    </>
                  ) : (
                    <>
                      <div className="kyc-ide__chrome">
                        <span className="kyc-ide__dots"><i /><i /><i /></span>
                        <span className="kyc-ide__tab">Overview · payments-service</span>
                        <span className="kyc-ide__live kyc-ide__live--done"><span className="kyc-ide__pulse" /> scan complete</span>
                      </div>
                      <div className="kyc-dash">
                        <div className="kyc-dash__stats">
                          {STATS.map((s, i) => (
                            <div className="kyc-dstat" key={s.l} style={{ animationDelay: (i * 0.07) + 's' }}>
                              <span className={'kyc-dstat__n' + (s.c === 'g' ? ' is-green' : s.c === 'a' ? ' is-amber' : '')}>{s.n}</span>
                              <span className="kyc-dstat__l">{s.l}</span>
                            </div>
                          ))}
                        </div>
                        <div className="kyc-dash__grid">
                          <div className="kyc-dpanel">
                            <h4>Languages</h4>
                            {LANGS.map((l, i) => (
                              <div className="kyc-drow" key={l.name} style={{ animationDelay: (0.25 + i * 0.06) + 's' }}>
                                <span className="kyc-drow__name">{l.name}</span>
                                <span className="kyc-dbar"><span style={{ width: l.pct + '%', animationDelay: (0.35 + i * 0.08) + 's' }} /></span>
                              </div>
                            ))}
                          </div>
                          <div className="kyc-dpanel">
                            <h4>Most complex symbols</h4>
                            {COMPLEX.map((c, i) => (
                              <div className="kyc-drow" key={c.s} style={{ animationDelay: (0.25 + i * 0.06) + 's' }}>
                                <span className="kyc-drow__sym">{c.s}</span>
                                <span className="kyc-drow__v">{c.v}</span>
                              </div>
                            ))}
                          </div>
                          <div className="kyc-dpanel">
                            <h4>Hub files</h4>
                            {HUB.map((h, i) => (
                              <div className="kyc-drow" key={h.f} style={{ animationDelay: (0.3 + i * 0.06) + 's' }}>
                                <span className="kyc-drow__sym">{h.f}</span>
                                <span className="kyc-drow__v kyc-drow__v--g">{h.v}</span>
                              </div>
                            ))}
                          </div>
                          <div className="kyc-dpanel">
                            <h4>Likely unused</h4>
                            {UNUSED.map((u, i) => (
                              <div className="kyc-drow" key={u.s + i} style={{ animationDelay: (0.3 + i * 0.06) + 's' }}>
                                <span className="kyc-drow__sym">{u.s}</span>
                                <span className="kyc-drow__path">{u.f}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                    </>
                  )}
                </div>
              </div>
              <div className="kyc-laptop__base"><span className="kyc-laptop__lip" /></div>
              <div className="kyc-laptop__shadow" />
            </div>

            <div className="kyc-prog" aria-hidden="true">
              <span className="kyc-prog__cap">Input</span>
              <span className="kyc-prog__track"><span className="kyc-prog__fill" style={{ width: (((stage + 1) / 5) * 100) + '%' }} /></span>
              <span className={'kyc-prog__cap' + (scanning ? '' : ' is-on')}>Output</span>
            </div>
          </div>
        </section>

        {/* ── How it works ── */}
        <section className="kyc-how" id="how-it-works">
          <div className="container">
            <div className="kyc-sec-head">
              <span className="kyc-eyebrow">How it works</span>
              <h2 className="kyc-sec-title">From a cold repo to a living map</h2>
              <p className="kyc-sec-sub">What actually happens between “point it at a folder” and “ask it anything.”</p>
            </div>
            <div className="kyc-steps">
              {STEPS.map((s) => (
                <div className="kyc-step" key={s.n}>
                  <div className="kyc-step__head"><span className="kyc-step__dot" /><span className="kyc-step__n">{s.n}</span></div>
                  <h3 className="kyc-step__title">{s.title}</h3>
                  <p className="kyc-step__body">{s.body}</p>
                </div>
              ))}
            </div>
            <p className="kyc-how__note">
              Every step runs on your machine. Bring your own LLM — OpenAI, Anthropic, Groq, or a local
              Ollama model — for explanations and Q&amp;A. <span className="kyc-accent">Your code never leaves your computer.</span>
            </p>
          </div>
        </section>

        {/* ── Features ── */}
        <section className="kyc-features" id="what-you-get">
          <div className="container">
            <div className="kyc-sec-head">
              <span className="kyc-eyebrow">What you get</span>
              <h2 className="kyc-sec-title">Everything you need to actually know a codebase</h2>
              <p className="kyc-sec-sub">
                Not a one-time analyzer — a living understanding of your project that stays current as
                you and your AI tools reshape it.
              </p>
            </div>
            <div className="kyc-deck">
              {FEATURES.map((f, i) => (
                <article className="kyc-block" key={f.title}>
                  <div className="kyc-block__inner">
                    <span className="kyc-block__num">{('0' + (i + 1)).slice(-2)}</span>
                    <h3 className="kyc-block__title">{f.title}</h3>
                    <p className="kyc-block__desc">{f.desc}</p>
                    <span className="kyc-block__ghost" aria-hidden="true">{('0' + (i + 1)).slice(-2)}</span>
                  </div>
                </article>
              ))}
            </div>
          </div>
        </section>

        {/* ── Closing CTA ── */}
        <section className="kyc-cta" id="install">
          <div className="container kyc-cta__inner">
            <h2 className="kyc-cta__title">Run it on your own codebase.</h2>
            <p className="kyc-cta__sub">
              Legend is open source and runs entirely on your machine. Install it, point it at any
              repository, and the map builds itself — your code never leaves your computer.
            </p>
            <div className="kyc-install">
              <span className="kyc-install__cmd"><span className="kyc-install__sym">$</span> uvx <span className="kyc-install__pkg">legend-lens</span> .</span>
              <button type="button" className={'kyc-install__copy' + (copied ? ' is-ok' : '')} onClick={copyInstall} aria-label={copied ? 'Copied' : 'Copy install command'}>
                {copied ? (
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg>
                ) : (
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" /><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" /></svg>
                )}
              </button>
            </div>
            <span className="kyc-install__hint">runs instantly with <a href="https://docs.astral.sh/uv/" target="_blank" rel="noopener noreferrer">uv</a> — or install it: <code>pipx install legend-lens</code> · <code>pip install legend-lens</code></span>
            <div className="kyc-cta__actions">
              <a href={DOCS_URL} className="kyc-btn kyc-btn--green" target="_blank" rel="noopener noreferrer">Read the docs →</a>
              <a href={GITHUB_URL} className="kyc-btn kyc-btn--ghost" target="_blank" rel="noopener noreferrer">View on GitHub</a>
            </div>
          </div>
        </section>
      </main>
      <Footer />
    </div>
  );
};

export default Legend;
