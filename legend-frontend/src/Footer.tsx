import React from 'react';
import './Footer.css';
import { DOCS_URL, GITHUB_URL } from './links';

const Footer: React.FC = () => (
  <footer className="kn-foot">
    <div className="container kn-foot__inner">
      <span className="kn-foot__brand">
        <span className="kn-foot__mark" aria-hidden="true" />
        Legend
      </span>
      <nav className="kn-foot__links">
        <a href="#how-it-works">How it works</a>
        <a href="#what-you-get">Features</a>
        <a href={DOCS_URL}>Docs</a>
        <a href={GITHUB_URL} target="_blank" rel="noopener noreferrer">GitHub</a>
      </nav>
      <span className="kn-foot__copy">© {new Date().getFullYear()} Legend — open source, local-first.</span>
    </div>
  </footer>
);

export default Footer;
