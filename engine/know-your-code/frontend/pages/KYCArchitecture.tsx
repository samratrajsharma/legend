import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { kycApi, Repo } from '../api/kycApi';
import KycChip from '../components/KycChip/KycChip';
import DependencyGraph from '../components/DependencyGraph/DependencyGraph';
import '../kyc.css';
import './KYCArchitecture.css';

export default function KYCArchitecture() {
  const { id = '' } = useParams();
  const [repo, setRepo] = useState<Repo | null>(null);
  useEffect(() => { kycApi.getRepo(id).then((r) => setRepo(r.data)).catch(() => {}); }, [id]);
  return (
    <div>
      <div className="page-header kyc-head">
        <div>
          <div className="kyc-eyebrow">Legend</div>
          <h1>Architecture</h1>
          <p>How {repo?.name || 'the codebase'} fits together — files are nodes, imports are edges. Hover to trace dependencies, click a node for detail.</p>
        </div>
        <KycChip />
      </div>
      <DependencyGraph repoId={id} ready={repo?.status === 'ready'} full />
    </div>
  );
}
