/**
 * Unified API Client
 * Centralized API communication layer for all backend API calls
 * 
 * @module api-client
 * @description Provides a single interface for all API communication with automatic
 * error handling, friends & family key management, and consistent request formatting.
 * 
 * @example
 * // Use the singleton instance
 * const chartData = await apiClient.calculateChart({
 *   full_name: "John Doe",
 *   year: 1990,
 *   month: 1,
 *   day: 1,
 *   // ...
 * });
 */

const API_BASE_URL = 'https://true-sidereal-api.onrender.com';

/**
 * API Client class for centralized API communication
 * @class APIClient
 */
class APIClient {
	/**
	 * Creates an instance of APIClient
	 * @constructor
	 */
	constructor() {
		/** @type {string} Base URL for all API requests */
		this.baseURL = API_BASE_URL;
		/** @type {Object} Default headers for all requests */
		this.defaultHeaders = {
			'Content-Type': 'application/json'
		};
	}

	/**
	 * Get friends and family key from URL parameters
	 * Handles URL-encoded values and split parameters (e.g., F&FKEY)
	 * @returns {string|null} The friends and family key, or null if not present
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
	 * @param {Object} [customHeaders={}] - Additional headers to include
	 * @returns {Object} Complete headers object with friends & family key if present
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
	 * @param {string} endpoint - API endpoint path (e.g., '/calculate_chart')
	 * @param {Object} [options={}] - Fetch options (method, body, headers, etc.)
	 * @returns {Promise<Object>} Parsed JSON response
	 * @throws {Error} If request fails or returns non-OK status
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
	 * Calculate astrological chart
	 * @param {Object} chartData - Chart calculation parameters
	 * @param {string} chartData.full_name - Full name
	 * @param {number} chartData.year - Birth year
	 * @param {number} chartData.month - Birth month (1-12)
	 * @param {number} chartData.day - Birth day
	 * @param {number} chartData.hour - Birth hour
	 * @param {number} chartData.minute - Birth minute
	 * @param {string} chartData.location - Birth location
	 * @param {boolean} chartData.unknown_time - Whether birth time is unknown
	 * @param {string} chartData.user_email - User email
	 * @param {boolean} [chartData.is_full_birth_name] - Whether name is full birth name
	 * @returns {Promise<Object>} Chart data with placements, houses, etc.
	 */
	async calculateChart(chartData) {
		return this.request('/calculate_chart', {
			method: 'POST',
			body: JSON.stringify(chartData)
		});
	}

	/**
	 * Generate AI astrological reading
	 * @param {Object} chartData - Calculated chart data
	 * @param {Object} userInputs - User input data
	 * @param {string|null} [chartImageBase64=null] - Base64 encoded chart image (optional)
	 * @returns {Promise<Object>} Reading response (may be async processing status)
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
	 * Get reading by chart hash (for polling)
	 * @param {string} chartHash - Unique chart hash identifier
	 * @returns {Promise<Object>} Reading status and content if available
	 */
	async getReading(chartHash) {
		return this.request(`/get_reading/${chartHash}`, {
			method: 'GET'
		});
	}

	/**
	 * Find famous people with similar astrological patterns
	 * @param {Object} chartData - Calculated chart data
	 * @param {number} [limit=10] - Maximum number of matches to return
	 * @returns {Promise<Object>} Object with matches array and similarity scores
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
	 * Log user click events for analytics
	 * @param {Object} clickData - Click tracking data
	 * @returns {Promise<Object>} Confirmation response
	 */
	async logClicks(clickData) {
		return this.request('/api/log-clicks', {
			method: 'POST',
			body: JSON.stringify(clickData)
		});
	}

	/**
	 * Generate synastry analysis between two people
	 * @param {string} person1Data - First person's chart data/reading
	 * @param {string} person2Data - Second person's chart data/reading
	 * @param {string} email - Email address to send results to
	 * @returns {Promise<Object>} Synastry analysis response
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

/**
 * Singleton API client instance
 * Use this instance throughout the application for all API calls
 * @type {APIClient}
 * @example
 * // Calculate a chart
 * const chart = await apiClient.calculateChart({...});
 * 
 * // Generate a reading
 * const reading = await apiClient.generateReading(chartData, userInputs);
 */
const apiClient = new APIClient();

