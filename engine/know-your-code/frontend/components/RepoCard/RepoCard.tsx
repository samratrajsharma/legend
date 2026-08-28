import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { kycApi, Repo } from '../../api/kycApi';
import './RepoCard.css';

const STATUS: Record<string, { label: string; cls: string }> = {
  ready: { label: 'Ready', cls: 'kyc-pill--ok' },
  indexing: { label: 'Indexing…', cls: 'kyc-pill--idx' },
  failed: { label: 'Failed', cls: 'kyc-pill--err' },
};

export default function RepoCard({ repo, onChange }: { repo: Repo; onChange?: () => void }) {
  const nav = useNavigate();
  const [busy, setBusy] = useState(false);
  const s = repo.stats || {};
  const langs: string[] = Array.isArray(s.langs) ? s.langs : [];
  const st = STATUS[repo.status] || STATUS.indexing;
  const open = () => nav(`/app/legend/repos/${repo.id}`);
  const del = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!window.confirm(`Delete ${repo.name}? This cannot be undone.`)) return;
    setBusy(true);
    try { await kycApi.deleteRepo(repo.id); onChange && onChange(); }
    catch { /* admin-only; 403 for others */ } finally { setBusy(false); }
  };
  return (
    <div className="kyc-card" onClick={open}>
      <div className="kyc-card-top">
        <div className="kyc-card-name">{repo.name}</div>
        <span className={'kyc-pill ' + st.cls}>{st.label}</span>
      </div>
      <div className="kyc-card-meta">
        {langs.length ? langs.slice(0, 4).join(' · ') : '—'}
        {s.loc ? ` · ${Number(s.loc).toLocaleString()} LOC` : ''}
      </div>
      <div className="chip-list kyc-card-chips">{langs.slice(0, 4).map((l) => <span key={l} className="chip">{l}</span>)}</div>
      <div className="kyc-card-actions" onClick={(e) => e.stopPropagation()}>
        <button className="btn btn--secondary btn--sm" onClick={open}>Open</button>
        <button className="btn btn--secondary btn--sm" onClick={() => nav(`/app/legend/repos/${repo.id}/tour`)}>Tour</button>
        <button className="btn btn--danger btn--sm" disabled={busy} onClick={del}>Delete</button>
      </div>
    </div>
  );
}
