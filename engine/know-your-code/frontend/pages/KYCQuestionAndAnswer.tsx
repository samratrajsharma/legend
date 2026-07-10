import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { kycApi, Repo } from '../api/kycApi';
import KycChip from '../components/KycChip/KycChip';
import QAChatPanel from '../components/QAChatPanel/QAChatPanel';
import '../kyc.css';
import './KYCQuestionAndAnswer.css';

export default function KYCQuestionAndAnswer() {
  const { id = '' } = useParams();
  const [repo, setRepo] = useState<Repo | null>(null);
  useEffect(() => { kycApi.getRepo(id).then((r) => setRepo(r.data)).catch(() => {}); }, [id]);
  return (
    <div>
      <div className="page-header kyc-head">
        <div>
          <div className="kyc-eyebrow">Know Your Code</div>
          <h1>Ask {repo?.name || 'this codebase'}</h1>
          <p>Ask anything about the code. Every answer cites the exact files and lines it came from.</p>
        </div>
        <KycChip />
      </div>
      <QAChatPanel repoId={id} ready={repo?.status === 'ready'} />
    </div>
  );
}
