// ============================================
// DOM ELEMENTS
// ============================================
const elements = {
  stateLoading: document.getElementById('state-loading'),
  stateError: document.getElementById('state-error'),
  stateResult: document.getElementById('state-result'),
  errorMessage: document.getElementById('error-message'),
  bulletList: document.getElementById('bullet-list'),
  tweetsContainer: document.getElementById('tweets-container'),
  themeToggle: document.getElementById('theme-toggle'),
  logo: document.getElementById('logo'),
  body: document.body
};

// ============================================
// THEME MANAGEMENT
// ============================================
function initTheme() {
  // Load saved theme preference
  chrome.storage.local.get(['theme'], (result) => {
    const savedTheme = result.theme || 'light';
    if (savedTheme === 'dark') {
      elements.body.classList.add('dark-mode');
      elements.themeToggle.textContent = '☀️';
    }
  });
}

function toggleTheme() {
  elements.body.classList.toggle('dark-mode');
  const isDark = elements.body.classList.contains('dark-mode');
  
  // Update icon
  elements.themeToggle.textContent = isDark ? '☀️' : '🌙';
  
  // Save preference
  chrome.storage.local.set({ theme: isDark ? 'dark' : 'light' });
}

// Attach theme toggle listener
elements.themeToggle.addEventListener('click', toggleTheme);

// ============================================
// UI STATE MANAGEMENT
// ============================================
function showState(state) {
  elements.stateLoading.classList.add('hidden');
  elements.stateError.classList.add('hidden');
  elements.stateResult.classList.add('hidden');
  
  if (state === 'loading') {
    elements.stateLoading.classList.remove('hidden');
    elements.logo.classList.remove('compact');
  } else if (state === 'error') {
    elements.stateError.classList.remove('hidden');
    elements.logo.classList.remove('compact');
  } else if (state === 'result') {
    elements.stateResult.classList.remove('hidden');
    // Make logo compact when showing results
    elements.logo.classList.add('compact');
  }
}

function showError(message) {
  elements.errorMessage.textContent = message;
  showState('error');
}

function renderResult(data) {
  // Parse and render vibe summary bullets
  const bullets = parseVibeSummary(data.vibe_summary);
  elements.bulletList.innerHTML = '';
  
  bullets.forEach(text => {
    // Skip any lines that look like analysis headers
    if (text.toLowerCase().includes('analysis') || 
        text.toLowerCase().includes('here') ||
        text.length < 5) {
      return;
    }
    
    const li = document.createElement('li');
    li.innerHTML = `<span class="bullet-icon">⭐</span><span>${text}</span>`;
    elements.bulletList.appendChild(li);
  });
  
  // Render top tweets
  elements.tweetsContainer.innerHTML = '';
  if (data.top_tweets && data.top_tweets.length > 0) {
    data.top_tweets.forEach(tweet => {
      const card = createTweetCard(tweet);
      elements.tweetsContainer.appendChild(card);
    });
  }
  
  showState('result');
}

function createTweetCard(tweet) {
  const card = document.createElement('div');
  card.className = 'tweet-card';
  card.onclick = () => window.open(tweet.tweet_url, '_blank');
  
  // Fallback avatar if image fails to load
  const avatarUrl = tweet.user_profile_image_url || 
    'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="36" height="36"%3E%3Crect fill="%23e5e5e5" width="36" height="36"/%3E%3C/svg%3E';
  
  card.innerHTML = `
    <div class="tweet-header">
      <img src="${avatarUrl}" 
           class="tweet-avatar" 
           onerror="this.src='data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 width=%2236%22 height=%2236%22%3E%3Crect fill=%22%23e5e5e5%22 width=%2236%22 height=%2236%22/%3E%3C/svg%3E'">
      <div class="tweet-user-info">
        <div class="tweet-user-name">
          ${escapeHtml(tweet.user_name)}
          <span class="verified-badge">✓</span>
        </div>
        <div class="tweet-username">@${escapeHtml(tweet.user_screen_name)}</div>
      </div>
    </div>
    <div class="tweet-text">${escapeHtml(tweet.text)}</div>
    <div class="tweet-stats">
      <div class="tweet-stat">❤️ ${formatNumber(tweet.favorite_count)}</div>
      <div class="tweet-stat">🔁 ${formatNumber(tweet.retweet_count)}</div>
    </div>
  `;
  
  return card;
}

function parseVibeSummary(summary) {
  const lines = summary
    .split('\n')
    .map(line => line.trim())
    .filter(line => line.length > 0)
    .map(line => {
      // Remove bullet markers and numbering
      return line
        .replace(/^[•\-\*]\s*/, '')
        .replace(/^\d+\.\s*/, '')
        .replace(/^[\u2022\u2023\u25E6\u2043\u2219]\s*/, '');
    })
    .filter(line => {
      // Filter out header-like lines
      const lower = line.toLowerCase();
      return line.length > 5 && 
             !lower.includes('here') && 
             !lower.includes('analysis') &&
             !lower.startsWith('based on');
    });
  
  return lines.length > 0 ? lines : [summary];
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function formatNumber(num) {
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
  if (num >= 1000) return (num / 1000).toFixed(1) + 'k';
  return num.toString();
}

// ============================================
// MAIN EXECUTION
// ============================================
async function run() {
  showState('loading');
  
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  
  if (!tab.url || tab.url.startsWith('chrome://') || tab.url.startsWith('chrome-extension://')) {
    showError('Cannot analyze Chrome internal pages');
    return;
  }
  
  const timeout = setTimeout(() => {
    showError('Request timed out. Is the backend running?');
  }, 35000);
  
  chrome.runtime.sendMessage({ action: "analyze", url: tab.url }, (response) => {
    clearTimeout(timeout);
    
    if (chrome.runtime.lastError) {
      console.error('Runtime error:', chrome.runtime.lastError);
      showError('Extension error. Try reloading the extension.');
      return;
    }
    
    if (response && response.error) {
      showError(response.error);
    } else if (response && response.vibe_summary) {
      renderResult(response);
    } else {
      showError('Invalid response from backend');
      console.error('Bad response:', response);
    }
  });
}

// Initialize theme on load
initTheme();

// Start analysis
run();