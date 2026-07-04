import './InfoTip.css';

export default function InfoTip({ text, label }: { text: string; label?: string }) {
  if (!text) return null;
  return (
    <span className="infotip" tabIndex={0} aria-label={label ? `${label}: ${text}` : text}>
      <span className="infotip__icon" aria-hidden="true">?</span>
      <span className="infotip__bubble" role="tooltip">
        {label && <strong>{label}</strong>}{text}
      </span>
    </span>
  );
}
