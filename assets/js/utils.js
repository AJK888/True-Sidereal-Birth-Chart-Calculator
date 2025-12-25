/**
 * Utility Functions Module
 * Shared helper functions for common operations
 * 
 * @module utils
 * @description Provides utility functions for date formatting, validation,
 * DOM manipulation, and other common operations.
 */

/**
 * Date utility functions
 */
const DateUtils = {
	/**
	 * Format date to MM/DD/YYYY
	 * @param {Date|string|number} date - Date to format
	 * @returns {string} Formatted date string
	 */
	formatMMDDYYYY(date) {
		const d = new Date(date);
		const month = String(d.getMonth() + 1).padStart(2, '0');
		const day = String(d.getDate()).padStart(2, '0');
		const year = d.getFullYear();
		return `${month}/${day}/${year}`;
	},

	/**
	 * Parse MM/DD/YYYY date string
	 * @param {string} dateString - Date string in MM/DD/YYYY format
	 * @returns {Date|null} Parsed date or null if invalid
	 */
	parseMMDDYYYY(dateString) {
		const parts = dateString.split('/');
		if (parts.length !== 3) return null;
		
		const month = parseInt(parts[0], 10) - 1;
		const day = parseInt(parts[1], 10);
		const year = parseInt(parts[2], 10);
		
		const date = new Date(year, month, day);
		if (date.getMonth() !== month || date.getDate() !== day || date.getFullYear() !== year) {
			return null;
		}
		
		return date;
	},

	/**
	 * Validate date is in valid range
	 * @param {Date} date - Date to validate
	 * @param {number} minYear - Minimum year (default: 1900)
	 * @param {number} maxYear - Maximum year (default: current year)
	 * @returns {boolean} True if date is valid
	 */
	isValidDateRange(date, minYear = 1900, maxYear = new Date().getFullYear()) {
		if (!(date instanceof Date) || isNaN(date.getTime())) return false;
		const year = date.getFullYear();
		return year >= minYear && year <= maxYear;
	}
};

/**
 * Time utility functions
 */
const TimeUtils = {
	/**
	 * Parse time string (HH:MM AM/PM)
	 * @param {string} timeString - Time string to parse
	 * @returns {Object|null} Object with {hour, minute} or null if invalid
	 */
	parseTime(timeString) {
		const regex = /^(\d{1,2}):(\d{2})\s*(AM|PM)$/i;
		const match = timeString.match(regex);
		
		if (!match) return null;
		
		let hour = parseInt(match[1], 10);
		const minute = parseInt(match[2], 10);
		const period = match[3].toUpperCase();
		
		if (hour < 1 || hour > 12 || minute < 0 || minute > 59) {
			return null;
		}
		
		if (period === 'PM' && hour !== 12) hour += 12;
		if (period === 'AM' && hour === 12) hour = 0;
		
		return { hour, minute };
	},

	/**
	 * Format time to HH:MM AM/PM
	 * @param {number} hour - Hour (0-23)
	 * @param {number} minute - Minute (0-59)
	 * @returns {string} Formatted time string
	 */
	formatTime(hour, minute) {
		const period = hour >= 12 ? 'PM' : 'AM';
		const displayHour = hour > 12 ? hour - 12 : (hour === 0 ? 12 : hour);
		const displayMinute = String(minute).padStart(2, '0');
		return `${displayHour}:${displayMinute} ${period}`;
	}
};

/**
 * Validation utility functions
 */
const ValidationUtils = {
	/**
	 * Validate email format
	 * @param {string} email - Email to validate
	 * @returns {boolean} True if valid email
	 */
	isValidEmail(email) {
		const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
		return regex.test(email);
	},

	/**
	 * Validate required field
	 * @param {*} value - Value to check
	 * @returns {boolean} True if value is not empty
	 */
	isRequired(value) {
		if (value === null || value === undefined) return false;
		if (typeof value === 'string') return value.trim().length > 0;
		return true;
	},

	/**
	 * Validate string length
	 * @param {string} value - String to validate
	 * @param {number} min - Minimum length
	 * @param {number} [max] - Maximum length
	 * @returns {boolean} True if valid length
	 */
	isValidLength(value, min, max) {
		if (typeof value !== 'string') return false;
		const length = value.trim().length;
		if (length < min) return false;
		if (max !== undefined && length > max) return false;
		return true;
	}
};

/**
 * DOM utility functions
 */
