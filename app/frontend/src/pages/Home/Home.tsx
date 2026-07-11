import { useEffect, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { kycApi, RepoListItem, WorkspaceFolder } from '../../api/client';
import './Home.css';

// The backend sometimes only has the repo id — derive a friendly name from the source.
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

const GitIcon = () => (
  <svg width="17" height="17" viewBox="0 0 16 16" fill="none" aria-hidden="true">
    <circle cx="4" cy="4" r="1.7" stroke="currentColor" strokeWidth="1.4" />
    <circle cx="4" cy="12" r="1.7" stroke="currentColor" strokeWidth="1.4" />
    <circle cx="12" cy="6.5" r="1.7" stroke="currentColor" strokeWidth="1.4" />
    <path d="M4 5.7v4.6M5.7 4H9.2a1.8 1.8 0 0 1 1.8 1.8v.9" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
  </svg>
);
const FolderIcon = () => (
  <svg width="17" height="17" viewBox="0 0 16 16" fill="none" aria-hidden="true">
    <path d="M1.8 4.2A1.2 1.2 0 0 1 3 3h3l1.4 1.4H13a1.2 1.2 0 0 1 1.2 1.2v6A1.2 1.2 0 0 1 13 12.8H3a1.2 1.2 0 0 1-1.2-1.2V4.2z" stroke="currentColor" strokeWidth="1.3" />
  </svg>
);

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
      </div>

      <div className="kyc-home__sec">
        <div className="kyc-home__sec-head">
          <span className="kyc-home__sec-title">Your codebases</span>
          {merged.length > 0 && <span className="kyc-count">{merged.length}</span>}
        </div>

        {merged.length === 0 ? (
          <div className="card kyc-empty">
            <h3>No codebases yet</h3>
            <p>Paste a local folder or a public Git URL above to index your first one.</p>
            <p className="kyc-empty__hint">Want generated answers in Ask and Learn? Add a model (local Ollama or a cloud key) in <Link to="/settings" className="kyc-link">AI settings</Link> — everything else works without one.</p>
          </div>
        ) : (
          <div className="kyc-grid">
            {merged.map(f => {
              const nm = displayName(f);
              const git = isGit(f.source);
              return (
                <button key={f.rid} type="button" className="kyc-cb" onClick={() => openFolder(f)} title={f.source || nm}>
                  <div className="kyc-cb__top">
                    <span className={'kyc-cb__icon' + (git ? ' kyc-cb__icon--git' : '')}>{git ? <GitIcon /> : <FolderIcon />}</span>
                    <div className="kyc-cb__id">
                      <div className="kyc-cb__name">{nm}</div>
                      {f.source && <div className="kyc-cb__source">{f.source}</div>}
                    </div>
                  </div>
                  {f.last_summary && <div className="kyc-cb__change">{f.last_summary}</div>}
                  <div className="kyc-cb__foot">
                    {f.connected
                      ? <span className="kyc-pill kyc-pill--live"><span className="kyc-dot" />live</span>
                      : <span className="kyc-pill">offline</span>}
                    {f.captures > 0 && <span className="kyc-pill kyc-pill--soft">{f.captures} capture{f.captures === 1 ? '' : 's'}</span>}
                    {f.last_ts && <span className="kyc-cb__date">{new Date(f.last_ts).toLocaleDateString()}</span>}
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
