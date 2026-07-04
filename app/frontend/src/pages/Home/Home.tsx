import { useEffect, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { kycApi, RepoListItem, WorkspaceFolder } from '../../api/client';
import './Home.css';
import { GLOSSARY } from '../../lib/glossary';

export default function Home() {
  const [source, setSource] = useState('');
  const [repos, setRepos] = useState<RepoListItem[]>([]);
  const [folders, setFolders] = useState<WorkspaceFolder[]>([]);
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<{ pct: number; message: string }>({ pct: 0, message: '' });
  const navigate = useNavigate();

  const loadLists = () => {
    kycApi.listRepos().then(r => setRepos(r.data)).catch(() => {});
    kycApi.workspace().then(r => setFolders(r.data.folders)).catch(() => {});
  };
  useEffect(() => { loadLists(); }, []);

  // Poll the backend until the repo finishes indexing (or errors), updating the
  // progress bar as stages report in.
  const pollUntilReady = (rid: string): Promise<void> =>
    new Promise((resolve, reject) => {
      const tick = () => {
        kycApi.repoStatus(rid).then(r => {
          const d = r.data;
          setProgress({ pct: d.pct, message: d.message });
          if (d.status === 'ready') resolve();
          else if (d.status === 'error') reject(new Error(d.error || 'Indexing failed'));
          else setTimeout(tick, 1000);
        }).catch(reject);
      };
      tick();
    });

  // Connect (or instantly reuse) a source, wait for indexing, then open it.
  const connectAndGo = async (src: string) => {
    setConnecting(true); setError(null); setProgress({ pct: 0, message: 'Starting…' });
    try {
      const r = await kycApi.connectRepo(src);
      const rid = r.data.repo_id;
      if (r.data.status !== 'ready') await pollUntilReady(rid);
      navigate(`/repos/${rid}/timeline`);
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'Failed to connect');
    } finally {
      setConnecting(false);
    }
  };

  const openFolder = (f: WorkspaceFolder) => {
    if (f.connected) { navigate(`/repos/${f.rid}/timeline`); return; }
    connectAndGo(f.source);
  };

  const merged: WorkspaceFolder[] = (() => {
    const map = new Map<string, WorkspaceFolder>();
    folders.forEach(f => map.set(f.rid, { ...f }));
    repos.forEach(r => {
      const ex = map.get(r.repo_id);
      if (ex) ex.connected = true;
      else map.set(r.repo_id, { rid: r.repo_id, name: r.name, source: r.source, captures: 0, last_ts: null, last_summary: null, metrics: null, connected: true });
    });
    return Array.from(map.values());
  })();

  const connect = () => {
    if (source.trim()) connectAndGo(source.trim());
  };

  return (
    <div>
      <div className="page-header">
        <h1>Connect a codebase</h1>
        <p>Paste a local path or git URL. KnowIT will parse it, build a code graph, and index it for semantic search.</p>
      </div>

      <div className="card kyc-start">
        <div className="card-header"><h3>Getting started</h3></div>
        <div className="kyc-start__steps">
          <div className="kyc-start__step">
            <span className="kyc-start__n">1</span>
            <div><strong>Connect a codebase</strong><p>Paste a local folder path or a public Git URL below.</p></div>
          </div>
          <div className="kyc-start__arrow">→</div>
          <div className="kyc-start__step">
            <span className="kyc-start__n">2</span>
            <div><strong>KnowIT indexes it</strong><p>Parses your code into symbols, builds a graph, and embeds it for search — cached after the first run.</p></div>
          </div>
          <div className="kyc-start__arrow">→</div>
          <div className="kyc-start__step">
            <span className="kyc-start__n">3</span>
            <div><strong>Explore the tabs</strong><p>Overview, Files, Diagrams, Ask, Learn, Track and more — each reads the indexed repo.</p></div>
          </div>
        </div>
        <p className="kyc-start__note">
          Want generated answers in <strong>Ask</strong> and <strong>Learn</strong>? Connect a model
          (local Ollama or a cloud key) in <Link to="/settings" className="kyc-start__link">AI settings</Link>.
          Everything else works without one.
        </p>
      </div>

      <div className="card kyc-home__connect">
        <div className="card-header"><h3>New connection</h3></div>
        {error && <div className="toast toast--err">{error}</div>}
        <div className="kyc-home__row">
          <input
            className="input"
            placeholder="C:\path\to\repo  or  https://github.com/owner/repo.git"
            value={source}
            onChange={e => setSource(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') connect(); }}
            disabled={connecting}
            autoFocus
          />
          <button className="btn btn--primary" onClick={connect} disabled={connecting || !source.trim()}>
            {connecting ? 'Indexing…' : 'Connect'}
          </button>
        </div>
        <p className="kyc-home__hint">
          Tip: the engine clones git URLs with depth 200 and caches parsed indexes by signature.
          Re-connecting the same source is instant.
        </p>
        {connecting && (
          <div style={{ marginTop: 14 }}>
            <div style={{ height: 8, background: 'rgba(127,127,127,0.18)', borderRadius: 999, overflow: 'hidden' }}>
              <div style={{ height: '100%', width: `${Math.max(4, progress.pct)}%`, background: 'var(--kyc-accent, #1DB954)', transition: 'width .3s ease' }} />
            </div>
            <div style={{ marginTop: 8, fontSize: 13, color: 'var(--kyc-muted, #6b7280)' }}>
              {progress.message || 'Working…'}{progress.pct ? ` · ${progress.pct}%` : ''}
            </div>
          </div>
        )}
      </div>

      <div className="card">
        <div className="card-header"><h3>Your tracked folders ({merged.length})</h3></div>
        {merged.length === 0 ? (
          <div className="empty-state">
            <h3>No folders yet</h3>
            <p>Connect one above to begin tracking it over time.</p>
          </div>
        ) : (
          <div className="kyc-home__list">
            {merged.map(f => (
              <button
                key={f.rid}
                type="button"
                className="kyc-home__item"
                onClick={() => openFolder(f)}
                title={f.source}
              >
                <div className="kyc-home__item-main">
                  <div className="kyc-home__item-name">{f.name}</div>
                  <div className="kyc-home__item-source">{f.source}</div>
                  {f.last_summary && <div className="kyc-home__item-change">Last change: {f.last_summary}</div>}
                </div>
                <div className="kyc-home__item-meta">
                  {f.captures > 0
                    ? <span className="kyc-home__status kyc-home__status--ready">{f.captures} capture{f.captures === 1 ? '' : 's'}</span>
                    : <span className="kyc-home__status">not captured</span>}
                  {f.last_ts && <span className="kyc-home__commit">{new Date(f.last_ts).toLocaleDateString()}</span>}
                  {!f.connected && <span className="kyc-home__commit">offline</span>}
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      <details className="card kyc-glossary">
        <summary className="kyc-glossary__summary">What the metrics mean</summary>
        <div className="kyc-glossary__grid">
          {GLOSSARY.map(g => (
            <div key={g.term} className="kyc-glossary__item">
              <div className="kyc-glossary__term">{g.term}</div>
              <div className="kyc-glossary__def">{g.def}</div>
            </div>
          ))}
        </div>
      </details>
    </div>
  );
}
