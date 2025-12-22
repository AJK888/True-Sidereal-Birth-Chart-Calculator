/**
 * Testing Helper Utilities
 * Utilities for testing and validation during development
 * 
 * @module test-helpers
 * @description Provides helper functions for manual testing, validation,
 * and debugging. Can be used in browser console or automated tests.
 */

/**
 * Test Helpers class
 * @class TestHelpers
 */
class TestHelpers {
	constructor() {
		this.testResults = [];
	}

	/**
	 * Run accessibility audit and log results
	 * @returns {Object} Audit results
	 */
	runAccessibilityAudit() {
		if (typeof accessibilityHelper === 'undefined') {
			console.warn('Accessibility helper not available');
			return null;
		}

		const audit = accessibilityHelper.runAudit();
		console.group('🔍 Accessibility Audit Results');
		
		if (audit.missingAltText.length > 0) {
			console.warn(`❌ ${audit.missingAltText.length} images missing alt text:`, audit.missingAltText);
		} else {
			console.log('✅ All images have alt text');
		}

		if (audit.missingLabels.length > 0) {
			console.warn(`❌ ${audit.missingLabels.length} form inputs missing labels:`, audit.missingLabels);
		} else {
			console.log('✅ All form inputs have labels');
		}

		if (audit.missingAriaLabels.length > 0) {
			console.warn(`❌ ${audit.missingAriaLabels.length} interactive elements missing aria labels:`, audit.missingAriaLabels);
		} else {
			console.log('✅ All interactive elements have aria labels');
		}

		console.groupEnd();
		return audit;
	}

	/**
	 * Test form validation
	 * @returns {boolean} True if form validation works
	 */
	testFormValidation() {
		const form = document.getElementById('chartForm');
		if (!form) {
			console.error('Form not found');
			return false;
		}

		console.group('🧪 Testing Form Validation');
		
		// Test required fields
		const requiredFields = form.querySelectorAll('[required]');
		let allValid = true;

		requiredFields.forEach(field => {
			const originalValue = field.value;
			field.value = '';
			
			if (typeof FormValidator !== 'undefined' && window.AstrologyCalculator?.formValidator) {
				const isValid = window.AstrologyCalculator.formValidator.validateField(field);
				if (isValid) {
					console.warn(`❌ ${field.name || field.id} should be invalid when empty`);
					allValid = false;
				} else {
					console.log(`✅ ${field.name || field.id} correctly validates as required`);
				}
			}
			
			field.value = originalValue;
		});

		console.groupEnd();
		return allValid;
	}

	/**
	 * Test API client connectivity
	 * @returns {Promise<boolean>} True if API is reachable
	 */
	async testAPIConnectivity() {
		if (typeof apiClient === 'undefined') {
			console.error('API client not available');
			return false;
		}

		console.group('🌐 Testing API Connectivity');
		
		try {
			// Test with a simple request (health check if available)
			const response = await fetch('https://true-sidereal-api.onrender.com/');
			console.log(`✅ API reachable: ${response.status} ${response.statusText}`);
			console.groupEnd();
			return true;
		} catch (error) {
			console.error('❌ API connectivity test failed:', error);
			console.groupEnd();
			return false;
		}
	}

	/**
	 * Test performance metrics
	 * @returns {Object} Performance metrics
	 */
	getPerformanceMetrics() {
		if (typeof performanceMonitor === 'undefined') {
			console.warn('Performance monitor not available');
			return null;
		}

		const metrics = performanceMonitor.getMetrics();
		console.group('⚡ Performance Metrics');
		console.table(metrics);
		console.groupEnd();
		return metrics;
	}

