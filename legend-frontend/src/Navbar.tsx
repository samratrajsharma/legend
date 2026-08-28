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
    <nav className={'lg-nav' + (scrolled ? ' lg-nav--scrolled' : '')}>
      <div className="lg-nav__inner">
        <a href="#lg-top" className="lg-nav__brand">
          <Logo className="lg-nav__mark" size={20} />
          <span className="lg-nav__name">Legend</span>
        </a>

        <ul className="lg-nav__links">
          <li><a href="#how-it-works">How it works</a></li>
          <li><a href="#what-you-get">What you get</a></li>
          <li><a href="#mcp">MCP</a></li>
          <li><a href={DOCS_URL}>Docs</a></li>
        </ul>

        <div className="lg-nav__cta">
          <a className="lg-nav__ghost" href={GITHUB_URL} target="_blank" rel="noopener noreferrer">GitHub</a>
          <a className="lg-nav__btn" href="#install">Install</a>
        </div>
      </div>
    </nav>
  );
};

export default Navbar;
