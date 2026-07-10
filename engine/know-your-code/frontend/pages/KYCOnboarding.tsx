import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { kycApi, Tour, TourStep } from '../api/kycApi';
import KycChip from '../components/KycChip/KycChip';
import '../kyc.css';
import './KYCOnboarding.css';

interface Props { repoId?: string; embedded?: boolean; }

export default function KYCOnboarding({ repoId, embedded }: Props) {
  const params = useParams();
  const id = repoId || params.id || '';
  const [tour, setTour] = useState<Tour | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [present, setPresent] = useState(false);
  const [idx, setIdx] = useState(0);

  const load = () =>
    kycApi.getTour(id).then((r) => setTour(r.data)).catch(() => {}).finally(() => setLoading(false));
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [id]);

  const generate = async () => {
    setBusy(true);
    try { const r = await kycApi.generateTour(id); setTour(r.data); setIdx(0); }
    catch { /* surfaced via empty steps */ } finally { setBusy(false); }
  };

  const steps: TourStep[] = tour?.steps || [];
  const head = !embedded && (
    <div className="page-header kyc-head">
      <div>
        <div className="kyc-eyebrow">Know Your Code</div>
        <h1>Onboarding tour</h1>
        <p>A guided walk through the codebase, from entry points to the core.</p>
      </div>
      <KycChip />
    </div>
  );

  if (loading) return <div>{head}<div className="dash-loading">Loading…</div></div>;

  if (steps.length === 0) {
    return (
      <div>{head}
        <div className="card"><div className="empty-state">
          <h3>No tour yet</h3>
          <p>Generate a guided onboarding tour for this codebase.</p>
          <button className="btn btn--primary" disabled={busy} onClick={generate}>
            {busy ? 'Generating…' : 'Generate tour'}
          </button>
        </div></div>
      </div>
    );
  }

  if (present) {
    const st = steps[idx];
    return (
      <div>{head}
        <div className="card kyc-present">
          <div className="kyc-present-count">Step {idx + 1} of {steps.length}</div>
          <h2>{st.title}</h2>
          <p>{st.description}</p>
          {st.file_path && <div className="kyc-step-file">{st.file_path}{st.line_range ? `:${st.line_range}` : ''}</div>}
          <div className="kyc-present-nav">
            <button className="btn btn--secondary" disabled={idx === 0} onClick={() => setIdx((i) => Math.max(0, i - 1))}>← Previous</button>
            <button className="btn btn--secondary" onClick={() => setPresent(false)}>Exit</button>
            {idx < steps.length - 1
              ? <button className="btn btn--primary" onClick={() => setIdx((i) => i + 1)}>Next →</button>
              : <button className="btn btn--primary" onClick={() => setPresent(false)}>Finish</button>}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div>{head}
      <div className="card">
        <div className="card-header">
          <h3>{steps.length} steps</h3>
          <div className="kyc-tour-actions">
            <button className="btn btn--secondary btn--sm" disabled={busy} onClick={generate}>{busy ? '…' : 'Regenerate'}</button>
            <button className="btn btn--primary btn--sm" onClick={() => { setIdx(0); setPresent(true); }}>Start tour</button>
          </div>
        </div>
        <ol className="kyc-steps">
          {steps.map((st, i) => (
            <li key={i} className="kyc-step">
              <div className="kyc-step-n">{i + 1}</div>
              <div className="kyc-step-body">
                <div className="kyc-step-title">{st.title}</div>
                <div className="kyc-step-desc">{st.description}</div>
                {st.file_path && <div className="kyc-step-file">{st.file_path}{st.line_range ? `:${st.line_range}` : ''}</div>}
              </div>
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}
