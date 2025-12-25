/*
	Forty by HTML5 UP
	html5up.net | @ajlkn
	Free for personal and commercial use under the CCA 3.0 license (html5up.net/license)
*/

// CRITICAL: Menu handler - MUST run immediately, before everything else
// SINGLE CONSOLIDATED HANDLER - no duplicates
(function() {
	var menuHandlerAttached = false;
	var outsideClickHandlerAttached = false;
	
	// CRITICAL: Prevent hash from ever being added to URL
	// Intercept all hash changes
	window.addEventListener('hashchange', function(event) {
		if (window.location.hash === '#menu') {
			event.preventDefault();
			event.stopImmediatePropagation();
			var cleanUrl = window.location.href.split('#')[0];
			window.history.replaceState(null, null, cleanUrl);
			return false;
		}
	}, true);
	
	// Override history methods to strip #menu
	var originalPushState = history.pushState;
	history.pushState = function() {
		if (arguments[2] && typeof arguments[2] === 'string' && arguments[2].includes('#menu')) {
			arguments[2] = arguments[2].split('#')[0];
		}
		return originalPushState.apply(history, arguments);
	};
	
	var originalReplaceState = history.replaceState;
	history.replaceState = function() {
		if (arguments[2] && typeof arguments[2] === 'string' && arguments[2].includes('#menu')) {
			arguments[2] = arguments[2].split('#')[0];
		}
		return originalReplaceState.apply(history, arguments);
	};
	
	// Remove hash on page load - run immediately and aggressively
	(function removeMenuHash() {
		if (window.location.hash === '#menu' || window.location.hash === '#menu') {
			var cleanUrl = window.location.pathname + window.location.search;
			window.history.replaceState(null, null, cleanUrl);
			// Also prevent menu from opening if body class was set
			if (document.body && document.body.classList.contains('is-menu-visible')) {
				document.body.classList.remove('is-menu-visible');
			}
		}
	})();
	
	// Also remove hash after DOM is ready (in case it was added by theme scripts)
	if (document.readyState === 'loading') {
		document.addEventListener('DOMContentLoaded', function() {
			if (window.location.hash === '#menu') {
				window.history.replaceState(null, null, window.location.pathname + window.location.search);
				if (document.body && document.body.classList.contains('is-menu-visible')) {
					document.body.classList.remove('is-menu-visible');
				}
			}
		});
	}
	
	// Continuous monitoring to catch any hash additions (runs every 100ms for first 2 seconds)
	var hashCheckCount = 0;
	var hashCheckInterval = setInterval(function() {
		if (window.location.hash === '#menu') {
			window.history.replaceState(null, null, window.location.pathname + window.location.search);
			if (document.body && document.body.classList.contains('is-menu-visible')) {
				document.body.classList.remove('is-menu-visible');
			}
		}
		hashCheckCount++;
		if (hashCheckCount >= 20) { // Stop after 2 seconds (20 * 100ms)
			clearInterval(hashCheckInterval);
		}
	}, 100);
	
	function handleMenuClick(event) {
		var target = event.target;
		var isMenuButton = false;
		
		// Check if clicked element or parent is menu button/link
		// Don't intercept clicks inside the menu itself (allow menu links to work)
		if (target.id === 'menu' || target.closest('#menu')) {
			return; // Let menu links work normally
		}
		
		// Check if clicked element or parent is menu toggle button
		while (target && target !== document) {
			if (target.id === 'menu-toggle' || 
			    (target.tagName === 'A' && (target.getAttribute('href') === '#menu' || target.getAttribute('href') === 'javascript:void(0)'))) {
				isMenuButton = true;
				break;
			}
			target = target.parentElement;
		}
		
		if (isMenuButton) {
			event.preventDefault();
			event.stopPropagation();
			event.stopImmediatePropagation();
			
			// CRITICAL: Prevent hash from being added to URL - do this FIRST
			var cleanUrl = window.location.href.split('#')[0];
			if (window.location.href !== cleanUrl) {
				window.history.replaceState(null, null, cleanUrl);
			}
			
			// Toggle menu immediately
			var body = document.body;
			if (!body) return false;
			
			var wasVisible = body.classList.contains('is-menu-visible');
			body.classList.toggle('is-menu-visible');
			var isNowVisible = body.classList.contains('is-menu-visible');
			
			// Ensure menu is positioned correctly
			var menu = document.getElementById('menu');
			if (menu) {
				// Ensure menu is appended to body (not inside wrapper)
				if (menu.parentElement !== document.body) {
					document.body.appendChild(menu);
				}
				
				// Use consistent z-index (99999 to match custom.css)
				if (isNowVisible) {
					menu.style.cssText = 'display: flex !important; visibility: visible !important; opacity: 1 !important; pointer-events: auto !important; z-index: 99999 !important; position: fixed !important; top: 0 !important; left: 0 !important; width: 100% !important; height: 100% !important; filter: none !important; -webkit-filter: none !important;';
					var menuInner = menu.querySelector('.inner');
					if (menuInner) {
						menuInner.style.cssText = 'display: flex !important; flex-direction: column !important; align-items: center !important; justify-content: center !important; visibility: visible !important; opacity: 1 !important; transform: none !important; filter: none !important; -webkit-filter: none !important;';
					}
				} else {
					// Clear inline styles when closing to let CSS handle it
					menu.style.cssText = '';
					var menuInner = menu.querySelector('.inner');
					if (menuInner) {
						menuInner.style.cssText = '';
					}
				}
			}
			
			// Prevent hash one more time after event (multiple checks)
			setTimeout(function() {
				if (window.location.hash === '#menu') {
					window.history.replaceState(null, null, window.location.pathname + window.location.search);
				}
			}, 0);
			setTimeout(function() {
				if (window.location.hash === '#menu') {
					window.history.replaceState(null, null, window.location.pathname + window.location.search);
				}
			}, 10);
			setTimeout(function() {
				if (window.location.hash === '#menu') {
					window.history.replaceState(null, null, window.location.pathname + window.location.search);
				}
			}, 50);
			
			return false;
		}
	}
	
	// Outside click handler - close menu when clicking outside
	function handleOutsideClick(event) {
		var body = document.body;
		if (!body || !body.classList.contains('is-menu-visible')) {
			return; // Menu not visible, do nothing
		}
		
		var target = event.target;
		var menu = document.getElementById('menu');
		var menuInner = menu ? menu.querySelector('.inner') : null;
		
		// Check if clicked on menu button (handled separately)
		var clickedMenuButton = target.id === 'menu-toggle' || target.closest('#menu-toggle');
		if (clickedMenuButton) {
			return; // Menu button click is handled by handleMenuClick
		}
		
		// Check if clicked inside menu inner content (don't close)
		var clickedMenuInner = menuInner && (target === menuInner || menuInner.contains(target));
		if (clickedMenuInner) {
			return; // Clicked inside menu content, don't close
		}
		
		// Check if clicked on menu background (the overlay itself) - close menu
		var clickedMenuBackground = target.id === 'menu' || (menu && target === menu);
		
		// If clicked outside menu OR on menu background, close it
		if (!clickedMenuInner && (clickedMenuBackground || !menu || !menu.contains(target))) {
			body.classList.remove('is-menu-visible');
			if (menu) {
				menu.style.cssText = '';
				if (menuInner) {
					menuInner.style.cssText = '';
				}
			}
		}
	}
	
	// Attach in capture phase with highest priority - runs IMMEDIATELY
	// Only attach once to prevent duplicates
	if (!menuHandlerAttached) {
		document.addEventListener('click', handleMenuClick, true);
		menuHandlerAttached = true;
	}
	
	// Attach outside click handler
	if (!outsideClickHandlerAttached) {
		document.addEventListener('click', handleOutsideClick, true);
		outsideClickHandlerAttached = true;
	}
	
	// CRITICAL: Also attach direct listener to button when it becomes available
	// This ensures it works even if the document-level handler has timing issues
	function attachDirectButtonListener() {
		var menuButton = document.getElementById('menu-toggle');
		if (menuButton && !menuButton.dataset.listenerAttached) {
			menuButton.addEventListener('click', function(event) {
				event.preventDefault();
				event.stopPropagation();
				event.stopImmediatePropagation();
				
				// Prevent hash
				var cleanUrl = window.location.href.split('#')[0];
				if (window.location.href !== cleanUrl) {
					window.history.replaceState(null, null, cleanUrl);
				}
				
				// Toggle menu
				var body = document.body;
				if (!body) return false;
				
				var wasVisible = body.classList.contains('is-menu-visible');
				body.classList.toggle('is-menu-visible');
				var isNowVisible = body.classList.contains('is-menu-visible');
				
				// Ensure menu is positioned correctly
				var menu = document.getElementById('menu');
				if (menu) {
					if (menu.parentElement !== document.body) {
						document.body.appendChild(menu);
					}
					
					if (isNowVisible) {
						menu.style.cssText = 'display: flex !important; visibility: visible !important; opacity: 1 !important; pointer-events: auto !important; z-index: 99999 !important; position: fixed !important; top: 0 !important; left: 0 !important; width: 100% !important; height: 100% !important; filter: none !important; -webkit-filter: none !important;';
						var menuInner = menu.querySelector('.inner');
						if (menuInner) {
							menuInner.style.cssText = 'display: flex !important; flex-direction: column !important; align-items: center !important; justify-content: center !important; visibility: visible !important; opacity: 1 !important; transform: none !important; filter: none !important; -webkit-filter: none !important;';
						}
					} else {
						menu.style.cssText = '';
						var menuInner = menu.querySelector('.inner');
						if (menuInner) {
							menuInner.style.cssText = '';
						}
					}
				}
				
				// Prevent hash after event
				setTimeout(function() {
					if (window.location.hash === '#menu') {
						window.history.replaceState(null, null, window.location.pathname + window.location.search);
					}
				}, 0);
				
				return false;
			}, true);
			menuButton.dataset.listenerAttached = 'true';
			console.log('[Menu] Direct button listener attached');
		}
	}
	
	// Try to attach immediately
	attachDirectButtonListener();
	
	// Also try when DOM is ready
	if (document.readyState === 'loading') {
		document.addEventListener('DOMContentLoaded', attachDirectButtonListener);
	}
	
	// Also try after a short delay to catch late-loading elements
	setTimeout(attachDirectButtonListener, 100);
	setTimeout(attachDirectButtonListener, 500);
	
	// Immediately move menu to body if it exists (before DOM ready)
	function moveMenuToBody() {
		var menu = document.getElementById('menu');
		if (menu && menu.parentElement !== document.body) {
			document.body.appendChild(menu);
		}
	}
	
	// Try to move menu immediately
	if (document.readyState === 'loading') {
		document.addEventListener('DOMContentLoaded', moveMenuToBody);
	} else {
		moveMenuToBody();
	}
	
	// Also try after a delay
	setTimeout(moveMenuToBody, 100);
})();

