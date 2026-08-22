// src/App.jsx
import { useState, useEffect } from "react";
import { getIncidents, submitIncident } from "./api";
import "./App.css";

function App() {
  // "state" = data React re-renders the screen around when it changes
  const [incidents, setIncidents] = useState([]);   // the table rows
  const [errorText, setErrorText] = useState("");    // the form input
  const [loading, setLoading] = useState(false);

  // Load incidents from the backend and store them
  async function loadIncidents() {
    const data = await getIncidents();
    setIncidents(data);
  }

  // useEffect with [] runs ONCE when the page first loads
  useEffect(() => {
    loadIncidents();
  }, []);

  // Runs when the form is submitted
  async function handleSubmit(event) {
    event.preventDefault();          // stop the page from reloading
    if (!errorText.trim()) return;   // ignore empty input
    setLoading(true);
    await submitIncident(errorText); // send to the agent
    setErrorText("");                // clear the box
    await loadIncidents();           // refresh the table
    setLoading(false);
  }

  return (
    <div className="container">
      <h1>🤖 AI-SRE Platform</h1>
      <p>Submit an incident and let the agent diagnose it.</p>

      <form onSubmit={handleSubmit} className="incident-form">
        <input
          type="text"
          value={errorText}
          onChange={(e) => setErrorText(e.target.value)}
          placeholder="e.g. Pod payment-service is in CrashLoopBackOff"
        />
        <button type="submit" disabled={loading}>
          {loading ? "Diagnosing..." : "Submit Incident"}
        </button>
      </form>

      <h2>Incident History</h2>
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Error</th>
            <th>Matched Runbook</th>
            <th>Diagnosis</th>
            <th>Time</th>
          </tr>
        </thead>
        <tbody>
          {incidents.map((inc) => (
            <tr key={inc.id}>
              <td>{inc.id}</td>
              <td>{inc.error_message}</td>
              <td>{inc.matched_runbook}</td>
              <td>{inc.diagnosis}</td>
              <td>{new Date(inc.created_at).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default App;

