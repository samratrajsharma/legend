import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { kycApi } from '../../api/client';
import './Track.css';

export default function Track() {
  const { repoId } = useParams<{ repoId: string }>();
  const [isGit, setIsGit] = useState<boolean | null>(null);
  const [commits, setCommits] = useState<any[]>([]);
  const [base, setBase] = useState(''); const [head, setHead] = useState('');
  const [diff, setDiff] = useState<any>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!repoId) return;
    kycApi.trackCommits(repoId).then(r => {
      setIsGit(r.data.is_git); setCommits(r.data.commits);
      if (r.data.commits.length >= 2) {
        setHead(r.data.commits[0].sha); setBase(r.data.commits[1].sha);
      }
    });
  }, [repoId]);

  const runDiff = async () => {
    if (!repoId || !base || !head) return;
    setRunning(true); setError(null); setDiff(null);
    try {
      const r = await kycApi.trackDiff(repoId, base, head);
      setDiff(r.data);
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Diff failed');
    } finally { setRunning(false); }
  };

  if (isGit === false) {
    return (
      <div>
        <div className="page-header"><h1>Track</h1></div>
        <div className="card empty-state">
          <h3>Not a git repository</h3>
          <p>Track diffs across commits only work on git repos.</p>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="page-header">
        <h1>Track</h1>
        <p>Snapshot the repo at two commits and diff structurally: files, symbols, imports, complexity.</p>
      </div>

      <div className="card">
        <div className="card-header"><h3>Pick two commits</h3></div>
        <div className="track__row">
          <div>
            <label>Base</label>
            <select className="input" value={base} onChange={e => setBase(e.target.value)}>
              <option value="">(pick)</option>
              {commits.map(c => <option key={c.sha} value={c.sha}>{c.short} · {c.date} · {c.subject}</option>)}
            </select>
          </div>
          <div>
            <label>Head</label>
            <select className="input" value={head} onChange={e => setHead(e.target.value)}>
              <option value="">(pick)</option>
              {commits.map(c => <option key={c.sha} value={c.sha}>{c.short} · {c.date} · {c.subject}</option>)}
            </select>
          </div>
          <button className="btn btn--primary" onClick={runDiff} disabled={!base || !head || running}>
            {running ? 'Diffing…' : 'Diff'}
          </button>
        </div>
      </div>

      {error && <div className="card"><div className="toast toast--err">{error}</div></div>}

      {running && <div className="dash-loading">Snapshotting both commits (this can take a minute)…</div>}

      {diff && (
        <>
          <div className="stats">
            <div className="stat-card"><div className="stat-card__label">Files +</div><div className="stat-card__value stat-card__value--success">{diff.diff.files_added.length}</div></div>
            <div className="stat-card"><div className="stat-card__label">Files −</div><div className="stat-card__value stat-card__value--danger">{diff.diff.files_removed.length}</div></div>
            <div className="stat-card"><div className="stat-card__label">Symbols +</div><div className="stat-card__value stat-card__value--success">{diff.diff.symbols_added.length}</div></div>
            <div className="stat-card"><div className="stat-card__label">Symbols −</div><div className="stat-card__value stat-card__value--danger">{diff.diff.symbols_removed.length}</div></div>
            <div className="stat-card"><div className="stat-card__label">Modified</div><div className="stat-card__value stat-card__value--warning">{diff.diff.symbols_modified.length}</div></div>
          </div>

          <div className="card">
            <div className="card-header"><h3>Changelog</h3></div>
            <Changelog text={diff.changelog} />
          </div>

          {diff.diff.complexity_changes?.length > 0 && (
            <div className="card">
              <div className="card-header"><h3>Complexity changes</h3></div>
              <div className="table-wrap">
                <table className="table">
                  <thead><tr><th>Symbol</th><th>File</th><th>From</th><th>To</th></tr></thead>
                  <tbody>
                    {diff.diff.complexity_changes.map((c: any, i: number) => (
                      <tr key={i}>
                        <td><code>{c.symbol}</code></td>
                        <td><code>{c.file}</code></td>
                        <td>{c.from}</td>
                        <td><strong style={{ color: c.to > c.from ? 'var(--dash-danger)' : 'var(--dash-success)' }}>{c.to}</strong></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <div className="card">
            <div className="card-header"><h3>Architecture delta (DOT)</h3></div>
            <ArchDelta dot={diff.arch_delta_dot} />
          </div>
        </>
      )}
    </div>
  );
}

// ── Changelog: render the engine's markdown-ish text as structured rows ──
function Changelog({ text }: { text: string }) {
  const lines = (text || '').split('\n');
  return (
    <div className="track__log">
      {lines.map((raw, i) => {
        const t = raw.trim();
        if (!t) return null;
        const hdr = t.match(/^\*\*(.+?)\*\*\s*(.*)$/);
        if (hdr) return <div key={i} className="track__log-h">{hdr[1]}{hdr[2] ? ' ' + hdr[2] : ''}</div>;
        const item = t.match(/^-\s+(.*)$/);
        if (item) {
          const mm = item[1].match(/^(.*?)\s*\(([^()]+)\)\s*$/);
          return (
            <div key={i} className="track__log-li">
              <code className="track__log-sym">{mm ? mm[1] : item[1]}</code>
              {mm && <span className="track__log-path">{mm[2]}</span>}
            </div>
          );
        }
        return <div key={i} className="track__log-p">{t.replace(/\*\*/g, '')}</div>;
      })}
    </div>
  );
}

// ── Architecture delta: parse the Graphviz DOT edges into a readable list ──
function ArchDelta({ dot }: { dot: string }) {
  const edges: { src: string; dst: string; color: string }[] = [];
  const re = /"([^"]+)"\s*->\s*"([^"]+)"(?:\s*\[color="([^"]+)"\])?/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(dot || '')) !== null) {
    edges.push({ src: m[1], dst: m[2], color: m[3] || '#888888' });
  }
  const base = (p: string) => p.split(/[\\/]/).pop() || p;
  if (edges.length === 0) {
    return <p className="track__none">No structural dependency changes between these commits.</p>;
  }
  return (
    <>
      <p className="track__hint-line">{edges.length} changed import edge{edges.length === 1 ? '' : 's'} (hover a row for full paths).</p>
      <div className="track__edges">
        {edges.map((e, i) => (
          <div key={i} className="track__edge" title={`${e.src}  ->  ${e.dst}`}>
            <code className="track__edge-node">{base(e.src)}</code>
            <span className="track__edge-arrow" style={{ color: e.color }}>→</span>
            <code className="track__edge-node">{base(e.dst)}</code>
          </div>
        ))}
      </div>
      <details className="track__raw">
        <summary>Raw DOT</summary>
        <pre className="track__changelog">{dot}</pre>
      </details>
    </>
  );
}
