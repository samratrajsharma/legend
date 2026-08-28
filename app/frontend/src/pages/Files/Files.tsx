import { useEffect, useMemo, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import { kycApi, FunctionExplainResponse } from '../../api/client';
import './Files.css';
import Markdown from '../../components/Markdown/Markdown';

// ─────────────────────────────────────────────────────────────────
// File tree node model — folders contain children, files don't.
// ─────────────────────────────────────────────────────────────────
type TreeNode = {
  name: string;          // segment name (last path component)
  path: string;          // full repo-relative path so far
  isFile: boolean;
  children: TreeNode[];  // empty for files
};

// Build a real hierarchy from a flat list of file paths.
// Handles both forward and backslash separators (Windows-friendly).
function buildTree(files: string[]): TreeNode {
  const root: TreeNode = { name: '', path: '', isFile: false, children: [] };
  for (const file of files) {
    const parts = file.replace(/\\/g, '/').split('/').filter(Boolean);
    let cursor = root;
    let acc = '';
    for (let i = 0; i < parts.length; i++) {
      const seg = parts[i];
      acc = acc ? acc + '/' + seg : seg;
      const isLeaf = i === parts.length - 1;
      let next = cursor.children.find(c => c.name === seg && c.isFile === isLeaf);
      if (!next) {
        next = { name: seg, path: file /* leaf uses original for selection */, isFile: isLeaf, children: [] };
        if (!isLeaf) next.path = acc;
        cursor.children.push(next);
      }
      cursor = next;
    }
  }
  // Sort: folders first (alpha), files after (alpha).
  const sort = (n: TreeNode) => {
    n.children.sort((a, b) => {
      if (a.isFile !== b.isFile) return a.isFile ? 1 : -1;
      return a.name.localeCompare(b.name);
    });
    n.children.forEach(sort);
  };
  sort(root);
  return root;
}

// Default-expand folders leading to a given selected path so the user
// always sees the highlight when they pick a deep file.
function pathsToExpand(selected: string | null): Set<string> {
  if (!selected) return new Set();
  const parts = selected.replace(/\\/g, '/').split('/').filter(Boolean);
  const out = new Set<string>();
  let acc = '';
  for (let i = 0; i < parts.length - 1; i++) {
    acc = acc ? acc + '/' + parts[i] : parts[i];
    out.add(acc);
  }
  return out;
}

// Tiny icon helpers — inline SVGs so no font dependency.
const FolderIcon = ({ open }: { open: boolean }) => (
  <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden>
    {open
      ? <path d="M2 4.5A1.5 1.5 0 0 1 3.5 3h3l1.5 1.5h5A1.5 1.5 0 0 1 14.5 6v.5H2V4.5zM2 7h12.5l-1.2 5.4a1.5 1.5 0 0 1-1.46 1.1H3.16a1.5 1.5 0 0 1-1.46-1.1L0.5 7H2z"
              fill="#4ADE80" />
      : <path d="M2 4.5A1.5 1.5 0 0 1 3.5 3h3l1.5 1.5h5A1.5 1.5 0 0 1 14.5 6v6a1.5 1.5 0 0 1-1.5 1.5h-10A1.5 1.5 0 0 1 1.5 12V4.5z"
              fill="#1DB954" />
    }
  </svg>
);
const FileIcon = ({ lang }: { lang?: string }) => {
  // Pick a tint by extension hint.
  const tint = lang === 'python'     ? '#fcd34d'
             : lang === 'javascript' ? '#fbbf24'
             : lang === 'typescript' ? '#4ade80'
             : '#6f6f6f';
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path d="M4 1.5A1.5 1.5 0 0 1 5.5 0h4L13 3.5V14.5A1.5 1.5 0 0 1 11.5 16h-6A1.5 1.5 0 0 1 4 14.5v-13z"
            fill="#1AA34A" stroke={tint} strokeWidth="1.2" />
      <path d="M9.5 0v3.5H13" fill="none" stroke={tint} strokeWidth="1.2" />
    </svg>
  );
};
const Chevron = ({ open }: { open: boolean }) => (
  <svg width="10" height="10" viewBox="0 0 10 10" fill="none" aria-hidden
       style={{ transform: open ? 'rotate(90deg)' : 'none', transition: 'transform 0.15s' }}>
    <path d="M3 2 L7 5 L3 8" stroke="#1ED760" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" fill="none" />
  </svg>
);

