/**
 * Synastry Analysis Frontend
 * Handles form submission and displays results
 */

const SynastryManager = {
	API_BASE: "https://true-sidereal-api.onrender.com",
	
	init() {
		this.checkFriendsFamilyKey();
		this.setupForm();
	},
	
	checkFriendsFamilyKey() {
		// Check for FRIENDS_AND_FAMILY_KEY in URL
		// Handle case where key contains & character (e.g., F&FKEY)
		let friendsAndFamilyKey = null;
		const urlParams = new URLSearchParams(window.location.search);
		friendsAndFamilyKey = urlParams.get('FRIENDS_AND_FAMILY_KEY');
		
		// Handle URL-encoded values and split values
		if (!friendsAndFamilyKey) {
			const allParams = new URLSearchParams(window.location.search);
			const keys = Array.from(allParams.keys());
			const keyIndex = keys.indexOf('FRIENDS_AND_FAMILY_KEY');
			if (keyIndex !== -1 && keyIndex < keys.length - 1) {
				// Check if next param might be part of the value
				const nextKey = keys[keyIndex + 1];
				if (nextKey === 'FKEY' || !allParams.get(nextKey)) {
					// Likely split value, try to reconstruct
					friendsAndFamilyKey = allParams.get('FRIENDS_AND_FAMILY_KEY') + '&' + nextKey;
				}
			}
		}
		
		// Decode URL-encoded characters
		if (friendsAndFamilyKey) {
			friendsAndFamilyKey = decodeURIComponent(friendsAndFamilyKey);
		}
		
		if (!friendsAndFamilyKey) {
			// Redirect to home if no key
			window.location.href = 'index.html';
			return;
		}
		
		// Store the key for later use
		this.friendsAndFamilyKey = friendsAndFamilyKey;
		
		// Synastry menu item is now always visible, no need to show it
	},
	
	setupForm() {
		const form = document.getElementById('synastryForm');
		if (!form) return;
		
		form.addEventListener('submit', async (e) => {
			e.preventDefault();
			await this.submitSynastry();
		});
	},
	
	async submitSynastry() {
		const person1Data = document.getElementById('person1Data').value.trim();
		const person2Data = document.getElementById('person2Data').value.trim();
		const userEmail = document.getElementById('userEmail').value.trim();
		
		if (!person1Data || !person2Data) {
			this.showError('Please paste data for both Person 1 and Person 2.');
			return;
		}
		
		if (!userEmail) {
			this.showError('Please enter your email address.');
			return;
		}
		
		// Get FRIENDS_AND_FAMILY_KEY (use stored value or extract from URL)
		let friendsAndFamilyKey = this.friendsAndFamilyKey;
		if (!friendsAndFamilyKey) {
			// Try to get from URL - handle both direct param and split values
			const urlParams = new URLSearchParams(window.location.search);
			friendsAndFamilyKey = urlParams.get('FRIENDS_AND_FAMILY_KEY');
			
			// Handle URL-encoded values and split values (e.g., F&FKEY gets split)
			if (!friendsAndFamilyKey || friendsAndFamilyKey.length < 3) {
				// Check if key was split due to & character
				const allParams = new URLSearchParams(window.location.search);
				const keys = Array.from(allParams.keys());
				const keyIndex = keys.indexOf('FRIENDS_AND_FAMILY_KEY');
				if (keyIndex !== -1 && keyIndex < keys.length - 1) {
					const nextKey = keys[keyIndex + 1];
					const nextValue = allParams.get(nextKey);
					// If next param has no value or is likely part of the key
					if (!nextValue || nextKey === 'FKEY' || (nextKey.length <= 10 && !nextValue.includes('='))) {
						const firstPart = allParams.get('FRIENDS_AND_FAMILY_KEY') || '';
						friendsAndFamilyKey = firstPart + '&' + nextKey;
					}
				}
			}
			
			// Also check if key is in the raw URL string (for complex cases)
			if (!friendsAndFamilyKey || friendsAndFamilyKey.length < 3) {
				const rawUrl = window.location.href;
				const keyMatch = rawUrl.match(/FRIENDS_AND_FAMILY_KEY=([^&]+)/);
				if (keyMatch && keyMatch[1]) {
					friendsAndFamilyKey = decodeURIComponent(keyMatch[1]);
				}
			}
			
			if (friendsAndFamilyKey) {
				friendsAndFamilyKey = decodeURIComponent(friendsAndFamilyKey);
			}
		}
		
		// Log for debugging (first 3 chars only for security)
		console.log('[Synastry] Using F&F key:', friendsAndFamilyKey ? (friendsAndFamilyKey.substring(0, 3) + '...') : 'none');
		
		if (!friendsAndFamilyKey) {
			this.showError('Friends and family key is required. Please access this page with the correct key.');
			return;
		}
		
		// Show loading, hide results and error
		document.getElementById('loading').style.display = 'block';
		document.getElementById('results').style.display = 'none';
		document.getElementById('errorMessage').style.display = 'none';
		document.getElementById('submitBtn').disabled = true;
		
		try {
			const headers = {
				'Content-Type': 'application/json',
				'X-Friends-And-Family-Key': friendsAndFamilyKey
			};
			
			const response = await fetch(`${this.API_BASE}/api/synastry`, {
				method: 'POST',
				headers: headers,
				body: JSON.stringify({
					person1_data: person1Data,
					person2_data: person2Data,
					user_email: userEmail
				})
			});
			
			if (!response.ok) {
				const errorData = await response.json().catch(() => ({ detail: 'Unknown error occurred' }));
				throw new Error(errorData.detail || `Server error: ${response.status}`);
			}
			
			const data = await response.json();
			
			// Display results
			if (data.analysis) {
				document.getElementById('resultsContent').textContent = data.analysis;
				document.getElementById('results').style.display = 'block';
				document.getElementById('loading').style.display = 'none';
				
				// Scroll to results
				document.getElementById('results').scrollIntoView({ behavior: 'smooth' });
			} else {
				throw new Error('No analysis data received');
			}
			
		} catch (error) {
			console.error('Error submitting synastry:', error);
			this.showError(error.message || 'An error occurred while generating the synastry analysis. Please try again.');
			document.getElementById('loading').style.display = 'none';
		} finally {
			document.getElementById('submitBtn').disabled = false;
		}
	},
	
	showError(message) {
		const errorDiv = document.getElementById('errorMessage');
		errorDiv.textContent = message;
		errorDiv.style.display = 'block';
		errorDiv.scrollIntoView({ behavior: 'smooth' });
	}
};

// Initialize when page loads
document.addEventListener('DOMContentLoaded', () => {
	SynastryManager.init();
});

