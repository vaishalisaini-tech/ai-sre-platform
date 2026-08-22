// src/api.js
import axios from "axios";

// One place that knows where the backend lives.
const API_BASE = "/api";

// Fetch all logged incidents
export async function getIncidents() {
  const response = await axios.get(`${API_BASE}/incidents`);
  return response.data;
}

// Submit a new incident to the agent
export async function submitIncident(errorMessage) {
  const response = await axios.post(`${API_BASE}/incident`, {
    error_message: errorMessage,
  });
  return response.data;
}

