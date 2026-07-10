import { useEffect, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { kycApi, RepoListItem, WorkspaceFolder } from '../../api/client';
import './Home.css';
import { GLOSSARY } from '../../lib/glossary';

// The backend sometimes only has the repo id — derive a friendly name from the source path/URL.
function looksLikeId(s?: string) { return !!s && /^[0-9a-f]{10,}$/i.test(s); }
function nameFromSource(src?: string): string {
  if (!src) return '';
  const s = src.replace(/\\/g, '/').replace(/\/+$/, '');
  const gh = s.match(/(?:github\.com|gitlab\.com|bitbucket\.org)[/:]([^/]+)\/([^/]+?)(?:\.git)?$/i);
  if (gh) return `${gh[1]}/${gh[2]}`;
  let base = s.split('/').pop() || s;
  if (base.endsWith('.git')) base = base.slice(0, -4);
  return base || src;
}
function displayName(f: WorkspaceFolder): string {
  if (f.name && !looksLikeId(f.name)) return f.name;
  return nameFromSource(f.source) || f.name || f.rid;
}
function isGit(src?: string) { return !!src && /(^git@|https?:\/\/|\.git$)/i.test(src); }

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
      if (ex) {
        ex.connected = true;
        if (r.name && !looksLikeId(r.name)) ex.name = r.name;
        if (!ex.source) ex.source = r.source;
      } else {
        map.set(r.repo_id, { rid: r.repo_id, name: r.name, source: r.source, captures: 0, last_ts: null, last_summary: null, metrics: null, connected: true });
      }
    });
    return Array.from(map.values());
  })();

  const connect = () => { if (source.trim()) connectAndGo(source.trim()); };

  return (
    <div className="kyc-home">
      <div className="page-header">
        <h1>Connect a codebase</h1>
        <p>Paste a local path or Git URL — KnowIT parses it, builds a code graph, and indexes it for search.</p>
      </div>

      <div className="card kyc-connect">
        {error && <div className="toast toast--err" style={{ marginBottom: 12 }}>{error}</div>}
        <div className="kyc-connect__row">
          <input
            className="input kyc-connect__input"
            placeholder="C:\path\to\repo    or    https://github.com/owner/repo.git"
            value={source}
            onChange={e => setSource(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') connect(); }}
            disabled={connecting}
            autoFocus
          />
          <button className="btn btn--primary kyc-connect__btn" onClick={connect} disabled={connecting || !source.trim()}>
            {connecting ? 'Indexing…' : 'Connect'}
          </button>
        </div>

        {connecting ? (
          <div className="kyc-connect__prog">
            <div className="kyc-connect__bar"><div className="kyc-connect__fill" style={{ width: `${Math.max(4, progress.pct)}%` }} /></div>
            <div className="kyc-connect__prog-msg">{progress.message || 'Working…'}{progress.pct ? ` · ${progress.pct}%` : ''}</div>
          </div>
        ) : (
          <div className="kyc-connect__hint">Clones Git URLs at depth 200 · re-connecting the same source is instant (cached).</div>
        )}

        <details className="kyc-steps">
          <summary className="kyc-steps__summary">
            <span className="kyc-steps__dot" />
            How it works: connect → index → explore the tabs
            <span className="kyc-steps__more">details</span>
          </summary>
          <div className="kyc-steps__body">
            <div className="kyc-steps__row"><span className="kyc-steps__n">1</span><span><b>Connect</b> a local folder or a public Git URL above.</span></div>
            <div className="kyc-steps__row"><span className="kyc-steps__n">2</span><span><b>KnowIT indexes it</b> — symbols, a code graph, and embeddings. Cached after the first run.</span></div>
            <div className="kyc-steps__row"><span className="kyc-steps__n">3</span><span><b>Explore</b> Overview, Files, Diagrams, Ask, Learn, Track and more.</span></div>
            <div className="kyc-steps__note">Want generated answers in <b>Ask</b> and <b>Learn</b>? Add a model (local Ollama or a cloud key) in <Link to="/settings" className="kyc-link">AI settings</Link> — everything else works without one.</div>
          </div>
        </details>
      </div>

      <div className="card">
        <div className="card-header"><h3>Your codebases <span className="kyc-count">{merged.length}</span></h3></div>
        {merged.length === 0 ? (
          <div className="empty-state"><h3>No codebases yet</h3><p>Connect one above to start tracking it over time.</p></div>
        ) : (
          <div className="kyc-home__list">
            {merged.map(f => {
              const nm = displayName(f);
              return (
                <button key={f.rid} type="button" className={'kyc-folder' + (f.connected ? ' kyc-folder--live' : '')} onClick={() => openFolder(f)} title={f.source || nm}>
                  <span className="kyc-folder__icon">{isGit(f.source) ? '⎇' : '▣'}</span>
                  <div className="kyc-folder__main">
                    <div className="kyc-folder__name">{nm}</div>
                    {f.source && <div className="kyc-folder__source">{f.source}</div>}
                    {f.last_summary && <div className="kyc-folder__change">↳ {f.last_summary}</div>}
                  </div>
                  <div className="kyc-folder__meta">
                    {f.connected ? <span className="kyc-pill kyc-pill--live">● live</span> : <span className="kyc-pill">offline</span>}
                    {f.captures > 0 && <span className="kyc-pill kyc-pill--soft">{f.captures} capture{f.captures === 1 ? '' : 's'}</span>}
                    {f.last_ts && <span className="kyc-folder__date">{new Date(f.last_ts).toLocaleDateString()}</span>}
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>

      <details className="card kyc-ref">
        <summary className="kyc-ref__summary">
          <span className="kyc-ref__icon">i</span>
          <span className="kyc-ref__title">Reference — what the metrics mean</span>
          <span className="kyc-ref__hint">{GLOSSARY.length} terms</span>
          <span className="kyc-ref__chev">▸</span>
        </summary>
        <div className="kyc-ref__grid">
          {GLOSSARY.map(g => (
            <div key={g.term} className="kyc-ref__item">
              <div className="kyc-ref__term">{g.term}</div>
              <div className="kyc-ref__def">{g.def}</div>
            </div>
          ))}
        </div>
      </details>
    </div>
  );
}
