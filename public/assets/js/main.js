/*
	Forty by HTML5 UP
	html5up.net | @ajlkn
	Free for personal and commercial use under the CCA 3.0 license (html5up.net/license)
*/

// CRITICAL: Menu handler - MUST run immediately, before everything else
(function() {
	function handleMenuClick(event) {
		var target = event.target;
		var isMenuButton = false;
		var isMenuLink = false;
		
		// Check if clicked element or parent is menu button/link
		while (target && target !== document) {
			// Don't intercept clicks inside the menu itself (allow menu links to work)
			if (target.id === 'menu' || target.closest('#menu')) {
				return; // Let menu links work normally
			}
			
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
			
			console.log('[Menu] CRITICAL: Menu button clicked - intercepting');
			
			// Immediately prevent hash
			setTimeout(function() {
				if (window.location.hash === '#menu') {
					window.history.replaceState(null, null, window.location.pathname + window.location.search);
				}
			}, 0);
			
			// Toggle menu immediately
			var body = document.body;
			if (!body) return false;
			
			var wasVisible = body.classList.contains('is-menu-visible');
			body.classList.toggle('is-menu-visible');
			var isNowVisible = body.classList.contains('is-menu-visible');
			
			console.log('[Menu] Toggled - was:', wasVisible, 'now:', isNowVisible);
			
			// Force menu visibility and ensure it's above everything
			var menu = document.getElementById('menu');
			if (menu) {
				// Ensure menu is appended to body (not inside wrapper)
				if (menu.parentElement !== document.body) {
					document.body.appendChild(menu);
					console.log('[Menu] Moved menu to body');
				}
				
				if (isNowVisible) {
					menu.style.cssText = 'display: flex !important; visibility: visible !important; opacity: 1 !important; pointer-events: auto !important; z-index: 99999 !important; position: fixed !important; top: 0 !important; left: 0 !important; width: 100% !important; height: 100% !important; filter: none !important; -webkit-filter: none !important;';
					var menuInner = menu.querySelector('.inner');
					if (menuInner) {
						menuInner.style.cssText = 'display: block !important; visibility: visible !important; opacity: 1 !important; transform: none !important; filter: none !important; -webkit-filter: none !important;';
					}
					console.log('[Menu] Menu forced visible with z-index 99999');
				} else {
					menu.style.cssText = '';
					var menuInner = menu.querySelector('.inner');
					if (menuInner) {
						menuInner.style.cssText = '';
					}
				}
			} else {
				console.warn('[Menu] Menu element not found!');
			}
			
			return false;
		}
	}
	
	// Attach in capture phase with highest priority - runs IMMEDIATELY
	document.addEventListener('click', handleMenuClick, true);
	console.log('[Menu] CRITICAL handler attached (immediate, capture phase)');
	
	// Immediately move menu to body if it exists (before DOM ready)
	function moveMenuToBody() {
		var menu = document.getElementById('menu');
		if (menu && menu.parentElement !== document.body) {
			// Menu is inside wrapper, move it to body
			document.body.appendChild(menu);
			console.log('[Menu] CRITICAL: Moved menu to body immediately');
		}
	}
	
	// Try to move menu immediately
	if (document.readyState === 'loading') {
		document.addEventListener('DOMContentLoaded', moveMenuToBody);
	} else {
		moveMenuToBody();
	}
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
			console.log('[Menu] Initializing menu functionality...');
			
			// Set up click handler for menu toggle button - multiple approaches for reliability
			var menuButtonHandler = function(event) {
				event.preventDefault();
				event.stopPropagation();
				event.stopImmediatePropagation();
				console.log('[Menu] Toggle button clicked, preventing default');
				menuToggle();
				// Also prevent hash change immediately
				setTimeout(function() {
					if (window.location.hash === '#menu') {
						window.history.replaceState(null, null, window.location.pathname + window.location.search);
					}
				}, 0);
				return false;
			};
			
			// Remove any existing handlers first to prevent conflicts
			$(document).off('click', 'a[href="#menu"]');
			$('a[href="#menu"]').off('click');
			$('#menu-toggle').off('click');
			
			// Attach handler to menu toggle button by ID (most reliable) - use multiple methods
			var menuToggleBtn = document.getElementById('menu-toggle');
			if (menuToggleBtn) {
				// Native event listener (most reliable)
				menuToggleBtn.addEventListener('click', function(event) {
					event.preventDefault();
					event.stopPropagation();
					event.stopImmediatePropagation();
					console.log('[Menu] Toggle button clicked (native handler)');
					menuToggle();
					return false;
				}, false);
				
				// Also attach jQuery handler as backup
				$('#menu-toggle').on('click', function(event) {
					event.preventDefault();
					event.stopPropagation();
					event.stopImmediatePropagation();
					console.log('[Menu] Toggle button clicked (jQuery handler)');
					menuToggle();
					return false;
				});
			} else {
				console.warn('[Menu] Menu toggle button not found!');
			}
			
			// Also handle old href="#menu" links for compatibility
			document.addEventListener('click', function(event) {
				var target = event.target;
				// Check if clicked element or its parent is the menu link
				while (target && target !== document) {
					if ((target.id === 'menu-toggle') || 
					    (target.tagName === 'A' && target.getAttribute('href') === '#menu')) {
						event.preventDefault();
						event.stopPropagation();
						event.stopImmediatePropagation();
						console.log('[Menu] Toggle button clicked (capture phase)');
						menuToggle();
						setTimeout(function() {
							if (window.location.hash === '#menu') {
								window.history.replaceState(null, null, window.location.pathname + window.location.search);
							}
						}, 0);
						return false;
					}
					target = target.parentElement;
				}
			}, true); // Use capture phase
			
			// Also attach jQuery handlers for compatibility with old href="#menu"
			$(document).on('click', 'a[href="#menu"]', menuButtonHandler);
			
			// Also handle hashchange to prevent menu from opening on hash navigation
			$(window).on('hashchange', function() {
				if (window.location.hash === '#menu') {
					console.log('[Menu] Hash change detected, removing hash and toggling menu');
					window.history.replaceState(null, null, window.location.pathname + window.location.search);
					// Always toggle menu when hash appears
					menuToggle();
				}
			});
			
			// Also prevent hash from being added in the first place
			window.addEventListener('hashchange', function(event) {
				if (window.location.hash === '#menu') {
					console.log('[Menu] Hash change intercepted (native), removing hash');
					event.preventDefault();
					window.history.replaceState(null, null, window.location.pathname + window.location.search);
					// Toggle menu
					document.body.classList.toggle('is-menu-visible');
					if (typeof $body !== 'undefined' && $body) {
						$body.toggleClass('is-menu-visible');
					}
				}
			}, true);
			
			$body.on('keydown', function(event) {
				// Hide on escape.
				if (event.keyCode == 27)
					menuHide();
			});
			
			// Also prevent hash change on page load if hash is #menu
			if (window.location.hash === '#menu') {
				window.history.replaceState(null, null, window.location.pathname + window.location.search);
				// Open menu if hash was present
				setTimeout(function() {
					if (!$body.hasClass('is-menu-visible')) {
						menuToggle();
					}
				}, 100);
			}

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
						// Don't prevent default for actual navigation links
						if (href && href !== '#' && href !== '#menu' && href !== 'javascript:void(0)') {
							event.stopPropagation(); // Stop bubbling but allow navigation
							// Hide menu
							$menu._hide();
							// Navigate immediately
							window.location.href = href;
						} else {
							// For close buttons or special links, prevent default
							event.preventDefault();
							event.stopPropagation();
							$menu._hide();
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
				
				$menu
					.on('click', function(event) {
						event.stopPropagation();
						event.preventDefault();
						$body.removeClass('is-menu-visible');
					});

				// Add body click handler to close menu when clicking outside (only if menu exists and is visible)
				$body.on('click', function(event) {
					// Only close if menu is visible and click is outside the menu
					if ($body.hasClass('is-menu-visible') && !$(event.target).closest('#menu').length) {
						menuHide();
					}
				});
				
				console.log('[Menu] Menu initialization complete');
			} else {
				console.warn('[Menu] Menu element not found in DOM');
			}
		};
		
		// CRITICAL: Attach menu handler IMMEDIATELY - before ANY other scripts
		// This must run in the earliest possible capture phase to intercept clicks
		(function() {
			// Use immediate function to run as soon as script loads
			function handleMenuClick(event) {
				var target = event.target;
				var isMenuButton = false;
				
				// Check if clicked element or parent is menu button/link
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
					
					console.log('[Menu] CRITICAL: Menu button clicked - intercepting');
					
					// Immediately prevent hash
					setTimeout(function() {
						if (window.location.hash === '#menu') {
							window.history.replaceState(null, null, window.location.pathname + window.location.search);
						}
					}, 0);
					
					// Toggle menu immediately
					var body = document.body;
					var wasVisible = body.classList.contains('is-menu-visible');
					body.classList.toggle('is-menu-visible');
					var isNowVisible = body.classList.contains('is-menu-visible');
					
					console.log('[Menu] Toggled - was:', wasVisible, 'now:', isNowVisible);
					
					// Force menu visibility
					var menu = document.getElementById('menu');
					if (menu) {
						if (isNowVisible) {
							menu.style.cssText = 'display: flex !important; visibility: visible !important; opacity: 1 !important; pointer-events: auto !important; z-index: 10002 !important;';
							var menuInner = menu.querySelector('.inner');
							if (menuInner) {
								menuInner.style.cssText = 'display: block !important; visibility: visible !important; opacity: 1 !important; transform: none !important;';
							}
							console.log('[Menu] Menu forced visible');
						} else {
							menu.style.cssText = '';
							var menuInner = menu.querySelector('.inner');
							if (menuInner) {
								menuInner.style.cssText = '';
							}
						}
					}
					
					return false;
				}
			}
			
			// Attach in capture phase with highest priority
			document.addEventListener('click', handleMenuClick, true);
			console.log('[Menu] CRITICAL handler attached (capture phase)');
		})();
		
		// Initialize menu when DOM is ready
		if (document.readyState === 'loading') {
			$(document).ready(initMenu);
		} else {
			// DOM already loaded, initialize immediately
			initMenu();
		}

})(jQuery);