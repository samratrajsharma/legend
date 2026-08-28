import React from 'react';

// The Legend mark: a small node/edge graph (code as a connected map), in Spotify green.
const Logo: React.FC<{ size?: number; className?: string }> = ({ size = 20, className }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 48 48"
    fill="none"
    role="img"
    aria-label="Legend"
    className={className}
  >
    <g stroke="#1DB954" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="24" y1="24" x2="24" y2="9" />
      <line x1="24" y1="24" x2="37" y2="31.5" />
      <line x1="24" y1="24" x2="11" y2="31.5" />
      <line x1="24" y1="9" x2="37" y2="31.5" />
      <line x1="37" y1="31.5" x2="11" y2="31.5" />
      <line x1="11" y1="31.5" x2="24" y2="9" />
    </g>
    <g fill="#1DB954">
      <circle cx="24" cy="24" r="4.6" />
      <circle cx="24" cy="9" r="4" />
      <circle cx="37" cy="31.5" r="4" />
      <circle cx="11" cy="31.5" r="4" />
    </g>
  </svg>
);

export default Logo;