export default function Files() {
  const { repoId } = useParams<{ repoId: string }>();
  const [files, setFiles] = useState<string[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [content, setContent] = useState<{ text: string; language: string; loc: number } | null>(null);
  const [summary, setSummary] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [filter, setFilter] = useState('');
  const [byLanguage, setByLanguage] = useState<Record<string, string[]>>({});
  const [fnOpen, setFnOpen] = useState<{ file: string; symbol: string } | null>(null);
  const [fnData, setFnData] = useState<FunctionExplainResponse | null>(null);
  const [fnLoading, setFnLoading] = useState(false);
  const [fnError, setFnError] = useState<string | null>(null);

  useEffect(() => {
    if (!repoId) return;
    kycApi.files(repoId)
      .then(r => {
        const list = r.data.files;
        setFiles(list);
        setByLanguage(r.data.by_language || {});
        if (list.length > 0 && !selected) {
          setSelected(list[0]);
          setExpanded(pathsToExpand(list[0]));
        }
      })
      .catch(() => {});
    // eslint-disable-next-line
  }, [repoId]);

  useEffect(() => {
    if (!repoId || !selected) return;
    setLoading(true);
    Promise.all([
      kycApi.fileContent(repoId, selected).then(r => r.data),
      kycApi.fileSummary(repoId, selected).then(r => r.data).catch(() => null),
    ]).then(([c, s]) => {
      setContent({ text: c.text, language: c.language, loc: c.loc });
      setSummary(s);
    }).finally(() => setLoading(false));
  }, [repoId, selected]);

  // Reverse lookup: file → language, used for tinting file icons.
  const langOf = useMemo(() => {
    const m: Record<string, string> = {};
    Object.entries(byLanguage).forEach(([lang, fs]) => fs.forEach(f => { m[f] = lang; }));
    return m;
  }, [byLanguage]);

  // Build (or filter) the tree.
  const tree = useMemo(() => {
    const q = filter.trim().toLowerCase();
    const source = q
      ? files.filter(f => f.toLowerCase().includes(q))
      : files;
    return buildTree(source);
  }, [files, filter]);

  // When the user types in the filter, auto-expand everything that has matches.
  useEffect(() => {
    if (!filter.trim()) return;
    const all = new Set<string>();
    const walk = (n: TreeNode) => {
      if (!n.isFile && n.path) all.add(n.path);
      n.children.forEach(walk);
    };
    walk(tree);
    setExpanded(all);
  }, [filter, tree]);

  const toggle = (p: string) => {
    setExpanded(prev => {
      const next = new Set(prev);
      next.has(p) ? next.delete(p) : next.add(p);
      return next;
    });
  };

  const openFn = (file: string, symbol: string) => {
    if (!repoId) return;
    setFnOpen({ file, symbol }); setFnData(null); setFnError(null); setFnLoading(true);
    kycApi.explainFunction(repoId, file, symbol)
      .then(r => setFnData(r.data))
      .catch(e => setFnError(e?.response?.data?.detail || 'Explain failed'))
      .finally(() => setFnLoading(false));
  };
  const closeFn = () => { setFnOpen(null); setFnData(null); setFnError(null); };
  const fnPanelRef = useRef<HTMLDivElement>(null);
  const fnReturnFocus = useRef<HTMLElement | null>(null);
  // Modal a11y (QA #41): trap Tab within the dialog, close on Esc, and restore focus to
  // whatever opened it when it closes, so keyboard users aren't dropped back to the top.
  useEffect(() => {
    if (!fnOpen) return;
    fnReturnFocus.current = document.activeElement as HTMLElement | null;
    const panel = fnPanelRef.current;
    const focusables = () => Array.from(
      panel?.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), input, textarea, [tabindex]:not([tabindex="-1"])',
      ) ?? [],
    ).filter(el => el.offsetParent !== null);
    (focusables()[0] ?? panel)?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { closeFn(); return; }
      if (e.key !== 'Tab') return;
      const els = focusables();
      if (els.length === 0) { e.preventDefault(); return; }
      const first = els[0], last = els[els.length - 1];
      const active = document.activeElement as HTMLElement | null;
      if (e.shiftKey && (active === first || !panel?.contains(active))) {
        e.preventDefault(); last.focus();
      } else if (!e.shiftKey && active === last) {
        e.preventDefault(); first.focus();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('keydown', onKey);
      fnReturnFocus.current?.focus?.();          // restore focus on close
    };
  }, [fnOpen]);

  return (
    <div>
      <div className="page-header">
        <h1>Files</h1>
        <p>{files.length} files indexed. Click a folder to expand, a file to open.</p>
      </div>

      <div className="files">
        <div className="files__tree">
          <div className="card-header">
            <h3>File tree</h3>
          </div>
          <div className="files__filter">
            <input
              className="input"
              placeholder="Filter…"
              value={filter}
              onChange={e => setFilter(e.target.value)}
            />
          </div>
          <div className="files__tree-list">
            {tree.children.length === 0 ? (
              <div className="files__empty">No files match.</div>
            ) : (
              tree.children.map(child => (
                <TreeRow
                  key={child.path || child.name}
                  node={child}
                  depth={0}
                  selected={selected}
                  expanded={expanded}
                  onToggle={toggle}
                  onSelect={setSelected}
                  langOf={langOf}
                />
              ))
            )}
          </div>
        </div>

        <div className="files__viewer">
          {selected && (
            <>
              <div className="files__head">
                <div>
                  <div className="files__head-name"><code>{selected}</code></div>
                  {content && <div className="files__head-meta">{content.language} · {content.loc} LOC</div>}
                </div>
              </div>
              {loading ? (
                <div className="dash-loading" style={{ minHeight: 200 }}>Loading…</div>
              ) : (
                <>
                  {summary && (
                    <div className="files__summary">
                      {summary.purpose && <div className="files__summary-purpose">{summary.purpose}</div>}
                      <div className="files__summary-meta">
                        <span>complexity {summary.complexity_total}</span>
                        <span>imported by {summary.fan_in}</span>
                        <span>imports {summary.fan_out} internal</span>
                      </div>
                      {summary.defines?.length > 0 && (
                        <div className="files__defines">
                          <div className="files__defines-label">Defines</div>
                          <div className="files__defines-list">
                            {summary.defines.slice(0, 24).map((d: any) => (
                              <button
                                type="button"
                                key={d.symbol}
                                className="files__symbol-chip files__symbol-chip--btn"
                                title={`lines ${d.lines} — click to explain`}
                                onClick={() => openFn(selected!, d.symbol)}
                              >
                                <code>{d.symbol}</code>
                              </button>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                  {content?.language === 'markdown'
                    ? <div className="files__md"><Markdown text={content.text} /></div>
                    : <pre className="files__code">{content?.text || ''}</pre>}
                </>
              )}
            </>
          )}
        </div>
      </div>

      {fnOpen && (
        <div className="fnpanel__overlay" onClick={closeFn}>
          <div
            className="fnpanel card"
            onClick={e => e.stopPropagation()}
            ref={fnPanelRef}
            role="dialog"
            aria-modal="true"
            aria-label={`Function ${fnData?.name || fnOpen.symbol}`}
            tabIndex={-1}
          >
            <div className="card-header fnpanel__head">
              <div>
                <h3>
                  {fnData?.name || fnOpen.symbol}
                  {fnData?.kind && <span className="fnpanel__kind">{fnData.kind}</span>}
                </h3>
                <div className="fnpanel__sub">
                  <code>{fnOpen.file}</code>{fnData ? `  ·  lines ${fnData.line_start}-${fnData.line_end}` : ''}
                </div>
              </div>
              <button type="button" className="btn--ghost" onClick={closeFn} title="Close (Esc)">✕</button>
            </div>

            <div className="fnpanel__body">
              {fnError && <div className="toast toast--err">{fnError}</div>}

              <div className="fnpanel__section">
                <div className="fnpanel__label">Explanation</div>
                {fnLoading ? (
                  <div className="dash-loading">Explaining…</div>
                ) : fnData?.explanation ? (
                  <pre className="fnpanel__explain">{fnData.explanation}</pre>
                ) : fnData && !fnData.used_llm ? (
                  <div className="toast toast--err">{fnData.reason || 'Connect a model in Settings to get explanations.'}</div>
                ) : null}
              </div>

              {fnData && (fnData.callers.length > 0 || fnData.callees.length > 0) && (
                <div className="fnpanel__rels">
                  <div>
                    <div className="fnpanel__label">Called by ({fnData.callers.length})</div>
                    <div className="fnpanel__chips">
                      {fnData.callers.length === 0
                        ? <span className="fnpanel__muted">—</span>
                        : fnData.callers.map((c, i) => (
                            <button key={i} type="button" className="files__symbol-chip files__symbol-chip--btn"
                                    title={c.file} onClick={() => openFn(c.file, c.name)}>
                              <code>{c.name}</code>
                            </button>
                          ))}
                    </div>
                  </div>
                  <div>
                    <div className="fnpanel__label">Calls ({fnData.callees.length})</div>
                    <div className="fnpanel__chips">
                      {fnData.callees.length === 0
                        ? <span className="fnpanel__muted">—</span>
                        : fnData.callees.map((c, i) => (
                            <button key={i} type="button" className="files__symbol-chip files__symbol-chip--btn"
                                    title={c.file} onClick={() => openFn(c.file, c.name)}>
                              <code>{c.name}</code>
                            </button>
                          ))}
                    </div>
                  </div>
                </div>
              )}

              <div className="fnpanel__section">
                <div className="fnpanel__label">Source</div>
                <pre className="files__code fnpanel__code">{fnData?.code || ''}</pre>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────
// One row of the tree, recursive.
// ─────────────────────────────────────────────────────────────────
function TreeRow({
  node, depth, selected, expanded, onToggle, onSelect, langOf,
}: {
  node: TreeNode;
  depth: number;
  selected: string | null;
  expanded: Set<string>;
  onToggle: (p: string) => void;
  onSelect: (p: string) => void;
  langOf: Record<string, string>;
}) {
  const isOpen = node.isFile ? false : expanded.has(node.path || node.name);
  const isSelected = node.isFile && node.path === selected;
  const indentStyle = { paddingLeft: 8 + depth * 14 };

  if (node.isFile) {
    return (
      <button
        type="button"
        className={`files__row files__row--file${isSelected ? ' files__row--selected' : ''}`}
        style={indentStyle}
        onClick={() => onSelect(node.path)}
        title={node.path}
      >
        <span className="files__row-chev" />
        <FileIcon lang={langOf[node.path]} />
        <span className="files__row-label">{node.name}</span>
      </button>
    );
  }

  return (
    <>
      <button
        type="button"
        className="files__row files__row--folder"
        style={indentStyle}
        onClick={() => onToggle(node.path || node.name)}
      >
        <span className="files__row-chev"><Chevron open={isOpen} /></span>
        <FolderIcon open={isOpen} />
        <span className="files__row-label">{node.name}</span>
        <span className="files__row-count">{countFiles(node)}</span>
      </button>
      {isOpen && node.children.map(child => (
        <TreeRow
          key={child.path || child.name}
          node={child}
          depth={depth + 1}
          selected={selected}
          expanded={expanded}
          onToggle={onToggle}
          onSelect={onSelect}
          langOf={langOf}
        />
      ))}
    </>
  );
}

function countFiles(n: TreeNode): number {
  if (n.isFile) return 1;
  return n.children.reduce((acc, c) => acc + countFiles(c), 0);
}
