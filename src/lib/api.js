const DEFAULT_API_BASE = (import.meta.env.BASE_URL || "/").replace(/\/$/, "");
const API_BASE = (import.meta.env.VITE_API_BASE || DEFAULT_API_BASE).replace(/\/$/, "");

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  const raw = await response.text();
  let data = null;

  try {
    data = raw ? JSON.parse(raw) : null;
  } catch {
    data = { error: raw || "Unexpected response from DeepHPI." };
  }

  if (!response.ok) {
    throw new Error(data?.error || "Request failed.");
  }

  return data;
}

export const api = {
  submitJob(payload) {
    return request("/api/jobs", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  getJob(jobId) {
    return request(`/api/jobs/${jobId}`, { headers: {} });
  },
  getResults(jobId) {
    return request(`/api/jobs/${jobId}/results`, { headers: {} });
  },
  getNetwork(jobId) {
    return request(`/api/jobs/${jobId}/network`, { headers: {} });
  },
};
