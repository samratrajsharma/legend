import React, { useEffect, useState } from 'react';
import './Navbar.css';
import Logo from './Logo';
import { DOCS_URL, GITHUB_URL } from './links';

const Navbar: React.FC = () => {
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const h = () => setScrolled(window.scrollY > 10);
    window.addEventListener('scroll', h);
    return () => window.removeEventListener('scroll', h);
  }, []);

  return (
    <nav className={'kn-nav' + (scrolled ? ' kn-nav--scrolled' : '')}>
      <div className="kn-nav__inner">
        <a href="#kyc-top" className="kn-nav__brand">
          <Logo className="kn-nav__mark" size={20} />
          <span className="kn-nav__name">Legend</span>
        </a>

        <ul className="kn-nav__links">
          <li><a href="#how-it-works">How it works</a></li>
          <li><a href="#what-you-get">What you get</a></li>
          <li><a href={DOCS_URL} target="_blank" rel="noopener noreferrer">Docs</a></li>
        </ul>

        <div className="kn-nav__cta">
          <a className="kn-nav__ghost" href={GITHUB_URL} target="_blank" rel="noopener noreferrer">GitHub</a>
          <a className="kn-nav__btn" href="#install">Install</a>
        </div>
      </div>
    </nav>
  );
};

export default Navbar;
