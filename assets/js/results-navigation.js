/**
 * Results Navigation Module
 * Handles progressive disclosure and smooth scrolling for results sections
 * 
 * @module results-navigation
 * @description Provides navigation between result sections with smooth scrolling,
 * progressive disclosure, and section highlighting.
 */

/**
 * Results Navigation class
 * @class ResultsNavigation
 */
class ResultsNavigation {
	constructor() {
		this.sections = [];
		this.currentSection = null;
		this.navItems = [];
		this.init();
	}

	/**
	 * Initialize results navigation
	 */
	init() {
		// Wait for results container to be available
		if (document.getElementById('results')) {
			this.setupNavigation();
		} else {
			// Wait for results to be created
			const observer = new MutationObserver(() => {
				if (document.getElementById('results')) {
					this.setupNavigation();
					observer.disconnect();
				}
			});
			observer.observe(document.body, { childList: true, subtree: true });
		}
	}

	/**
	 * Setup navigation for results sections
	 */
	setupNavigation() {
		const resultsContainer = document.getElementById('results');
		if (!resultsContainer) return;

		// Find all result sections
		this.sections = Array.from(resultsContainer.querySelectorAll('.result-section'));
		
		// Create navigation menu if sections exist
		if (this.sections.length > 0) {
			this.createNavigationMenu();
			this.setupScrollSpy();
			this.setupSmoothScrolling();
		}
	}

	/**
	 * Create navigation menu for result sections
	 */
	createNavigationMenu() {
		// Check if nav already exists
		if (document.getElementById('results-nav')) return;

		const nav = document.createElement('nav');
		nav.id = 'results-nav';
		nav.className = 'results-nav';
		nav.setAttribute('aria-label', 'Results navigation');
		
		const ul = document.createElement('ul');
		ul.className = 'results-nav-list';

		this.sections.forEach((section, index) => {
			const header = section.querySelector('h2');
			if (!header) return;

			const sectionId = section.id || `result-section-${index}`;
			if (!section.id) section.id = sectionId;

			const li = document.createElement('li');
			const a = document.createElement('a');
			a.href = `#${sectionId}`;
			a.textContent = header.textContent.trim();
			a.className = 'results-nav-link';
			a.setAttribute('aria-label', `Jump to ${header.textContent.trim()}`);
			
			a.addEventListener('click', (e) => {
				e.preventDefault();
				this.scrollToSection(sectionId);
			});

			li.appendChild(a);
			ul.appendChild(li);
			this.navItems.push({ element: a, section });
		});

		nav.appendChild(ul);
		
		// Insert before results container
		const resultsContainer = document.getElementById('results');
		if (resultsContainer && resultsContainer.parentElement) {
			resultsContainer.parentElement.insertBefore(nav, resultsContainer);
		}
	}

	/**
	 * Setup scroll spy to highlight current section
	 */
	setupScrollSpy() {
		const observerOptions = {
			root: null,
			rootMargin: '-20% 0px -70% 0px',
			threshold: 0
		};

		const observer = new IntersectionObserver((entries) => {
			entries.forEach(entry => {
				if (entry.isIntersecting) {
					const sectionId = entry.target.id;
					this.highlightSection(sectionId);
				}
			});
		}, observerOptions);

		this.sections.forEach(section => {
			observer.observe(section);
		});
	}

	/**
	 * Highlight current section in navigation
	 * @param {string} sectionId - ID of section to highlight
	 */
	highlightSection(sectionId) {
		this.navItems.forEach(item => {
			const isActive = item.section.id === sectionId;
			item.element.classList.toggle('active', isActive);
			item.element.setAttribute('aria-current', isActive ? 'true' : 'false');
		});
		this.currentSection = sectionId;
	}

	/**
	 * Scroll to specific section
	 * @param {string} sectionId - ID of section to scroll to
	 */
	scrollToSection(sectionId) {
		const section = document.getElementById(sectionId);
		if (!section) return;

		// Use utility if available, otherwise native scroll
		if (typeof Utils !== 'undefined' && Utils.dom) {
			Utils.dom.scrollTo(section, { behavior: 'smooth', block: 'start' });
		} else {
			section.scrollIntoView({ behavior: 'smooth', block: 'start' });
		}

		// Announce to screen readers
		if (typeof accessibilityHelper !== 'undefined') {
			const header = section.querySelector('h2');
			if (header) {
				accessibilityHelper.announce(`Navigated to ${header.textContent.trim()}`);
			}
		}
	}

	/**
	 * Setup smooth scrolling for anchor links
	 */
	setupSmoothScrolling() {
		// Handle anchor links within results
		document.querySelectorAll('#results a[href^="#"]').forEach(link => {
			link.addEventListener('click', (e) => {
				const href = link.getAttribute('href');
				if (href && href.startsWith('#')) {
					const targetId = href.substring(1);
					const target = document.getElementById(targetId);
					if (target && target.closest('#results')) {
						e.preventDefault();
						this.scrollToSection(targetId);
					}
				}
			});
		});
	}

	/**
	 * Show/hide navigation based on scroll position
	 */
	updateNavigationVisibility() {
		const nav = document.getElementById('results-nav');
		const resultsContainer = document.getElementById('results');
		
		if (!nav || !resultsContainer) return;

		const resultsRect = resultsContainer.getBoundingClientRect();
		const isVisible = resultsRect.top < window.innerHeight && resultsRect.bottom > 0;
		
		nav.classList.toggle('visible', isVisible);
	}
}

/**
 * Initialize results navigation when results are displayed
 */
function initResultsNavigation() {
	// Wait for results to be shown
	const checkForResults = setInterval(() => {
		const resultsContainer = document.getElementById('results');
		if (resultsContainer && resultsContainer.style.display !== 'none') {
			if (!window.resultsNavigation) {
				window.resultsNavigation = new ResultsNavigation();
			}
			clearInterval(checkForResults);
		}
	}, 500);

	// Cleanup after 30 seconds
	setTimeout(() => clearInterval(checkForResults), 30000);
}

// Auto-initialize
if (typeof window !== 'undefined') {
	if (document.readyState === 'loading') {
		document.addEventListener('DOMContentLoaded', initResultsNavigation);
	} else {
		initResultsNavigation();
	}

	// Update nav visibility on scroll
	window.addEventListener('scroll', () => {
		if (window.resultsNavigation) {
			window.resultsNavigation.updateNavigationVisibility();
		}
	}, { passive: true });
}

