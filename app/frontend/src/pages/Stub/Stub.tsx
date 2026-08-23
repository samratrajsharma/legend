import './Stub.css';

export default function Stub({ title }: { title: string }) {
  return (
    <div>
      <div className="page-header">
        <h1>{title}</h1>
        <p>This page is stubbed for the v1 testbed. Coming in a future session.</p>
      </div>
      <div className="card stub">
        <div className="stub__icon" aria-hidden="true">
          <img src="/knowyourcode-icon.svg" width={64} height={64} alt="" />
        </div>
        <h3 className="stub__title">{title} is on the way</h3>
        <p className="stub__body">
          The KnowIT engine already supports this — it ships in the next round of UI work on this testbed.
          See the integration plan document for the full surface roadmap.
        </p>
      </div>
    </div>
  );
}
