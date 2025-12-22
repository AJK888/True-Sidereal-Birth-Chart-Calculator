/**
 * Performance Monitoring Module
 * Tracks and reports Core Web Vitals and custom performance metrics
 * 
 * @module performance-monitor
 * @description Monitors page load performance, Core Web Vitals (LCP, FID, CLS),
 * and custom metrics. Can send data to analytics or logging services.
 * 
 * @example
 * // Initialize monitoring
 * performanceMonitor.init();
 * 
 * // Track custom metric
 * performanceMonitor.trackMetric('chart_calculation_time', 1234);
 */

/**
 * Performance Monitor class
 * @class PerformanceMonitor
 */
class PerformanceMonitor {
	constructor() {
		/** @type {Object} Collected metrics */
		this.metrics = {};
		/** @type {boolean} Whether monitoring is enabled */
		this.enabled = true;
		/** @type {Array} Performance observers */
		this.observers = [];
	}

	/**
	 * Initialize performance monitoring
	 * Sets up Core Web Vitals tracking and page load metrics
	 */
	init() {
		if (!this.enabled || typeof window === 'undefined') return;

		// Track page load metrics
		this.trackPageLoad();

		// Track Core Web Vitals if supported
		if ('PerformanceObserver' in window) {
			this.trackLCP(); // Largest Contentful Paint
			this.trackFID(); // First Input Delay
			this.trackCLS(); // Cumulative Layout Shift
		}

		// Track custom navigation timing
		this.trackNavigationTiming();
	}

	/**
	 * Track page load performance
	 * @private
	 */
	trackPageLoad() {
		if (!window.performance || !window.performance.timing) return;

		window.addEventListener('load', () => {
			setTimeout(() => {
				const timing = window.performance.timing;
				const navigation = window.performance.navigation;

				this.metrics.pageLoad = {
					dns: timing.domainLookupEnd - timing.domainLookupStart,
					tcp: timing.connectEnd - timing.connectStart,
					request: timing.responseStart - timing.requestStart,
					response: timing.responseEnd - timing.responseStart,
					domProcessing: timing.domComplete - timing.domLoading,
					loadComplete: timing.loadEventEnd - timing.navigationStart,
					navigationType: this.getNavigationType(navigation.type)
				};

				this.logMetric('page_load', this.metrics.pageLoad);
			}, 0);
		});
	}

	/**
	 * Track Largest Contentful Paint (LCP)
	 * @private
	 */
	trackLCP() {
		try {
			const observer = new PerformanceObserver((list) => {
				const entries = list.getEntries();
				const lastEntry = entries[entries.length - 1];
				
				this.metrics.lcp = {
					value: lastEntry.renderTime || lastEntry.loadTime,
					element: lastEntry.element?.tagName || 'unknown',
					size: lastEntry.size || 0
				};

				this.logMetric('lcp', this.metrics.lcp);
			});

			observer.observe({ entryTypes: ['largest-contentful-paint'] });
			this.observers.push(observer);
		} catch (e) {
			console.warn('LCP tracking not supported:', e);
		}
	}

	/**
	 * Track First Input Delay (FID)
	 * @private
	 */
	trackFID() {
		try {
			const observer = new PerformanceObserver((list) => {
				const entries = list.getEntries();
				entries.forEach((entry) => {
					if (entry.processingStart - entry.startTime > 0) {
						this.metrics.fid = {
							value: entry.processingStart - entry.startTime,
							eventType: entry.name,
							target: entry.target?.tagName || 'unknown'
						};

						this.logMetric('fid', this.metrics.fid);
					}
				});
			});

			observer.observe({ entryTypes: ['first-input'] });
			this.observers.push(observer);
		} catch (e) {
			console.warn('FID tracking not supported:', e);
		}
	}

