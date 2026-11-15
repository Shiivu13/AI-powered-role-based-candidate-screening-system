import React, { useEffect, useState } from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, NavLink, Route, Routes } from "react-router-dom";
import { api } from "./api/client";
import type { Health } from "./api/types";
import { Logo } from "./components/icons";
import HistoryPage from "./pages/HistoryPage";
import ComparePage from "./pages/ComparePage";
import LabPage from "./pages/LabPage";
import SessionPage from "./pages/SessionPage";
import SetupPage from "./pages/SetupPage";
import "./styles.css";

function SystemStatus() {
  const [health, setHealth] = useState<Health | null>(null);
  const [down, setDown] = useState(false);
  useEffect(() => {
    api.health().then(setHealth).catch(() => setDown(true));
  }, []);
  if (down) return <span className="status status-down">backend offline</span>;
  if (!health) return null;
  return (
    <span className="status" title={`Embeddings: ${health.embedding_provider} · DB: ${health.database}`}>
      <span className={`dot ${health.llm_provider === "offline" ? "dot-amber" : "dot-green"}`} />
      {health.llm_provider === "offline" ? "Offline mode (no LLM key)" : `LLM: ${health.llm_model}`}
    </span>
  );
}

function App() {
  return (
    <BrowserRouter>
      <nav className="nav">
        <NavLink to="/" className="brand">
          <Logo size={20} /> ScreenRAG
        </NavLink>
        <div className="nav-links">
          <NavLink to="/" end>
            New interview
          </NavLink>
          <NavLink to="/sessions" end>
            Sessions
          </NavLink>
          <NavLink to="/compare">Compare</NavLink>
          <NavLink to="/lab">Retrieval lab</NavLink>
          <SystemStatus />
        </div>
      </nav>
      <Routes>
        <Route path="/" element={<SetupPage />} />
        <Route path="/sessions" element={<HistoryPage />} />
        <Route path="/sessions/:sessionId" element={<SessionPage />} />
        <Route path="/compare" element={<ComparePage />} />
        <Route path="/lab" element={<LabPage />} />
        <Route path="*" element={<div className="page">Not found</div>} />
      </Routes>
    </BrowserRouter>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
