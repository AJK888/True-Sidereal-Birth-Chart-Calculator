const FullReadingManager = {
	API_BASE: "https://true-sidereal-api.onrender.com",
	chartHash: null,
	chartId: null,
	conversationId: null,
	
	init() {
		// Wait for AuthManager to be available
		const checkAuthManager = () => {
			if (typeof AuthManager === 'undefined') {
				// Wait a bit more for AuthManager to load
				setTimeout(checkAuthManager, 100);
				return;
			}
			
			// Get chart_hash from URL
			const urlParams = new URLSearchParams(window.location.search);
			this.chartHash = urlParams.get('chart_hash');
			
			if (!this.chartHash) {
				document.getElementById('loading-message').innerHTML = `
					<h2>No Chart Found</h2>
					<p>Please generate a chart first, then access your full reading.</p>
					<a href="index.html" class="button primary">Go to Calculator</a>
				`;
				return;
			}
			
			// Check authentication
			if (AuthManager.isLoggedIn && AuthManager.isLoggedIn()) {
				// User is authenticated, load the reading
				this.loadFullReading();
			} else {
				// Show signup prompt
				document.getElementById('loading-message').style.display = 'none';
				document.getElementById('auth-required').style.display = 'block';
				
				const signupBtn = document.getElementById('signup-btn');
				const loginBtn = document.getElementById('login-btn');
				
				if (signupBtn) {
					// Remove any existing listeners
					const newSignupBtn = signupBtn.cloneNode(true);
					signupBtn.parentNode.replaceChild(newSignupBtn, signupBtn);
					
					newSignupBtn.addEventListener('click', () => {
						// Store chart_hash in localStorage so we can save chart after signup
						if (this.chartHash) {
							localStorage.setItem('pending_chart_hash', this.chartHash);
						}
						AuthManager.showRegisterModal();
						// Listen for successful signup
						window.addEventListener('auth-success', () => {
							// Try to save chart if we have pending chart data
							this.savePendingChart();
							this.loadFullReading();
						}, { once: true }); // Use once: true to prevent multiple listeners
					});
				}
				
				if (loginBtn) {
					// Remove any existing listeners
					const newLoginBtn = loginBtn.cloneNode(true);
					loginBtn.parentNode.replaceChild(newLoginBtn, loginBtn);
					
					newLoginBtn.addEventListener('click', () => {
						AuthManager.showLoginModal();
						// Listen for successful login
						window.addEventListener('auth-success', () => {
							// Try to save chart if we have pending chart data
							this.savePendingChart();
							this.loadFullReading();
						}, { once: true }); // Use once: true to prevent multiple listeners
					});
				}
			}
		};
		
		// Start checking for AuthManager
		checkAuthManager();
	},
	
	async loadFullReading() {
		try {
			// First, get the reading by chart_hash
			const readingResponse = await fetch(`${this.API_BASE}/get_reading/${this.chartHash}`, {
				method: 'GET',
				headers: {
					'Content-Type': 'application/json',
					...(typeof AuthManager !== 'undefined' && AuthManager.getAuthHeaders ? AuthManager.getAuthHeaders() : {})
				}
			});
			
			if (!readingResponse.ok) {
				if (readingResponse.status === 401) {
					// Not authenticated - show signup
					document.getElementById('loading-message').style.display = 'none';
					document.getElementById('auth-required').style.display = 'block';
					return;
				}
				throw new Error('Failed to load reading');
			}
			
			const readingData = await readingResponse.json();
			
			if (readingData.status === 'completed' && readingData.reading) {
				// Display the reading
				document.getElementById('loading-message').style.display = 'none';
				document.getElementById('reading-content').style.display = 'block';
				document.getElementById('reading-text').innerHTML = readingData.reading.replace(/\n/g, '<br>');
				
				// Initialize chat if we have chart_id
				if (readingData.chart_id) {
					this.chartId = readingData.chart_id;
					this.initChat();
				} else {
					// Try to find chart by hash
					await this.findChartByHash();
				}
			} else if (readingData.status === 'processing') {
				// Still processing
				document.getElementById('loading-message').innerHTML = `
					<h2>Your Reading is Being Generated</h2>
					<p>This can take up to 15 minutes. We'll email you when it's ready.</p>
					<p>You can check back here later or refresh the page.</p>
				`;
				// Poll for completion
				setTimeout(() => this.loadFullReading(), 30000); // Check every 30 seconds
			} else {
				throw new Error('Reading not available');
			}
		} catch (error) {
			console.error('Error loading full reading:', error);
			document.getElementById('loading-message').innerHTML = `
				<h2>Error Loading Reading</h2>
				<p>${error.message}</p>
				<a href="index.html" class="button primary">Go Back</a>
			`;
		}
	},
	
	async findChartByHash() {
		if (typeof AuthManager === 'undefined' || !AuthManager.isLoggedIn || !AuthManager.isLoggedIn()) {
			return;
		}
		
		try {
			// Get user's saved charts
			const charts = await AuthManager.getSavedCharts();
			if (charts) {
				// Find chart with matching hash
				for (const chart of charts) {
					if (chart.chart_hash === this.chartHash) {
						this.chartId = chart.id;
						this.initChat();
						return;
					}
				}
			}
		} catch (error) {
			console.error('Error finding chart:', error);
		}
	},
	
	initChat() {
		if (!this.chartId) {
			// Hide chat if no chart ID
			document.getElementById('chat-container').style.display = 'none';
			return;
		}
		
		// Show chat container
		document.getElementById('chat-container').style.display = 'flex';
		
		// Load conversation history
		this.loadConversationHistory();
		
		// Set up enter key for chat input
		document.getElementById('chat-input').addEventListener('keypress', (e) => {
			if (e.key === 'Enter') {
				this.sendChatMessage();
			}
		});
	},
	
	async loadConversationHistory() {
		if (!this.chartId) return;
		
		try {
			// Get all conversations for this chart
			const conversationsResponse = await fetch(`${this.API_BASE}/chat/conversations/${this.chartId}`, {
				method: 'GET',
				headers: {
					'Content-Type': 'application/json',
					...(typeof AuthManager !== 'undefined' && AuthManager.getAuthHeaders ? AuthManager.getAuthHeaders() : {})
				}
			});
			
			if (conversationsResponse.ok) {
				const conversationsData = await conversationsResponse.json();
				const conversations = conversationsData.conversations || [];
				
				// Use the most recent conversation or create a new one
				if (conversations.length > 0) {
					// Use the most recent conversation
					this.conversationId = conversations[0].id;
					
					// Load messages for this conversation
					const messagesResponse = await fetch(`${this.API_BASE}/chat/conversation/${this.conversationId}`, {
						method: 'GET',
						headers: {
							'Content-Type': 'application/json',
							...(typeof AuthManager !== 'undefined' && AuthManager.getAuthHeaders ? AuthManager.getAuthHeaders() : {})
						}
					});
					
					if (messagesResponse.ok) {
						const messagesData = await messagesResponse.json();
						const messages = messagesData.messages || [];
						
						// Display messages
						const messagesContainer = document.getElementById('chat-messages');
						messagesContainer.innerHTML = '';
						
						messages.forEach(msg => {
							this.addMessageToChat(msg.role === 'user' ? 'user' : 'assistant', msg.content);
						});
					}
				}
			}
		} catch (error) {
			console.error('Error loading conversation history:', error);
		}
	},
	
	async sendChatMessage() {
		const input = document.getElementById('chat-input');
		const message = input.value.trim();
		
		if (!message || !this.chartId) return;
		
		// Add user message to chat
		this.addMessageToChat('user', message);
		input.value = '';
		
		// Show loading indicator
		const loadingMsg = this.addMessageToChat('assistant', 'Thinking...');
		
		try {
			const response = await fetch(`${this.API_BASE}/chat/send`, {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					...(typeof AuthManager !== 'undefined' && AuthManager.getAuthHeaders ? AuthManager.getAuthHeaders() : {})
				},
				body: JSON.stringify({
					chart_id: this.chartId,
					conversation_id: this.conversationId,
					message: message
				})
			});
			
			if (!response.ok) {
				const errorData = await response.json();
				throw new Error(errorData.detail || 'Failed to send message');
			}
			
			const data = await response.json();
			
			// Update conversation ID if this was a new conversation
			if (data.conversation_id && !this.conversationId) {
				this.conversationId = data.conversation_id;
			}
			
			// Remove loading message and add response
			loadingMsg.remove();
			this.addMessageToChat('assistant', data.response);
			
		} catch (error) {
			console.error('Error sending chat message:', error);
			loadingMsg.remove();
			this.addMessageToChat('assistant', `Error: ${error.message}`);
		}
	},
	
	addMessageToChat(role, content) {
		const messagesContainer = document.getElementById('chat-messages');
		const messageDiv = document.createElement('div');
		messageDiv.className = `chat-message ${role}`;
		messageDiv.textContent = content;
		messagesContainer.appendChild(messageDiv);
		messagesContainer.scrollTop = messagesContainer.scrollHeight;
		return messageDiv;
	},
	
	async savePendingChart() {
		// Try to get chart data from localStorage or window
		const pendingHash = localStorage.getItem('pending_chart_hash');
		if (!pendingHash) return;
		
		try {
			// Get chart data from main page if available
			if (window.currentChartData && typeof AuthManager !== 'undefined' && AuthManager.isLoggedIn && AuthManager.isLoggedIn()) {
				const chartData = window.currentChartData;
				const userInputs = window.currentUserInputs;
				
				if (chartData && userInputs) {
					await AuthManager.saveCurrentChart(chartData, null, userInputs, true);
					localStorage.removeItem('pending_chart_hash');
					console.log('Pending chart saved after account creation');
				}
			}
		} catch (error) {
			console.error('Error saving pending chart:', error);
		}
	}
};

// Global functions for chat UI
function toggleChat() {
	const container = document.getElementById('chat-container');
	const icon = document.getElementById('chat-toggle-icon');
	
	if (container.classList.contains('chat-minimized')) {
		container.classList.remove('chat-minimized');
		icon.innerHTML = '<i class="fas fa-chevron-down"></i>';
	} else {
		container.classList.add('chat-minimized');
		icon.innerHTML = '<i class="fas fa-chevron-up"></i>';
	}
}

function sendChatMessage() {
	FullReadingManager.sendChatMessage();
}

// Initialize when page loads
document.addEventListener('DOMContentLoaded', () => {
	FullReadingManager.init();
});

