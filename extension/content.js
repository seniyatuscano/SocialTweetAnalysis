/**
 * Content script: grabs the current page URL and sends it to the local FastAPI backend.
 * Runs when the page has finished loading (document_idle).
 */

const BACKEND_BASE = 'http://localhost:8000';

function sendUrlToBackend() {
  const url = window.location.href;
  if (!url) return;

  fetch(`${BACKEND_BASE}/url`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ url }),
  })
    .then((res) => {
      if (!res.ok) {
        throw new Error(`Backend responded with ${res.status}`);
      }
      return res.json();
    })
    .then((data) => {
      console.log('[Social Backchannel] URL sent to backend:', url, data);
    })
    .catch((err) => {
      console.warn('[Social Backchannel] Failed to send URL to backend:', err.message);
    });
}

// Send the current page URL when the content script runs
sendUrlToBackend();
