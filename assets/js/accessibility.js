/**
 * Accessibility Helper Utilities
 * Utilities for improving and testing accessibility
 * 
 * @module accessibility
 * @description Provides helpers for keyboard navigation, focus management,
 * screen reader announcements, and accessibility testing.
 */

/**
 * Accessibility Helper class
 * @class AccessibilityHelper
 */
class AccessibilityHelper {
	constructor() {
		this.announcements = [];
		this.focusHistory = [];
		this.maxFocusHistory = 10;
	}

	/**
	 * Announce message to screen readers
	 * @param {string} message - Message to announce
	 * @param {string} [priority='polite'] - Priority: 'polite' or 'assertive'
	 */
	announce(message, priority = 'polite') {
		const announcement = document.createElement('div');
		announcement.setAttribute('role', 'status');
		announcement.setAttribute('aria-live', priority);
		announcement.setAttribute('aria-atomic', 'true');
		announcement.className = 'sr-only';
		announcement.textContent = message;
		
		document.body.appendChild(announcement);
		
		// Remove after announcement
		setTimeout(() => {
			document.body.removeChild(announcement);
		}, 1000);
		
		this.announcements.push({ message, priority, timestamp: Date.now() });
	}

	/**
	 * Trap focus within an element (for modals)
	 * @param {HTMLElement} container - Container element
	 * @returns {Function} Function to remove focus trap
	 */
	trapFocus(container) {
		const focusableElements = container.querySelectorAll(
			'a[href], button:not([disabled]), textarea:not([disabled]), ' +
			'input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'
		);
		
		const firstElement = focusableElements[0];
		const lastElement = focusableElements[focusableElements.length - 1];
		
		const handleTab = (e) => {
			if (e.key !== 'Tab') return;
			
			if (e.shiftKey) {
				if (document.activeElement === firstElement) {
					e.preventDefault();
					lastElement.focus();
				}
			} else {
				if (document.activeElement === lastElement) {
					e.preventDefault();
					firstElement.focus();
				}
			}
		};
		
		container.addEventListener('keydown', handleTab);
		
		// Focus first element
		if (firstElement) {
			firstElement.focus();
		}
		
		// Return cleanup function
		return () => {
			container.removeEventListener('keydown', handleTab);
		};
	}

	/**
	 * Track focus for keyboard navigation debugging
	 * @param {HTMLElement} element - Element that received focus
	 */
	trackFocus(element) {
		this.focusHistory.push({
			element: element.tagName,
			id: element.id,
			className: element.className,
			timestamp: Date.now()
		});
		
		// Keep only recent history
		if (this.focusHistory.length > this.maxFocusHistory) {
			this.focusHistory.shift();
		}
	}

	/**
	 * Check if element is keyboard accessible
	 * @param {HTMLElement} element - Element to check
	 * @returns {boolean} True if keyboard accessible
	 */
	isKeyboardAccessible(element) {
		if (!element) return false;
		
		// Check if element is focusable
		const isFocusable = element.tabIndex >= 0 || 
			element.tagName === 'A' ||
			element.tagName === 'BUTTON' ||
			element.tagName === 'INPUT' ||
			element.tagName === 'TEXTAREA' ||
			element.tagName === 'SELECT';
		
		// Check if disabled
		const isDisabled = element.hasAttribute('disabled') || 
			element.getAttribute('aria-disabled') === 'true';
		
		return isFocusable && !isDisabled;
	}

	/**
	 * Ensure element has accessible name
	 * @param {HTMLElement} element - Element to check
	 * @returns {boolean} True if has accessible name
	 */
	hasAccessibleName(element) {
		if (!element) return false;
		
		// Check for aria-label
		if (element.getAttribute('aria-label')) return true;
		
		// Check for aria-labelledby
		if (element.getAttribute('aria-labelledby')) return true;
		
		// Check for associated label
		if (element.id) {
			const label = document.querySelector(`label[for="${element.id}"]`);
			if (label && label.textContent.trim()) return true;
		}
		
		// Check for text content (for buttons, links)
		if (['BUTTON', 'A'].includes(element.tagName)) {
			if (element.textContent.trim()) return true;
		}
		
		// Check for title attribute
		if (element.getAttribute('title')) return true;
		
		return false;
	}

	/**
	 * Check color contrast ratio (basic check)
	 * @param {string} foreground - Foreground color
	 * @param {string} background - Background color
	 * @returns {number} Contrast ratio
	 */
	getContrastRatio(foreground, background) {
		// This is a simplified version - for production, use a proper library
		const fg = this.hexToRgb(foreground);
		const bg = this.hexToRgb(background);
		
		if (!fg || !bg) return 0;
		
		const getLuminance = (r, g, b) => {
			const [rs, gs, bs] = [r, g, b].map(val => {
				val = val / 255;
				return val <= 0.03928 ? val / 12.92 : Math.pow((val + 0.055) / 1.055, 2.4);
			});
			return 0.2126 * rs + 0.7152 * gs + 0.0722 * bs;
		};
		
		const l1 = getLuminance(fg.r, fg.g, fg.b);
		const l2 = getLuminance(bg.r, bg.g, bg.b);
		
		const lighter = Math.max(l1, l2);
		const darker = Math.min(l1, l2);
		
		return (lighter + 0.05) / (darker + 0.05);
	}

	/**
	 * Convert hex color to RGB
	 * @private
	 * @param {string} hex - Hex color string
	 * @returns {Object|null} RGB object or null
	 */
	hexToRgb(hex) {
		const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
		return result ? {
			r: parseInt(result[1], 16),
			g: parseInt(result[2], 16),
			b: parseInt(result[3], 16)
		} : null;
	}

	/**
	 * Run basic accessibility audit
	 * @returns {Object} Audit results
	 */
	runAudit() {
		const results = {
			missingAltText: [],
			missingLabels: [],
			lowContrast: [],
			keyboardTraps: [],
			missingAriaLabels: []
		};
		
		// Check images without alt text
		const images = document.querySelectorAll('img');
		images.forEach(img => {
			if (!img.alt && !img.getAttribute('aria-hidden')) {
				results.missingAltText.push(img);
			}
		});
		
		// Check form inputs without labels
		const inputs = document.querySelectorAll('input, textarea, select');
		inputs.forEach(input => {
			if (!this.hasAccessibleName(input)) {
				results.missingLabels.push(input);
			}
		});
		
		// Check interactive elements without aria labels
		const interactive = document.querySelectorAll('button, a');
		interactive.forEach(el => {
			if (!this.hasAccessibleName(el) && !el.getAttribute('aria-hidden')) {
				results.missingAriaLabels.push(el);
			}
		});
		
		return results;
	}
}

/**
 * Singleton accessibility helper instance
 * @type {AccessibilityHelper}
 */
const accessibilityHelper = new AccessibilityHelper();

// Auto-initialize focus tracking
if (typeof window !== 'undefined') {
	document.addEventListener('focusin', (e) => {
		accessibilityHelper.trackFocus(e.target);
	}, true);
}

// Make available globally
if (typeof window !== 'undefined') {
	window.accessibilityHelper = accessibilityHelper;
}