	/**
	 * Test keyboard navigation
	 * @returns {boolean} True if keyboard nav works
	 */
	testKeyboardNavigation() {
		console.group('⌨️ Testing Keyboard Navigation');
		
		const interactiveElements = document.querySelectorAll(
			'a, button, input, textarea, select, [tabindex]:not([tabindex="-1"])'
		);

		let allAccessible = true;
		interactiveElements.forEach((el, index) => {
			if (index === 0) el.focus();
			
			const isAccessible = accessibilityHelper?.isKeyboardAccessible(el) ?? true;
			if (!isAccessible) {
				console.warn(`❌ ${el.tagName} (${el.id || el.className}) not keyboard accessible`);
				allAccessible = false;
			}
		});

		if (allAccessible) {
			console.log(`✅ All ${interactiveElements.length} interactive elements are keyboard accessible`);
		}

		console.groupEnd();
		return allAccessible;
	}

	/**
	 * Validate design tokens are loaded
	 * @returns {boolean} True if tokens are available
	 */
	validateDesignTokens() {
		console.group('🎨 Validating Design Tokens');
		
		const requiredTokens = [
			'--color-primary',
			'--spacing-md',
			'--font-size-base',
			'--border-radius-md',
			'--transition-base'
		];

		let allPresent = true;
		requiredTokens.forEach(token => {
			const value = getComputedStyle(document.documentElement).getPropertyValue(token);
			if (!value || value.trim() === '') {
				console.warn(`❌ Design token ${token} not found`);
				allPresent = false;
			} else {
				console.log(`✅ ${token}: ${value.trim()}`);
			}
		});

		console.groupEnd();
		return allPresent;
	}

	/**
	 * Run all tests
	 * @returns {Object} Test results summary
	 */
	async runAllTests() {
		console.group('🧪 Running All Tests');
		
		const results = {
			accessibility: this.runAccessibilityAudit(),
			formValidation: this.testFormValidation(),
			apiConnectivity: await this.testAPIConnectivity(),
			performance: this.getPerformanceMetrics(),
			keyboardNav: this.testKeyboardNavigation(),
			designTokens: this.validateDesignTokens()
		};

		const passed = Object.values(results).filter(r => r === true || (r && !Array.isArray(r))).length;
		const total = Object.keys(results).length;

		console.log(`\n📊 Test Summary: ${passed}/${total} tests passed`);
		console.groupEnd();

		return results;
	}

	/**
	 * Check for console errors
	 * @returns {Array} List of errors found
	 */
	checkConsoleErrors() {
		// This would need to be set up before page load
		// For now, just check if error tracker has errors
		if (typeof errorTracker !== 'undefined') {
			const stats = errorTracker.getStats();
			console.log('Error Tracker Stats:', stats);
			return stats;
		}
		return null;
	}

	/**
	 * Validate HTML structure
	 * @returns {Object} Validation results
	 */
	validateHTMLStructure() {
		console.group('📋 Validating HTML Structure');
		
		const checks = {
			hasMainContent: !!document.querySelector('main, #main'),
			hasHeader: !!document.querySelector('header, #header'),
			hasFooter: !!document.querySelector('footer, #footer'),
			hasForm: !!document.getElementById('chartForm'),
			hasResults: !!document.getElementById('results'),
			allImagesHaveAlt: Array.from(document.querySelectorAll('img')).every(img => img.alt || img.getAttribute('aria-hidden')),
			allInputsHaveLabels: Array.from(document.querySelectorAll('input, textarea, select')).every(input => {
				return input.labels?.length > 0 || input.getAttribute('aria-label') || input.getAttribute('aria-labelledby');
			})
		};

		Object.entries(checks).forEach(([check, passed]) => {
			console.log(`${passed ? '✅' : '❌'} ${check}: ${passed}`);
		});

		console.groupEnd();
		return checks;
	}
}

/**
 * Singleton test helpers instance
 * @type {TestHelpers}
 */
const testHelpers = new TestHelpers();

// Make available globally for console access
if (typeof window !== 'undefined') {
	window.testHelpers = testHelpers;
	
	// Add convenience function
	window.runTests = () => testHelpers.runAllTests();
}

