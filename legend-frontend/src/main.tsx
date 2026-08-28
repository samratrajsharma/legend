import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './theme.css';
import Legend from './Legend';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Legend />
  </StrictMode>
);