(function($) {

	var	$window = $(window),
		$body = $('body'),
		$wrapper = $('#wrapper'),
		$header = $('#header'),
		$banner = $('#banner');

	// Breakpoints.
		try {
			if (typeof breakpoints !== 'undefined' && typeof breakpoints === 'function') {
				breakpoints({
					xlarge:    ['1281px',   '1680px'   ],
					large:     ['981px',    '1280px'   ],
					medium:    ['737px',    '980px'    ],
					small:     ['481px',    '736px'    ],
					xsmall:    ['361px',    '480px'    ],
					xxsmall:   [null,       '360px'    ]
				});
			} else {
				console.warn('[main.js] breakpoints library not loaded. Some responsive features may not work.');
			}
		} catch (e) {
			console.warn('[main.js] Error initializing breakpoints:', e);
		}

	/**
	 * Applies parallax scrolling to an element's background image.
	 * @return {jQuery} jQuery object.
	 */
	$.fn._parallax = (browser.name == 'ie' || browser.name == 'edge' || browser.mobile) ? function() { return $(this) } : function(intensity) {

		var	$window = $(window),
			$this = $(this);

		if (this.length == 0 || intensity === 0)
			return $this;

		if (this.length > 1) {

			for (var i=0; i < this.length; i++)
				$(this[i])._parallax(intensity);

			return $this;

		}

		if (!intensity)
			intensity = 0.25;

		$this.each(function() {

			var $t = $(this),
				on, off;

			on = function() {

				$t.css('background-position', 'center 100%, center 100%, center 0px');

				$window
					.on('scroll._parallax', function() {

						var pos = parseInt($window.scrollTop()) - parseInt($t.position().top);

						$t.css('background-position', 'center ' + (pos * (-1 * intensity)) + 'px');

					});

			};

			off = function() {

				$t
					.css('background-position', '');

				$window
					.off('scroll._parallax');

			};

			if (typeof breakpoints !== 'undefined') {
				breakpoints.on('<=medium', off);
				breakpoints.on('>medium', on);
			}

		});

		$window
			.off('load._parallax resize._parallax')
			.on('load._parallax resize._parallax', function() {
				$window.trigger('scroll');
			});

		return $(this);

	};

	// Play initial animations on page load.
		$window.on('load', function() {
			window.setTimeout(function() {
				$body.removeClass('is-preload');
			}, 100);
		});

	// Clear transitioning state on unload/hide.
		$window.on('unload pagehide', function() {
			window.setTimeout(function() {
				$('.is-transitioning').removeClass('is-transitioning');
			}, 250);
		});

	// Fix: Enable IE-only tweaks.
		if (browser.name == 'ie' || browser.name == 'edge')
			$body.addClass('is-ie');

	// Scrolly.
		$('.scrolly').scrolly({
			offset: function() {
				return $header.height() - 2;
			}
		});

	// Tiles.
		var $tiles = $('.tiles > article');

		$tiles.each(function() {

			var $this = $(this),
				$image = $this.find('.image'), $img = $image.find('img'),
				$link = $this.find('.link'),
				x;

			// Image.

				// Set image.
					$this.css('background-image', 'url(' + $img.attr('src') + ')');

				// Set position.
					if (x = $img.data('position'))
						$image.css('background-position', x);

				// Hide original.
					$image.hide();

			// Link.
				if ($link.length > 0) {

					$x = $link.clone()
						.text('')
						.addClass('primary')
						.appendTo($this);

					$link = $link.add($x);

					$link.on('click', function(event) {

						var href = $link.attr('href');

						// Prevent default.
							event.stopPropagation();
							event.preventDefault();

						// Target blank?
							if ($link.attr('target') == '_blank') {

								// Open in new tab.
									window.open(href);

							}

						// Otherwise ...
							else {

								// Start transitioning.
									$this.addClass('is-transitioning');
									$wrapper.addClass('is-transitioning');

								// Redirect.
									window.setTimeout(function() {
										location.href = href;
									}, 500);

							}

					});

				}

		});

	// Header.
		if ($banner.length > 0
		&&	$header.hasClass('alt')) {

			$window.on('resize', function() {
				$window.trigger('scroll');
			});

			$window.on('load', function() {

				$banner.scrollex({
					bottom:		$header.height() + 10,
					terminate:	function() { $header.removeClass('alt'); },
					enter:		function() { $header.addClass('alt'); },
					leave:		function() { $header.removeClass('alt'); $header.addClass('reveal'); }
				});

				window.setTimeout(function() {
					$window.triggerHandler('scroll');
				}, 100);

			});

		}

	// Banner.
		$banner.each(function() {

			var $this = $(this),
				$image = $this.find('.image'), $img = $image.find('img');

			// Parallax.
				$this._parallax(0.275);

			// Image.
				if ($image.length > 0) {

					// Set image.
						$this.css('background-image', 'url(' + $img.attr('src') + ')');

					// Hide original.
						$image.hide();

				}

		});

	// Menu.
		var $menu = $('#menu'),
			$menuInner;

		// Menu toggle function - works even if menu doesn't exist yet
		var menuToggle = function() {
			try {
				var $menuEl = $('#menu');
				console.log('[Menu] Toggle called, menu element found:', $menuEl.length > 0);
				
				// Always use direct class toggle - most reliable
				var wasVisible = $body.hasClass('is-menu-visible');
				$body.toggleClass('is-menu-visible');
				var isNowVisible = $body.hasClass('is-menu-visible');
				
				console.log('[Menu] Toggle result - was:', wasVisible, 'now:', isNowVisible);
				console.log('[Menu] Body class:', $body.hasClass('is-menu-visible'));
				
				if ($menuEl.length > 0) {
					console.log('[Menu] Menu element display:', $menuEl.css('display'), 'visibility:', $menuEl.css('visibility'), 'opacity:', $menuEl.css('opacity'));
				}
				
				// Also try using menu._toggle if available (for animations)
				if ($menuEl.length > 0 && typeof $menuEl._toggle === 'function') {
					// The class toggle above already happened, but _toggle handles locking
					// So we'll just ensure the state is correct
					if (isNowVisible && !wasVisible) {
						// Menu is opening - ensure it's visible
						$menuEl.css({
							'display': 'flex',
							'visibility': 'visible',
							'opacity': '1'
						});
					}
				}
			} catch (e) {
				// If anything fails, use direct class toggle
				console.error('[Menu] Toggle error:', e);
				$body.toggleClass('is-menu-visible');
			}
		};

		var menuHide = function() {
			try {
				var $menuEl = $('#menu');
				if ($menuEl.length > 0 && typeof $menuEl._hide === 'function') {
					$menuEl._hide();
				} else {
					// Fallback: just remove the class directly
					$body.removeClass('is-menu-visible');
				}
			} catch (e) {
				// If anything fails, use direct class removal
				console.warn('Menu hide error:', e);
				$body.removeClass('is-menu-visible');
			}
		};

		// Initialize menu functionality - run after DOM is ready
		var initMenu = function() {
			// Hash prevention is already handled at top of file (lines 15-40)
			// No need to duplicate hashchange/history handlers here
			
			// ESC key handler - use document level to catch all ESC presses
			$(document).on('keydown', function(event) {
				// Hide on escape when menu is visible
				if (event.keyCode == 27 && $body.hasClass('is-menu-visible')) {
					event.preventDefault();
					event.stopPropagation();
					menuHide();
				}
			});
			

			// Only initialize menu if it exists
			if ($menu.length > 0) {
				console.log('[Menu] Menu element found, setting up...');
				// Check if inner wrapper already exists to prevent double-wrapping
				if ($menu.children('.inner').length === 0) {
					$menu.wrapInner('<div class="inner"></div>');
				}
				$menuInner = $menu.children('.inner');
				$menu._locked = false;

				$menu._lock = function() {
					if ($menu._locked)
						return false;
					$menu._locked = true;
					window.setTimeout(function() {
						$menu._locked = false;
					}, 350);
					return true;
				};

				$menu._show = function() {
					if ($menu._lock())
						$body.addClass('is-menu-visible');
				};

				$menu._hide = function() {
					if ($menu._lock())
						$body.removeClass('is-menu-visible');
				};

				$menu._toggle = function() {
					if ($menu._lock()) {
						$body.toggleClass('is-menu-visible');
						var isVisible = $body.hasClass('is-menu-visible');
						console.log('[Menu] Toggled, is-menu-visible:', isVisible);
						console.log('[Menu] Menu element:', $menu.length, 'Display:', $menu.css('display'), 'Visibility:', $menu.css('visibility'), 'Opacity:', $menu.css('opacity'));
						// Force check menu visibility after a short delay
						setTimeout(function() {
							console.log('[Menu] After toggle - Display:', $menu.css('display'), 'Visibility:', $menu.css('visibility'), 'Opacity:', $menu.css('opacity'));
						}, 100);
					}
				};

				$menuInner
					.on('click', function(event) {
						event.stopPropagation();
					})
					.on('click', 'a', function(event) {
						var href = $(this).attr('href');
						// CRITICAL: Prevent navigation - just close menu
						// User wants to stay on same page to preserve calculated data
						event.preventDefault();
						event.stopPropagation();
						
						// Hide menu immediately
						$menu._hide();
						
						// If it's a valid link, scroll to section or handle internally
						// But don't navigate away from page
						if (href && href !== '#' && href !== '#menu' && href !== 'javascript:void(0)') {
							// Check if it's an anchor link on same page
							if (href.startsWith('#')) {
								var target = $(href);
								if (target.length) {
									// Scroll to section on same page
									$('html, body').animate({
										scrollTop: target.offset().top
									}, 500);
								}
							} else if (href.startsWith('/') || href.startsWith('./') || href.includes(window.location.hostname)) {
								// Same domain - could navigate, but user wants to stay on page
								// Just close menu, don't navigate
								console.log('[Menu] Link clicked but navigation prevented to preserve data:', href);
							} else {
								// External link - could open in new tab, but for now just close menu
								console.log('[Menu] External link clicked but navigation prevented:', href);
							}
						}
					});

				// CRITICAL: Ensure menu is always appended to body (not inside wrapper)
				// This prevents it from being affected by wrapper blur
				if ($menu.parent().length === 0 || $menu.parent()[0] !== $body[0]) {
					$menu.appendTo($body);
					console.log('[Menu] Menu appended to body');
				}
				// Double-check menu is not inside wrapper
				if ($menu.closest('#wrapper').length > 0) {
					$menu.detach().appendTo($body);
					console.log('[Menu] Menu was inside wrapper, moved to body');
				}
				
				// Only add close button if it doesn't exist
				if ($menu.find('a.close').length === 0) {
					$menu.append('<a class="close" href="#menu">Close</a>');
				}
				
				// Click on menu background (outside inner) should close menu
				$menu.on('click', function(event) {
					// Only close if clicking directly on menu element (background), not on inner content
					if (event.target === $menu[0]) {
						event.stopPropagation();
						event.preventDefault();
						menuHide();
					}
				});

				// Outside click handler is already attached at top of file
				// No need to attach again here
				
				console.log('[Menu] Menu initialization complete');
			} else {
				console.warn('[Menu] Menu element not found in DOM');
			}
		};
		
		// NOTE: Menu toggle handler is already attached at top of file (lines 8-104)
		// No need to attach again here - this prevents duplicate handlers
		
		// Initialize menu when DOM is ready
		if (document.readyState === 'loading') {
			$(document).ready(initMenu);
		} else {
			// DOM already loaded, initialize immediately
			initMenu();
		}

})(jQuery);