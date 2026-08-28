import { useEffect, useMemo, useRef, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { kycApi, CodemapData, CodemapArea } from '../../api/client';
import { useModalDialog } from '../../lib/useModalDialog';
import './Diagrams.css';

// ─────────────────────────────────────────────────────────────────
// Three-layer architecture view, all React-native (no iframe).
//   Layer 1 — Area Mindmap : SVG of colored area bubbles.
//   Layer 2 — Area Drill   : overlay with file cards.
//   Layer 3 — File Deep-Dive : source + tabbed analysis (Static / LLM).
// ─────────────────────────────────────────────────────────────────
export default function Diagrams() {
  const { repoId } = useParams<{ repoId: string }>();
  const [data, setData] = useState<CodemapData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [openArea, setOpenArea] = useState<string | null>(null);
  const [openFile, setOpenFile] = useState<string | null>(null);
  const [refreshTick, setRefreshTick] = useState(0);

  useEffect(() => {
    if (!repoId) return;
    setLoading(true); setError(null); setData(null);
    kycApi.codemapData(repoId, refreshTick)
      .then(r => setData(r.data))
      .catch(e => setError(e?.response?.data?.detail || e?.message || 'Failed to build architecture data'))
      .finally(() => setLoading(false));
  }, [repoId, refreshTick]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return;
      if (openFile) setOpenFile(null);
      else if (openArea) setOpenArea(null);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [openFile, openArea]);

  if (loading) return <div className="dash-loading">Building architecture map…</div>;
  if (error) return (
    <div>
      <div className="page-header"><h1>Insight Graph</h1></div>
      <div className="card">
        <div className="toast toast--err">{error}</div>
        <button className="btn btn--primary btn--sm" style={{ marginTop: 10 }} onClick={() => setRefreshTick(t => t + 1)}>Regenerate</button>
      </div>
    </div>
  );
  if (!data) return null;

  const s = data.stats;
  return (
    <div className="diag">
      <div className="page-header">
        <h1>Insight Graph</h1>
        <p>Three-layer view: directories (areas) → files inside → source + analysis. Click anywhere to drill down. Esc returns.</p>
      </div>

      <div className="diag__stats">
        <Stat label="Files" value={String(s.files)} accent="primary" />
        <Stat label="Lines" value={s.loc.toLocaleString()} />
        <Stat label="Areas" value={String(s.areas)} accent="success" />
        <Stat label="Edges" value={String(s.edges)} />
        <Stat label="Depth" value={String(s.depth)} />
      </div>

      <div className="card">
        <div className="diag__head">
          <h3>Layer 1 — Areas</h3>
          <div className="diag__actions">
            <button className="btn btn--secondary btn--sm" onClick={() => setRefreshTick(t => t + 1)}>Regenerate</button>
          </div>
        </div>
        <p className="diag__hint">
          <strong>Hover</strong> an area to trace dependencies · <strong>Click</strong> to open it · <strong>Drag</strong> to pan · <strong>Scroll</strong> to zoom · <strong>Double-click</strong> empty space to reset.
        </p>
        <AreaMindmap data={data} onAreaClick={setOpenArea} />
      </div>

      {openArea && (
        <AreaDrill
          data={data}
          areaId={openArea}
          onClose={() => setOpenArea(null)}
          onFileOpen={(rel) => setOpenFile(rel)}
        />
      )}

      {openFile && repoId && (
        <FileDeepDive
          data={data}
          repoId={repoId}
          fileRel={openFile}
          onClose={() => setOpenFile(null)}
          onJump={(rel) => setOpenFile(rel)}
        />
      )}
    </div>
  );
}

function Stat({ label, value, accent }: { label: string; value: string; accent?: 'success' | 'warning' | 'primary' }) {
  return (
    <div className="stat-card">
      <div className="stat-card__label">{label}</div>
      <div className={`stat-card__value${accent ? ' stat-card__value--' + accent : ''}`}>{value}</div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────
// Layer 1 — Area Mindmap (SVG) with dynamic box sizing
// ─────────────────────────────────────────────────────────────────
// Approximate "how wide is this text?" for a given font size.
// 12.5px Segoe UI / Roboto runs ~6.4px per char average.
const CHAR_W_TITLE = 6.8;
const CHAR_W_SUB   = 5.4;

function truncateToWidth(s: string, maxW: number, charW: number): string {
  const maxChars = Math.max(3, Math.floor(maxW / charW));
  return s.length > maxChars ? s.slice(0, maxChars - 1) + '…' : s;
}

function AreaMindmap({ data, onAreaClick }: { data: CodemapData; onAreaClick: (id: string) => void }) {
  const { areas, E, BANDNAME } = data;
  const [hoverId, setHoverId] = useState<string | null>(null);
  const W = 1600;
  const NB = BANDNAME.length;

  // Layout — areas are grouped into dependency bands. Within each band we WRAP
  // boxes onto as many sub-rows as needed and stack bands vertically, so nothing
  // overlaps no matter how many areas a large repo has. The canvas height grows
  // to fit; Fit / zoom / pan handle the rest.
  const MARGIN_X = 70, MARGIN_TOP = 60, BAND_GAP = 50, ROW_GAP = 22, BOX_GAP = 26;
  const layout = useMemo(() => {
    const maxLines = Math.max(...areas.map(a => a.lines), 1);
    const clamp = (lo: number, v: number, hi: number) => Math.max(lo, Math.min(hi, v));
    type AreaNode = CodemapArea & { w: number; h: number; cx: number; cy: number; nameDisplay: string; subDisplay: string };
    const nodes: AreaNode[] = [];
    const usable = W - MARGIN_X * 2;
    let y = MARGIN_TOP;

    for (let bi = 0; bi < NB; bi++) {
      const ns = areas.filter(a => a.band === bi);
      if (ns.length === 0) continue;                  // skip empty bands entirely
      const boxes = ns.map(a => {
        const sub = `${a.files} files · ${a.lines.toLocaleString()} ln`;
        const linesW = 118 + a.lines / maxLines * 150;
        const nameW  = a.name.length * CHAR_W_TITLE + 24;
        const subW   = sub.length * CHAR_W_SUB + 24;
        const w = clamp(122, Math.max(linesW, nameW, subW), 260);
        const h = clamp(40, 38 + a.lines / maxLines * 54, 92);
        return {
          a, w, h,
          nameDisplay: truncateToWidth(a.name, w - 16, CHAR_W_TITLE),
          subDisplay:  truncateToWidth(sub,   w - 16, CHAR_W_SUB),
        };
      });

      // Greedy wrap: fill a row until the next box would exceed the usable
      // width, then start a new row. Each row is centered.
      let row: typeof boxes = [];
      let rowW = 0, rowMaxH = 0;
      const flush = () => {
        const totalW = row.reduce((s, it) => s + it.w, 0) + BOX_GAP * Math.max(0, row.length - 1);
        let x = MARGIN_X + Math.max(0, (usable - totalW) / 2);
        for (const it of row) {
          nodes.push({
            ...it.a, w: it.w, h: it.h,
            cx: x + it.w / 2, cy: y + rowMaxH / 2,
            nameDisplay: it.nameDisplay, subDisplay: it.subDisplay,
          });
          x += it.w + BOX_GAP;
        }
        y += rowMaxH + ROW_GAP;
        row = []; rowW = 0; rowMaxH = 0;
      };
      for (const it of boxes) {
        const add = (row.length ? BOX_GAP : 0) + it.w;
        if (row.length && rowW + add > usable) flush();
        row.push(it); rowW += add; rowMaxH = Math.max(rowMaxH, it.h);
      }
      if (row.length) flush();
      y += BAND_GAP - ROW_GAP;                         // gap between bands
    }
    return { nodes, height: Math.max(480, y + MARGIN_TOP - BAND_GAP) };
  }, [areas, NB]);
  const positioned = layout.nodes;
  const H = layout.height;

  const byId = useMemo(() => {
    const m: Record<string, typeof positioned[0]> = {};
    positioned.forEach(a => { m[a.id] = a; });
    return m;
  }, [positioned]);

  const adj = useMemo(() => {
    const a: Record<string, { in: string[]; out: string[] }> = {};
    positioned.forEach(p => { a[p.id] = { in: [], out: [] }; });
    E.forEach(([s, t]) => {
      if (a[s] && a[t]) { a[s].out.push(t); a[t].in.push(s); }
    });
    return a;
  }, [positioned, E]);

  const isFocused = (id: string): boolean => {
    if (!hoverId) return true;
    if (id === hoverId) return true;
    const ax = adj[hoverId];
    if (!ax) return false;
    return ax.in.includes(id) || ax.out.includes(id);
  };

  const edgePath = (s: string, t: string): string => {
    const A = byId[s], B = byId[t];
    if (!A || !B) return '';
    const my = (A.cy + B.cy) / 2;
    return `M${A.cx},${A.cy} C${A.cx},${my} ${B.cx},${my} ${B.cx},${B.cy}`;
  };

  // ── Pan + zoom state. Zoom is intentionally gentle:
  //    wheel ticks step by ~5% (vs the 10% codemap uses) and zoom is bounded
  //    so the diagram can't shrink to a dot or balloon off-screen. Discrete
  //    buttons (− / Fit / +) give predictable jumps.
  const svgRef = useRef<SVGSVGElement | null>(null);
  const VB_INIT: [number, number, number, number] = [0, 0, W, H];
  const MIN_VB_W = 320;     // hard zoom-in limit (≈ 5×)
  const MAX_VB_W = W * 2.4; // hard zoom-out limit
  const WHEEL_STEP = 1.05;
  const BUTTON_STEP = 1.25;

  const vbRef = useRef<[number, number, number, number]>([...VB_INIT] as [number, number, number, number]);
  const dragRef = useRef<[number, number, number, number] | null>(null);

  const updateVB = () => {
    if (svgRef.current) svgRef.current.setAttribute('viewBox', vbRef.current.join(' '));
  };

  // Zoom keeping a focal point fixed (default = canvas center).
  const zoomBy = (factor: number, focusX?: number, focusY?: number) => {
    const vb = vbRef.current;
    // Compute candidate new width/height
    const aspect = vb[3] / vb[2];
    let newW = vb[2] * factor;
    if (newW < MIN_VB_W) newW = MIN_VB_W;
    if (newW > MAX_VB_W) newW = MAX_VB_W;
    if (Math.abs(newW - vb[2]) < 0.5) return; // saturated — no-op
    const newH = newW * aspect;
    // Use the actual SVG client rect to translate focus pixel → viewBox coord
    const r = svgRef.current?.getBoundingClientRect();
    let fx = vb[0] + vb[2] / 2;
    let fy = vb[1] + vb[3] / 2;
    if (r && focusX !== undefined && focusY !== undefined) {
      fx = vb[0] + ((focusX - r.left) / r.width)  * vb[2];
      fy = vb[1] + ((focusY - r.top)  / r.height) * vb[3];
    }
    const fxRel = (fx - vb[0]) / vb[2];
    const fyRel = (fy - vb[1]) / vb[3];
    vb[0] = fx - fxRel * newW;
    vb[1] = fy - fyRel * newH;
    vb[2] = newW;
    vb[3] = newH;
    updateVB();
  };

  const fit = () => {
    vbRef.current = [...VB_INIT] as [number, number, number, number];
    updateVB();
  };

  return (
    <div className="diag__mindmap">
      <div className="diag__legend">
        {BANDNAME.map((b, i) => (
          <span key={i} className="diag__legend-item">
            <span className="diag__legend-dot" />
            {b}
          </span>
        ))}
      </div>

      {/* Explicit, predictable zoom controls. */}
      <div className="diag__zoom-bar">
        <button className="diag__zoom-btn" title="Zoom out"     onClick={() => zoomBy(BUTTON_STEP)}>−</button>
        <button className="diag__zoom-btn" title="Fit to view"  onClick={fit}>Fit</button>
        <button className="diag__zoom-btn" title="Zoom in"      onClick={() => zoomBy(1 / BUTTON_STEP)}>+</button>
      </div>

      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="xMidYMid meet"
        className="diag__mindmap-svg"
        onWheel={(e) => {
          e.preventDefault();
          // Bounded, gentle wheel zoom centered on the cursor.
          const factor = e.deltaY > 0 ? WHEEL_STEP : 1 / WHEEL_STEP;
          zoomBy(factor, e.clientX, e.clientY);
        }}
        onMouseDown={(e) => {
          dragRef.current = [e.clientX, e.clientY, vbRef.current[0], vbRef.current[1]];
        }}
        onMouseMove={(e) => {
          if (!dragRef.current || !svgRef.current) return;
          const r = svgRef.current.getBoundingClientRect();
          const vb = vbRef.current;
          vb[0] = dragRef.current[2] - (e.clientX - dragRef.current[0]) / r.width * vb[2];
          vb[1] = dragRef.current[3] - (e.clientY - dragRef.current[1]) / r.height * vb[3];
          updateVB();
        }}
        onMouseUp={() => { dragRef.current = null; }}
        onMouseLeave={() => { dragRef.current = null; }}
        onDoubleClick={fit}
      >
        <defs>
          <marker id="diag-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M0,0 L10,5 L0,10 z" fill="#3a3a3a" />
          </marker>
          <marker id="diag-arrow-hi" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M0,0 L10,5 L0,10 z" fill="#1ED760" />
          </marker>
        </defs>

        <g>
          {E.map(([s, t], i) => {
            if (!byId[s] || !byId[t]) return null;
            const hit = hoverId === s || hoverId === t;
            return (
              <path
                key={i}
                d={edgePath(s, t)}
                fill="none"
                stroke={hit ? '#1ED760' : '#333333'}
                strokeOpacity={hit ? 0.95 : (hoverId ? 0.03 : 0.18)}
                strokeWidth={hit ? 2.4 : 1.2}
                markerEnd={hit ? 'url(#diag-arrow-hi)' : 'url(#diag-arrow)'}
              />
            );
          })}
        </g>

        <g>
          {positioned.map(a => (
            <g
              key={a.id}
              className={`diag__node${!isFocused(a.id) ? ' diag__node--dim' : ''}`}
              onMouseEnter={() => setHoverId(a.id)}
              onMouseLeave={() => setHoverId(null)}
              onClick={() => onAreaClick(a.id)}
              style={{ cursor: 'pointer' }}
              // Keyboard access for the Insight Graph (QA #42): each area is a focusable
              // button; Tab moves between areas, Enter/Space drills in, focus mirrors hover.
              tabIndex={0}
              role="button"
              aria-label={`${a.id}: ${a.files} files, ${a.lines.toLocaleString()} lines. Open area.`}
              onFocus={() => setHoverId(a.id)}
              onBlur={() => setHoverId(null)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onAreaClick(a.id); }
              }}
            >
              <title>{a.id}{'\n'}{a.files} files · {a.lines.toLocaleString()} lines</title>
              <rect
                x={a.cx - a.w / 2} y={a.cy - a.h / 2}
                width={a.w} height={a.h} rx={9}
                fill={hoverId === a.id ? '#1f1f1f' : '#181818'}
                stroke={hoverId === a.id ? '#1ED760' : '#2c2c2c'}
                strokeWidth={hoverId === a.id ? 2 : 1.25}
              />
              <text x={a.cx} y={a.cy - 2} textAnchor="middle" fontSize={12.5} fontWeight={600} fill="#ffffff">
                {a.nameDisplay}
              </text>
              <text x={a.cx} y={a.cy + 13} textAnchor="middle" fontSize={10} fill="#a7a7a7" opacity={0.9}>
                {a.subDisplay}
              </text>
            </g>
          ))}
        </g>
      </svg>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────
// Layer 2 — Area Drill
// ─────────────────────────────────────────────────────────────────
function AreaDrill({
  data, areaId, onClose, onFileOpen,
}: {
  data: CodemapData; areaId: string;
  onClose: () => void; onFileOpen: (rel: string) => void;
}) {
  const area = data.areas.find(a => a.id === areaId);
  const files = data.AREAFILES[areaId] || [];
  const [q, setQ] = useState('');
  const sheetRef = useModalDialog<HTMLDivElement>(true, onClose);
  if (!area) return null;
  const filteredFiles = q.trim()
    ? files.filter(rel => rel.toLowerCase().includes(q.trim().toLowerCase()))
    : files;

  return (
    <div className="diag__ov" onClick={onClose}>
      <div className="diag__sheet" onClick={e => e.stopPropagation()}
           ref={sheetRef} role="dialog" aria-modal="true" aria-label={area.name} tabIndex={-1}>
        <header className="diag__sheet-head">
          <div>
            <span className="diag__bartag">
              {data.BANDNAME[area.band]}
            </span>
            <h2 className="diag__sheet-title">{area.name}</h2>
            <div className="diag__sheet-meta">{area.id} · {area.files} files · {area.lines.toLocaleString()} lines</div>
            <p className="diag__sheet-desc">{data.AREADESC[areaId] || ''}</p>
          </div>
          <button className="diag__close" onClick={onClose}>×</button>
        </header>

        <div className="diag__sheet-filter">
          <input
            className="input"
            placeholder={`Filter ${files.length} files…`}
            value={q}
            onChange={e => setQ(e.target.value)}
            autoFocus
          />
        </div>

        <div className="diag__file-grid">
          {filteredFiles.map(rel => {
            const F = data.FILEINDEX[rel];
            if (!F) return null;
            return (
              <button key={rel} className="diag__file-card" onClick={() => onFileOpen(rel)}>
                <div className="diag__file-card-head">
                  <span className="diag__file-card-name">{F.n}</span>
                  <span className="diag__file-card-ln">{F.l} ln</span>
                </div>
                <div className="diag__file-card-doc">
                  {F.doc ? F.doc.split(/\n\s*\n/)[0].slice(0, 140) : `${F.n} — ${F.l} lines.`}
                </div>
                <div className="diag__file-card-cnt">
                  {F.c.length} classes · {F.f.length} functions · imports {F.deps.length} · used by {F.used.length}
                  <span className="diag__file-card-open">open ▸</span>
                </div>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────
// Layer 3 — File Deep-Dive (source + Static/LLM tabs)
// Static tab now pulls richer data via the file_summary endpoint:
// per-symbol complexity, fan-in/out, internal deps, public API, imports.
// ─────────────────────────────────────────────────────────────────
type FileSummary = {
  file: string;
  language: string;
  loc: number;
  purpose: string;
  imports: string[];
  internal_deps: string[];
  dependents: string[];
  defines: { symbol: string; kind: string; complexity: number; lines: string; calls: number }[];
  public_api: { symbol: string; used_by: string[] }[];
  error: string;
  complexity_total: number;
  fan_in: number;
  fan_out: number;
};

function FileDeepDive({
  data, repoId, fileRel, onClose, onJump,
}: {
  data: CodemapData; repoId: string; fileRel: string;
  onClose: () => void; onJump: (rel: string) => void;
}) {
  const F = data.FILEINDEX[fileRel];
  const src = data.SRC[fileRel];
  const [tab, setTab] = useState<'static' | 'llm'>('static');
  const [summary, setSummary] = useState<FileSummary | null>(null);
  const [summaryErr, setSummaryErr] = useState<string | null>(null);
  const [llm, setLlm] = useState<{ explanation: string | null; used_llm: boolean; reason: string | null } | null>(null);
  const [llmLoading, setLlmLoading] = useState(false);
  const [llmError, setLlmError] = useState<string | null>(null);
  const winRef = useModalDialog<HTMLDivElement>(true, onClose);

  // Pull rich static metadata (per-symbol complexity, public API, etc.)
  useEffect(() => {
    setSummary(null); setSummaryErr(null);
    kycApi.fileSummary(repoId, fileRel)
      .then(r => setSummary(r.data as FileSummary))
      .catch(e => setSummaryErr(e?.response?.data?.detail || 'Could not fetch file metadata'));
  }, [repoId, fileRel]);

  const fetchLlm = () => {
    setLlmLoading(true); setLlmError(null); setLlm(null);
    kycApi.explainFile(repoId, fileRel)
      .then(r => setLlm(r.data))
      .catch(e => setLlmError(e?.response?.data?.detail || 'LLM explain failed'))
      .finally(() => setLlmLoading(false));
  };
  useEffect(() => {
    if (tab === 'llm' && !llm && !llmLoading && !llmError) fetchLlm();
    // eslint-disable-next-line
  }, [tab]);

  if (!F) return null;
  const area = data.areas.find(a => a.id === F.area);

  const role = (): { tag: string; text: string } => {
    const d = F.deps.length, u = F.used.length;
    if (!u && d) return { tag: 'Entry point', text: `Nothing else imports this; it pulls in ${d} module(s). Usually an app, script, or test you run directly.` };
    if (!d && u) return { tag: 'Foundational leaf', text: `It imports nothing in-repo, yet ${u} module(s) depend on it — a shared building block. Treat its public surface as stable.` };
    if (u >= 5) return { tag: 'Hub', text: `${u} modules import it (and it imports ${d}). High blast radius — changes here touch a lot of the system.` };
    if (!d && !u) return { tag: 'Standalone', text: `No in-repo imports either way — self-contained, or wired only via dynamic paths the static scan can't see.` };
    return { tag: 'Mid-chain', text: `Imports ${d} in-repo module(s) and is used by ${u}. Depends on what's below it, supports what's above.` };
  };
  const R = role();

  // Helpers
  const complexityBand = (c: number): string => {
    if (c >= 15) return 'diag__cx--high';
    if (c >= 8)  return 'diag__cx--med';
    return 'diag__cx--low';
  };

  // Symbol distribution (functions vs methods vs classes)
  const symStats = summary ? (() => {
    const fns = summary.defines.filter(d => d.kind === 'function').length;
    const methods = summary.defines.filter(d => d.kind === 'method').length;
    const classes = summary.defines.filter(d => d.kind === 'class').length;
    return { fns, methods, classes };
  })() : null;

  // Reading order suggestion: classes first (declarations), then high-complexity
  // functions (they drive behavior).
  const readingOrder = summary ? [
    ...summary.defines.filter(d => d.kind === 'class').slice(0, 3),
    ...summary.defines.filter(d => d.kind !== 'class').sort((a, b) => b.complexity - a.complexity).slice(0, 3),
  ].slice(0, 5) : [];

  return (
    <div className="diag__fov" onClick={onClose}>
      <div className="diag__fwin" onClick={e => e.stopPropagation()}
           ref={winRef} role="dialog" aria-modal="true" aria-label={fileRel} tabIndex={-1}>
        <header className="diag__fwin-head">
          {area && (
            <span className="diag__bartag">
              {F.area}
            </span>
          )}
          <span className="diag__fwin-name">{F.n}</span>
          <span className="diag__fwin-meta">{F.l} lines</span>
          <span className="diag__path">{fileRel}</span>
          <button className="diag__close" onClick={onClose}>×</button>
        </header>

        <div className="diag__fwin-body">
          <div className="diag__fwin-left">
            <div className="diag__tabs">
              <button className={`diag__tab${tab === 'static' ? ' diag__tab--active' : ''}`} onClick={() => setTab('static')}>Static analysis</button>
              <button className={`diag__tab${tab === 'llm' ? ' diag__tab--active' : ''}`} onClick={() => setTab('llm')}>LLM explanation</button>
            </div>

            {tab === 'static' && (
              <div className="diag__analysis">
                {/* Role header */}
                <div className="diag__rolebox">
                  <strong>{R.tag}.</strong> {R.text}
                </div>

                {/* At-a-glance metric tiles */}
                {summary && (
                  <div className="diag__metric-grid">
                    <Metric label="Lines"      value={String(summary.loc)} />
                    <Metric label="Complexity" value={String(summary.complexity_total)} band={complexityBand(summary.complexity_total / Math.max(1, summary.defines.length))} />
                    <Metric label="Fan-in"     value={String(summary.fan_in)} />
                    <Metric label="Fan-out"    value={String(summary.fan_out)} />
                    {symStats && <Metric label="Classes"   value={String(symStats.classes)} />}
                    {symStats && <Metric label="Functions" value={String(symStats.fns + symStats.methods)} />}
                  </div>
                )}

                {summaryErr && (
                  <div className="diag__note">Couldn't fetch enriched metadata: {summaryErr}</div>
                )}

                {/* Overview */}
                <h3>Overview</h3>
                {F.doc
                  ? <p>{F.doc}</p>
                  : summary?.purpose
                    ? <p>{summary.purpose}</p>
                    : <span className="diag__none">No file-level docstring. The static analysis below is reconstructed from the file's symbols and imports.</span>
                }

                {/* Suggested reading order */}
                {readingOrder.length > 0 && (
                  <>
                    <h3>Suggested reading order</h3>
                    <ol className="diag__reading">
                      {readingOrder.map((d, i) => (
                        <li key={i}>
                          <span className="diag__sym-kind">{d.kind}</span>
                          <code className="diag__sym-name">{d.symbol}</code>
                          {d.complexity > 0 && (
                            <span className={`diag__cx ${complexityBand(d.complexity)}`}>cx {d.complexity}</span>
                          )}
                          <span className="diag__sym-lines">lines {d.lines}</span>
                        </li>
                      ))}
                    </ol>
                  </>
                )}

                {/* Imports (all of them, internal + external) */}
                {summary && summary.imports.length > 0 && (
                  <>
                    <h3>Imports ({summary.imports.length})</h3>
                    <div className="diag__imports">
                      {summary.imports.slice(0, 30).map(imp => (
                        <code key={imp} className="diag__import-chip">{imp}</code>
                      ))}
                      {summary.imports.length > 30 && (
                        <span className="diag__none">+ {summary.imports.length - 30} more</span>
                      )}
                    </div>
                  </>
                )}

                {/* Depends on / Used by — clickable to jump */}
                <h3>Depends on ({F.deps.length})</h3>
                {F.deps.length === 0
                  ? <span className="diag__none">— none in-repo (a leaf)</span>
                  : <div>{F.deps.map(d => <FileChip key={d} rel={d} data={data} onClick={onJump} />)}</div>
                }

                <h3>Used by ({F.used.length})</h3>
                {F.used.length === 0
                  ? <span className="diag__none">— none (entry point / not imported)</span>
                  : <div>{F.used.map(d => <FileChip key={d} rel={d} data={data} onClick={onJump} />)}</div>
                }

                {/* Public API — which symbols are used externally */}
                {summary && summary.public_api.length > 0 && (
                  <>
                    <h3>Public API ({summary.public_api.length})</h3>
                    <p className="diag__note">Symbols in this file that are called or imported from other files. Changing their signatures will ripple to those callers.</p>
                    <div className="diag__public-api">
                      {summary.public_api.map((p, i) => (
                        <div key={i} className="diag__api-row">
                          <code className="diag__sym-name">{p.symbol}</code>
                          <span className="diag__api-used">used by {p.used_by.length} file{p.used_by.length === 1 ? '' : 's'}</span>
                          {p.used_by.length > 0 && (
                            <div className="diag__api-chips">
                              {p.used_by.slice(0, 4).map(u => <FileChip key={u} rel={u} data={data} onClick={onJump} />)}
                              {p.used_by.length > 4 && <span className="diag__none">+ {p.used_by.length - 4} more</span>}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </>
                )}

                {/* Classes with complexity from summary, if present */}
                {F.c.length > 0 && (
                  <>
                    <h3>Classes ({F.c.length})</h3>
                    {F.c.map((c, i) => {
                      const cs = summary?.defines.find(d => d.kind === 'class' && (d.symbol === c.n || d.symbol.endsWith('.' + c.n)));
                      return (
                        <div key={i} className="diag__member">
                          <div className="diag__member-head">
                            <span className="diag__member-name">class {c.n}</span>
                            {cs && cs.complexity > 0 && (
                              <span className={`diag__cx ${complexityBand(cs.complexity)}`}>cx {cs.complexity}</span>
                            )}
                            {cs && <span className="diag__sym-lines">lines {cs.lines}</span>}
                          </div>
                          {c.doc && <div className="diag__member-doc">{c.doc}</div>}
                          {c.m && c.m.length > 0 && (
                            <div style={{ marginTop: 4 }}>
                              {c.m.map(m => <span key={m} className="diag__meth">{m}()</span>)}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </>
                )}

                {/* Functions with complexity */}
                {F.f.length > 0 && (
                  <>
                    <h3>Functions ({F.f.length})</h3>
                    {F.f.map((fn, i) => {
                      const cs = summary?.defines.find(d => d.kind !== 'class' && (d.symbol === fn.n || d.symbol.endsWith('.' + fn.n)));
                      return (
                        <div key={i} className="diag__member">
                          <div className="diag__member-head">
                            <span className="diag__member-name">{fn.n}{fn.sig || '()'}</span>
                            {cs && cs.complexity > 0 && (
                              <span className={`diag__cx ${complexityBand(cs.complexity)}`}>cx {cs.complexity}</span>
                            )}
                            {cs && cs.calls > 0 && (
                              <span className="diag__sym-lines">{cs.calls} call site{cs.calls === 1 ? '' : 's'}</span>
                            )}
                          </div>
                          {fn.doc && <div className="diag__member-doc">{fn.doc}</div>}
                        </div>
                      );
                    })}
                  </>
                )}
              </div>
            )}

            {tab === 'llm' && (
              <div className="diag__analysis">
                <div className="diag__rolebox">
                  An LLM explanation augments the static analysis with prose. Connect a model in <Link to="/settings" style={{ color: 'var(--kyc-accent)', fontWeight: 600 }}>AI settings</Link> (local Ollama or a provider key) to enable it.
                </div>
                {llmLoading && <div className="dash-loading" style={{ minHeight: 160 }}>Asking the model…</div>}
                {llmError && <div className="toast toast--err">{llmError}</div>}
                {llm && !llm.used_llm && (
                  <div className="toast toast--ok">
                    <strong>No LLM configured.</strong> {llm.reason}
                  </div>
                )}
                {llm && llm.used_llm && llm.explanation && (
                  <div className="diag__llm-text">{llm.explanation}</div>
                )}
                {llm && (
                  <button className="btn btn--secondary btn--sm" style={{ marginTop: 12 }} onClick={fetchLlm}>
                    Re-generate
                  </button>
                )}
              </div>
            )}
          </div>

          <div className="diag__fwin-right">
            {src === undefined ? (
              <div className="diag__src-none">Source not embedded for this file.</div>
            ) : (
              <SourceView src={src} />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function Metric({ label, value, band }: { label: string; value: string; band?: string }) {
  return (
    <div className="diag__metric">
      <div className="diag__metric-label">{label}</div>
      <div className={`diag__metric-value ${band || ''}`}>{value}</div>
    </div>
  );
}

function FileChip({ rel, data, onClick }: { rel: string; data: CodemapData; onClick: (rel: string) => void }) {
  if (!data.FILEINDEX[rel]) return null;
  const base = rel.split('/').pop() || rel;
  return (
    <button className="diag__fchip" title={rel} onClick={() => onClick(rel)}>
      {base}
    </button>
  );
}

function SourceView({ src }: { src: string }) {
  const lines = src.split('\n');
  const gutter = lines.map((_, i) => i + 1).join('\n');
  return (
    <div className="diag__code">
      <pre className="diag__code-gut">{gutter}</pre>
      <pre className="diag__code-src">{src}</pre>
    </div>
  );
}
