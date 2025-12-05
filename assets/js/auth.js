/**
 * Authentication and User Account Management
 * Handles login, registration, saved charts, and chat functionality
 */
const AuthManager = {
    API_BASE: "https://true-sidereal-api.onrender.com",
    
    // State
    currentUser: null,
    authToken: null,
    savedCharts: [],
    currentChatConversation: null,
    currentChartId: null,
    
    init() {
        // Load stored auth state
        this.loadAuthState();
        this.bindEvents();
        this.updateUI();
    },
    
    // ============================================================
    // AUTH STATE MANAGEMENT
    // ============================================================
    
    loadAuthState() {
        const token = localStorage.getItem('auth_token');
        const user = localStorage.getItem('auth_user');
        
        if (token && user) {
            this.authToken = token;
            try {
                this.currentUser = JSON.parse(user);
                // Verify token is still valid
                this.verifyToken();
            } catch (e) {
                this.logout();
            }
        }
    },
    
    saveAuthState(token, user) {
        this.authToken = token;
        this.currentUser = user;
        localStorage.setItem('auth_token', token);
        localStorage.setItem('auth_user', JSON.stringify(user));
    },
    
    clearAuthState() {
        this.authToken = null;
        this.currentUser = null;
        this.savedCharts = [];
        this.currentChatConversation = null;
        localStorage.removeItem('auth_token');
        localStorage.removeItem('auth_user');
    },
    
    isLoggedIn() {
        return this.authToken !== null && this.currentUser !== null;
    },
    
    getAuthHeaders() {
        if (!this.authToken) return {};
        return {
            'Authorization': `Bearer ${this.authToken}`
        };
    },
    
    async verifyToken() {
        try {
            const response = await fetch(`${this.API_BASE}/auth/me`, {
                headers: this.getAuthHeaders()
            });
            
            if (!response.ok) {
                // Only logout on 401 (unauthorized) - other errors might be temporary
                if (response.status === 401) {
                    console.log('Token invalid or expired, logging out');
                    this.logout();
                } else {
                    console.warn('Token verification returned status:', response.status);
                }
            }
        } catch (e) {
            // Network error - don't logout, might just be temporary connectivity issue
            console.error('Token verification network error:', e);
        }
    },
    
    // ============================================================
    // AUTH ACTIONS
    // ============================================================
    
    async register(email, password, fullName) {
        try {
            const response = await fetch(`${this.API_BASE}/auth/register`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    email: email,
                    password: password,
                    full_name: fullName || null
                })
            });
            
            let data;
            try {
                data = await response.json();
            } catch (jsonError) {
                // Server returned non-JSON response (possibly crashed)
                console.error('Server response was not JSON:', jsonError);
                throw new Error('Server error - please try again in a moment');
            }
            
            if (!response.ok) {
                throw new Error(data.detail || 'Registration failed');
            }
            
            this.saveAuthState(data.access_token, data.user);
            this.updateUI();
            this.closeModals();
            this.showNotification('Account created successfully!', 'success');
            
            return data;
        } catch (error) {
            console.error('Registration error:', error);
            throw error;
        }
    },
    
    async login(email, password) {
        try {
            const response = await fetch(`${this.API_BASE}/auth/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    email: email,
                    password: password
                })
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.detail || 'Login failed');
            }
            
            this.saveAuthState(data.access_token, data.user);
            this.updateUI();
            this.closeModals();
            this.showNotification('Welcome back!', 'success');
            
            // Load saved charts
            await this.loadSavedCharts();
            
            return data;
        } catch (error) {
            throw error;
        }
    },
    
    logout() {
        this.clearAuthState();
        this.updateUI();
        this.showNotification('Logged out successfully', 'info');
    },
    
    // ============================================================
    // SAVED CHARTS
    // ============================================================
    
    async loadSavedCharts() {
        if (!this.isLoggedIn()) return;
        
        try {
            const response = await fetch(`${this.API_BASE}/charts/list`, {
                headers: this.getAuthHeaders()
            });
            
            if (response.ok) {
                this.savedCharts = await response.json();
                this.renderSavedChartsList();
            } else {
                console.error('Failed to load charts, status:', response.status);
                // Show empty state on error
                this.savedCharts = [];
                this.renderSavedChartsList();
            }
        } catch (error) {
            console.error('Failed to load saved charts:', error);
            // Show empty state on network error
            this.savedCharts = [];
            this.renderSavedChartsList();
        }
    },
    
    async saveCurrentChart(chartData, reading, userInputs) {
        if (!this.isLoggedIn()) {
            this.showLoginModal();
            return;
        }
        
        try {
            const response = await fetch(`${this.API_BASE}/charts/save`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...this.getAuthHeaders()
                },
                body: JSON.stringify({
                    chart_name: userInputs.full_name,
                    birth_year: parseInt(userInputs.birth_date.split('/')[2]),
                    birth_month: parseInt(userInputs.birth_date.split('/')[0]),
                    birth_day: parseInt(userInputs.birth_date.split('/')[1]),
                    birth_hour: this.parseTimeHour(userInputs.birth_time),
                    birth_minute: this.parseTimeMinute(userInputs.birth_time),
                    birth_location: userInputs.location,
                    unknown_time: chartData.unknown_time || false,
                    chart_data_json: JSON.stringify(chartData),
                    ai_reading: reading
                })
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.detail || 'Failed to save chart');
            }
            
            this.showNotification('Chart saved successfully!', 'success');
            await this.loadSavedCharts();
            
            return data.id;
        } catch (error) {
            this.showNotification(error.message, 'error');
            throw error;
        }
    },
    
    async loadChart(chartId) {
        if (!this.isLoggedIn()) return;
        
        try {
            const response = await fetch(`${this.API_BASE}/charts/${chartId}`, {
                headers: this.getAuthHeaders()
            });
            
            if (!response.ok) {
                throw new Error('Failed to load chart');
            }
            
            const data = await response.json();
            this.currentChartId = chartId;
            
            return data;
        } catch (error) {
            this.showNotification(error.message, 'error');
            throw error;
        }
    },
    
    async deleteChart(chartId) {
        if (!this.isLoggedIn()) return;
        
        if (!confirm('Are you sure you want to delete this chart? This action cannot be undone.')) {
            return;
        }
        
        try {
            const response = await fetch(`${this.API_BASE}/charts/${chartId}`, {
                method: 'DELETE',
                headers: this.getAuthHeaders()
            });
            
            if (!response.ok) {
                throw new Error('Failed to delete chart');
            }
            
            this.showNotification('Chart deleted', 'info');
            await this.loadSavedCharts();
        } catch (error) {
            this.showNotification(error.message, 'error');
        }
    },
    
    // ============================================================
    // CHAT FUNCTIONALITY
    // ============================================================
    
    async sendChatMessage(chartId, message, conversationId = null) {
        if (!this.isLoggedIn()) {
            this.showLoginModal();
            return;
        }
        
        try {
            const response = await fetch(`${this.API_BASE}/chat/send`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...this.getAuthHeaders()
                },
                body: JSON.stringify({
                    chart_id: chartId,
                    message: message,
                    conversation_id: conversationId
                })
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.detail || 'Failed to send message');
            }
            
            this.currentChatConversation = data.conversation_id;
            
            return data;
        } catch (error) {
            this.showNotification(error.message, 'error');
            throw error;
        }
    },
    
    async loadConversations(chartId) {
        if (!this.isLoggedIn()) return [];
        
        try {
            const response = await fetch(`${this.API_BASE}/chat/conversations/${chartId}`, {
                headers: this.getAuthHeaders()
            });
            
            if (response.ok) {
                return await response.json();
            }
            return [];
        } catch (error) {
            console.error('Failed to load conversations:', error);
            return [];
        }
    },
    
    async loadConversation(conversationId) {
        if (!this.isLoggedIn()) return null;
        
        try {
            const response = await fetch(`${this.API_BASE}/chat/conversation/${conversationId}`, {
                headers: this.getAuthHeaders()
            });
            
            if (response.ok) {
                return await response.json();
            }
            return null;
        } catch (error) {
            console.error('Failed to load conversation:', error);
            return null;
        }
    },
    
    // ============================================================
    // UI MANAGEMENT
    // ============================================================
    
    bindEvents() {
        // General click handlers (auth menu links are bound directly in bindAuthMenuLinks)
        document.addEventListener('click', (e) => {
            if (e.target.matches('.modal-close, .modal-close *')) {
                this.closeModals();
            }
            if (e.target.matches('.modal-overlay')) {
                this.closeModals();
            }
            if (e.target.matches('.saved-chart-item')) {
                const chartId = e.target.dataset.chartId;
                if (chartId) this.openSavedChart(chartId);
            }
            if (e.target.matches('.delete-chart-btn, .delete-chart-btn *')) {
                e.stopPropagation();
                const chartId = e.target.closest('.saved-chart-item')?.dataset.chartId;
                if (chartId) this.deleteChart(chartId);
            }
            if (e.target.matches('.chat-with-chart-btn, .chat-with-chart-btn *')) {
                e.stopPropagation();
                const chartId = e.target.closest('.saved-chart-item')?.dataset.chartId;
                if (chartId) this.openChatForChart(chartId);
            }
        });
        
        // Login form submit
        document.addEventListener('submit', async (e) => {
            if (e.target.matches('#loginForm')) {
                e.preventDefault();
                const email = e.target.querySelector('#loginEmail').value;
                const password = e.target.querySelector('#loginPassword').value;
                const errorEl = e.target.querySelector('.form-error');
                const submitBtn = e.target.querySelector('button[type="submit"]');
                
                try {
                    submitBtn.disabled = true;
                    submitBtn.textContent = 'Logging in...';
                    errorEl.style.display = 'none';
                    await this.login(email, password);
                } catch (error) {
                    errorEl.textContent = error.message;
                    errorEl.style.display = 'block';
                } finally {
                    submitBtn.disabled = false;
                    submitBtn.textContent = 'Login';
                }
            }
            
            if (e.target.matches('#registerForm')) {
                e.preventDefault();
                const email = e.target.querySelector('#registerEmail').value;
                const password = e.target.querySelector('#registerPassword').value;
                const confirmPassword = e.target.querySelector('#registerConfirmPassword').value;
                const fullName = e.target.querySelector('#registerFullName').value;
                const errorEl = e.target.querySelector('.form-error');
                const submitBtn = e.target.querySelector('button[type="submit"]');
                
                if (password !== confirmPassword) {
                    errorEl.textContent = 'Passwords do not match';
                    errorEl.style.display = 'block';
                    return;
                }
                
                try {
                    submitBtn.disabled = true;
                    submitBtn.textContent = 'Creating account...';
                    errorEl.style.display = 'none';
                    await this.register(email, password, fullName);
                } catch (error) {
                    errorEl.textContent = error.message;
                    errorEl.style.display = 'block';
                } finally {
                    submitBtn.disabled = false;
                    submitBtn.textContent = 'Create Account';
                }
            }
            
            if (e.target.matches('#chatForm')) {
                e.preventDefault();
                const input = e.target.querySelector('#chatInput');
                const message = input.value.trim();
                
                if (!message || !this.currentChartId) return;
                
                input.value = '';
                await this.handleChatSubmit(message);
            }
        });
    },
    
    updateUI() {
        const authMenuSection = document.getElementById('authMenuSection');
        if (!authMenuSection) return;
        
        if (this.isLoggedIn()) {
            const userName = this.currentUser.full_name || this.currentUser.email.split('@')[0];
            authMenuSection.innerHTML = `
                <li class="auth-menu-divider"></li>
                <li class="auth-menu-user"><i class="fas fa-user-circle"></i> ${userName}</li>
                <li><a href="javascript:void(0)" id="dashboardBtn" class="auth-action"><i class="fas fa-chart-pie"></i> My Charts</a></li>
                <li><a href="javascript:void(0)" id="logoutBtn" class="auth-action"><i class="fas fa-sign-out-alt"></i> Logout</a></li>
            `;
        } else {
            authMenuSection.innerHTML = `
                <li class="auth-menu-divider"></li>
                <li><a href="javascript:void(0)" id="loginBtn" class="auth-action"><i class="fas fa-sign-in-alt"></i> Login</a></li>
                <li><a href="javascript:void(0)" id="registerBtn" class="auth-action"><i class="fas fa-user-plus"></i> Sign Up</a></li>
            `;
        }
        
        // Bind click handlers directly to the auth links to bypass Forty theme's menu handler
        this.bindAuthMenuLinks();
    },
    
    bindAuthMenuLinks() {
        // Direct click handlers that run before the theme's menu handler
        const loginBtn = document.getElementById('loginBtn');
        const registerBtn = document.getElementById('registerBtn');
        const dashboardBtn = document.getElementById('dashboardBtn');
        const logoutBtn = document.getElementById('logoutBtn');
        
        if (loginBtn) {
            loginBtn.onclick = (e) => {
                e.preventDefault();
                e.stopPropagation();
                e.stopImmediatePropagation();
                this.closeMenu();
                setTimeout(() => this.showLoginModal(), 100);
                return false;
            };
        }
        
        if (registerBtn) {
            registerBtn.onclick = (e) => {
                e.preventDefault();
                e.stopPropagation();
                e.stopImmediatePropagation();
                this.closeMenu();
                setTimeout(() => this.showRegisterModal(), 100);
                return false;
            };
        }
        
        if (dashboardBtn) {
            dashboardBtn.onclick = (e) => {
                e.preventDefault();
                e.stopPropagation();
                e.stopImmediatePropagation();
                this.closeMenu();
                setTimeout(() => this.showDashboard(), 100);
                return false;
            };
        }
        
        if (logoutBtn) {
            logoutBtn.onclick = (e) => {
                e.preventDefault();
                e.stopPropagation();
                e.stopImmediatePropagation();
                this.closeMenu();
                setTimeout(() => this.logout(), 100);
                return false;
            };
        }
    },
    
    showLoginModal() {
        this.closeModals();
        const modal = document.createElement('div');
        modal.className = 'modal-overlay auth-modal';
        modal.innerHTML = `
            <div class="modal-content">
                <button class="modal-close">&times;</button>
                <h2>Welcome Back</h2>
                <p class="modal-subtitle">Login to access your saved charts and explore them with our astrologer</p>
                <form id="loginForm">
                    <div class="form-error" style="display: none;"></div>
                    <div class="form-group">
                        <label for="loginEmail">Email</label>
                        <input type="email" id="loginEmail" required placeholder="your@email.com">
                    </div>
                    <div class="form-group">
                        <label for="loginPassword">Password</label>
                        <input type="password" id="loginPassword" required placeholder="••••••••">
                    </div>
                    <button type="submit" class="btn-primary">Login</button>
                </form>
                <p class="modal-footer">
                    Don't have an account? <a href="#" onclick="AuthManager.showRegisterModal(); return false;">Sign up</a>
                </p>
            </div>
        `;
        document.body.appendChild(modal);
        setTimeout(() => modal.classList.add('active'), 10);
        modal.querySelector('#loginEmail').focus();
    },
    
    showRegisterModal() {
        this.closeModals();
        const modal = document.createElement('div');
        modal.className = 'modal-overlay auth-modal';
        modal.innerHTML = `
            <div class="modal-content">
                <button class="modal-close">&times;</button>
                <h2>Create Your Account</h2>
                <p class="modal-subtitle">Save your charts and unlock personalized AI guidance</p>
                <form id="registerForm">
                    <div class="form-error" style="display: none;"></div>
                    <div class="form-group">
                        <label for="registerFullName">Full Name <span class="optional">(optional)</span></label>
                        <input type="text" id="registerFullName" placeholder="Your name">
                    </div>
                    <div class="form-group">
                        <label for="registerEmail">Email</label>
                        <input type="email" id="registerEmail" required placeholder="your@email.com">
                    </div>
                    <div class="form-group">
                        <label for="registerPassword">Password</label>
                        <input type="password" id="registerPassword" required minlength="8" placeholder="At least 8 characters">
                    </div>
                    <div class="form-group">
                        <label for="registerConfirmPassword">Confirm Password</label>
                        <input type="password" id="registerConfirmPassword" required placeholder="••••••••">
                    </div>
                    <button type="submit" class="btn-primary">Create Account</button>
                </form>
                <p class="modal-footer">
                    Already have an account? <a href="#" onclick="AuthManager.showLoginModal(); return false;">Login</a>
                </p>
            </div>
        `;
        document.body.appendChild(modal);
        setTimeout(() => modal.classList.add('active'), 10);
        modal.querySelector('#registerFullName').focus();
    },
    
    showDashboard() {
        this.closeModals();
        const modal = document.createElement('div');
        modal.className = 'modal-overlay dashboard-modal';
        modal.innerHTML = `
            <div class="modal-content dashboard-content">
                <button class="modal-close">&times;</button>
                <div class="dashboard-header">
                    <h2><i class="fas fa-stars"></i> My Dashboard</h2>
                    <p>Welcome, ${this.currentUser.full_name || this.currentUser.email}</p>
                </div>
                <div class="dashboard-tabs">
                    <button class="tab-btn active" data-tab="charts">My Charts</button>
                </div>
                <div class="dashboard-body">
                    <div id="chartsTab" class="tab-content active">
                        <div class="saved-charts-list" id="savedChartsList">
                            <div class="loading">Loading your charts...</div>
                        </div>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        setTimeout(() => modal.classList.add('active'), 10);
        this.loadSavedCharts();
    },
    
    renderSavedChartsList() {
        const container = document.getElementById('savedChartsList');
        if (!container) return;
        
        if (this.savedCharts.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-chart-pie"></i>
                    <h3>No saved charts yet</h3>
                    <p>Generate a chart and save it to access it here and explore it with our astrologer.</p>
                </div>
            `;
            return;
        }
        
        container.innerHTML = this.savedCharts.map(chart => `
            <div class="saved-chart-item" data-chart-id="${chart.id}">
                <div class="chart-info">
                    <h4>${chart.chart_name}</h4>
                    <p class="chart-meta">
                        <span><i class="fas fa-calendar"></i> ${chart.birth_date}</span>
                        <span><i class="fas fa-map-marker-alt"></i> ${chart.birth_location}</span>
                    </p>
                    <p class="chart-created">Saved ${this.formatDate(chart.created_at)}</p>
                </div>
                <div class="chart-actions">
                    ${chart.has_reading ? '<span class="badge reading-badge"><i class="fas fa-scroll"></i> Has Reading</span>' : ''}
                    <button class="chat-with-chart-btn" title="Chat about this chart">
                        <i class="fas fa-comments"></i> Chat
                    </button>
                    <button class="delete-chart-btn" title="Delete chart">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </div>
        `).join('');
    },
    
    async openSavedChart(chartId) {
        try {
            const chart = await this.loadChart(chartId);
            this.closeModals();
            
            // Display the chart in the results section
            if (chart.chart_data) {
                AstrologyCalculator.displayInitialResults(chart.chart_data);
                if (chart.ai_reading) {
                    AstrologyCalculator.geminiOutput.innerHTML = chart.ai_reading.replace(/\n/g, '<br>');
                    if (AstrologyCalculator.copyReadingBtn) {
                        AstrologyCalculator.copyReadingBtn.style.display = 'inline-block';
                    }
                }
                
                // Scroll to results
                AstrologyCalculator.resultsContainer.style.display = 'block';
                setTimeout(() => {
                    AstrologyCalculator.resultsContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }, 100);
                
                // Show save chart button state
                this.updateSaveChartButton(true);
            }
        } catch (error) {
            console.error('Failed to open saved chart:', error);
        }
    },
    
    async openChatForChart(chartId) {
        try {
            const chart = await this.loadChart(chartId);
            await this.showChatModal(chart);
        } catch (error) {
            console.error('Failed to open chat:', error);
        }
    },
    
    async showChatModal(chart) {
        this.closeModals();
        this.currentChartId = chart.id;
        this.currentChatConversation = null;
        
        const modal = document.createElement('div');
        modal.className = 'modal-overlay chat-modal';
        modal.innerHTML = `
            <div class="modal-content chat-content">
                <button class="modal-close">&times;</button>
                <div class="chat-header">
                    <h2><i class="fas fa-stars"></i> Your Astrologer</h2>
                    <p>Chatting about: <strong>${chart.chart_name}</strong></p>
                </div>
                <div class="chat-messages" id="chatMessages">
                    <div class="loading">Loading conversation...</div>
                </div>
                <form id="chatForm" class="chat-input-form">
                    <input type="text" id="chatInput" placeholder="Ask about your chart..." autocomplete="off">
                    <button type="submit" class="chat-send-btn">
                        <i class="fas fa-paper-plane"></i>
                    </button>
                </form>
            </div>
        `;
        document.body.appendChild(modal);
        setTimeout(() => modal.classList.add('active'), 10);
        
        // Load conversation history
        const messagesContainer = document.getElementById('chatMessages');
        try {
            // Get all conversations for this chart
            const conversations = await this.loadConversations(chart.id);
            
            // If there are conversations, load the most recent one
            if (conversations && conversations.length > 0) {
                const latestConversation = conversations[0]; // Most recent is first
                this.currentChatConversation = latestConversation.id;
                
                // Load the full conversation with messages
                const conversation = await this.loadConversation(latestConversation.id);
                
                if (conversation && conversation.messages && conversation.messages.length > 0) {
                    // Display existing messages
                    messagesContainer.innerHTML = '';
                    conversation.messages.forEach(msg => {
                        const msgEl = document.createElement('div');
                        msgEl.className = `chat-message ${msg.role}-message`;
                        if (msg.role === 'user') {
                            msgEl.innerHTML = `
                                <div class="message-content">${this.escapeHtml(msg.content)}</div>
                            `;
                        } else {
                            msgEl.innerHTML = `
                                <div class="astrologer-avatar"><i class="fas fa-sun"></i></div>
                                <div class="message-content">${this.formatChatResponse(msg.content)}</div>
                            `;
                        }
                        messagesContainer.appendChild(msgEl);
                    });
                    messagesContainer.scrollTop = messagesContainer.scrollHeight;
                } else {
                    // No messages, show welcome
                    this.showWelcomeMessage(messagesContainer, chart.chart_name);
                }
            } else {
                // No conversations, show welcome
                this.showWelcomeMessage(messagesContainer, chart.chart_name);
            }
        } catch (error) {
            console.error('Error loading conversation:', error);
            // Show welcome message on error
            this.showWelcomeMessage(messagesContainer, chart.chart_name);
        }
        
        modal.querySelector('#chatInput').focus();
    },
    
    showWelcomeMessage(container, chartName) {
        container.innerHTML = `
            <div class="welcome-message">
                <div class="astrologer-avatar"><i class="fas fa-sun"></i></div>
                <div class="message-content">
                    <p>Hello! I'm here to help you explore and understand ${chartName}'s birth chart. I can discuss the patterns, tendencies, and themes revealed through astrological symbolism.</p>
                    <p>What would you like to explore? You could ask about:</p>
                    <ul>
                        <li>Specific placements (e.g., "What does my Moon in Scorpio suggest?")</li>
                        <li>Life themes (e.g., "What patterns does my chart show around relationships?")</li>
                        <li>Self-reflection (e.g., "What does my Saturn placement suggest I'm learning?")</li>
                        <li>Understanding aspects (e.g., "What does my Sun square Mars mean?")</li>
                    </ul>
                    <p class="chat-disclaimer"><em>Note: Astrology is a symbolic tool for self-reflection, not a predictive science. These interpretations are for entertainment and personal insight only, not professional advice.</em></p>
                </div>
            </div>
        `;
    },
    
    async handleChatSubmit(message) {
        const messagesContainer = document.getElementById('chatMessages');
        if (!messagesContainer) return;
        
        // Add user message to UI
        const userMsgEl = document.createElement('div');
        userMsgEl.className = 'chat-message user-message';
        userMsgEl.innerHTML = `
            <div class="message-content">${this.escapeHtml(message)}</div>
        `;
        messagesContainer.appendChild(userMsgEl);
        
        // Add loading indicator
        const loadingEl = document.createElement('div');
        loadingEl.className = 'chat-message assistant-message loading';
        loadingEl.innerHTML = `
            <div class="astrologer-avatar"><i class="fas fa-sun"></i></div>
            <div class="message-content">
                <div class="typing-indicator">
                    <span></span><span></span><span></span>
                </div>
            </div>
        `;
        messagesContainer.appendChild(loadingEl);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
        
        try {
            const response = await this.sendChatMessage(
                this.currentChartId,
                message,
                this.currentChatConversation
            );
            
            // Remove loading indicator
            loadingEl.remove();
            
            // Add assistant response
            const assistantMsgEl = document.createElement('div');
            assistantMsgEl.className = 'chat-message assistant-message';
            assistantMsgEl.innerHTML = `
                <div class="astrologer-avatar"><i class="fas fa-sun"></i></div>
                <div class="message-content">${this.formatChatResponse(response.response)}</div>
            `;
            messagesContainer.appendChild(assistantMsgEl);
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
            
        } catch (error) {
            loadingEl.remove();
            
            const errorMsgEl = document.createElement('div');
            errorMsgEl.className = 'chat-message assistant-message error';
            errorMsgEl.innerHTML = `
                <div class="astrologer-avatar"><i class="fas fa-exclamation-triangle"></i></div>
                <div class="message-content">I'm sorry, I encountered an error. Please try again.</div>
            `;
            messagesContainer.appendChild(errorMsgEl);
        }
    },
    
    closeModals() {
        document.querySelectorAll('.modal-overlay').forEach(modal => {
            modal.classList.remove('active');
            setTimeout(() => modal.remove(), 300);
        });
    },
    
    closeMenu() {
        // Close the Forty theme's sidebar menu
        const body = document.body;
        if (body.classList.contains('is-menu-visible')) {
            body.classList.remove('is-menu-visible');
        }
    },
    
    // Add "Save Chart" button to results
    addSaveChartButton() {
        const existingBtn = document.getElementById('saveChartBtn');
        if (existingBtn) return;
        
        const geminiHeader = document.querySelector('#gemini-title .major');
        if (!geminiHeader) return;
        
        const saveBtn = document.createElement('button');
        saveBtn.id = 'saveChartBtn';
        saveBtn.className = 'save-chart-btn';
        saveBtn.innerHTML = '<i class="fas fa-save"></i> Save Chart';
        saveBtn.onclick = () => this.handleSaveChart();
        
        geminiHeader.appendChild(saveBtn);
    },
    
    updateSaveChartButton(isSaved) {
        const btn = document.getElementById('saveChartBtn');
        if (btn) {
            if (isSaved) {
                btn.innerHTML = '<i class="fas fa-check"></i> Saved';
                btn.classList.add('saved');
                btn.disabled = true;
            } else {
                btn.innerHTML = '<i class="fas fa-save"></i> Save Chart';
                btn.classList.remove('saved');
                btn.disabled = false;
            }
        }
    },
    
    async handleSaveChart() {
        if (!this.isLoggedIn()) {
            this.showLoginModal();
            return;
        }
        
        // Get current chart data from AstrologyCalculator
        if (!window.currentChartData || !window.currentUserInputs) {
            this.showNotification('No chart data to save', 'error');
            return;
        }
        
        try {
            const reading = AstrologyCalculator.geminiOutput?.innerText || null;
            await this.saveCurrentChart(
                window.currentChartData,
                reading,
                window.currentUserInputs
            );
            this.updateSaveChartButton(true);
        } catch (error) {
            console.error('Failed to save chart:', error);
        }
    },
    
    // ============================================================
    // UTILITIES
    // ============================================================
    
    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.innerHTML = `
            <span>${message}</span>
            <button class="notification-close">&times;</button>
        `;
        document.body.appendChild(notification);
        
        setTimeout(() => notification.classList.add('active'), 10);
        
        const closeBtn = notification.querySelector('.notification-close');
        closeBtn.onclick = () => {
            notification.classList.remove('active');
            setTimeout(() => notification.remove(), 300);
        };
        
        setTimeout(() => {
            notification.classList.remove('active');
            setTimeout(() => notification.remove(), 300);
        }, 5000);
    },
    
    formatDate(dateString) {
        const date = new Date(dateString);
        const now = new Date();
        const diff = now - date;
        
        if (diff < 60000) return 'just now';
        if (diff < 3600000) return `${Math.floor(diff / 60000)} min ago`;
        if (diff < 86400000) return `${Math.floor(diff / 3600000)} hours ago`;
        if (diff < 604800000) return `${Math.floor(diff / 86400000)} days ago`;
        
        return date.toLocaleDateString();
    },
    
    formatChatResponse(text) {
        return text
            .replace(/\n\n/g, '</p><p>')
            .replace(/\n/g, '<br>')
            .replace(/^/, '<p>')
            .replace(/$/, '</p>');
    },
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },
    
    parseTimeHour(timeStr) {
        const match = timeStr.match(/(\d{1,2}):(\d{2})\s*(AM|PM)/i);
        if (!match) return 12;
        let hour = parseInt(match[1], 10);
        const ampm = match[3].toUpperCase();
        if (ampm === 'PM' && hour < 12) hour += 12;
        if (ampm === 'AM' && hour === 12) hour = 0;
        return hour;
    },
    
    parseTimeMinute(timeStr) {
        const match = timeStr.match(/(\d{1,2}):(\d{2})\s*(AM|PM)/i);
        if (!match) return 0;
        return parseInt(match[2], 10);
    }
};

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    AuthManager.init();
});