const DOMUtils = {
	/**
	 * Smooth scroll to element
	 * @param {HTMLElement|string} element - Element or selector
	 * @param {Object} [options={}] - Scroll options
	 * @param {string} [options.behavior='smooth'] - Scroll behavior
	 * @param {string} [options.block='start'] - Block alignment
	 */
	scrollTo(element, options = {}) {
		const el = typeof element === 'string' ? document.querySelector(element) : element;
		if (!el) return;
		
		el.scrollIntoView({
			behavior: options.behavior || 'smooth',
			block: options.block || 'start',
			inline: options.inline || 'nearest'
		});
	},

	/**
	 * Check if element is in viewport
	 * @param {HTMLElement} element - Element to check
	 * @param {number} [threshold=0] - Visibility threshold (0-1)
	 * @returns {boolean} True if element is visible
	 */
	isInViewport(element, threshold = 0) {
		if (!element) return false;
		
		const rect = element.getBoundingClientRect();
		const windowHeight = window.innerHeight || document.documentElement.clientHeight;
		const windowWidth = window.innerWidth || document.documentElement.clientWidth;
		
		const visibleHeight = Math.min(rect.bottom, windowHeight) - Math.max(rect.top, 0);
		const visibleWidth = Math.min(rect.right, windowWidth) - Math.max(rect.left, 0);
		const visibleArea = visibleHeight * visibleWidth;
		const totalArea = rect.height * rect.width;
		
		return totalArea > 0 && (visibleArea / totalArea) >= threshold;
	},

	/**
	 * Debounce function calls
	 * @param {Function} func - Function to debounce
	 * @param {number} wait - Wait time in milliseconds
	 * @returns {Function} Debounced function
	 */
	debounce(func, wait) {
		let timeout;
		return function executedFunction(...args) {
			const later = () => {
				clearTimeout(timeout);
				func(...args);
			};
			clearTimeout(timeout);
			timeout = setTimeout(later, wait);
		};
	},

	/**
	 * Throttle function calls
	 * @param {Function} func - Function to throttle
	 * @param {number} limit - Time limit in milliseconds
	 * @returns {Function} Throttled function
	 */
	throttle(func, limit) {
		let inThrottle;
		return function(...args) {
			if (!inThrottle) {
				func.apply(this, args);
				inThrottle = true;
				setTimeout(() => inThrottle = false, limit);
			}
		};
	},

	/**
	 * Get computed CSS variable value
	 * @param {string} variable - CSS variable name (with or without --)
	 * @param {HTMLElement} [element=document.documentElement] - Element to get value from
	 * @returns {string} CSS variable value
	 */
	getCSSVariable(variable, element = document.documentElement) {
		const varName = variable.startsWith('--') ? variable : `--${variable}`;
		return getComputedStyle(element).getPropertyValue(varName).trim();
	},

	/**
	 * Set CSS variable value
	 * @param {string} variable - CSS variable name (with or without --)
	 * @param {string} value - Value to set
	 * @param {HTMLElement} [element=document.documentElement] - Element to set value on
	 */
	setCSSVariable(variable, value, element = document.documentElement) {
		const varName = variable.startsWith('--') ? variable : `--${variable}`;
		element.style.setProperty(varName, value);
	}
};

/**
 * String utility functions
 */
const StringUtils = {
	/**
	 * Capitalize first letter
	 * @param {string} str - String to capitalize
	 * @returns {string} Capitalized string
	 */
	capitalize(str) {
		if (!str) return '';
		return str.charAt(0).toUpperCase() + str.slice(1).toLowerCase();
	},

	/**
	 * Truncate string with ellipsis
	 * @param {string} str - String to truncate
	 * @param {number} maxLength - Maximum length
	 * @param {string} [suffix='...'] - Suffix to add
	 * @returns {string} Truncated string
	 */
	truncate(str, maxLength, suffix = '...') {
		if (!str || str.length <= maxLength) return str;
		return str.slice(0, maxLength - suffix.length) + suffix;
	},

	/**
	 * Sanitize string for display (basic XSS prevention)
	 * @param {string} str - String to sanitize
	 * @returns {string} Sanitized string
	 */
	sanitize(str) {
		const div = document.createElement('div');
		div.textContent = str;
		return div.innerHTML;
	}
};

/**
 * Number utility functions
 */
const NumberUtils = {
	/**
	 * Format number with commas
	 * @param {number} num - Number to format
	 * @returns {string} Formatted number string
	 */
	formatNumber(num) {
		return num.toLocaleString();
	},

	/**
	 * Clamp number between min and max
	 * @param {number} value - Value to clamp
	 * @param {number} min - Minimum value
	 * @param {number} max - Maximum value
	 * @returns {number} Clamped value
	 */
	clamp(value, min, max) {
		return Math.min(Math.max(value, min), max);
	},

	/**
	 * Check if value is numeric
	 * @param {*} value - Value to check
	 * @returns {boolean} True if numeric
	 */
	isNumeric(value) {
		return !isNaN(parseFloat(value)) && isFinite(value);
	}
};

/**
 * Export all utilities as a single object
 */
const Utils = {
	date: DateUtils,
	time: TimeUtils,
	validation: ValidationUtils,
	dom: DOMUtils,
	string: StringUtils,
	number: NumberUtils
};

// Make available globally
if (typeof window !== 'undefined') {
	window.Utils = Utils;
}

