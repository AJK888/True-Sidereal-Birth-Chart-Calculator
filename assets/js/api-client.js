/**
 * Unified API Client
 * Centralized API communication layer
 */

const API_BASE_URL = 'https://true-sidereal-api.onrender.com';

class APIClient {
	constructor() {
		this.baseURL = API_BASE_URL;
		this.defaultHeaders = {
			'Content-Type': 'application/json'
		};
	}

	/**
	 * Get friends and family key from URL
	 */
	getFriendsFamilyKey() {
		const urlParams = new URLSearchParams(window.location.search);
		let key = urlParams.get('FRIENDS_AND_FAMILY_KEY');
		
		// Handle URL-encoded values and split values
		if (!key) {
			const allParams = new URLSearchParams(window.location.search);
			const keys = Array.from(allParams.keys());
			const keyIndex = keys.indexOf('FRIENDS_AND_FAMILY_KEY');
			if (keyIndex !== -1 && keyIndex < keys.length - 1) {
				const nextKey = keys[keyIndex + 1];
				if (nextKey === 'FKEY' || !allParams.get(nextKey)) {
					key = allParams.get('FRIENDS_AND_FAMILY_KEY') + '&' + nextKey;
				}
			}
		}
		
		if (key) {
			key = decodeURIComponent(key);
		}
		
		return key;
	}

	/**
	 * Build headers with optional friends and family key
	 */
	buildHeaders(customHeaders = {}) {
		const headers = { ...this.defaultHeaders, ...customHeaders };
		const friendsFamilyKey = this.getFriendsFamilyKey();
		
		if (friendsFamilyKey) {
			headers['X-Friends-And-Family-Key'] = friendsFamilyKey;
		}
		
		return headers;
	}

	/**
	 * Generic fetch wrapper with error handling
	 */
	async request(endpoint, options = {}) {
		const url = `${this.baseURL}${endpoint}`;
		const config = {
			...options,
			headers: this.buildHeaders(options.headers || {})
		};

		try {
			const response = await fetch(url, config);
			
			if (!response.ok) {
				const errorData = await response.json().catch(() => ({ 
					detail: `HTTP ${response.status}: ${response.statusText}` 
				}));
				throw new Error(errorData.detail || `API Error ${response.status}`);
			}
			
			return await response.json();
		} catch (error) {
			console.error(`API request failed for ${endpoint}:`, error);
			throw error;
		}
	}

	/**
	 * Calculate chart
	 */
	async calculateChart(chartData) {
		return this.request('/calculate_chart', {
			method: 'POST',
			body: JSON.stringify(chartData)
		});
	}

	/**
	 * Generate reading
	 */
	async generateReading(chartData, userInputs, chartImageBase64 = null) {
		return this.request('/generate_reading', {
			method: 'POST',
			body: JSON.stringify({
				chart_data: chartData,
				unknown_time: chartData.unknown_time,
				user_inputs: userInputs,
				chart_image_base64: chartImageBase64
			})
		});
	}

	/**
	 * Get reading by hash
	 */
	async getReading(chartHash) {
		return this.request(`/get_reading/${chartHash}`, {
			method: 'GET'
		});
	}

	/**
	 * Find similar famous people
	 */
	async findSimilarFamousPeople(chartData, limit = 10) {
		return this.request('/api/find-similar-famous-people', {
			method: 'POST',
			body: JSON.stringify({
				chart_data: chartData,
				limit: limit
			})
		});
	}

	/**
	 * Log clicks
	 */
	async logClicks(clickData) {
		return this.request('/api/log-clicks', {
			method: 'POST',
			body: JSON.stringify(clickData)
		});
	}

	/**
	 * Synastry analysis
	 */
	async synastryAnalysis(person1Data, person2Data, email) {
		return this.request('/api/synastry', {
			method: 'POST',
			body: JSON.stringify({
				person1_data: person1Data,
				person2_data: person2Data,
				email: email
			})
		});
	}
}

// Export singleton instance
const apiClient = new APIClient();

