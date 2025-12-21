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
		const urlParams = new URLSearchParams(window.location.search);
		const friendsAndFamilyKey = urlParams.get('FRIENDS_AND_FAMILY_KEY');
		
		if (!friendsAndFamilyKey) {
			// Redirect to home if no key
			window.location.href = 'index.html';
			return;
		}
		
		// Show synastry menu item
		const menuItem = document.getElementById('synastry-menu-item');
		if (menuItem) {
			menuItem.style.display = 'block';
		}
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
		
		// Get FRIENDS_AND_FAMILY_KEY from URL
		const urlParams = new URLSearchParams(window.location.search);
		const friendsAndFamilyKey = urlParams.get('FRIENDS_AND_FAMILY_KEY');
		
		// Show loading, hide results and error
		document.getElementById('loading').style.display = 'block';
		document.getElementById('results').style.display = 'none';
		document.getElementById('errorMessage').style.display = 'none';
		document.getElementById('submitBtn').disabled = true;
		
		try {
			const headers = {
				'Content-Type': 'application/json'
			};
			
			if (friendsAndFamilyKey) {
				headers['X-Friends-And-Family-Key'] = friendsAndFamilyKey;
			}
			
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