	/**
	 * Track Cumulative Layout Shift (CLS)
	 * @private
	 */
	trackCLS() {
		try {
			let clsValue = 0;
			const observer = new PerformanceObserver((list) => {
				const entries = list.getEntries();
				entries.forEach((entry) => {
					if (!entry.hadRecentInput) {
						clsValue += entry.value;
					}
				});

				this.metrics.cls = {
					value: clsValue,
					timestamp: Date.now()
				};

				this.logMetric('cls', this.metrics.cls);
			});

			observer.observe({ entryTypes: ['layout-shift'] });
			this.observers.push(observer);
		} catch (e) {
			console.warn('CLS tracking not supported:', e);
		}
	}

	/**
	 * Track navigation timing API
	 * @private
	 */
	trackNavigationTiming() {
		if (!window.performance || !window.performance.getEntriesByType) return;

		window.addEventListener('load', () => {
			setTimeout(() => {
				const navigation = window.performance.getEntriesByType('navigation')[0];
				if (navigation) {
					this.metrics.navigation = {
						domContentLoaded: navigation.domContentLoadedEventEnd - navigation.domContentLoadedEventStart,
						loadComplete: navigation.loadEventEnd - navigation.loadEventStart,
						domInteractive: navigation.domInteractive - navigation.fetchStart,
						timeToFirstByte: navigation.responseStart - navigation.requestStart
					};

					this.logMetric('navigation_timing', this.metrics.navigation);
				}
			}, 0);
		});
	}

	/**
	 * Track custom performance metric
	 * @param {string} name - Metric name
	 * @param {number} value - Metric value (usually in milliseconds)
	 * @param {Object} [metadata={}] - Additional metadata
	 */
	trackMetric(name, value, metadata = {}) {
		if (!this.enabled) return;

		this.metrics[name] = {
			value,
			timestamp: Date.now(),
			...metadata
		};

		this.logMetric(name, this.metrics[name]);
	}

	/**
	 * Start a performance timer
	 * @param {string} name - Timer name
	 * @returns {Function} Stop function that records the metric
	 * @example
	 * const stopTimer = performanceMonitor.startTimer('chart_calculation');
	 * // ... do work ...
	 * stopTimer(); // Records the elapsed time
	 */
	startTimer(name) {
		const startTime = performance.now();
		return () => {
			const duration = performance.now() - startTime;
			this.trackMetric(name, duration);
			return duration;
		};
	}

	/**
	 * Log metric (can be overridden to send to analytics)
	 * @param {string} name - Metric name
	 * @param {Object} data - Metric data
	 */
	logMetric(name, data) {
		if (process.env.NODE_ENV === 'development') {
			console.log(`[Performance] ${name}:`, data);
		}

		// Send to backend if API client is available
		if (typeof apiClient !== 'undefined') {
			// Send performance metrics to backend for analytics
			apiClient.logClicks({
				type: 'performance',
				metric: name,
				data: data,
				timestamp: new Date().toISOString(),
				url: window.location.href
			}).catch(() => {
				// Silently fail - don't create error loops
			});
		}
	}

	/**
	 * Get navigation type string
	 * @private
	 * @param {number} type - Navigation type code
	 * @returns {string} Navigation type name
	 */
	getNavigationType(type) {
		const types = {
			0: 'navigate',
			1: 'reload',
			2: 'back_forward',
			255: 'reserved'
		};
		return types[type] || 'unknown';
	}

	/**
	 * Get all collected metrics
	 * @returns {Object} All metrics
	 */
	getMetrics() {
		return { ...this.metrics };
	}

	/**
	 * Clear all metrics
	 */
	clearMetrics() {
		this.metrics = {};
	}

	/**
	 * Disconnect all observers
	 */
	disconnect() {
		this.observers.forEach(observer => observer.disconnect());
		this.observers = [];
	}
}

/**
 * Singleton performance monitor instance
 * @type {PerformanceMonitor}
 */
const performanceMonitor = new PerformanceMonitor();

// Auto-initialize on page load
if (typeof window !== 'undefined') {
	if (document.readyState === 'loading') {
		document.addEventListener('DOMContentLoaded', () => performanceMonitor.init());
	} else {
		performanceMonitor.init();
	}
}

