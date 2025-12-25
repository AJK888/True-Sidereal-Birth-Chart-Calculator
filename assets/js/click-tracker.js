/**
 * Click Tracker - Logs all user clicks for debugging
 * Sends click events to backend API for logging
 */

const ClickTracker = {
    API_BASE: "https://true-sidereal-api.onrender.com",
    enabled: true,
    queue: [],
    batchSize: 10,
    flushInterval: 5000, // 5 seconds
    flushTimer: null,

    init() {
        if (!this.enabled) return;
        
        // Start periodic flush
        this.startFlushTimer();
        
        // Flush on page unload
        window.addEventListener('beforeunload', () => {
            this.flush(true); // Force immediate flush
        });
        
        // Track all clicks
        document.addEventListener('click', (e) => {
            this.trackClick(e);
        }, true); // Use capture phase to catch all clicks
        
        console.log('[ClickTracker] Initialized - tracking all clicks');
    },

    trackClick(event) {
        if (!this.enabled) return;
        
        try {
            const target = event.target;
            const element = {
                tag: target.tagName,
                id: target.id || null,
                className: target.className || null,
                text: target.textContent?.trim().substring(0, 100) || null,
                href: target.href || (target.closest('a')?.href) || null,
                type: target.type || null,
                name: target.name || null,
                value: target.value || null,
                dataset: this.extractDataset(target),
                ariaLabel: target.getAttribute('aria-label') || null,
                role: target.getAttribute('role') || null,
            };

            // Get parent context
            const parent = target.parentElement;
            const parentInfo = parent ? {
                tag: parent.tagName,
                id: parent.id || null,
                className: parent.className || null,
            } : null;

            // Get page context
            const pageInfo = {
                url: window.location.href,
                pathname: window.location.pathname,
                search: window.location.search,
                hash: window.location.hash,
                title: document.title,
                referrer: document.referrer || null,
            };

            // Get user context if available
            const userInfo = this.getUserInfo();

            // Get viewport info
            const viewportInfo = {
                width: window.innerWidth,
                height: window.innerHeight,
                scrollX: window.scrollX,
                scrollY: window.scrollY,
            };

            const clickData = {
                timestamp: new Date().toISOString(),
                element: element,
                parent: parentInfo,
                page: pageInfo,
                user: userInfo,
                viewport: viewportInfo,
                event: {
                    button: event.button,
                    ctrlKey: event.ctrlKey,
                    shiftKey: event.shiftKey,
                    altKey: event.altKey,
                    metaKey: event.metaKey,
                }
            };

            this.queue.push(clickData);

            // Flush if queue is full
            if (this.queue.length >= this.batchSize) {
                this.flush();
            }
        } catch (error) {
            console.error('[ClickTracker] Error tracking click:', error);
        }
    },

    extractDataset(element) {
        const dataset = {};
        if (element.dataset) {
            for (const key in element.dataset) {
                dataset[key] = element.dataset[key];
            }
        }
        return Object.keys(dataset).length > 0 ? dataset : null;
    },

    getUserInfo() {
        try {
            // Try to get user info from AuthManager if available
            if (window.AuthManager && typeof window.AuthManager.isLoggedIn === 'function') {
                const isLoggedIn = window.AuthManager.isLoggedIn();
                if (isLoggedIn) {
                    const userEmail = window.AuthManager.getUserEmail?.() || null;
                    return {
                        loggedIn: true,
                        email: userEmail,
                    };
                }
            }
            return { loggedIn: false };
        } catch (error) {
            return { loggedIn: false, error: error.message };
        }
    },

    startFlushTimer() {
        if (this.flushTimer) {
            clearInterval(this.flushTimer);
        }
        this.flushTimer = setInterval(() => {
            if (this.queue.length > 0) {
                this.flush();
            }
        }, this.flushInterval);
    },

    async flush(immediate = false) {
        if (this.queue.length === 0) return;

        const batch = [...this.queue];
        this.queue = [];

        try {
            const response = await fetch(`${this.API_BASE}/api/log-clicks`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    clicks: batch,
                    page: window.location.pathname,
                    timestamp: new Date().toISOString(),
                }),
                // Don't wait for response if not immediate (fire and forget)
                ...(immediate ? {} : { keepalive: true })
            });

            if (!response.ok) {
                console.warn('[ClickTracker] Failed to log clicks:', response.status);
                // Re-queue if failed (but limit queue size)
                if (this.queue.length < 100) {
                    this.queue.unshift(...batch);
                }
            } else {
                console.log(`[ClickTracker] Logged ${batch.length} clicks`);
            }
        } catch (error) {
            console.error('[ClickTracker] Error flushing clicks:', error);
            // Re-queue if failed (but limit queue size)
            if (this.queue.length < 100) {
                this.queue.unshift(...batch);
            }
        }
    },

    // Manual flush for testing
    forceFlush() {
        this.flush(true);
    },

    // Disable tracking
    disable() {
        this.enabled = false;
        if (this.flushTimer) {
            clearInterval(this.flushTimer);
            this.flushTimer = null;
        }
    },

    // Enable tracking
    enable() {
        this.enabled = true;
        this.startFlushTimer();
    }
};

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => ClickTracker.init());
} else {
    ClickTracker.init();
}

// Make available globally for debugging
window.ClickTracker = ClickTracker;

