/**
 * Form Validation Module
 * Provides real-time validation feedback for the chart form
 * 
 * @module form-validator
 * @description Validates form inputs in real-time with visual feedback,
 * error messages, and accessibility support.
 * 
 * @example
 * const validator = new FormValidator(document.getElementById('chartForm'));
 * // Validation happens automatically on blur and submit
 */

/**
 * Form Validator class for real-time form validation
 * @class FormValidator
 */
class FormValidator {
	/**
	 * Creates an instance of FormValidator
	 * @constructor
	 * @param {HTMLFormElement} form - Form element to validate
	 */
	constructor(form) {
		/** @type {HTMLFormElement} Form element being validated */
		this.form = form;
		/** @type {Object} Map of field names to error messages */
		this.errors = {};
		this.init();
	}

	/**
	 * Initialize validation listeners
	 * @private
	 */
	init() {
		// Add validation listeners to all inputs
		const inputs = this.form.querySelectorAll('input[type="text"], input[type="email"]');
		inputs.forEach(input => {
			// Validate on blur
			input.addEventListener('blur', () => this.validateField(input));
			// Clear errors on input
			input.addEventListener('input', () => this.clearFieldError(input));
		});

		// Validate on submit
		this.form.addEventListener('submit', (e) => {
			if (!this.validateForm()) {
				e.preventDefault();
				return false;
			}
		});
	}

	/**
	 * Validate a single form field
	 * @param {HTMLInputElement} field - Input field to validate
	 * @returns {boolean} True if field is valid, false otherwise
	 */
	validateField(field) {
		const fieldName = field.name || field.id;
		let isValid = true;
		let errorMessage = '';

		// Remove existing error styling
		this.clearFieldError(field);

		// Required field check
		if (field.hasAttribute('required') && !field.value.trim()) {
			isValid = false;
			errorMessage = 'This field is required';
		}

		// Email validation
		if (field.type === 'email' && field.value.trim()) {
			const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
			if (!emailRegex.test(field.value)) {
				isValid = false;
				errorMessage = 'Please enter a valid email address';
			}
		}

		// Birth date validation
		if (fieldName === 'birthDate' && field.value.trim()) {
			const dateRegex = /^\d{2}\/\d{2}\/\d{4}$/;
			if (!dateRegex.test(field.value)) {
				isValid = false;
				errorMessage = 'Please enter date in MM/DD/YYYY format';
			} else {
				const [month, day, year] = field.value.split('/').map(Number);
				if (month < 1 || month > 12 || day < 1 || day > 31 || year < 1900 || year > new Date().getFullYear()) {
					isValid = false;
					errorMessage = 'Please enter a valid date';
				}
			}
		}

		// Birth time validation
		if (fieldName === 'birthTime' && field.value.trim()) {
			const timeRegex = /^(\d{1,2}):(\d{2})\s*(AM|PM)$/i;
			if (!timeRegex.test(field.value)) {
				isValid = false;
				errorMessage = 'Please enter time in HH:MM AM/PM format';
			} else {
				const match = field.value.match(timeRegex);
				const hour = parseInt(match[1]);
				const minute = parseInt(match[2]);
				if (hour < 1 || hour > 12 || minute < 0 || minute > 59) {
					isValid = false;
					errorMessage = 'Please enter a valid time';
				}
			}
		}

		// Location validation (basic check)
		if (fieldName === 'location' && field.value.trim()) {
			if (field.value.length < 3) {
				isValid = false;
				errorMessage = 'Please enter a more specific location';
			}
		}

		if (!isValid) {
			this.showFieldError(field, errorMessage);
			this.errors[fieldName] = errorMessage;
		} else {
			delete this.errors[fieldName];
		}

		return isValid;
	}

	/**
	 * Validate entire form
	 * @returns {boolean} True if form is valid, false otherwise
	 */
	validateForm() {
		const inputs = this.form.querySelectorAll('input[type="text"], input[type="email"]');
		let isValid = true;

		inputs.forEach(input => {
			if (!this.validateField(input)) {
				isValid = false;
			}
		});

		// Check terms checkbox
		const termsCheckbox = this.form.querySelector('[name="terms"]');
		if (termsCheckbox && !termsCheckbox.checked) {
			isValid = false;
			const termsError = document.getElementById('termsError');
			if (termsError) {
				termsError.style.display = 'block';
			}
		}

		return isValid;
	}

	/**
	 * Display error message for a field
	 * @private
	 * @param {HTMLInputElement} field - Field with error
	 * @param {string} message - Error message to display
	 */
	showFieldError(field, message) {
		// Add error class
		field.classList.add('field-error');
		
		// Create or update error message
		let errorElement = field.parentElement.querySelector('.field-error-message');
		if (!errorElement) {
			errorElement = document.createElement('span');
			errorElement.className = 'field-error-message';
			field.parentElement.appendChild(errorElement);
		}
		errorElement.textContent = message;
		errorElement.setAttribute('role', 'alert');
		errorElement.setAttribute('aria-live', 'polite');
	}

	/**
	 * Clear error message for a field
	 * @private
	 * @param {HTMLInputElement} field - Field to clear error for
	 */
	clearFieldError(field) {
		field.classList.remove('field-error');
		const errorElement = field.parentElement.querySelector('.field-error-message');
		if (errorElement) {
			errorElement.remove();
		}
		delete this.errors[field.name || field.id];
	}

	/**
	 * Get all current validation errors
	 * @returns {Object} Map of field names to error messages
	 */
	getErrors() {
		return { ...this.errors };
	}

	/**
	 * Check if form has any validation errors
	 * @returns {boolean} True if errors exist, false otherwise
	 */
	hasErrors() {
		return Object.keys(this.errors).length > 0;
	}
}

