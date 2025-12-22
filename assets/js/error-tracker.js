/**
 * Error Tracking Module
 * Centralized error tracking and reporting
 * 
 * @module error-tracker
 * @description Captures and reports JavaScript errors, unhandled promise rejections,
 * and custom errors. Can send to logging services or analytics.
 * 
 * @example
 * // Initialize error tracking
 * errorTracker.init();
 * 
 * // Track custom error
 * errorTracker.trackError('Custom error', { context: 'chart_calculation' });
 */

/**
 * Error Tracker class
 * @class ErrorTracker
 */
class ErrorTracker {
	constructor() {
		/** @type {boolean} Whether tracking is enabled */
		this.enabled = true;
		/** @type {Array} Error queue for batching */
		this.errorQueue = [];
		/** @type {number} Batch interval in milliseconds */
		this.batchInterval = 5000;
		/** @type {number|null} Batch timer ID */
		this.batchTimer = null;
	}

	/**
	 * Initialize error tracking
	 * Sets up global error handlers
	 */
	init() {
		if (!this.enabled) return;

		// Track unhandled errors
		window.addEventListener('error', (event) => {
			this.handleError({
				message: event.message,
				filename: event.filename,
				lineno: event.lineno,
				colno: event.colno,
				error: event.error,
				type: 'javascript_error'
			});
		});

		// Track unhandled promise rejections
		window.addEventListener('unhandledrejection', (event) => {
			this.handleError({
				message: event.reason?.message || 'Unhandled Promise Rejection',
				error: event.reason,
				type: 'promise_rejection'
			});
		});

		// Start batch processing
		this.startBatchProcessing();
	}

	/**
	 * Handle an error
	 * @param {Object} errorData - Error information
	 * @param {string} errorData.message - Error message
	 * @param {string} [errorData.filename] - Source filename
	 * @param {number} [errorData.lineno] - Line number
	 * @param {number} [errorData.colno] - Column number
	 * @param {Error} [errorData.error] - Error object
	 * @param {string} [errorData.type] - Error type
	 * @param {Object} [errorData.context] - Additional context
	 */
	handleError(errorData) {
		const error = {
			message: errorData.message || 'Unknown error',
			filename: errorData.filename || 'unknown',
			lineno: errorData.lineno || 0,
			colno: errorData.colno || 0,
			type: errorData.type || 'custom_error',
			timestamp: new Date().toISOString(),
			url: window.location.href,
			userAgent: navigator.userAgent,
			stack: errorData.error?.stack || '',
			context: errorData.context || {}
		};

		// Log to console in development (browser-safe - never access process directly)
		// In browser, only check hostname to avoid ReferenceError
		try {
			const isDevelopment = (typeof window !== 'undefined' && window.location) && 
			                      (window.location.hostname === 'localhost' || 
			                       window.location.hostname === '127.0.0.1' ||
			                       window.location.hostname.includes('localhost'));
			
			if (isDevelopment) {
				console.error('[Error Tracker]', error);
			}
		} catch (e) {
			// Silently fail - don't break error tracking if logging fails
		}

		// Add to queue for batching
		this.errorQueue.push(error);

		// Send immediately for critical errors
		if (errorData.type === 'critical') {
			this.sendErrors([error]);
		}
	}

	/**
	 * Track a custom error
	 * @param {string} message - Error message
	 * @param {Object} [context={}] - Additional context
	 * @param {string} [type='custom_error'] - Error type
	 */
	trackError(message, context = {}, type = 'custom_error') {
		this.handleError({
			message,
			context,
			type
		});
	}

	/**
	 * Track API errors
	 * @param {string} endpoint - API endpoint that failed
	 * @param {Error} error - Error object
	 * @param {Object} [requestData={}] - Request data
	 */
	trackAPIError(endpoint, error, requestData = {}) {
		this.handleError({
			message: `API Error: ${endpoint}`,
			error,
			type: 'api_error',
			context: {
				endpoint,
				requestData: this.sanitizeRequestData(requestData)
			}
		});
	}

	/**
	 * Start batch processing of errors
	 * @private
	 */
	startBatchProcessing() {
		this.batchTimer = setInterval(() => {
			if (this.errorQueue.length > 0) {
				this.sendErrors([...this.errorQueue]);
				this.errorQueue = [];
			}
		}, this.batchInterval);
	}

	/**
	 * Send errors to backend or logging service
	 * @private
	 * @param {Array} errors - Array of error objects
	 */
	sendErrors(errors) {
		// Send to backend if API client is available
		if (typeof apiClient !== 'undefined') {
			apiClient.logClicks({
				type: 'errors',
				errors: errors,
				timestamp: new Date().toISOString(),
				url: window.location.href,
				userAgent: navigator.userAgent
			}).catch(() => {
				// Silently fail - don't create error loops
			});
		}

		// Could also send to external services like Sentry, LogRocket, etc.
		// if (window.Sentry) {
		//   errors.forEach(error => window.Sentry.captureException(error));
		// }
	}

	/**
	 * Sanitize request data to remove sensitive information
	 * @private
	 * @param {Object} data - Request data
	 * @returns {Object} Sanitized data
	 */
	sanitizeRequestData(data) {
		const sanitized = { ...data };
		const sensitiveKeys = ['password', 'token', 'key', 'secret', 'email'];

		Object.keys(sanitized).forEach(key => {
			if (sensitiveKeys.some(sensitive => key.toLowerCase().includes(sensitive))) {
				sanitized[key] = '[REDACTED]';
			}
		});

		return sanitized;
	}

	/**
	 * Get error statistics
	 * @returns {Object} Error statistics
	 */
	getStats() {
		return {
			queueLength: this.errorQueue.length,
			enabled: this.enabled
		};
	}

	/**
	 * Clear error queue
	 */
	clearQueue() {
		this.errorQueue = [];
	}

	/**
	 * Disable error tracking
	 */
	disable() {
		this.enabled = false;
		if (this.batchTimer) {
			clearInterval(this.batchTimer);
			this.batchTimer = null;
		}
	}

	/**
	 * Enable error tracking
	 */
	enable() {
		this.enabled = true;
		this.init();
	}
}

/**
 * Singleton error tracker instance
 * @type {ErrorTracker}
 */
const errorTracker = new ErrorTracker();

// Auto-initialize
if (typeof window !== 'undefined') {
	errorTracker.init();
}

