import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'

// StrictMode removed — it double-mounts components in dev,
// causing two WebSocket connections and duplicate events.
ReactDOM.createRoot(document.getElementById('root')).render(
  <App />
)
