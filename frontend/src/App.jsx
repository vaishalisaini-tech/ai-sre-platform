import { useState, useEffect } from "react";
import { getIncidents, submitIncident } from "./api";
import "./App.css";

function actionStatus(action = "") {
  const a = action.toUpperCase();
  if (a.startsWith("EXECUTED")) return { key: "remediated", label: "Auto-Remediated", cls: "badge-green" };
  if (a.startsWith("ESCALATED")) return { key: "escalated", label: "Escalated", cls: "badge-red" };
  if (a.startsWith("FAILED")) return { key: "escalated", label: "Failed", cls: "badge-red" };
  if (a.startsWith("PENDING")) return { key: "pending", label: "Pending Approval", cls: "badge-amber" };
  return { key: "logged", label: "Logged", cls: "badge-gray" };
}

function timeAgo(ts) {
  if (!ts) return "";
  const diff = (Date.now() - new Date(ts).getTime()) / 1000;
  if (diff < 60) return `${Math.floor(diff)}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return new Date(ts).toLocaleDateString();
}

// Bin incidents into per-minute buckets over the last N minutes
function buildBuckets(incidents, minutes = 15) {
  const now = Date.now();
  const buckets = new Array(minutes).fill(0);
  incidents.forEach((i) => {
    const t = new Date(i.created_at).getTime();
    const diffMin = Math.floor((now - t) / 60000);
    if (diffMin >= 0 && diffMin < minutes) buckets[minutes - 1 - diffMin] += 1;
  });
  return buckets;
}

const FILTERS = [
  { key: "all", label: "All" },
  { key: "remediated", label: "Auto-Remediated" },
  { key: "pending", label: "Pending" },
  { key: "escalated", label: "Escalated" },
];

export default function App() {
  const [incidents, setIncidents] = useState([]);
  const [errorText, setErrorText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(null);
  const [filter, setFilter] = useState("all");
  const [theme, setTheme] = useState(() => localStorage.getItem("theme") || "dark");

  useEffect(() => { localStorage.setItem("theme", theme); }, [theme]);

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

  const total = incidents.length;
  const remediated = incidents.filter((i) => actionStatus(i.action_taken).key === "remediated").length;
  const escalated = incidents.filter((i) => actionStatus(i.action_taken).key === "escalated").length;
  const pending = incidents.filter((i) => actionStatus(i.action_taken).key === "pending").length;

  const filtered = filter === "all"
    ? incidents
    : incidents.filter((i) => actionStatus(i.action_taken).key === filter);

  const buckets = buildBuckets(incidents, 15);
  const maxBucket = Math.max(1, ...buckets);

  return (
    <div className={`app ${theme}`}>
      <header className="header">
        <div className="brand">
          <span className="logo">🤖</span>
          <div>
            <h1>AI-SRE Platform</h1>
            <p className="subtitle">Autonomous incident detection, diagnosis &amp; remediation</p>
          </div>
        </div>
        <div className="header-right">
          <button className="theme-btn" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>
            {theme === "dark" ? "☀️ Light" : "🌙 Dark"}
          </button>
          <div className="status-pill"><span className="pulse" />Agent Online</div>
        </div>
      </header>

      <section className="stats">
        <StatCard label="Total Incidents" value={total} accent="blue" />
        <StatCard label="Auto-Remediated" value={remediated} accent="green" />
        <StatCard label="Pending Approval" value={pending} accent="amber" />
        <StatCard label="Escalated" value={escalated} accent="red" />
      </section>

      <section className="card">
        <div className="card-head">
          <h2>Incident Activity</h2>
          <span className="muted-tag">last 15 min</span>
        </div>
        <div className="chart">
          {buckets.map((v, idx) => (
            <div className="bar-wrap" key={idx}>
              <div className="bar" style={{ height: `${(v / maxBucket) * 100}%` }} title={`${v} incident(s)`} />
            </div>
          ))}
        </div>
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

        <div className="filters">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              className={`filter-pill ${filter === f.key ? "active" : ""}`}
              onClick={() => setFilter(f.key)}
            >
              {f.label}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="empty">Loading incidents…</div>
        ) : filtered.length === 0 ? (
          <div className="empty">No incidents in this view.</div>
        ) : (
          <div className="incident-list">
            {filtered.map((inc) => {
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

