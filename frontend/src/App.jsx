import { useState, useEffect } from "react";
import { getIncidents, submitIncident } from "./api";
import "./App.css";

// Map an action_taken string to a status badge category
function actionStatus(action = "") {
  const a = action.toUpperCase();
  if (a.startsWith("EXECUTED")) return { label: "Auto-Remediated", cls: "badge-green" };
  if (a.startsWith("ESCALATED")) return { label: "Escalated", cls: "badge-red" };
  if (a.startsWith("FAILED")) return { label: "Failed", cls: "badge-red" };
  if (a.startsWith("PENDING")) return { label: "Pending Approval", cls: "badge-amber" };
  return { label: "Logged", cls: "badge-gray" };
}

function timeAgo(ts) {
  if (!ts) return "";
  const diff = (Date.now() - new Date(ts).getTime()) / 1000;
  if (diff < 60) return `${Math.floor(diff)}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return new Date(ts).toLocaleDateString();
}

export default function App() {
  const [incidents, setIncidents] = useState([]);
  const [errorText, setErrorText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(null);

  async function loadIncidents() {
    try {
      const data = await getIncidents();
      setIncidents(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  // Initial load + auto-refresh every 5s so autonomous incidents appear live
  useEffect(() => {
    loadIncidents();
    const id = setInterval(loadIncidents, 5000);
    return () => clearInterval(id);
  }, []);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!errorText.trim()) return;
    setSubmitting(true);
    await submitIncident(errorText);
    setErrorText("");
    await loadIncidents();
    setSubmitting(false);
  }

  // Derived stats
  const total = incidents.length;
  const remediated = incidents.filter((i) => (i.action_taken || "").toUpperCase().startsWith("EXECUTED")).length;
  const escalated = incidents.filter((i) => (i.action_taken || "").toUpperCase().startsWith("ESCALATED")).length;
  const pending = incidents.filter((i) => (i.action_taken || "").toUpperCase().startsWith("PENDING")).length;

  return (
    <div className="app">
      <header className="header">
        <div className="brand">
          <span className="logo">🤖</span>
          <div>
            <h1>AI-SRE Platform</h1>
            <p className="subtitle">Autonomous incident detection, diagnosis &amp; remediation</p>
          </div>
        </div>
        <div className="status-pill">
          <span className="pulse" />
          Agent Online
        </div>
      </header>

      <section className="stats">
        <StatCard label="Total Incidents" value={total} accent="blue" />
        <StatCard label="Auto-Remediated" value={remediated} accent="green" />
        <StatCard label="Pending Approval" value={pending} accent="amber" />
        <StatCard label="Escalated" value={escalated} accent="red" />
      </section>

      <section className="card">
        <h2>Simulate an Incident</h2>
        <form onSubmit={handleSubmit} className="incident-form">
          <input
            value={errorText}
            onChange={(e) => setErrorText(e.target.value)}
            placeholder="e.g. Pod payment-service is in CrashLoopBackOff"
          />
          <button type="submit" disabled={submitting}>
            {submitting ? "Diagnosing…" : "Submit Incident"}
          </button>
        </form>
      </section>

      <section className="card">
        <div className="card-head">
          <h2>Incident History</h2>
          <span className="live-tag"><span className="pulse small" /> Live</span>
        </div>

        {loading ? (
          <div className="empty">Loading incidents…</div>
        ) : incidents.length === 0 ? (
          <div className="empty">No incidents yet. Submit one above, or let the agent detect a failing pod.</div>
        ) : (
          <div className="incident-list">
            {incidents.map((inc) => {
              const status = actionStatus(inc.action_taken);
              const isOpen = expanded === inc.id;
              return (
                <div key={inc.id} className={`incident ${isOpen ? "open" : ""}`} onClick={() => setExpanded(isOpen ? null : inc.id)}>
                  <div className="incident-row">
                    <span className="inc-id">#{inc.id}</span>
                    <span className="inc-error">{inc.error_message}</span>
                    <span className="inc-runbook">{inc.matched_runbook || "—"}</span>
                    <span className={`badge ${status.cls}`}>{status.label}</span>
                    <span className="inc-time">{timeAgo(inc.created_at)}</span>
                  </div>
                  {isOpen && (
                    <div className="incident-detail">
                      <div><strong>Diagnosis</strong><p>{inc.diagnosis}</p></div>
                      <div><strong>Action</strong><p>{inc.action_taken}</p></div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </section>

      <footer className="footer">Built with FastAPI · LangGraph · pgvector · Gemini · GKE · Terraform · Jenkins</footer>
    </div>
  );
}

function StatCard({ label, value, accent }) {
  return (
    <div className={`stat stat-${accent}`}>
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}

