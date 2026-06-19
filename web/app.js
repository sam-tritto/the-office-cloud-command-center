/**
 * ScrantonOS — Client-Side Chat Application
 * ==========================================
 * WebSocket-based real-time chat with character avatars,
 * HITL approval handling, and markdown rendering.
 */

(() => {
  'use strict';

  // ═══════════════════════════════════════════════════════════════
  // Character Configuration
  // ═══════════════════════════════════════════════════════════════

  const CHARACTERS = {
    michael:    { name: 'Michael Scott',     emoji: '👔', color: '#4A90D9', title: 'Regional Manager' },
    dwight:     { name: 'Dwight Schrute',    emoji: '🥋', color: '#C0392B', title: 'Asst. Regional Manager' },
    oscar:      { name: 'Oscar Martinez',    emoji: '📊', color: '#27AE60', title: 'FinOps Analyst' },
    stanley:    { name: 'Stanley Hudson',    emoji: '🧩', color: '#7F8C8D', title: 'IAM Compliance' },
    toby:       { name: 'Toby Flenderson',   emoji: '📋', color: '#95A5A6', title: 'HITL Approval Gate' },
    angela:     { name: 'Angela Martin',     emoji: '🐱', color: '#E91E63', title: 'Firebase Monitor' },
    jim:        { name: 'Jim Halpert',       emoji: '😏', color: '#3498DB', title: 'UI/UX Reviewer' },
    meredith:   { name: 'Meredith Palmer',   emoji: '🔥', color: '#E74C3C', title: 'Chaos Engineer' },
    gabe:       { name: 'Gabe Lewis',        emoji: '📚', color: '#8E44AD', title: 'Documentation RAG' },
    jan:        { name: 'Jan Levinson',      emoji: '📈', color: '#D4AC0D', title: 'Tech Debt Auditor' },
    bob_vance:  { name: 'Bob Vance',         emoji: '❄️', color: '#1ABC9C', title: 'Legacy Migration' },
    pam:        { name: 'Pam Beesly',        emoji: '🎨', color: '#F39C12', title: 'Artifact Generator' },
    erin:       { name: 'Erin Hannon',       emoji: '🎀', color: '#00BCD4', title: 'Git Pipeline' },
    kevin:      { name: 'Kevin Malone',      emoji: '🌶️', color: '#E67E22', title: 'Metrics Dashboard' },
    ryan:       { name: 'Ryan Howard',       emoji: '📈', color: '#BDC3C7', title: 'Tech Recommender' },
    user:       { name: 'You',               emoji: '👤', color: '#7C3AED', title: '' },
    system:     { name: 'System',            emoji: '⚙️', color: '#6366f1', title: '' },
  };

  // ═══════════════════════════════════════════════════════════════
  // DOM References
  // ═══════════════════════════════════════════════════════════════

  const chatContainer = document.getElementById('chat-container');
  const chatInput = document.getElementById('chat-input');
  const sendBtn = document.getElementById('send-btn');
  const statusDot = document.getElementById('status-dot');
  const statusText = document.getElementById('status-text');
  const typingIndicator = document.getElementById('typing-indicator');
  const typingName = document.getElementById('typing-name');
  const multiAgentToggleBtn = document.getElementById('multi-agent-toggle-btn');

  function classifyIntent(text) {
    const inputLower = text.toLowerCase();
    
    const INTENTS = {
      dwight: ["logs", "crash", "error", "memory", "leak", "oom", "container", "failure", "uptime", "incident", "outage", "alert", "monitor", "sre", "reliability", "health check", "status", "down", "502", "504", "timeout", "latency", "performance", "system"],
      oscar: ["billing", "cost", "spend", "budget", "expense", "invoice", "finops", "price", "charge", "bigquery cost", "gpu cost", "compute cost", "storage cost", "burn rate", "savings", "over budget", "cloud spend", "money"],
      angela: ["firebase", "crashlytics", "anr", "mobile crash", "app crash", "firebase config", "fcm", "firestore", "realtime database"],
      stanley: ["iam", "access", "permission", "role", "grant", "revoke", "policy", "service account", "credentials", "authenticate", "authorize", "security", "admin access", "viewer access"],
      jan: ["todo", "fixme", "hack", "technical debt", "tech debt", "backlog", "sprint", "velocity", "overdue", "ticket", "code quality", "cleanup", "refactor"],
      jim: ["ui", "ux", "frontend", "front-end", "css", "layout", "design", "component", "styling", "pixel", "alignment", "responsive", "accessibility", "a11y", "visual"],
      meredith: ["chaos", "fuzz", "stress test", "load test", "rate limit", "ddos", "benchmark", "performance test", "breaking point", "resilience", "fault injection"],
      gabe: ["documentation", "docs", "wiki", "how to", "how do", "guide", "manual", "procedure", "protocol", "onboarding", "reference", "section"],
      bob_vance: ["legacy", "migration", "archive", "cold storage", "glacier", "old system", "mainframe", "on-premise", "on-prem", "migrate", "backup", "archival"],
      creed: ["delete", "purge", "erase", "gdpr", "right to be forgotten", "pii", "remove user", "data deletion", "scrub", "wipe", "forget", "destroy"],
      pam: ["report", "summary", "artifact", "document", "format", "generate report", "create report", "executive summary"],
      erin: ["git", "deploy", "deployment", "ci/cd", "pipeline", "build", "merge", "branch", "pr", "pull request", "commit", "release", "rollback"],
      kevin: ["dashboard", "metrics", "count", "calculate", "math", "how many", "total", "sum", "average", "stats"],
      ryan: ["modernize", "rewrite", "scale", "architecture", "rust", "web3", "ai", "serverless", "go", "golang", "microservices", "wuphf"]
    };

    for (const [agent, keywords] of Object.entries(INTENTS)) {
      if (keywords.some(kw => inputLower.includes(kw))) {
        return agent;
      }
    }
    return "michael";
  }

  // Attachment DOM
  const imageUpload = document.getElementById('image-upload');
  const attachBtn = document.getElementById('attach-btn');
  const imagePreviewContainer = document.getElementById('image-preview-container');
  const imagePreviewImg = document.getElementById('image-preview-img');
  const removeImageBtn = document.getElementById('remove-image-btn');
  
  let currentAttachmentBase64 = null;

  // Dashboard DOM
  const dashboardDrawer = document.getElementById('dashboard-drawer');
  const dashboardTitle = document.getElementById('dashboard-title');
  const closeDashboardBtn = document.getElementById('close-dashboard-btn');
  const chartContainer = document.getElementById('chart-container');
  const dashboardChartCanvas = document.getElementById('dashboard-chart');
  const metricsGrid = document.getElementById('metrics-grid');
  
  let currentChartInstance = null;

  if (closeDashboardBtn) {
    closeDashboardBtn.addEventListener('click', () => {
      dashboardDrawer.classList.remove('active');
      document.body.classList.remove('drawer-open');
    });
  }

  // ═══════════════════════════════════════════════════════════════
  // WebSocket Connection
  // ═══════════════════════════════════════════════════════════════

  let ws = null;
  let reconnectAttempts = 0;
  const MAX_RECONNECT = 10;
  const RECONNECT_DELAY = 2000;

  function connect() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${location.host}/ws`;

    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      reconnectAttempts = 0;
      setConnectionStatus(true);
      sendBtn.disabled = false;
      console.log('[ScrantonOS] Connected to server');
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleMessage(data);
      } catch (e) {
        console.error('[ScrantonOS] Failed to parse message:', e);
      }
    };

    ws.onclose = () => {
      setConnectionStatus(false);
      sendBtn.disabled = true;
      console.log('[ScrantonOS] Disconnected');

      if (reconnectAttempts < MAX_RECONNECT) {
        reconnectAttempts++;
        const delay = RECONNECT_DELAY * Math.min(reconnectAttempts, 5);
        console.log(`[ScrantonOS] Reconnecting in ${delay}ms (attempt ${reconnectAttempts})`);
        setTimeout(connect, delay);
      }
    };

    ws.onerror = (err) => {
      console.error('[ScrantonOS] WebSocket error:', err);
    };
  }

  function setConnectionStatus(connected) {
    statusDot.className = connected ? 'status-dot' : 'status-dot status-dot--disconnected';
    statusText.textContent = connected ? 'Connected' : 'Disconnected';
  }

  // ═══════════════════════════════════════════════════════════════
  // Message Handling
  // ═══════════════════════════════════════════════════════════════

  function handleMessage(data) {
    if (data.type === 'session_init') {
      window.sessionId = data.session_id;
      return;
    }

    hideTyping();

    const {
      agent_name,
      agent_id,
      message,
      message_type,
      flavor_quote,
      timestamp,
      metadata,
    } = data;

    // For async webhook alerts, briefly show a typing animation before rendering
    if (message_type === 'webhook_alert') {
      showTyping(agent_id || 'system');
      setTimeout(() => {
        hideTyping();
        renderMessage({
          agentId: agent_id || 'system',
          agentName: agent_name || 'Unknown',
          message: message || '',
          messageType: message_type || 'agent_response',
          flavorQuote: flavor_quote,
          timestamp: timestamp,
          metadata: metadata,
        });
      }, 900);
      return;
    }

    renderMessage({
      agentId: agent_id || 'system',
      agentName: agent_name || 'Unknown',
      message: message || '',
      messageType: message_type || 'agent_response',
      flavorQuote: flavor_quote,
      timestamp: timestamp,
      metadata: metadata,
    });

    if (metadata && metadata.chart_data) {
      renderChartData(metadata.chart_data);
    }
  }

  // ═══════════════════════════════════════════════════════════════
  // Dashboard & Charts Rendering
  // ═══════════════════════════════════════════════════════════════

  function renderChartData(chartData) {
    if (!dashboardDrawer || !window.Chart) return;

    // Open drawer
    dashboardDrawer.classList.add('active');
    document.body.classList.add('drawer-open');

    // Reset view
    chartContainer.style.display = 'none';
    metricsGrid.style.display = 'none';
    if (currentChartInstance) {
      currentChartInstance.destroy();
      currentChartInstance = null;
    }

    const { type, metrics } = chartData;

    if (type === 'metrics') {
      // Kevin's Key Metrics Grid
      dashboardTitle.textContent = "Kevin's Key Metrics";
      metricsGrid.style.display = 'grid';
      metricsGrid.innerHTML = `
        <div class="metric-card">
          <span class="metric-card__label">Total Spend</span>
          <span class="metric-card__value">${metrics.total_spend}</span>
        </div>
        <div class="metric-card">
          <span class="metric-card__label">Budget Util</span>
          <span class="metric-card__value">${metrics.budget_utilization}</span>
        </div>
        <div class="metric-card">
          <span class="metric-card__label">Crash Free</span>
          <span class="metric-card__value">${metrics.crash_free_users}</span>
        </div>
        <div class="metric-card">
          <span class="metric-card__label">Critical Threats</span>
          <span class="metric-card__value">${metrics.critical_threats}</span>
        </div>
        <div class="metric-card metric-card--highlight">
          <span class="metric-card__label">Total Errors</span>
          <span class="metric-card__value">${metrics.total_errors}</span>
        </div>
        <div class="metric-card metric-card--highlight" title="Plus the Keleven variable!">
          <span class="metric-card__label">Adj. Incidents</span>
          <span class="metric-card__value">${metrics.adjusted_incidents}</span>
        </div>
      `;
      return;
    }

    // Chart.js visualizations
    chartContainer.style.display = 'block';
    let config = null;

    if (type === 'sre') {
      dashboardTitle.textContent = "Log Severity Distribution";
      config = {
        type: 'pie',
        data: {
          labels: ['Critical', 'Error', 'Warning'],
          datasets: [{
            data: [metrics.critical_count, metrics.error_count, metrics.warning_count],
            backgroundColor: ['#dc2626', '#f97316', '#f59e0b'],
            borderWidth: 0
          }]
        },
        options: { responsive: true, plugins: { legend: { position: 'bottom' } } }
      };
    } else if (type === 'finops') {
      dashboardTitle.textContent = "Top Services by Cost";
      const labels = metrics.top_services.map(s => Object.keys(s)[0]);
      const data = metrics.top_services.map(s => Object.values(s)[0]);
      config = {
        type: 'bar',
        data: {
          labels: labels,
          datasets: [{
            label: 'Cost (USD)',
            data: data,
            backgroundColor: '#27AE60',
            borderRadius: 4
          }]
        },
        options: { responsive: true, scales: { y: { beginAtZero: true } } }
      };
    } else if (type === 'firebase') {
      dashboardTitle.textContent = "Recent Crash Occurrences";
      const labels = metrics.recent_issues.map(i => i.issue_id);
      const data = metrics.recent_issues.map(i => i.occurrences);
      config = {
        type: 'bar',
        data: {
          labels: labels,
          datasets: [{
            label: 'Occurrences',
            data: data,
            backgroundColor: '#E91E63',
            borderRadius: 4
          }]
        },
        options: { responsive: true, indexAxis: 'y', scales: { x: { beginAtZero: true } } }
      };
    }

    if (config) {
      currentChartInstance = new Chart(dashboardChartCanvas, config);
    }
  }

  // ═══════════════════════════════════════════════════════════════
  // Message Rendering
  // ═══════════════════════════════════════════════════════════════

  function renderMessage({ agentId, agentName, message, messageType, flavorQuote, timestamp, metadata }) {
    const char = CHARACTERS[agentId] || CHARACTERS.system;
    const isUser = messageType === 'user_input';
    const isError = messageType === 'error';
    const isSystem = messageType === 'system';
    const isHITL = messageType === 'hitl_pause';
    const isWebhook = messageType === 'webhook_alert';

    const el = document.createElement('div');
    el.className = [
      'message',
      isUser     ? 'message--user'    : '',
      isError    ? 'message--error'   : '',
      isSystem   ? 'message--system'  : '',
      isWebhook  ? 'message--webhook' : '',
    ].filter(Boolean).join(' ');
    el.style.setProperty('--accent-color', char.color);

    // Avatar
    const avatarEl = document.createElement('div');
    avatarEl.className = 'message__avatar';
    avatarEl.style.borderColor = char.color + '40';

    // Check for avatar image
    const avatarImg = `/static/avatars/${agentId}.png`;
    avatarEl.innerHTML = `<span>${char.emoji}</span>`;
    // Try to load avatar image
    if (agentId !== 'user' && agentId !== 'system') {
      const img = new Image();
      img.onload = () => {
        avatarEl.innerHTML = '';
        avatarEl.appendChild(img);
      };
      img.src = avatarImg;
      img.alt = char.name;
    }

    // Bubble
    const bubbleEl = document.createElement('div');
    bubbleEl.className = 'message__bubble';

    // Header
    const headerEl = document.createElement('div');
    headerEl.className = 'message__header';

    const nameEl = document.createElement('span');
    nameEl.className = 'message__name';
    nameEl.style.color = char.color;
    nameEl.textContent = char.name;

    headerEl.appendChild(nameEl);

    if (char.title && !isUser) {
      const titleEl = document.createElement('span');
      titleEl.className = 'message__title';
      titleEl.textContent = char.title;
      headerEl.appendChild(titleEl);
    }

    // Webhook alert: LIVE EVENT badge + source chip
    if (isWebhook && metadata) {
      const badge = document.createElement('span');
      badge.className = 'message__live-badge';
      badge.textContent = '⚡ LIVE';
      headerEl.appendChild(badge);

      if (metadata.source) {
        const sourceChip = document.createElement('span');
        sourceChip.className = 'message__source-chip';
        const sourceIcons = { github: '🐙', logs: '📋', billing: '💰', firebase: '🔥', iam: '🔐' };
        sourceChip.textContent = `${sourceIcons[metadata.source] || '📡'} ${metadata.source.toUpperCase()}`;
        headerEl.appendChild(sourceChip);
      }
    }

    if (timestamp) {
      const timeEl = document.createElement('span');
      timeEl.className = 'message__time';
      timeEl.textContent = formatTime(timestamp);
      headerEl.appendChild(timeEl);
    }

    // Message text
    const textEl = document.createElement('div');
    textEl.className = 'message__text';
    textEl.innerHTML = renderMarkdown(message);

    bubbleEl.appendChild(headerEl);
    bubbleEl.appendChild(textEl);

    // HITL card
    if (isHITL && metadata) {
      const hitlCard = createHITLCard(metadata);
      bubbleEl.appendChild(hitlCard);
    }

    // Flavor quote
    if (flavorQuote && !isUser) {
      const quoteEl = document.createElement('div');
      quoteEl.className = 'message__quote';
      quoteEl.textContent = flavorQuote;
      bubbleEl.appendChild(quoteEl);
    }

    el.appendChild(avatarEl);
    el.appendChild(bubbleEl);

    chatContainer.appendChild(el);
    scrollToBottom();
  }

  // ═══════════════════════════════════════════════════════════════
  // HITL Approval Card
  // ═══════════════════════════════════════════════════════════════

  function createHITLCard(metadata) {
    const card = document.createElement('div');
    card.className = 'hitl-card';
    card.id = `hitl-${metadata.request_id}`;

    const riskColors = {
      low: '#10b981',
      medium: '#f59e0b',
      high: '#ef4444',
      critical: '#dc2626',
    };
    const riskColor = riskColors[metadata.risk_level] || riskColors.medium;

    card.innerHTML = `
      <div class="hitl-card__header">
        <span>⏸️</span>
        <span>Workflow Paused — Human Approval Required</span>
      </div>
      <dl class="hitl-card__details">
        <dt>Action</dt>
        <dd>${metadata.action_type || 'Unknown'}</dd>
        ${metadata.action_details?.target_user ? `<dt>User</dt><dd>${metadata.action_details.target_user}</dd>` : ''}
        ${metadata.action_details?.target_role ? `<dt>Role</dt><dd>${metadata.action_details.target_role}</dd>` : ''}
        ${metadata.action_details?.target_user_id ? `<dt>User ID</dt><dd>${metadata.action_details.target_user_id}</dd>` : ''}
        <dt>Risk Level</dt>
        <dd style="color: ${riskColor}; font-weight: 600;">${(metadata.risk_level || 'medium').toUpperCase()}</dd>
        <dt>Request ID</dt>
        <dd style="font-size: 0.75em; opacity: 0.7;">${metadata.request_id}</dd>
      </dl>
      <div class="hitl-card__actions">
        <button class="hitl-btn hitl-btn--approve" onclick="window.scrantonHITL('${metadata.request_id}', true)" id="hitl-approve-${metadata.request_id}">
          ✅ Approve
        </button>
        <button class="hitl-btn hitl-btn--reject" onclick="window.scrantonHITL('${metadata.request_id}', false)" id="hitl-reject-${metadata.request_id}">
          ❌ Reject
        </button>
      </div>
    `;

    return card;
  }

  // Global HITL handler
  window.scrantonHITL = (requestId, approved) => {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      alert('Not connected to server');
      return;
    }

    // Disable buttons
    const approveBtn = document.getElementById(`hitl-approve-${requestId}`);
    const rejectBtn = document.getElementById(`hitl-reject-${requestId}`);
    if (approveBtn) approveBtn.disabled = true;
    if (rejectBtn) rejectBtn.disabled = true;

    // Send HITL response
    ws.send(JSON.stringify({
      type: 'hitl_response',
      request_id: requestId,
      approved: approved,
      note: approved ? '' : 'Rejected by operator via UI',
    }));

    // Update card appearance
    const card = document.getElementById(`hitl-${requestId}`);
    if (card) {
      card.style.animation = 'none';
      card.style.borderColor = approved ? 'rgba(16, 185, 129, 0.4)' : 'rgba(239, 68, 68, 0.4)';
      card.style.background = approved ? 'rgba(16, 185, 129, 0.08)' : 'rgba(239, 68, 68, 0.08)';
    }
  };

  // ═══════════════════════════════════════════════════════════════
  // Simple Markdown Renderer
  // ═══════════════════════════════════════════════════════════════

  function renderMarkdown(text) {
    if (!text) return '';

    let html = escapeHtml(text);

    // Code blocks (must come before inline code)
    html = html.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>');
    html = html.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>');

    // Inline code
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

    // Bold
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

    // Italic
    html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');

    // Headers
    html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
    html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
    html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');

    // Unordered lists
    html = html.replace(/^[-•] (.+)$/gm, '<li>$1</li>');
    html = html.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');

    // Ordered lists
    html = html.replace(/^\d+\. (.+)$/gm, '<li>$1</li>');

    // Horizontal rules
    html = html.replace(/^---$/gm, '<hr>');

    // Line breaks → paragraphs
    html = html.replace(/\n\n/g, '</p><p>');
    html = html.replace(/\n/g, '<br>');
    html = `<p>${html}</p>`;

    // Clean up empty paragraphs
    html = html.replace(/<p><\/p>/g, '');
    html = html.replace(/<p>(<h[1-3]>)/g, '$1');
    html = html.replace(/(<\/h[1-3]>)<\/p>/g, '$1');
    html = html.replace(/<p>(<pre>)/g, '$1');
    html = html.replace(/(<\/pre>)<\/p>/g, '$1');
    html = html.replace(/<p>(<ul>)/g, '$1');
    html = html.replace(/(<\/ul>)<\/p>/g, '$1');
    html = html.replace(/<p>(<hr>)<\/p>/g, '$1');

    return html;
  }

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  // ═══════════════════════════════════════════════════════════════
  // Utilities
  // ═══════════════════════════════════════════════════════════════

  function formatTime(timestamp) {
    try {
      const date = new Date(timestamp);
      return date.toLocaleTimeString('en-US', {
        hour: 'numeric',
        minute: '2-digit',
        hour12: true,
      });
    } catch {
      return '';
    }
  }

  function scrollToBottom() {
    requestAnimationFrame(() => {
      chatContainer.scrollTo({
        top: chatContainer.scrollHeight,
        behavior: 'smooth',
      });
    });
  }

  function showTyping(agentId) {
    const char = CHARACTERS[agentId] || CHARACTERS.system;
    typingAvatar.textContent = char.emoji;
    typingName.textContent = `${char.name} is thinking...`;
    typingIndicator.classList.add('active');
    scrollToBottom();
  }

  function hideTyping() {
    typingIndicator.classList.remove('active');
  }

  // ═══════════════════════════════════════════════════════════════
  // Input Handling
  // ═══════════════════════════════════════════════════════════════

  function sendMessage() {
    const text = chatInput.value.trim();
    if ((!text && !currentAttachmentBase64) || !ws || ws.readyState !== WebSocket.OPEN) return;

    const multiAgent = multiAgentToggleBtn ? multiAgentToggleBtn.checked : false;

    ws.send(JSON.stringify({
      type: 'chat',
      message: text,
      attachment_base64: currentAttachmentBase64 || "",
      multi_agent: multiAgent,
    }));

    // Clear input
    chatInput.value = '';
    chatInput.style.height = 'auto';
    sendBtn.disabled = true;

    // Clear attachment
    currentAttachmentBase64 = null;
    imageUpload.value = '';
    imagePreviewContainer.style.display = 'none';
    imagePreviewImg.src = '';

    // Show typing indicator
    if (multiAgent) {
      showTyping('michael');
    } else {
      showTyping(classifyIntent(text));
    }
  }

  // File Upload Handlers
  if (attachBtn && imageUpload) {
    attachBtn.addEventListener('click', () => {
      imageUpload.click();
    });

    imageUpload.addEventListener('change', (e) => {
      const file = e.target.files[0];
      if (!file) return;

      // Basic validation
      if (!file.type.startsWith('image/')) {
        alert('Please select an image file.');
        return;
      }

      const reader = new FileReader();
      reader.onload = (event) => {
        currentAttachmentBase64 = event.target.result;
        imagePreviewImg.src = currentAttachmentBase64;
        imagePreviewContainer.style.display = 'flex';
        sendBtn.disabled = false; // Allow sending just an image
      };
      reader.readAsDataURL(file);
    });
  }

  if (removeImageBtn) {
    removeImageBtn.addEventListener('click', () => {
      currentAttachmentBase64 = null;
      imageUpload.value = '';
      imagePreviewContainer.style.display = 'none';
      imagePreviewImg.src = '';
      // Update send button state
      sendBtn.disabled = !chatInput.value.trim();
    });
  }

  // Auto-resize textarea
  chatInput.addEventListener('input', () => {
    chatInput.style.height = 'auto';
    chatInput.style.height = Math.min(chatInput.scrollHeight, 160) + 'px';
    sendBtn.disabled = !chatInput.value.trim() && !currentAttachmentBase64;
  });

  // Enter to send (Shift+Enter for newline)
  chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  sendBtn.addEventListener('click', sendMessage);

  // ═══════════════════════════════════════════════════════════════
  // Command Palette
  // ═══════════════════════════════════════════════════════════════

  const helpBtn = document.getElementById('help-btn');
  const commandPalette = document.getElementById('command-palette');
  
  if (helpBtn && commandPalette) {
    helpBtn.addEventListener('click', () => {
      commandPalette.classList.toggle('active');
    });

    document.addEventListener('click', (e) => {
      if (!helpBtn.contains(e.target) && !commandPalette.contains(e.target)) {
        commandPalette.classList.remove('active');
      }
    });

    // Handle command clicks
    commandPalette.addEventListener('click', (e) => {
      const cmdBtn = e.target.closest('.command-item');
      if (cmdBtn) {
        chatInput.value = cmdBtn.dataset.cmd;
        chatInput.focus();
        commandPalette.classList.remove('active');
      }
    });
  }

  // ═══════════════════════════════════════════════════════════════
  // Initialize
  // ═══════════════════════════════════════════════════════════════

  connect();

})();
