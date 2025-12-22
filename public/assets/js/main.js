/*
	Forty by HTML5 UP
	html5up.net | @ajlkn
	Free for personal and commercial use under the CCA 3.0 license (html5up.net/license)
*/

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
				if ($menuEl.length > 0 && typeof $menuEl._toggle === 'function') {
					console.log('[Menu] Using menu._toggle()');
					$menuEl._toggle();
				} else {
					// Fallback: just toggle the class directly
					console.log('[Menu] Using fallback toggle');
					$body.toggleClass('is-menu-visible');
					console.log('[Menu] Body class after toggle:', $body.hasClass('is-menu-visible'));
					console.log('[Menu] Menu element:', $menuEl.length, 'Menu visible:', $menuEl.is(':visible'));
				}
			} catch (e) {
				// If anything fails, use direct class toggle
				console.error('Menu toggle error:', e);
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
			
			// Attach handler using capture phase to run before other handlers
			document.addEventListener('click', function(event) {
				var target = event.target;
				// Check if clicked element or its parent is the menu link
				while (target && target !== document) {
					if (target.tagName === 'A' && target.getAttribute('href') === '#menu') {
						event.preventDefault();
						event.stopPropagation();
						event.stopImmediatePropagation();
						console.log('[Menu] Toggle button clicked (capture phase), preventing default');
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
			
			// Also attach jQuery handlers for compatibility
			$(document).on('click', 'a[href="#menu"]', menuButtonHandler);
			$('a[href="#menu"]').on('click', menuButtonHandler);
			
			// Also handle hashchange to prevent menu from opening on hash navigation
			$(window).on('hashchange', function() {
				if (window.location.hash === '#menu') {
					console.log('[Menu] Hash change detected, removing hash');
					window.history.replaceState(null, null, window.location.pathname + window.location.search);
					// If menu isn't visible, toggle it
					if (!$body.hasClass('is-menu-visible')) {
						menuToggle();
					}
				}
			});
			
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
						event.preventDefault();
						event.stopPropagation();
						// Hide.
						$menu._hide();
						// Redirect.
						window.setTimeout(function() {
							window.location.href = href;
						}, 250);
					});

				// Check if menu is already appended to body to prevent duplicate close buttons
				if ($menu.parent().length === 0 || $menu.parent()[0] !== $body[0]) {
					$menu.appendTo($body);
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
		
		// Initialize menu when DOM is ready
		if (document.readyState === 'loading') {
			$(document).ready(initMenu);
		} else {
			// DOM already loaded, initialize immediately
			initMenu();
		}

})(jQuery);