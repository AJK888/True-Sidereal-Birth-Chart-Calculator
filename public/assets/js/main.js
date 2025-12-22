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
		if (typeof breakpoints !== 'undefined') {
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
			var $menuEl = $('#menu');
			if ($menuEl.length > 0 && typeof $menuEl._toggle === 'function') {
				$menuEl._toggle();
			} else {
				// Fallback: just toggle the class directly
				$body.toggleClass('is-menu-visible');
			}
		};

		var menuHide = function() {
			var $menuEl = $('#menu');
			if ($menuEl.length > 0 && typeof $menuEl._hide === 'function') {
				$menuEl._hide();
			} else {
				// Fallback: just remove the class directly
				$body.removeClass('is-menu-visible');
			}
		};

		// Set up body click handlers first (these are needed for menu toggle button)
		$body
			.on('click', 'a[href="#menu"]', function(event) {
				event.stopPropagation();
				event.preventDefault();
				menuToggle();
			})
			.on('keydown', function(event) {
				// Hide on escape.
				if (event.keyCode == 27)
					menuHide();
			});

		// Only initialize menu if it exists
		if ($menu.length > 0) {
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
				if ($menu._lock())
					$body.toggleClass('is-menu-visible');
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
		}

})(jQuery);