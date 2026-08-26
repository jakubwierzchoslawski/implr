import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import '@xyflow/react/dist/style.css';
import './tokens.css';
import './app.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
