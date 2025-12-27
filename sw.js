/**
 * Service Worker for Synthesis Astrology
 * Provides offline support and caching
 * 
 * @version 1.0.0
 */

// Bump versions to ensure clients receive updated JS/CSS promptly.
const CACHE_NAME = 'synthesis-astrology-v2';
const RUNTIME_CACHE = 'synthesis-astrology-runtime-v2';

// Assets to cache on install
const PRECACHE_ASSETS = [
	'/',
	'/index.html',
	'/assets/css/main.css',
	'/assets/css/design-tokens.css',
	'/assets/css/custom.css',
	'/assets/css/fontawesome-all.min.css',
	'/assets/js/utils.js',
	'/assets/js/state-manager.js',
	'/assets/js/api-client.js',
	'/assets/js/form-validator.js',
	'/assets/js/calculator.js',
	'/images/star-background.jpg'
];

// Install event - cache assets
self.addEventListener('install', (event) => {
	console.log('[SW] Installing service worker...');
	
	event.waitUntil(
		caches.open(CACHE_NAME)
			.then((cache) => {
				console.log('[SW] Caching assets');
				return cache.addAll(PRECACHE_ASSETS);
			})
			.then(() => {
				console.log('[SW] Service worker installed');
				return self.skipWaiting(); // Activate immediately
			})
			.catch((error) => {
				console.error('[SW] Cache install failed:', error);
			})
	);
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
	console.log('[SW] Activating service worker...');
	
	event.waitUntil(
		caches.keys()
			.then((cacheNames) => {
				return Promise.all(
					cacheNames
						.filter((cacheName) => {
							// Delete old caches
							return cacheName !== CACHE_NAME && 
							       cacheName !== RUNTIME_CACHE;
						})
						.map((cacheName) => {
							console.log('[SW] Deleting old cache:', cacheName);
							return caches.delete(cacheName);
						})
				);
			})
			.then(() => {
				console.log('[SW] Service worker activated');
				return self.clients.claim(); // Take control immediately
			})
	);
});

// Fetch event - serve from cache, fallback to network
self.addEventListener('fetch', (event) => {
	// Skip non-GET requests
	if (event.request.method !== 'GET') {
		return;
	}

	// Skip API requests (always use network)
	if (event.request.url.includes('/api/') || 
	    event.request.url.includes('true-sidereal-api.onrender.com')) {
		return;
	}

	// Skip external resources
	if (!event.request.url.startsWith(self.location.origin)) {
		return;
	}

	event.respondWith(
		caches.match(event.request)
			.then((cachedResponse) => {
				// Return cached version if available
				if (cachedResponse) {
					return cachedResponse;
				}

				// Otherwise fetch from network
				return fetch(event.request)
					.then((response) => {
						// Don't cache non-successful responses
						if (!response || response.status !== 200 || response.type !== 'basic') {
							return response;
						}

						// Clone the response
						const responseToCache = response.clone();

						// Cache the response
						caches.open(RUNTIME_CACHE)
							.then((cache) => {
								cache.put(event.request, responseToCache);
							});

						return response;
					})
					.catch((error) => {
						console.error('[SW] Fetch failed:', error);
						
						// Return offline page if available
						if (event.request.destination === 'document') {
							return caches.match('/index.html');
						}
					});
			})
	);
});

// Message event - handle messages from client
self.addEventListener('message', (event) => {
	if (event.data && event.data.type === 'SKIP_WAITING') {
		self.skipWaiting();
	}
	
	if (event.data && event.data.type === 'CACHE_URLS') {
		event.waitUntil(
			caches.open(CACHE_NAME)
				.then((cache) => {
					return cache.addAll(event.data.urls);
				})
		);
	}
});

