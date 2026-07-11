import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { kycApi } from '../../api/client';
import './Track.css';

export default function Track() {
  const { repoId } = useParams<{ repoId: string }>();
  const [isGit, setIsGit] = useState<boolean | null>(null);
  const [commits, setCommits] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [reason, setReason] = useState('');
  const [repoPath, setRepoPath] = useState('');
  const [base, setBase] = useState(''); const [head, setHead] = useState('');
  const [diff, setDiff] = useState<any>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!repoId) return;
    setLoading(true); setError(null);
    kycApi.trackCommits(repoId)
      .then(r => {
        setIsGit(r.data.is_git);
        setCommits(r.data.commits || []);
        setReason(r.data.reason || '');
        setRepoPath(r.data.path || '');
        if ((r.data.commits || []).length >= 2) {
          setHead(r.data.commits[0].sha); setBase(r.data.commits[1].sha);
        }
      })
      .catch(e => setError(e?.response?.data?.detail || 'Could not read this repository\'s commit history.'))
      .finally(() => setLoading(false));
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

  if (loading) return <div className="dash-loading">Reading commit history...</div>;

  if (isGit === false) {
    return (
      <div>
        <div className="page-header"><h1>Track</h1></div>
        <div className="card empty-state">
          <h3>No git history here</h3>
          <p>Track compares the codebase at two commits, so it needs git history.</p>
          {reason && <p className="track__why"><strong>Reason:</strong> {reason}</p>}
          {repoPath && <p className="track__why"><strong>Looked in:</strong> <code>{repoPath}</code></p>}
        </div>
      </div>
    );
  }

  // isGit === null means the history call failed outright - say so instead of
  // rendering two empty dropdowns.
  if (isGit === null || commits.length === 0) {
    return (
      <div>
        <div className="page-header"><h1>Track</h1></div>
        <div className="card empty-state">
          <h3>{error ? 'Could not load commits' : 'No commits found'}</h3>
          <p>{error || reason || 'This repository has git metadata but no commit history to compare.'}</p>
          {repoPath && <p className="track__why"><strong>Looked in:</strong> <code>{repoPath}</code></p>}
        </div>
      </div>
    );
  }

  const shaLabel = (sha: string) => {
    const c = commits.find(x => x.sha === sha);
    return c ? `${c.short} ${c.subject}` : '-';
  };
  const compareLatest = () => {
    if (commits.length < 2) return;
    setHead(commits[0].sha); setBase(commits[1].sha);
  };

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

        {base && head && (
          <div className="track__range">
            <code>{shaLabel(base)}</code>
            <span className="track__range-arrow">→</span>
            <code>{shaLabel(head)}</code>
            {commits.length >= 2 && (
              <button className="btn btn--secondary btn--sm track__range-btn" onClick={compareLatest}>
                Use latest commit
              </button>
            )}
          </div>
        )}
      </div>

      {!diff && !running && !error && (
        <div className="card">
          <div className="card-header"><h3>What a structural diff gives you</h3></div>
          <p className="track__lead">
            This is not a text diff. KnowIT re-indexes the codebase at both commits and compares the
            structures, so you get what actually changed in the architecture rather than which lines moved.
          </p>
          <div className="track__what">
            <div><strong>Files &amp; symbols</strong><span>Functions and classes that appeared, disappeared, or were rewritten.</span></div>
            <div><strong>Complexity</strong><span>Which functions got harder to reason about, and by how much.</span></div>
            <div><strong>Architecture delta</strong><span>Import edges added or removed - new coupling between modules.</span></div>
          </div>
          <p className="track__note">
            Both commits get fully indexed, so the first diff on a large repo can take a minute.
          </p>
        </div>
      )}

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
