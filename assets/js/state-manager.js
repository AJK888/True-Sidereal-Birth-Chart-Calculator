/**
 * Centralized State Manager
 * Manages application state using event-driven pattern
 * 
 * @module state-manager
 * @description Provides centralized state management with subscription-based updates.
 * Components can subscribe to state changes and react automatically.
 * 
 * @example
 * // Subscribe to chart data changes
 * const unsubscribe = stateManager.subscribe('currentChartData', (newData, oldData) => {
 *   console.log('Chart data updated:', newData);
 * });
 * 
 * // Update state
 * stateManager.setState('currentChartData', chartData);
 * 
 * // Unsubscribe when done
 * unsubscribe();
 */

/**
 * State Manager class for centralized application state
 * @class StateManager
 */
class StateManager {
	/**
	 * Creates an instance of StateManager
	 * @constructor
	 */
	constructor() {
		/** @type {Object} Application state */
		this.state = {
			/** @type {Object|null} Current calculated chart data */
			currentChartData: null,
			/** @type {Object|null} Current user input data */
			currentUserInputs: null,
			/** @type {boolean} Loading state flag */
			isLoading: false,
			/** @type {Object|null} Current authenticated user */
			user: null,
			/** @type {Array|null} User's saved charts */
			savedCharts: null
		};
		/** @type {Object} Map of state keys to listener callbacks */
		this.listeners = {};
	}

	/**
	 * Get current state or specific state key
	 * @param {string} [key] - Optional state key to retrieve
	 * @returns {*} State value if key provided, or entire state object
	 * @example
	 * const chartData = stateManager.getState('currentChartData');
	 * const allState = stateManager.getState();
	 */
	getState(key) {
		if (key) {
			return this.state[key];
		}
		return { ...this.state };
	}

	/**
	 * Update state and notify listeners
	 * @param {string} key - State key to update
	 * @param {*} value - New value for the state key
	 * @example
	 * stateManager.setState('isLoading', true);
	 * stateManager.setState('currentChartData', chartData);
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
	 * Subscribe to state changes for a specific key or all changes
	 * @param {string} key - State key to subscribe to (use '*' for all changes)
	 * @param {Function} callback - Callback function called on state change
	 * @param {*} callback.newValue - New state value
	 * @param {*} callback.oldValue - Previous state value
	 * @param {Object} callback.fullState - Complete current state
	 * @returns {Function} Unsubscribe function
	 * @example
	 * const unsubscribe = stateManager.subscribe('currentChartData', (newData, oldData, state) => {
	 *   updateUI(newData);
	 * });
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
	 * Notify listeners of state change (internal method)
	 * @private
	 * @param {string} key - State key that changed
	 * @param {*} newValue - New value
	 * @param {*} oldValue - Previous value
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
	 * Reset all state to initial values
	 * @example
	 * stateManager.reset(); // Clears all state and notifies listeners
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

/**
 * Singleton state manager instance
 * Use this instance throughout the application for state management
 * @type {StateManager}
 */
const stateManager = new StateManager();

