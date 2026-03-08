chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "analyze") {
    const backendUrl = `http://127.0.0.1:8000/analyze?url=${encodeURIComponent(request.url)}&count=10`;
    
    console.log('🔵 Background: Fetching', backendUrl);
    
    fetch(backendUrl)
      .then(async (res) => {
        console.log('🔵 Background: Response status', res.status);
        
        // CRITICAL FIX: Handle non-200 responses properly
        if (!res.ok) {
          const text = await res.text();
          try {
            const json = JSON.parse(text);
            console.error('🔴 Backend error:', json.detail);
            sendResponse({ error: json.detail || `Server error ${res.status}` });
          } catch {
            console.error('🔴 Backend returned non-JSON:', text);
            sendResponse({ error: `Backend returned ${res.status}: ${text.substring(0, 100)}` });
          }
          return null; // Stop the chain
        }
        
        return res.json();
      })
      .then(data => {
        if (data) {
          console.log('🟢 Background: Success', data);
          sendResponse(data);
        }
      })
      .catch(err => {
        console.error('🔴 Background: Network error', err);
        sendResponse({ error: 'Cannot reach backend. Is it running on port 8000?' });
      });
    
    return true; // Keep channel open for async response
  }
});