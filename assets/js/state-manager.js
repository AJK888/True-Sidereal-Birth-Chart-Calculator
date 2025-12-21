/**
 * Centralized State Manager
 * Manages application state using event-driven pattern
 */

class StateManager {
	constructor() {
		this.state = {
			currentChartData: null,
			currentUserInputs: null,
			isLoading: false,
			user: null,
			savedCharts: null
		};
		this.listeners = {};
	}

	/**
	 * Get current state
	 */
	getState(key) {
		if (key) {
			return this.state[key];
		}
		return { ...this.state };
	}

	/**
	 * Update state and notify listeners
	 */
	setState(key, value) {
		const oldValue = this.state[key];
		this.state[key] = value;
		
		// Notify listeners
		this.notify(key, value, oldValue);
		
		// Also notify general state change
		this.notify('*', this.state, this.state);
	}

	/**
	 * Subscribe to state changes
	 */
	subscribe(key, callback) {
		if (!this.listeners[key]) {
			this.listeners[key] = [];
		}
		this.listeners[key].push(callback);
		
		// Return unsubscribe function
		return () => {
			this.listeners[key] = this.listeners[key].filter(cb => cb !== callback);
		};
	}

	/**
	 * Notify listeners of state change
	 */
	notify(key, newValue, oldValue) {
		if (this.listeners[key]) {
			this.listeners[key].forEach(callback => {
				try {
					callback(newValue, oldValue, this.state);
				} catch (error) {
					console.error('Error in state listener:', error);
				}
			});
		}
	}

	/**
	 * Reset state
	 */
	reset() {
		this.state = {
			currentChartData: null,
			currentUserInputs: null,
			isLoading: false,
			user: null,
			savedCharts: null
		};
		this.notify('*', this.state, this.state);
	}
}

// Export singleton instance
const stateManager = new StateManager();

