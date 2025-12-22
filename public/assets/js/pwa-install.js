/**
 * PWA Install Prompt Handler
 * Handles "Add to Home Screen" prompts and installation
 * 
 * @module pwa-install
 */

/**
 * PWA Install Manager
 * @class PWAInstall
 */
class PWAInstall {
	constructor() {
		this.deferredPrompt = null;
		this.installButton = null;
		this.isInstalled = this.checkIfInstalled();
		
		this.init();
	}

	/**
	 * Initialize PWA install functionality
	 */
	init() {
		// Check if already installed
		if (this.isInstalled) {
			return;
		}

		// Listen for beforeinstallprompt event
		window.addEventListener('beforeinstallprompt', (e) => {
			e.preventDefault();
			this.deferredPrompt = e;
			this.showInstallButton();
		});

		// Listen for app installed event
		window.addEventListener('appinstalled', () => {
			console.log('PWA installed');
			this.isInstalled = true;
			this.hideInstallButton();
			this.deferredPrompt = null;
		});

		// Check if running as standalone (already installed)
		if (window.matchMedia('(display-mode: standalone)').matches) {
			this.isInstalled = true;
		}
	}

	/**
	 * Check if app is already installed
	 * @returns {boolean} True if installed
	 */
	checkIfInstalled() {
		// Check if running in standalone mode
		if (window.matchMedia('(display-mode: standalone)').matches) {
			return true;
		}

		// Check if running from home screen (iOS)
		if (window.navigator.standalone === true) {
			return true;
		}

		return false;
	}

	/**
	 * Show install button
	 */
	showInstallButton() {
		// Create install button if it doesn't exist
		if (!this.installButton) {
			this.installButton = document.createElement('button');
			this.installButton.className = 'pwa-install-button';
			this.installButton.innerHTML = '<i class="fas fa-download"></i> Install App';
			this.installButton.setAttribute('aria-label', 'Install Synthesis Astrology app');
			this.installButton.addEventListener('click', () => this.promptInstall());
			
			// Add to header or appropriate location
			const header = document.getElementById('header');
			if (header) {
				header.appendChild(this.installButton);
			}
		}

		this.installButton.style.display = 'block';
	}

	/**
	 * Hide install button
	 */
	hideInstallButton() {
		if (this.installButton) {
			this.installButton.style.display = 'none';
		}
	}

	/**
	 * Prompt user to install PWA
	 */
	async promptInstall() {
		if (!this.deferredPrompt) {
			return;
		}

		// Show the install prompt
		this.deferredPrompt.prompt();

		// Wait for user response
		const { outcome } = await this.deferredPrompt.userChoice;

		if (outcome === 'accepted') {
			console.log('User accepted install prompt');
		} else {
			console.log('User dismissed install prompt');
		}

		this.deferredPrompt = null;
		this.hideInstallButton();
	}

	/**
	 * Get installation status
	 * @returns {Object} Installation status
	 */
	getStatus() {
		return {
			isInstalled: this.isInstalled,
			canInstall: !!this.deferredPrompt,
			isStandalone: window.matchMedia('(display-mode: standalone)').matches
		};
	}
}

// Initialize PWA install manager
let pwaInstall;

if (typeof window !== 'undefined') {
	pwaInstall = new PWAInstall();
	window.pwaInstall = pwaInstall;
}

