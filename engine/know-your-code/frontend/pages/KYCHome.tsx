import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { kycApi, Repo } from '../api/kycApi';
import KycChip from '../components/KycChip/KycChip';
import RepoCard from '../components/RepoCard/RepoCard';
import '../kyc.css';
import './KYCHome.css';

export default function KYCHome() {
  const nav = useNavigate();
  const [repos, setRepos] = useState<Repo[]>([]);
  const [loading, setLoading] = useState(true);
  const [modal, setModal] = useState<null | 'git' | 'upload'>(null);
  const [name, setName] = useState('');
  const [url, setUrl] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  const load = () =>
    kycApi.listRepos().then((r) => setRepos(r.data)).catch(() => {}).finally(() => setLoading(false));
  useEffect(() => { load(); }, []);

  const submit = async () => {
    setBusy(true); setErr('');
    try {
      if (modal === 'git') {
        const r = await kycApi.createRepo({ source: 'git', source_url: url, name: name || url.split('/').pop() || 'repo' });
        nav(`/app/know-your-code/repos/${r.data.id}`);
      } else if (modal === 'upload' && file) {
        const r = await kycApi.createRepo({ source: 'upload', name: name || file.name.replace(/\.zip$/, '') });
        await kycApi.uploadZip(r.data.id, file);
        nav(`/app/know-your-code/repos/${r.data.id}`);
      }
    } catch (e: any) {
      setErr(e?.response?.data?.detail || 'Could not create the codebase.');
    } finally { setBusy(false); }
  };

  return (
    <div>
      <div className="page-header kyc-head">
        <div>
          <div className="kyc-eyebrow">Know Your Code</div>
          <h1>Map your codebase in minutes.</h1>
          <p>Connect a repository to ask questions in plain English, see how it fits together, and onboard engineers faster.</p>
        </div>
        <KycChip />
      </div>

      <div className="kyc-hero">
        <button className="kyc-hero-action" onClick={() => { setModal('git'); setName(''); setUrl(''); setErr(''); }}>
          <span className="kyc-hero-ico">⎇</span>
          <span className="kyc-hero-t">Connect a Git repo</span>
          <span className="kyc-hero-d">Clone from a URL and index it automatically.</span>
        </button>
        <button className="kyc-hero-action" onClick={() => { setModal('upload'); setName(''); setFile(null); setErr(''); }}>
          <span className="kyc-hero-ico">⇪</span>
          <span className="kyc-hero-t">Upload a zip</span>
          <span className="kyc-hero-d">Drop in a zipped codebase to analyse it privately.</span>
        </button>
      </div>

      <div className="card">
        <div className="card-header">
          <h3>Recent codebases</h3>
          <button className="btn btn--secondary btn--sm" onClick={() => nav('/app/know-your-code/repos')}>View all</button>
        </div>
        {loading ? (
          <div className="dash-loading">Loading…</div>
        ) : repos.length === 0 ? (
          <div className="empty-state"><h3>No codebases yet</h3><p>Connect a Git repo or upload a zip to begin.</p></div>
        ) : (
          <div className="kyc-grid">{repos.slice(0, 6).map((r) => <RepoCard key={r.id} repo={r} onChange={load} />)}</div>
        )}
      </div>

      {modal && (
        <div className="modal-overlay" onClick={() => !busy && setModal(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>{modal === 'git' ? 'Connect a Git repo' : 'Upload a zip'}</h3>
            <div className="form-row"><div className="input-group">
              <label>Name</label>
              <input value={name} onChange={(e) => setName(e.target.value)} placeholder="my-service" />
            </div></div>
            {modal === 'git' ? (
              <div className="form-row"><div className="input-group">
                <label>Git URL</label>
                <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://github.com/org/repo.git" />
              </div></div>
            ) : (
              <div className="form-row"><div className="input-group">
                <label>Archive (.zip)</label>
                <input type="file" accept=".zip" onChange={(e) => setFile(e.target.files?.[0] || null)} />
              </div></div>
            )}
            {err && <div className="kyc-toast kyc-toast--err">{err}</div>}
            <div className="kyc-modal-actions">
              <button className="btn btn--secondary" disabled={busy} onClick={() => setModal(null)}>Cancel</button>
              <button className="btn btn--primary" disabled={busy || (modal === 'git' ? !url : !file)} onClick={submit}>
                {busy ? 'Working…' : 'Create'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
