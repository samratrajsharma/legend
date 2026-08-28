import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { kycApi, Repo } from '../api/kycApi';
import KycChip from '../components/KycChip/KycChip';
import RepoCard from '../components/RepoCard/RepoCard';
import '../kyc.css';
import './KYCRepos.css';

export default function KYCRepos() {
  const nav = useNavigate();
  const [items, setItems] = useState<Repo[]>([]);
  const [loading, setLoading] = useState(true);
  const load = () =>
    kycApi.listRepos().then((r) => setItems(r.data)).catch(() => {}).finally(() => setLoading(false));
  useEffect(() => { load(); }, []);

  return (
    <div>
      <div className="page-header kyc-head">
        <div>
          <div className="kyc-eyebrow">Legend</div>
          <h1>Codebases</h1>
          <p>Connect a repository to ask questions, see architecture, and onboard engineers faster.</p>
        </div>
        <KycChip />
      </div>

      <div className="card">
        <div className="card-header">
          <h3>Your codebases</h3>
          <button className="btn btn--primary btn--sm" onClick={() => nav('/app/legend')}>+ New codebase</button>
        </div>
        {loading ? (
          <div className="dash-loading">Loading…</div>
        ) : items.length === 0 ? (
          <div className="empty-state">
            <h3>No codebases yet</h3>
            <p>Connect a Git repo or upload a zip to begin.</p>
            <button className="btn btn--primary" onClick={() => nav('/app/legend')}>Get started</button>
          </div>
        ) : (
          <div className="kyc-grid">{items.map((r) => <RepoCard key={r.id} repo={r} onChange={load} />)}</div>
        )}
      </div>
    </div>
  );
}
