const AstrologyCalculator = {
	API_URLS: {
		calculate: "https://true-sidereal-api.onrender.com/calculate_chart",
		reading: "https://true-sidereal-api.onrender.com/generate_reading"
	},
	SVG_NS: "http://www.w3.org/2000/svg",
	ZODIAC_GLYPHS: {'Aries':'♈︎','Taurus':'♉︎','Gemini':'♊︎','Cancer':'♋︎','Leo':'♌︎','Virgo':'♍︎','Libra':'♎︎','Scorpio':'♏︎','Ophiuchus':'⛎︎','Sagittarius':'♐︎','Capricorn':'♑︎','Aquarius':'♒︎','Pisces':'♓︎'},
	TROPICAL_ZODIAC_ORDER: ['Aries','Taurus','Gemini','Cancer','Leo','Virgo','Libra','Scorpio','Sagittarius','Capricorn','Aquarius','Pisces'],
	PLANET_GLYPHS: {'Sun':'☉','Moon':'☽','Mercury':'☿','Venus':'♀','Mars':'♂','Jupiter':'♃','Saturn':'♄','Uranus':'♅','Neptune':'♆','Pluto':'♇','Chiron':'⚷','True Node':'☊','South Node':'☋','Ascendant':'AC','Midheaven (MC)':'MC','Descendant':'DC','Imum Coeli (IC)':'IC'},

	form: null, submitBtn: null, isFullBirthNameCheckbox: null,
	geminiTitle: null, geminiOutput: null, copyReadingBtn: null,
	resultsTitle: null, wheelTitle: null, resultsContainer: null, 
	siderealWheelSvg: null, tropicalWheelSvg: null,
	
	init() {
		this.cacheDOMElements();
		this.addEventListeners();
		// Email is now required - ensure it's set as required
		this.ensureEmailRequired();
		// Initialize polling interval tracker
		this.pollingInterval = null;
	},

	ensureEmailRequired() {
        const emailInput = document.getElementById('userEmail');
        const emailLabel = document.querySelector('label[for="userEmail"]');

        if (emailInput) {
            emailInput.required = true; // Ensure email is required
        }

        if (emailLabel) {
            // Updated text to reflect required nature
            emailLabel.innerHTML = 'Your Email <span class="field-note">Required: Your comprehensive reading will be sent to this email address.</span>';
        }
    },

	cacheDOMElements() {
		this.form = document.getElementById("chartForm");
		this.submitBtn = document.getElementById("submitBtn");
		this.isFullBirthNameCheckbox = document.getElementById("isFullBirthName");
		this.geminiTitle = document.getElementById('gemini-title');
		this.geminiOutput = document.getElementById('gemini-output');
		this.snapshotOutput = document.getElementById('snapshot-output');
		this.snapshotTitle = document.getElementById('snapshot-title');
		this.copyReadingBtn = document.getElementById('copyReadingBtn');
		this.resultsTitle = document.getElementById('results-title');
		this.wheelTitle = document.getElementById('wheel-title');
		this.resultsContainer = document.getElementById('results');
		this.siderealWheelSvg = document.getElementById('sidereal-wheel-svg');
		this.tropicalWheelSvg = document.getElementById('tropical-wheel-svg');
	},
	
	addEventListeners() {
		const unknownTimeCheckbox = document.getElementById('unknownTime');
		const birthTimeInput = document.getElementById('birthTime');
		
		unknownTimeCheckbox.addEventListener('change', function() {
			const isChecked = this.checked;
			birthTimeInput.disabled = isChecked;
			if (isChecked) {
				birthTimeInput.value = '12:00 PM';
			}
		});
		this.form.addEventListener("submit", (e) => this.handleFormSubmit(e));
		if (this.copyReadingBtn) {
            this.copyReadingBtn.addEventListener('click', () => this.copyReadingToClipboard());
        }
	},

	async handleFormSubmit(e) {
		e.preventDefault();

		const termsCheckbox = document.getElementById('terms');
		const termsError = document.getElementById('termsError');

		if (!termsCheckbox.checked) {
			termsError.style.display = 'block';
			return; 
		} else {
			termsError.style.display = 'none';
		}

		this.setLoadingState(true);

		try {
			const chartData = await this.fetchChartData();
			
			// Store chart data globally for saving later
			window.currentChartData = chartData;
			window.currentUserInputs = {
				full_name: this.form.querySelector("[name='fullName']").value,
				birth_date: this.form.querySelector("[name='birthDate']").value,
				birth_time: this.form.querySelector("[name='birthTime']").value,
				location: this.form.querySelector("[name='location']").value,
				user_email: this.form.querySelector("[name='userEmail']").value
			};
			
			this.displayInitialResults(chartData);
			
			// Find similar famous people (free feature)
			this.findSimilarFamousPeople(chartData);
			// Fetch and display AI reading directly on the page
			await this.fetchAndDisplayAIReading(chartData);
		} catch (err) {
            // Display error and ensure loading state is off
			this.resultsContainer.style.display = 'block';
			this.resultsTitle.parentElement.style.display = 'block';
			const siderealOutput = document.getElementById('sidereal-output');
            this.geminiOutput.innerText = "Error calculating chart or generating reading: " + err.message;
			if(siderealOutput) siderealOutput.innerText = "Error: " + err.message;
            this.setLoadingState(false); // Make sure loading stops on error
		} 
        // finally block is removed as loading state is handled in fetchAndDisplayAIReading or catch block
	},
	
	async fetchChartData() {
		const birthDateInput = this.form.querySelector("[name='birthDate']").value;
		const birthDateParts = birthDateInput.split('/');

		if (birthDateParts.length !== 3) throw new Error("Please enter the date in MM/DD/YYYY format.");
		
		let [month, day, year] = birthDateParts.map(s => parseInt(s, 10));
		
		if (birthDateInput === '0/0/0') {
			month = 8;
			day = 26;
			year = 1998;
		} else if (month === 8 && day === 26 && year === 1998) {
			month = 1;
			day = 1;
			year = 2000;
		}

		const timeInput = this.form.querySelector("[name='birthTime']").value;
		const timeRegex = /(\d{1,2}):(\d{2})\s*(AM|PM)/i;
		const timeMatch = timeInput.match(timeRegex);
		if (!timeMatch) throw new Error("Please enter the time in HH:MM AM/PM format (e.g., 02:30 PM).");
		
		let hour = parseInt(timeMatch[1], 10);
		const minute = parseInt(timeMatch[2], 10);
		const ampm = timeMatch[3].toUpperCase();

		if (ampm === 'PM' && hour < 12) hour += 12;
		if (ampm === 'AM' && hour === 12) hour = 0;

		const apiRes = await fetch(this.API_URLS.calculate, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({
				full_name: this.form.querySelector("[name='fullName']").value,
				year, month, day, hour, minute,
				location: this.form.querySelector("[name='location']").value,
				unknown_time: this.form.querySelector("[name='unknownTime']").checked,
				user_email: this.form.querySelector("[name='userEmail']").value,
				is_full_birth_name: this.form.querySelector("[name='isFullBirthName']").checked
			}),
		});

		if (!apiRes.ok) {
			const errData = await apiRes.json();
			throw new Error(`API Error ${apiRes.status}: ${errData.detail}`);
		}
		return await apiRes.json();
	},

	async fetchAndDisplayAIReading(chartData) {
		try {
			const userInputs = {
				full_name: this.form.querySelector("[name='fullName']").value,
				birth_date: this.form.querySelector("[name='birthDate']").value,
				birth_time: this.form.querySelector("[name='birthTime']").value,
				location: this.form.querySelector("[name='location']").value,
				user_email: this.form.querySelector("[name='userEmail']").value
			};

			let chartImageBase64 = null;
			// Removed image generation logic as it's not needed without email

			const headers = { "Content-Type": "application/json" };
			const urlParams = new URLSearchParams(window.location.search);
			const adminSecret = urlParams.get('admin_secret');
			if (adminSecret) {
				headers['X-Admin-Secret'] = adminSecret;
			}

            // This fetch now waits for the full reading before proceeding
			const readingRes = await fetch(this.API_URLS.reading, {
				method: "POST",
				headers: headers,
				body: JSON.stringify({
					chart_data: chartData,
					unknown_time: chartData.unknown_time,
					user_inputs: userInputs,
					chart_image_base64: null // Not sending image data anymore
				})
			});

			if (!readingRes.ok) {
                let errorData;
                try {
                    errorData = await readingRes.json();
                } catch (jsonErr) {
                    const text = await readingRes.text();
                    console.error("Failed to parse error response as JSON:", text);
                    errorData = { detail: 'AI Reading service failed to respond correctly.' };
                }
                
                // Check if it's a subscription error
                if (readingRes.status === 402 && errorData.detail && errorData.detail.error === "Subscription required") {
                    // Display friendly subscription message instead of error
                    const message = errorData.detail.message || 'A monthly subscription is required for comprehensive full readings and other premium services.';
                    this.geminiOutput.innerHTML = `
                        <div style="padding: 20px; background-color: rgba(27, 108, 168, 0.1); border-left: 4px solid #1b6ca8; margin-bottom: 15px; border-radius: 4px;">
                            <h3 style="margin-top: 0; color: #1b6ca8;">Unlock Full Readings & Premium Features</h3>
                            <p style="color: rgba(255, 255, 255, 0.9); margin-bottom: 1em;">${message}</p>
                            <p style="color: rgba(255, 255, 255, 0.8); margin-bottom: 1em;">Good news! You can still get <strong>unlimited free snapshot readings</strong> with your chart calculation. The snapshot provides quick insights into your core patterns.</p>
                            <div style="margin-top: 1.5em;">
                                <a href="#pricing-section" class="button primary" onclick="window.scrollTo({top: document.getElementById('pricing-section').offsetTop - 100, behavior: 'smooth'})">View Pricing & Subscribe</a>
                            </div>
                        </div>
                    `;
                    if (this.copyReadingBtn) {
                        this.copyReadingBtn.style.display = 'none';
                    }
                    this.setLoadingState(false);
                    return; // Exit early - don't throw error
                }
                
                throw new Error(errorData.detail || 'AI Reading service failed.');
            }

			let readingResult;
			try {
				readingResult = await readingRes.json();
				console.log("Reading response received:", readingResult); // Debug log
			} catch (jsonErr) {
				const text = await readingRes.text();
				console.error("Failed to parse response as JSON:", text);
				throw new Error("Invalid response format from server. Please try again.");
			}
            
			// Check if this is the new async processing response
			if (readingResult && readingResult.status === "processing") {
				// Display the processing message with instructions
				const message = readingResult.message || "Your comprehensive astrology reading is being generated.";
				const instructions = readingResult.instructions || "You can safely close this page - your reading will be sent to your email when ready.";
				const estimatedTime = readingResult.estimated_time || "up to 15 minutes";
				const email = readingResult.email || "your email";
				const chartHash = readingResult.chart_hash;
				
				this.geminiOutput.innerHTML = `
					<div style="padding: 20px; background-color: #f0f7ff; border-left: 4px solid #1b6ca8; margin-bottom: 15px;">
						<h3 style="margin-top: 0; color: #1b6ca8;">⏳ ${message}</h3>
						<p style="margin-bottom: 10px; color: #2c3e50;"><strong style="color: #2c3e50;">Estimated time:</strong> ${estimatedTime}</p>
						<p style="margin-bottom: 0; color: #2c3e50;">${instructions}</p>
						${email ? `<p style="margin-top: 10px; font-size: 0.9em; color: #34495e;">Your reading will be sent to: <strong style="color: #1b6ca8;">${email}</strong></p>` : ''}
						<p id="pollingStatus" style="margin-top: 10px; font-size: 0.85em; color: #666; font-style: italic;">Checking for completed reading...</p>
					</div>
					<div style="padding: 20px; background-color: #f8f4ff; border-left: 4px solid #7c3aed; margin-top: 15px; border-radius: 4px;">
						<h4 style="margin-top: 0; color: #7c3aed; font-size: 1.1em;">💬 Want to Go Deeper Into Your Chart?</h4>
						<p style="margin-bottom: 12px; color: #5b21b6; line-height: 1.5;">
							Click <strong style="color: #7c3aed;">"Save Chart"</strong> to create a free account and unlock the ability to have an ongoing conversation with our AI astrologer about YOUR specific chart.
						</p>
						<ul style="margin: 0 0 12px 0; padding-left: 20px; color: #5b21b6; line-height: 1.7;">
							<li><strong style="color: #7c3aed;">Ask follow-up questions</strong> – "Why do I self-sabotage when things are going well?"</li>
							<li><strong style="color: #7c3aed;">Explore your shadow patterns</strong> – Understand the unconscious behaviors holding you back</li>
							<li><strong style="color: #7c3aed;">Discover your highest potential</strong> – Find the specific path to becoming the best version of your unique self</li>
						</ul>
						<p style="margin-bottom: 0; font-size: 0.9em; color: #7c3aed;">
							<em>Your chart data stays private and is only used to provide you with personalized insights.</em>
						</p>
					</div>
				`;
				if (this.copyReadingBtn) {
					this.copyReadingBtn.style.display = 'none'; // Hide copy button while processing
				}
				
				// Start polling for the completed reading if we have a chart hash
				if (chartHash) {
					this.startPollingForReading(chartHash);
				}
				return; // Exit early after showing processing message
			} else if (readingResult && readingResult.gemini_reading) {
				// Legacy format: reading is immediately available
				this.geminiOutput.innerHTML = readingResult.gemini_reading.replace(/\n/g, '<br>');
				if (this.copyReadingBtn) {
					this.copyReadingBtn.style.display = 'inline-block'; // Show copy button
				}
				// Show popup for free users about saving and chatting
				this.showSaveAndChatPopup();
			} else {
				// No reading available - log for debugging
				console.warn("Unexpected response format:", readingResult);
				console.warn("Response status:", readingResult?.status);
				console.warn("Has gemini_reading:", !!readingResult?.gemini_reading);
				
				// Check if there's an error message in the response
				if (readingResult && readingResult.detail) {
					// Check if it's a subscription error
					if (readingResult.detail.error === "Subscription required") {
						this.geminiOutput.innerHTML = `
							<div style="padding: 20px; background-color: rgba(27, 108, 168, 0.1); border-left: 4px solid #1b6ca8; margin-bottom: 15px;">
								<h3 style="margin-top: 0; color: #1b6ca8;">Subscription Required</h3>
								<p style="color: rgba(255, 255, 255, 0.9);">${readingResult.detail.message || 'A monthly subscription is required for comprehensive full readings.'}</p>
								<p style="color: rgba(255, 255, 255, 0.7); margin-top: 1em;">Good news! You can still get <strong>unlimited free snapshot readings</strong> with your chart calculation. The snapshot provides quick insights into your core patterns.</p>
								<div style="margin-top: 1.5em;">
									<a href="#pricing-section" class="button primary" onclick="window.scrollTo({top: document.getElementById('pricing-section').offsetTop - 100, behavior: 'smooth'})">View Pricing & Subscribe</a>
								</div>
							</div>
						`;
						if (typeof AuthManager !== 'undefined' && AuthManager.showUpgradePrompt) {
							AuthManager.showUpgradePrompt('reading');
						}
					} else {
						this.geminiOutput.innerHTML = `<div style="padding: 15px; background-color: #fee; border-left: 4px solid #e53e3e; color: #c33;">
							<strong>Error:</strong> ${readingResult.detail.message || readingResult.detail}
						</div>`;
					}
				} else {
					this.geminiOutput.innerHTML = "The AI reading could not be generated at this time.";
				}
				if (this.copyReadingBtn) {
					this.copyReadingBtn.style.display = 'none'; // Hide copy button
				}
			}

		} catch (err) {
			console.error("Error in fetchAndDisplayAIReading:", err);
			console.error("Error details:", {
				message: err.message,
				stack: err.stack,
				name: err.name
			});
			// Don't show error for subscription-related messages - they're handled above
			if (err.message && err.message.includes('Subscription required')) {
				// Already handled, don't show error
				return;
			}
			this.geminiOutput.innerHTML = `<div style="padding: 15px; background-color: #fee; border-left: 4px solid #e53e3e; color: #c33;">
				<strong>Error:</strong> The AI reading is currently unavailable. ${err.message}
			</div>`;
            if (this.copyReadingBtn) {
                this.copyReadingBtn.style.display = 'none'; // Hide copy button on error
            }
		} finally {
            this.setLoadingState(false); // Stop loading indicator here
        }
	},

	startPollingForReading(chartHash) {
		// Clear any existing polling interval
		if (this.pollingInterval) {
			clearInterval(this.pollingInterval);
		}
		
		// Track start time for accurate elapsed time calculation
		const startTime = Date.now();
		const maxElapsedMs = 15 * 60 * 1000; // 15 minutes in milliseconds
		const pollInterval = 5000; // Poll every 5 seconds
		
		const pollForReading = async () => {
			// Calculate actual elapsed time
			const elapsedMs = Date.now() - startTime;
			const elapsedSeconds = Math.floor(elapsedMs / 1000);
			const elapsedMinutes = Math.floor(elapsedSeconds / 60);
			
			try {
				const response = await fetch(`${this.API_URLS.reading.replace('/generate_reading', '')}/get_reading/${chartHash}`);
				
				if (!response.ok) {
					console.warn(`Polling failed with status: ${response.status} (${elapsedSeconds}s elapsed)`);
					if (elapsedMs >= maxElapsedMs) {
						this.stopPolling();
						const statusEl = document.getElementById('pollingStatus');
						if (statusEl) {
							statusEl.textContent = "Reading generation is taking longer than expected. Please check your email.";
						}
					}
					return;
				}
				
				const result = await response.json();
				
				if (result.status === "completed" && result.reading) {
					// Reading is ready!
					this.stopPolling();
					this.geminiOutput.innerHTML = result.reading.replace(/\n/g, '<br>');
					if (this.copyReadingBtn) {
						this.copyReadingBtn.style.display = 'inline-block'; // Show copy button
					}
					console.log("Reading successfully retrieved and displayed!");
					// Show popup for free users about saving and chatting
					this.showSaveAndChatPopup();
				} else {
					// Still processing
					const statusEl = document.getElementById('pollingStatus');
					if (statusEl) {
						// Show seconds for first minute, then minutes
						let elapsedText;
						if (elapsedSeconds < 60) {
							elapsedText = `${elapsedSeconds} second${elapsedSeconds !== 1 ? 's' : ''} elapsed`;
						} else {
							elapsedText = `${elapsedMinutes} minute${elapsedMinutes !== 1 ? 's' : ''} elapsed`;
						}
						statusEl.textContent = `Still generating... (${elapsedText})`;
					}
					
					if (elapsedMs >= maxElapsedMs) {
						this.stopPolling();
						if (statusEl) {
							statusEl.textContent = "Reading generation is taking longer than expected. Please check your email.";
						}
					}
				}
			} catch (error) {
				const elapsedMs = Date.now() - startTime;
				const elapsedSeconds = Math.floor(elapsedMs / 1000);
				console.error(`Polling error (${elapsedSeconds}s elapsed):`, error);
				if (elapsedMs >= maxElapsedMs) {
					this.stopPolling();
					const statusEl = document.getElementById('pollingStatus');
					if (statusEl) {
						statusEl.textContent = "Unable to check reading status. Please check your email.";
					}
				}
			}
		};
		
		// Start polling immediately, then every 5 seconds
		pollForReading();
		this.pollingInterval = setInterval(pollForReading, pollInterval);
	},

	stopPolling() {
		if (this.pollingInterval) {
			clearInterval(this.pollingInterval);
			this.pollingInterval = null;
		}
	},

	async loadAndDrawTransitChart() {
		try {
			// Get user's current location
			let location = await this.getUserLocation();
			if (!location) {
				// Fallback to a default location if geolocation fails
				console.warn("Could not get user location, using default");
				location = "Boston, MA, USA";
			}
			
			const now = new Date();
			const apiRes = await fetch(this.API_URLS.calculate, {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					full_name: "Current Transits",
					year: now.getFullYear(),
					month: now.getMonth() + 1,
					day: now.getDate(),
					hour: now.getHours(),
					minute: now.getMinutes(),
					location: location,
					unknown_time: false
				}),
			});
			if (!apiRes.ok) {
				const errData = await apiRes.json();
				throw new Error(`API Error ${apiRes.status}: ${errData.detail}`);
			}
			const transitData = await apiRes.json();
			this.drawChartWheel(transitData, 'sidereal-transit-wheel-svg', 'sidereal');
			this.drawChartWheel(transitData, 'tropical-transit-wheel-svg', 'tropical');

			const legendHtml = this.getLegendHtml();
			const container = document.querySelector('#transit-chart .chart-wheels-wrapper');
			const oldLegend = container.nextElementSibling;
			if (oldLegend && oldLegend.classList.contains('glyph-legend-details')) {
				oldLegend.remove();
			}
			container.insertAdjacentHTML('afterend', legendHtml);

		} catch (err) {
			console.error("Failed to load transit chart:", err);
			document.getElementById('sidereal-transit-wheel-svg').innerHTML = '<text x="500" y="500" fill="white" font-size="20" text-anchor="middle">Could not load transits.</text>';
		}
	},

	async getUserLocation() {
		// Try to get user's location using browser geolocation API
		return new Promise((resolve) => {
			if (!navigator.geolocation) {
				console.warn("Geolocation is not supported by this browser");
				resolve(null);
				return;
			}

			// Set a timeout for geolocation (5 seconds)
			const timeout = setTimeout(() => {
				console.warn("Geolocation request timed out");
				resolve(null);
			}, 5000);

			navigator.geolocation.getCurrentPosition(
				async (position) => {
					clearTimeout(timeout);
					const lat = position.coords.latitude;
					const lng = position.coords.longitude;
					
					// Reverse geocode to get location name
					try {
						// Use Nominatim (free reverse geocoding)
						const response = await fetch(
							`https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lng}&format=json&addressdetails=1`,
							{
								headers: {
									'User-Agent': 'SynthesisAstrology/1.0'
								}
							}
						);
						
						if (response.ok) {
							const data = await response.json();
							const address = data.address || {};
							
							// Build location string from address components
							let locationParts = [];
							if (address.city) locationParts.push(address.city);
							else if (address.town) locationParts.push(address.town);
							else if (address.village) locationParts.push(address.village);
							
							if (address.state) locationParts.push(address.state);
							else if (address.region) locationParts.push(address.region);
							
							if (address.country) {
								const country = address.country_code ? address.country_code.toUpperCase() : address.country;
								locationParts.push(country);
							}
							
							if (locationParts.length > 0) {
								resolve(locationParts.join(', '));
							} else {
								// Fallback: use coordinates
								resolve(`${lat.toFixed(4)}, ${lng.toFixed(4)}`);
							}
						} else {
							// Fallback: use coordinates
							resolve(`${lat.toFixed(4)}, ${lng.toFixed(4)}`);
						}
					} catch (error) {
						console.warn("Reverse geocoding failed:", error);
						// Fallback: use coordinates
						resolve(`${lat.toFixed(4)}, ${lng.toFixed(4)}`);
					}
				},
				(error) => {
					clearTimeout(timeout);
					console.warn("Geolocation error:", error.message);
					resolve(null);
				},
				{
					enableHighAccuracy: false,
					timeout: 5000,
					maximumAge: 300000 // Cache for 5 minutes
				}
			);
		});
	},

	setLoadingState(isLoading) {
		this.submitBtn.disabled = isLoading;
		// Updated button text for synchronous loading
		this.submitBtn.innerText = isLoading ? "Generating AI Synthesis..." : "Generate My Reading";

		if (isLoading) {
			this.resultsContainer.style.display = 'none';
			if (this.copyReadingBtn) {
                this.copyReadingBtn.style.display = 'none';
            }
		}
	},

	displayInitialResults(chartData) {
		// Ensure results container is visible
		this.resultsContainer.style.display = 'block';
		
        // Display snapshot reading if available
		console.log("Chart data received:", chartData);
		console.log("Snapshot reading:", chartData.snapshot_reading);
		console.log("Snapshot title element:", this.snapshotTitle);
		console.log("Snapshot output element:", this.snapshotOutput);
		
		// Check if snapshot reading exists and is not null/empty
		const hasSnapshot = chartData.snapshot_reading && 
		                    chartData.snapshot_reading !== null && 
		                    chartData.snapshot_reading !== undefined &&
		                    String(chartData.snapshot_reading).trim() !== '';
		
		if (hasSnapshot) {
			console.log("Displaying snapshot reading");
			if (this.snapshotTitle) {
				this.snapshotTitle.style.display = 'block';
				console.log("Snapshot title display set to block");
			} else {
				console.error("Snapshot title element not found!");
			}
			if (this.snapshotOutput) {
				const snapshotText = String(chartData.snapshot_reading).replace(/\n/g, '<br>');
				// Check if user has subscription (if AuthManager is available)
				const hasSubscription = typeof AuthManager !== 'undefined' && AuthManager.hasActiveSubscription && AuthManager.hasActiveSubscription();
				
				if (!hasSubscription) {
					// Add upgrade prompt after snapshot
					this.snapshotOutput.innerHTML = snapshotText + `
						<div style="margin-top: 2em; padding: 1.5em; background-color: rgba(27, 108, 168, 0.1); border-left: 4px solid #1b6ca8; border-radius: 4px;">
							<h4 style="margin-top: 0; color: #1b6ca8;">Want a Deeper Analysis?</h4>
							<p style="color: rgba(255, 255, 255, 0.9); margin-bottom: 1em;">This is your free snapshot reading. Subscribe to get a comprehensive 15+ page full reading covering all aspects of your chart, plus unlimited chat conversations with our AI astrologer.</p>
							<a href="#pricing-section" class="button primary" onclick="window.scrollTo({top: document.getElementById('pricing-section').offsetTop - 100, behavior: 'smooth'})">View Pricing & Subscribe</a>
						</div>
					`;
				} else {
					this.snapshotOutput.innerHTML = snapshotText;
				}
				console.log("Snapshot output populated");
			} else {
				console.error("Snapshot output element not found!");
			}
		} else {
			console.log("Snapshot reading not available or empty");
			if (this.snapshotTitle) {
				this.snapshotTitle.style.display = 'none';
			}
		}
		
        // Updated initial message for synchronous loading
		this.geminiOutput.innerHTML = "Generating AI Synthesis... This deep analysis can take up to 10 minutes. Please do not leave this page while it loads.";
		this.renderTextResults(chartData);

		this.geminiTitle.parentElement.style.display = 'block';
		this.resultsTitle.parentElement.style.display = 'block';
        if(this.copyReadingBtn) { // Hide copy button initially
            this.copyReadingBtn.style.display = 'none';
        }
		
		// Add save chart button if AuthManager is available
		if (typeof AuthManager !== 'undefined') {
			AuthManager.addSaveChartButton();
			AuthManager.updateSaveChartButton(false);
		}


		const chartWheelsWrapper = document.querySelector('#results .chart-wheels-wrapper');
		const chartPlaceholder = document.getElementById('chart-placeholder');

		if (!chartData.unknown_time) {
			this.wheelTitle.parentElement.style.display = 'block';
			chartWheelsWrapper.style.display = 'grid';
			chartPlaceholder.style.display = 'none';

			this.drawChartWheel(chartData, 'sidereal-wheel-svg', 'sidereal');
			this.drawChartWheel(chartData, 'tropical-wheel-svg', 'tropical');
			
			const legendHtml = this.getLegendHtml();
			const oldLegend = chartWheelsWrapper.nextElementSibling;
			if (oldLegend && oldLegend.classList.contains('glyph-legend-details')) {
				oldLegend.remove();
			}
			chartWheelsWrapper.insertAdjacentHTML('afterend', legendHtml);
		} else {
			this.wheelTitle.parentElement.style.display = 'block';
			chartWheelsWrapper.style.display = 'none';
			chartPlaceholder.style.display = 'block';
            // Also clear the SVGs explicitly if time is unknown
             if (this.siderealWheelSvg) this.siderealWheelSvg.innerHTML = '';
             if (this.tropicalWheelSvg) this.tropicalWheelSvg.innerHTML = '';
		}

		this.resultsContainer.style.display = 'block';
		
		setTimeout(() => {
			this.resultsContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
		}, 100);
	},
    
	copyReadingToClipboard() {
        if (!this.geminiOutput) return;

        // Create a temporary div to decode HTML entities
        const tempDiv = document.createElement('div');
        // Convert <br> tags to newlines first, then decode HTML entities
        const htmlWithNewlines = this.geminiOutput.innerHTML.replace(/<br\s*\/?>/gi, '\n');
        tempDiv.innerHTML = htmlWithNewlines;
        // textContent automatically decodes HTML entities (&lt; -> <, &gt; -> >, &amp; -> &, etc.)
        const textToCopy = tempDiv.textContent || tempDiv.innerText || '';

        const textArea = document.createElement('textarea');
        textArea.value = textToCopy;
        textArea.style.position = 'fixed'; // Prevent scrolling to bottom of page in MS Edge.
        textArea.style.left = '-9999px';
        textArea.style.top = '0';
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();

        try {
            // Use document.execCommand for broader compatibility
            document.execCommand('copy'); 
            this.copyReadingBtn.innerText = 'Copied!';
            setTimeout(() => {
                this.copyReadingBtn.innerText = 'Copy Reading';
            }, 2000);
        } catch (err) {
            console.error('Failed to copy text: ', err);
            this.copyReadingBtn.innerText = 'Copy Failed';
             setTimeout(() => {
                this.copyReadingBtn.innerText = 'Copy Reading';
            }, 2000);
        }

        document.body.removeChild(textArea);
    },

	renderTextResults(res) {
		// --- SIDEREAL REPORT ---
		let siderealOut = `=== SIDEREAL CHART: ${res.name || 'N/A'} ===\n`;
		siderealOut += `- UTC Date & Time: ${res.utc_datetime || 'N/A'}${res.unknown_time ? ' (Noon Estimate)' : ''}\n`;
		siderealOut += `- Location: ${res.location || 'N/A'}\n`;
		siderealOut += `- Day/Night Determination: ${res.day_night_status || 'N/A'}\n\n`;
		
		siderealOut += `--- CHINESE ZODIAC ---\n`;
		siderealOut += `- Your sign is the ${res.chinese_zodiac || 'N/A'}\n\n`;

		siderealOut += `--- NUMEROLOGY REPORT ---\n`;
		if (res.numerology_analysis) {
			siderealOut += `- Life Path Number: ${res.numerology_analysis.life_path_number || 'N/A'}\n`;
			siderealOut += `- Day Number: ${res.numerology_analysis.day_number || 'N/A'}\n`;
			siderealOut += `- Lucky Number: ${res.numerology_analysis.lucky_number || 'N/A'}\n`;
			
			if (res.numerology_analysis.name_numerology) {
				siderealOut += `\n-- NAME NUMEROLOGY --\n`;
				siderealOut += `- Expression (Destiny) Number: ${res.numerology_analysis.name_numerology.expression_number || 'N/A'}\n`;
				siderealOut += `- Soul Urge Number: ${res.numerology_analysis.name_numerology.soul_urge_number || 'N/A'}\n`;
				siderealOut += `- Personality Number: ${res.numerology_analysis.name_numerology.personality_number || 'N/A'}\n`;
			}
		}
		
		if (res.sidereal_chart_analysis) {
			siderealOut += `\n-- SIDEREAL CHART ANALYSIS --\n`;
			siderealOut += `- Chart Ruler: ${res.sidereal_chart_analysis.chart_ruler || 'N/A'}\n`;
			siderealOut += `- Dominant Sign: ${res.sidereal_chart_analysis.dominant_sign || 'N/A'}\n`;
			siderealOut += `- Dominant Element: ${res.sidereal_chart_analysis.dominant_element || 'N/A'}\n`;
			siderealOut += `- Dominant Modality: ${res.sidereal_chart_analysis.dominant_modality || 'N/A'}\n`;
			siderealOut += `- Dominant Planet: ${res.sidereal_chart_analysis.dominant_planet || 'N/A'}\n\n`;
		}
		
		siderealOut += `--- MAJOR POSITIONS ---\n`;
		if (res.sidereal_major_positions) {
			res.sidereal_major_positions.forEach(p => {
				let line = `- ${p.name}: ${p.position}`;
				if (!['Ascendant', 'Descendant', 'Midheaven (MC)', 'Imum Coeli (IC)', 'South Node'].includes(p.name)) {
					line += ` (${p.percentage}%)`;
				}
				if (p.retrograde) { line += " (Rx)"; }
				if (p.house_info) { line += ` ${p.house_info}`; }
				siderealOut += `${line}\n`;
			});
		}

		if (res.sidereal_retrogrades && res.sidereal_retrogrades.length > 0) {
			siderealOut += `\n--- RETROGRADE PLANETS (Energy turned inward) ---\n`;
			res.sidereal_retrogrades.forEach(p => {
				siderealOut += `- ${p.name}\n`;
			});
		}

		siderealOut += `\n--- MAJOR ASPECTS (ranked by influence score) ---\n`;
		if (res.sidereal_aspects && res.sidereal_aspects.length > 0) {
			res.sidereal_aspects.forEach(a => { siderealOut += `- ${a.p1_name} ${a.type} ${a.p2_name} (orb ${a.orb}, score ${a.score})\n`; });
		} else {
			siderealOut += "- No major aspects detected.\n";
		}
		
		siderealOut += `\n--- ASPECT PATTERNS ---\n`;
		if (res.sidereal_aspect_patterns && res.sidereal_aspect_patterns.length > 0) {
			res.sidereal_aspect_patterns.forEach(p => {
				let line = `- ${p.description}`;
				if (p.orb) {
					line += ` (avg orb ${p.orb})`;
				}
				if (p.score) {
					line += ` (score ${p.score})`;
				}
				siderealOut += `${line}\n`;
			});
		} else {
			siderealOut += "- No major aspect patterns detected.\n";
		}

		if (!res.unknown_time) {
			siderealOut += `\n--- ADDITIONAL POINTS & ANGLES ---\n`;
			if (res.sidereal_additional_points) {
				res.sidereal_additional_points.forEach(p => {
					let line = `- ${p.name}: ${p.info}`;
					if (p.retrograde) { line += " (Rx)"; }
					siderealOut += `${line}\n`;
				});
			}
			siderealOut += `\n--- HOUSE RULERS ---\n`;
			if (res.house_rulers) {
				for (const [house, info] of Object.entries(res.house_rulers)) { siderealOut += `- ${house}: ${info}\n`; }
			}
			siderealOut += `\n--- HOUSE SIGN DISTRIBUTIONS ---\n`;
			if (res.house_sign_distributions) {
				for (const [house, segments] of Object.entries(res.house_sign_distributions)) {
					siderealOut += `${house}:\n`;
					if (segments && segments.length > 0) {
						segments.forEach(seg => { siderealOut += `      - ${seg}\n`; });
					}
				}
			}
		} else {
			siderealOut += `\n- (House Rulers, House Distributions, and some additional points require a known birth time and are not displayed.)\n`;
		}

		document.getElementById('sidereal-output').innerText = siderealOut;


		// --- TROPICAL REPORT ---
		let tropicalOut = '';
		if (res.tropical_major_positions && res.tropical_major_positions.length > 0) {
			tropicalOut += `=== TROPICAL CHART ===\n\n`;
			if (res.tropical_chart_analysis) {
				tropicalOut += `-- CHART ANALYSIS --\n`;
				tropicalOut += `- Dominant Sign: ${res.tropical_chart_analysis.dominant_sign || 'N/A'}\n`;
				tropicalOut += `- Dominant Element: ${res.tropical_chart_analysis.dominant_element || 'N/A'}\n`;
				tropicalOut += `- Dominant Modality: ${res.tropical_chart_analysis.dominant_modality || 'N/A'}\n`;
				tropicalOut += `- Dominant Planet: ${res.tropical_chart_analysis.dominant_planet || 'N/A'}\n\n`;
			}
			tropicalOut += `--- MAJOR POSITIONS ---\n`;
			res.tropical_major_positions.forEach(p => {
				let line = `- ${p.name}: ${p.position}`;
				if (!['Ascendant', 'Descendant', 'Midheaven (MC)', 'Imum Coeli (IC)', 'South Node'].includes(p.name)) {
					line += ` (${p.percentage}%)`;
				}
				if (p.retrograde) { line += " (Rx)"; }
				if (p.house_info) { line += ` ${p.house_info}`; }
				tropicalOut += `${line}\n`;
			});

			if (res.tropical_retrogrades && res.tropical_retrogrades.length > 0) {
				tropicalOut += `\n--- RETROGRADE PLANETS (Energy turned inward) ---\n`;
				res.tropical_retrogrades.forEach(p => {
					tropicalOut += `- ${p.name}\n`;
				});
			}

			tropicalOut += `\n--- MAJOR ASPECTS (ranked by influence score) ---\n`;
			if (res.tropical_aspects && res.tropical_aspects.length > 0) {
				res.tropical_aspects.forEach(a => { tropicalOut += `- ${a.p1_name} ${a.type} ${a.p2_name} (orb ${a.orb}, score ${a.score})\n`; });
			} else {
				tropicalOut += "- No major aspects detected.\n";
			}
			
			tropicalOut += `\n--- ASPECT PATTERNS ---\n`;
			if (res.tropical_aspect_patterns && res.tropical_aspect_patterns.length > 0) {
				res.tropical_aspect_patterns.forEach(p => {
					let line = `- ${p.description}`;
					if (p.orb) {
						line += ` (avg orb ${p.orb})`;
					}
					if (p.score) {
						line += ` (score ${p.score})`;
					}
					tropicalOut += `${line}\n`;
				});
			} else {
				tropicalOut += "- No major aspect patterns detected.\n";
			}
			
			if (!res.unknown_time) {
				tropicalOut += `\n--- ADDITIONAL POINTS & ANGLES ---\n`;
				if (res.tropical_additional_points) {
					res.tropical_additional_points.forEach(p => {
						let line = `- ${p.name}: ${p.info}`;
						if (p.retrograde) { line += " (Rx)"; }
						tropicalOut += `${line}\n`;
					});
				}
			}
		}
		document.getElementById('tropical-output').innerText = tropicalOut;
	},
	
	drawChartWheel(data, svgId, chartType) {
		const svg = document.getElementById(svgId);
		if (!svg) return;
		svg.innerHTML = ''; // Clear previous chart

		const centerX = 500, centerY = 500;
		const zodiacRadius = 450, houseRingRadius = 350, innerRadius = 150;
		
		const positions = data[`${chartType}_major_positions`];
		const aspects = data[`${chartType}_aspects`];
		const houseCusps = data[`${chartType}_house_cusps`];

		// Check if Ascendant data is available (needed for rotation)
		const ascendant = positions.find(p => p.name === 'Ascendant');
		if (!ascendant || ascendant.degrees === null) {
            // Display message directly in the SVG area if time is unknown
			svg.innerHTML = '<text x="500" y="500" font-size="20" fill="white" text-anchor="middle">Chart wheel requires birth time.</text>';
			return; // Stop drawing if no Ascendant
		}
		
		// Rotation based on Ascendant degree
		const rotation = ascendant.degrees - 180; 

		const mainGroup = document.createElementNS(this.SVG_NS, 'g');
		mainGroup.setAttribute('transform', `rotate(${rotation} ${centerX} ${centerY})`);
		svg.appendChild(mainGroup);

		// Helper to convert degrees to SVG coordinates
		const degreeToCartesian = (radius, angleDegrees) => {
			const angleRadians = -angleDegrees * (Math.PI / 180); // SVG rotation is clockwise, math is counter-clockwise
			return { x: centerX + radius * Math.cos(angleRadians), y: centerY + radius * Math.sin(angleRadians) };
		};

		// Draw Aspect Lines
		if (aspects) {
			aspects.forEach(aspect => {
				// Ensure degrees exist for both planets involved in the aspect
				if (aspect.p1_degrees === null || aspect.p2_degrees === null) return; 
				const p1Coords = degreeToCartesian(innerRadius, aspect.p1_degrees);
				const p2Coords = degreeToCartesian(innerRadius, aspect.p2_degrees);
				const line = document.createElementNS(this.SVG_NS, 'line');
				line.setAttribute('x1', p1Coords.x); line.setAttribute('y1', p1Coords.y);
				line.setAttribute('x2', p2Coords.x); line.setAttribute('y2', p2Coords.y);
				const aspectClass = aspect.type.toLowerCase().replace(' ', '-'); // e.g., 'square', 'grand-trine'
				line.setAttribute('class', `aspect-line aspect-${aspectClass}`);
				mainGroup.appendChild(line);
			});
		}

		// Draw Concentric Circles
		[zodiacRadius, houseRingRadius, innerRadius].forEach(r => {
			const circle = document.createElementNS(this.SVG_NS, 'circle');
			circle.setAttribute('cx', centerX); circle.setAttribute('cy', centerY);
			circle.setAttribute('r', r);
			circle.setAttribute('class', 'wheel-circle');
			mainGroup.appendChild(circle);
		});
		
		// Draw Zodiac Signs & Dividers
		const glyphRadius = houseRingRadius + (zodiacRadius - houseRingRadius) / 2; // Midpoint of the zodiac band
		if (chartType === 'sidereal' && data.true_sidereal_signs) {
			// Sidereal: Use variable sign boundaries
			data.true_sidereal_signs.forEach(sign => {
				const [name, start, end] = sign;
				// Draw divider line at the start of the sign
				const p1 = degreeToCartesian(houseRingRadius, start);
				const p2 = degreeToCartesian(zodiacRadius, start);
				const line = document.createElementNS(this.SVG_NS, 'line');
				line.setAttribute('x1', p1.x); line.setAttribute('y1', p1.y);
				line.setAttribute('x2', p2.x); line.setAttribute('y2', p2.y);
				line.setAttribute('class', 'zodiac-divider');
				mainGroup.appendChild(line);

				// Place glyph in the middle of the sign
				const midAngle = start + ((end - start + 360) % 360) / 2; // Handle wrap-around
				const textCoords = degreeToCartesian(glyphRadius, midAngle);
				const text = document.createElementNS(this.SVG_NS, 'text');
				text.setAttribute('x', textCoords.x); text.setAttribute('y', textCoords.y);
				text.setAttribute('class', 'zodiac-glyph');
				text.setAttribute('transform', `rotate(${-rotation} ${textCoords.x} ${textCoords.y})`); // Counter-rotate text
				text.textContent = this.ZODIAC_GLYPHS[name];
				mainGroup.appendChild(text);
			});
		} else { // Tropical Signs: Equal 30-degree divisions
			for (let i = 0; i < 12; i++) {
				const start = i * 30;
				// Draw divider line
				const p1 = degreeToCartesian(houseRingRadius, start);
				const p2 = degreeToCartesian(zodiacRadius, start);
				const line = document.createElementNS(this.SVG_NS, 'line');
				line.setAttribute('x1', p1.x); line.setAttribute('y1', p1.y);
				line.setAttribute('x2', p2.x); line.setAttribute('y2', p2.y);
				line.setAttribute('class', 'zodiac-divider');
				mainGroup.appendChild(line);

				// Place glyph in the middle (15 degrees into the sign)
				const midAngle = start + 15;
				const textCoords = degreeToCartesian(glyphRadius, midAngle);
				const text = document.createElementNS(this.SVG_NS, 'text');
				text.setAttribute('x', textCoords.x); text.setAttribute('y', textCoords.y);
				text.setAttribute('class', 'zodiac-glyph');
				text.setAttribute('transform', `rotate(${-rotation} ${textCoords.x} ${textCoords.y})`); // Counter-rotate text
				// FIX: Look up the glyph from the ZODIAC_GLYPHS map using the name from TROPICAL_ZODIAC_ORDER
                const signName = this.TROPICAL_ZODIAC_ORDER[i];
				text.textContent = this.ZODIAC_GLYPHS[signName]; 
				mainGroup.appendChild(text);
			}
		}


		// Draw House Cusps & Numbers
		if (houseCusps && houseCusps.length === 12) {
			// Draw cusp lines
			houseCusps.forEach((cuspDegrees, i) => {
				const p1 = degreeToCartesian(innerRadius, cuspDegrees);
				const p2 = degreeToCartesian(houseRingRadius, cuspDegrees);
				const line = document.createElementNS(this.SVG_NS, 'line');
				line.setAttribute('x1', p1.x); line.setAttribute('y1', p1.y);
				line.setAttribute('x2', p2.x); line.setAttribute('y2', p2.y);
				// Make Asc/MC/Desc/IC lines thicker
				line.setAttribute('class', (i % 3 === 0) ? 'house-cusp major' : 'house-cusp'); 
				mainGroup.appendChild(line);
			});
			// Draw house numbers in the middle of each house
			for (let i = 0; i < 12; i++) {
				const startAngle = houseCusps[i];
				const endAngle = houseCusps[(i + 1) % 12];
				// Calculate midpoint angle, handling wrap-around from 360 to 0
				let midAngle = (startAngle + endAngle) / 2;
				if (endAngle < startAngle) midAngle = ((startAngle + endAngle + 360) / 2) % 360; 
				const textCoords = degreeToCartesian(innerRadius + 25, midAngle); // Place number inside inner circle
				const text = document.createElementNS(this.SVG_NS, 'text');
				text.setAttribute('x', textCoords.x); text.setAttribute('y', textCoords.y);
				text.setAttribute('class', 'house-number');
				text.setAttribute('transform', `rotate(${-rotation} ${textCoords.x} ${textCoords.y})`); // Counter-rotate text
				text.textContent = i + 1;
				mainGroup.appendChild(text);
			}
		}
		
		// Draw Planets/Points with adjusted positions to avoid overlap
		if (positions) {
			const outerGlyphRadius = zodiacRadius + 35; // Position glyphs outside the wheel
			const glyphConnectorRadius = zodiacRadius; // Line starts from outer circle
			const minGlyphSeparation = 8; // Minimum degrees between glyphs

			// Filter valid planets and sort by degree
			let planets = positions
				.filter(p => p.degrees !== null && this.PLANET_GLYPHS[p.name])
				.sort((a, b) => a.degrees - b.degrees);

			// Adjust positions iteratively to prevent overlap
			if (planets.length > 0) {
				// Initialize adjusted degrees
				planets.forEach(p => p.adjustedDegrees = p.degrees); 

				// Run adjustment loop twice for better distribution
				for (let k = 0; k < 2; k++) { 
					// Check wrap-around overlap (last planet vs first planet)
					let last = planets[planets.length - 1];
					let first = planets[0];
					let angleDiffWrap = (first.adjustedDegrees + 360) - last.adjustedDegrees;
					if (angleDiffWrap < minGlyphSeparation) {
						let adjustment = (minGlyphSeparation - angleDiffWrap) / 2;
						first.adjustedDegrees += adjustment;
						last.adjustedDegrees -= adjustment;
					}
					// Check overlap between adjacent planets
					for (let i = 1; i < planets.length; i++) {
						let prev = planets[i-1];
						let current = planets[i];
						let angleDiff = current.adjustedDegrees - prev.adjustedDegrees;
						if (angleDiff < minGlyphSeparation) {
							let adjustment = (minGlyphSeparation - angleDiff) / 2;
							prev.adjustedDegrees -= adjustment; // Push previous back
							current.adjustedDegrees += adjustment; // Push current forward
						}
					}
				}
			}

			// Draw each planet glyph and connecting line
			planets.forEach(planet => {
				// Line from outer circle to adjusted glyph position
				const lineStartCoords = degreeToCartesian(glyphConnectorRadius, planet.degrees); // Line starts at true degree
				const lineEndCoords = degreeToCartesian(outerGlyphRadius, planet.adjustedDegrees); // Line ends at adjusted degree
				const line = document.createElementNS(this.SVG_NS, 'line');
				line.setAttribute('x1', lineStartCoords.x); line.setAttribute('y1', lineStartCoords.y);
				line.setAttribute('x2', lineEndCoords.x); line.setAttribute('y2', lineEndCoords.y);
				line.setAttribute('class', 'zodiac-divider'); // Use same style as dividers
				mainGroup.appendChild(line);

				// Place planet glyph at adjusted position
				const textCoords = degreeToCartesian(outerGlyphRadius + 20, planet.adjustedDegrees); // Place glyph slightly further out
				const text = document.createElementNS(this.SVG_NS, 'text');
				text.setAttribute('x', textCoords.x); text.setAttribute('y', textCoords.y);
				text.setAttribute('class', 'planet-glyph');
				text.setAttribute('transform', `rotate(${-rotation} ${textCoords.x} ${textCoords.y})`); // Counter-rotate
				text.textContent = this.PLANET_GLYPHS[planet.name];
				mainGroup.appendChild(text);

				// Add 'Rx' symbol if retrograde
				if (planet.retrograde) {
					const rxCoords = degreeToCartesian(outerGlyphRadius + 22, planet.adjustedDegrees + 4.5); // Offset slightly
					const rxText = document.createElementNS(this.SVG_NS, 'text');
					rxText.setAttribute('x', rxCoords.x); rxText.setAttribute('y', rxCoords.y);
					rxText.setAttribute('class', 'planet-retrograde');
					rxText.setAttribute('transform', `rotate(${-rotation} ${rxCoords.x} ${rxCoords.y})`); // Counter-rotate
					rxText.textContent = '℞';
					mainGroup.appendChild(rxText);
				}
			});
		}
	},
	
	getLegendHtml() {
		let legendText = '--- ZODIAC SIGNS ---\n';
		for (const [name, glyph] of Object.entries(this.ZODIAC_GLYPHS)) {
			legendText += `${glyph} - ${name}\n`;
		}
		legendText += '\n--- PLANETS & POINTS ---\n';
		for (const [name, glyph] of Object.entries(this.PLANET_GLYPHS)) {
			legendText += `${glyph} - ${name}\n`;
		}
		return `
			<details class="glyph-legend-details">
				<summary>Glyph Legend</summary>
				<pre>${legendText}</pre>
			</details>
		`;
	},
	
	async findSimilarFamousPeople(chartData) {
		// Show the famous people section
		const famousPeopleSection = document.getElementById('famous-people-section');
		const loadingDiv = document.getElementById('famous-people-loading');
		const resultsDiv = document.getElementById('famous-people-results');
		
		if (!famousPeopleSection) return;
		
		famousPeopleSection.style.display = 'block';
		loadingDiv.style.display = 'block';
		resultsDiv.style.display = 'none';
		
		try {
			const response = await fetch(`${this.API_URLS.calculate.replace('/calculate_chart', '/api/find-similar-famous-people')}`, {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json'
				},
				body: JSON.stringify({
					chart_data: chartData,
					limit: 10
				})
			});
			
			if (!response.ok) {
				const errorData = await response.json().catch(() => ({ detail: `HTTP ${response.status}` }));
				throw new Error(errorData.detail || `API error: ${response.status}`);
			}
			
			const data = await response.json();
			
			if (data.matches && data.matches.length > 0) {
				this.displayFamousPeopleMatches(data.matches);
				loadingDiv.style.display = 'none';
				resultsDiv.style.display = 'grid';
			} else if (data.message) {
				loadingDiv.innerHTML = `<p>${data.message}</p>`;
			} else {
				loadingDiv.innerHTML = '<p>No matches found yet. Check back soon as we add more famous people!</p>';
			}
		} catch (error) {
			console.error('Error finding similar famous people:', error);
			loadingDiv.innerHTML = `<p>Unable to find matches at this time. ${error.message || 'Please try again later.'}</p>`;
		}
	},
	
	displayFamousPeopleMatches(matches) {
		const resultsDiv = document.getElementById('famous-people-results');
		if (!resultsDiv) return;
		
		let html = '';
		
		matches.forEach(match => {
			const similarityColor = match.similarity_score >= 70 ? '#4CAF50' : 
			                       match.similarity_score >= 50 ? '#FF9800' : '#2196F3';
			
			html += `
				<div class="famous-person-card" style="
					background: rgba(27, 108, 168, 0.1);
					border: 1px solid rgba(27, 108, 168, 0.3);
					border-radius: 8px;
					padding: 1.5em;
					transition: transform 0.2s, box-shadow 0.2s;
				" onmouseover="this.style.transform='translateY(-5px)'; this.style.boxShadow='0 5px 15px rgba(27, 108, 168, 0.3)'" 
				   onmouseout="this.style.transform=''; this.style.boxShadow=''">
					<div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 1em;">
						<h3 style="margin: 0; color: #1b6ca8;">${match.name}</h3>
						<div style="
							background: ${similarityColor};
							color: white;
							padding: 0.3em 0.8em;
							border-radius: 20px;
							font-size: 0.85em;
							font-weight: bold;
						">${match.similarity_score}% match</div>
					</div>
					${match.occupation ? `<p style="color: rgba(255, 255, 255, 0.8); margin: 0.5em 0; font-style: italic;">${match.occupation}</p>` : ''}
					<div style="margin: 1em 0; padding: 1em; background: rgba(0, 0, 0, 0.2); border-radius: 4px;">
						<p style="margin: 0.3em 0; font-size: 0.9em;">
							<strong>Born:</strong> ${match.birth_date} in ${match.birth_location}
						</p>
						${match.sun_sign_sidereal ? `<p style="margin: 0.3em 0; font-size: 0.9em;"><strong>Sun:</strong> ${match.sun_sign_sidereal} (Sidereal), ${match.sun_sign_tropical || 'N/A'} (Tropical)</p>` : ''}
						${match.moon_sign_sidereal ? `<p style="margin: 0.3em 0; font-size: 0.9em;"><strong>Moon:</strong> ${match.moon_sign_sidereal} (Sidereal), ${match.moon_sign_tropical || 'N/A'} (Tropical)</p>` : ''}
					</div>
					<a href="${match.wikipedia_url}" target="_blank" rel="noopener noreferrer" 
					   style="
						display: inline-block;
						margin-top: 1em;
						padding: 0.6em 1.2em;
						background: #1b6ca8;
						color: white;
						text-decoration: none;
						border-radius: 4px;
						transition: background 0.2s;
					" onmouseover="this.style.background='#155a8a'" onmouseout="this.style.background='#1b6ca8'">
						Learn More on Wikipedia →
					</a>
				</div>
			`;
		});
		
		resultsDiv.innerHTML = html;
		
		// Add CSS for grid layout if not already present
		if (!document.getElementById('famous-people-grid-style')) {
			const style = document.createElement('style');
			style.id = 'famous-people-grid-style';
			style.textContent = `
				.famous-people-grid {
					display: grid;
					grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
					gap: 1.5em;
					margin-top: 2em;
				}
				@media (max-width: 768px) {
					.famous-people-grid {
						grid-template-columns: 1fr;
					}
				}
			`;
			document.head.appendChild(style);
		}
	}
};

document.addEventListener('DOMContentLoaded', () => {
	AstrologyCalculator.init();
	window.addEventListener('load', () => {
		setTimeout(() => {
			AstrologyCalculator.loadAndDrawTransitChart();
		}, 100);
	});
});

