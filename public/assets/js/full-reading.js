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
			
			// Get chart_hash from URL (may or may not be present)
			const urlParams = new URLSearchParams(window.location.search);
			this.chartHash = urlParams.get('chart_hash');
			
			// Wire up inline full-reading form (if present)
			this.initInlineForm();
			
			// Check authentication
			if (AuthManager.isLoggedIn && AuthManager.isLoggedIn()) {
				// User is authenticated, try to load existing reading if we have a chart_hash
				if (this.chartHash) {
					this.loadFullReading();
				} else {
					// No existing hash; prompt user to use the inline form
					const loadingEl = document.getElementById('loading-message');
					if (loadingEl) {
						loadingEl.innerHTML = `
							<h2>No Saved Full Reading Found</h2>
							<p>You can generate a new complete reading using the form above.</p>
						`;
					}
				}
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
	
	initInlineForm() {
		const form = document.getElementById('fullReadingForm');
		if (!form) return;
		
		form.addEventListener('submit', async (e) => {
			e.preventDefault();
			
			try {
				// Basic auth check: require login for full reading
				if (!(typeof AuthManager !== 'undefined' && AuthManager.isLoggedIn && AuthManager.isLoggedIn())) {
					document.getElementById('loading-message').style.display = 'none';
					document.getElementById('auth-required').style.display = 'block';
					return;
				}
				
				const loadingEl = document.getElementById('loading-message');
				if (loadingEl) {
					loadingEl.style.display = 'block';
					loadingEl.innerHTML = `
						<h2>Queuing Your Full Reading...</h2>
						<p>We are recalculating your chart and generating a fresh full report. This can take several minutes.</p>
					`;
				}
				const readingContent = document.getElementById('reading-content');
				if (readingContent) {
					readingContent.style.display = 'none';
				}
				
				// Parse birth date
				const birthDateInput = form.querySelector("[name='birthDate']").value;
				const birthDateParts = birthDateInput.split('/');
				if (birthDateParts.length !== 3) {
					throw new Error("Please enter the date in MM/DD/YYYY format.");
				}
				let [month, day, year] = birthDateParts.map(s => parseInt(s, 10));
				
				// Parse time unless unknown
				let hour = 12;
				let minute = 0;
				const unknownTime = form.querySelector("[name='unknownTime']").checked;
				if (!unknownTime) {
					const timeInput = form.querySelector("[name='birthTime']").value;
					const timeRegex = /(\d{1,2}):(\d{2})\s*(AM|PM)/i;
					const timeMatch = timeInput.match(timeRegex);
					if (!timeMatch) throw new Error("Please enter the time in HH:MM AM/PM format (e.g., 02:30 PM).");
					
					hour = parseInt(timeMatch[1], 10);
					minute = parseInt(timeMatch[2], 10);
					const ampm = timeMatch[3].toUpperCase();
					if (ampm === 'PM' && hour < 12) hour += 12;
					if (ampm === 'AM' && hour === 12) hour = 0;
				}
				
				// Call calculate_chart to get chart_data
				const calcRes = await fetch(this.API_BASE.replace('/onrender.com', '/onrender.com') + '/calculate_chart', {
					method: 'POST',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({
						full_name: form.querySelector("[name='fullName']").value,
						year, month, day, hour, minute,
						location: form.querySelector("[name='location']").value,
						unknown_time: unknownTime,
						user_email: form.querySelector("[name='userEmail']").value,
						is_full_birth_name: form.querySelector("[name='isFullBirthName']").checked
					})
				});
				
				if (!calcRes.ok) {
					const errData = await calcRes.json().catch(() => ({}));
					throw new Error(errData.detail || `Chart calculation failed (${calcRes.status}).`);
				}
				
				const chartData = await calcRes.json();
				
				// Queue full reading via /generate_reading
				const userInputs = {
					full_name: form.querySelector("[name='fullName']").value,
					birth_date: birthDateInput,
					birth_time: form.querySelector("[name='birthTime']").value,
					location: form.querySelector("[name='location']").value,
					user_email: form.querySelector("[name='userEmail']").value
				};
				
				const readingRes = await fetch(`${this.API_BASE}/generate_reading`, {
					method: 'POST',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({
						chart_data: chartData,
						unknown_time: chartData.unknown_time,
						user_inputs: userInputs,
						chart_image_base64: null
					})
				});
				
				if (!readingRes.ok) {
					const errData = await readingRes.json().catch(() => ({}));
					throw new Error(errData.detail || `Failed to queue full reading (${readingRes.status}).`);
				}
				
				const readingInfo = await readingRes.json();
				if (readingInfo.chart_hash) {
					this.chartHash = readingInfo.chart_hash;
					
					// Update URL so refresh uses the same hash
					try {
						const url = new URL(window.location.href);
						url.searchParams.set('chart_hash', this.chartHash);
						window.history.replaceState({}, '', url.toString());
					} catch (e) {
						console.warn('Could not update URL with chart_hash:', e);
					}
					
					// Start polling for completed reading
					this.loadFullReading();
				}
				
				if (loadingEl) {
					loadingEl.innerHTML = `
						<h2>Your Reading is Being Generated</h2>
						<p>This can take up to 15 minutes. We'll email you when it's ready.</p>
						<p>You can check back here later or refresh the page.</p>
					`;
				}
			} catch (error) {
				console.error('Error starting full reading from inline form:', error);
				const loadingEl = document.getElementById('loading-message');
				if (loadingEl) {
					loadingEl.innerHTML = `
						<h2>Error Starting Full Reading</h2>
						<p>${error.message}</p>
					`;
				}
			}
		});
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

