import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import './index.css'

try {
  const s = localStorage.getItem('hey-girlie-theme')
  if (s === 'light' || s === 'dark') {
    document.documentElement.dataset.theme = s
  } else if (s === 'intense') {
    document.documentElement.dataset.theme = 'dark'
  } else if (s === 'soft' || s === 'cozy') {
    document.documentElement.dataset.theme = 'light'
  }
} catch {
  /* ignore */
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
