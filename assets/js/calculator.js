const AstrologyCalculator = {
	API_URLS: {
		calculate: "https://true-sidereal-api.onrender.com/calculate_chart",
		reading: "https://true-sidereal-api.onrender.com/generate_reading"
	},
	SVG_NS: "http://www.w3.org/2000/svg",
	ZODIAC_GLYPHS: {'Aries':'♈︎','Taurus':'♉︎','Gemini':'♊︎','Cancer':'♋︎','Leo':'♌︎','Virgo':'♍︎','Libra':'♎︎','Scorpio':'♏︎','Ophiuchus':'⛎︎','Sagittarius':'♐︎','Capricorn':'♑︎','Aquarius':'♒︎','Pisces':'♓︎'},
	TROPICAL_ZODIAC_ORDER: ['Aries','Taurus','Gemini','Cancer','Leo','Virgo','Libra','Scorpio','Sagittarius','Capricorn','Aquarius','Pisces'],
	PLANET_GLYPHS: {'Sun':'☉','Moon':'☽','Mercury':'☿','Venus':'♀','Mars':'♂','Jupiter':'♃','Saturn':'♄','Uranus':'♅','Neptune':'♆','Pluto':'♇','Chiron':'⚷','True Node':'☊','South Node':'☋','Ascendant':'AC','Midheaven (MC)':'MC','Descendant':'DC','Imum Coeli (IC)':'IC'},

	form: null, submitBtn: null, noFullNameCheckbox: null,
	geminiTitle: null, geminiOutput: null, copyReadingBtn: null,
	resultsTitle: null, wheelTitle: null, resultsContainer: null, 
	siderealWheelSvg: null, tropicalWheelSvg: null,
	
	init() {
		this.cacheDOMElements();
		this.addEventListeners();
	},

	cacheDOMElements() {
		this.form = document.getElementById("chartForm");
		this.submitBtn = document.getElementById("submitBtn");
		this.noFullNameCheckbox = document.getElementById("noFullName");
		this.geminiTitle = document.getElementById('gemini-title');
		this.geminiOutput = document.getElementById('gemini-output');
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
        // The copy button is no longer needed in this workflow, so we can remove its event listener logic
	},

	async handleFormSubmit(e) {
		e.preventDefault();

		const termsCheckbox = document.getElementById('terms');
		const termsError = document.getElementById('termsError');
        const userEmailInput = this.form.querySelector("[name='userEmail']");

		if (!termsCheckbox.checked) {
			termsError.style.display = 'block';
			return; 
		} else {
			termsError.style.display = 'none';
		}

        // Require an email address for the background task workflow
        if (!userEmailInput.value) {
            this.geminiOutput.innerText = "An email address is required to receive your generated report. Please enter your email and try again.";
            this.geminiTitle.parentElement.style.display = 'block';
            this.resultsContainer.style.display = 'block';
            this.resultsContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
            return;
        }

		this.setLoadingState(true);

		try {
			const chartData = await this.fetchChartData();
			this.displayInitialResults(chartData);
			// This function now just kicks off the background process
			await this.submitForBackgroundProcessing(chartData);
		} catch (err) {
			this.resultsContainer.style.display = 'block';
			this.resultsTitle.parentElement.style.display = 'block';
			const siderealOutput = document.getElementById('sidereal-output');
			if(siderealOutput) siderealOutput.innerText = "Error: " + err.message;

		} finally {
            // The loading state is now handled inside the submit function
		}
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
				no_full_name: this.form.querySelector("[name='noFullName']").checked
			}),
		});

		if (!apiRes.ok) {
			const errData = await apiRes.json();
			throw new Error(`API Error ${apiRes.status}: ${errData.detail}`);
		}
		return await apiRes.json();
	},

	async submitForBackgroundProcessing(chartData) {
		try {
			const userInputs = {
				full_name: this.form.querySelector("[name='fullName']").value,
				birth_date: this.form.querySelector("[name='birthDate']").value,
				birth_time: this.form.querySelector("[name='birthTime']").value,
				location: this.form.querySelector("[name='location']").value,
				user_email: this.form.querySelector("[name='userEmail']").value
			};

			let chartImageBase64 = null;
			if (this.siderealWheelSvg && this.siderealWheelSvg.innerHTML.trim() !== '' && !chartData.unknown_time) {
				const svgString = new XMLSerializer().serializeToString(this.siderealWheelSvg);
				chartImageBase64 = btoa(unescape(encodeURIComponent(svgString)));
			}

			const headers = { "Content-Type": "application/json" };
			const urlParams = new URLSearchParams(window.location.search);
			const adminSecret = urlParams.get('admin_secret');
			if (adminSecret) {
				headers['X-Admin-Secret'] = adminSecret;
			}

			const readingRes = await fetch(this.API_URLS.reading, {
				method: "POST",
				headers: headers,
				body: JSON.stringify({
					chart_data: chartData,
					unknown_time: chartData.unknown_time,
					user_inputs: userInputs,
					chart_image_base64: chartImageBase64
				})
			});

			if (!readingRes.ok) {
                const errorData = await readingRes.json().catch(() => ({ detail: 'Failed to start report generation.' }));
                throw new Error(errorData.detail || 'Failed to start report generation.');
            }
            
            // On success, show confirmation message
			this.geminiOutput.innerHTML = "<strong>Success!</strong> Your report is now being generated. The complete reading will be sent to your email address shortly. Please check your inbox (and spam folder).";

		} catch (err) {
			this.geminiOutput.innerText = "Error: Could not start the report generation. " + err.message;
		} finally {
            // End the loading state now that the request is complete
            this.setLoadingState(false);
        }
	},

	async loadAndDrawTransitChart() {
		try {
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
					location: "Boston, MA, USA",
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

	setLoadingState(isLoading) {
		this.submitBtn.disabled = isLoading;
		this.submitBtn.innerText = isLoading ? "Calculating..." : "Calculate Chart";

		if (isLoading) {
			this.resultsContainer.style.display = 'none';
			if (this.copyReadingBtn) {
                this.copyReadingBtn.style.display = 'none';
            }
		}
	},

	displayInitialResults(chartData) {
        // Updated message for background processing to be more descriptive
		this.geminiOutput.innerHTML = "Your chart data has been calculated. We are now submitting it for AI analysis. The final report will be sent to your email.";
		this.renderTextResults(chartData);

		this.geminiTitle.parentElement.style.display = 'block';
		this.resultsTitle.parentElement.style.display = 'block';

        // Hide the copy button as it's not relevant for this workflow
        if(this.copyReadingBtn) {
            this.copyReadingBtn.style.display = 'none';
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
		}

		this.resultsContainer.style.display = 'block';
		
		setTimeout(() => {
			this.resultsContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
		}, 100);
	},
    
	copyReadingToClipboard() {
        // This function is no longer used in the main workflow but is kept for potential future use.
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
		svg.innerHTML = '';

		const centerX = 500, centerY = 500;
		const zodiacRadius = 450, houseRingRadius = 350, innerRadius = 150;
		
		const positions = data[`${chartType}_major_positions`];
		const aspects = data[`${chartType}_aspects`];
		const houseCusps = data[`${chartType}_house_cusps`];

		const ascendant = positions.find(p => p.name === 'Ascendant');
		if (!ascendant || ascendant.degrees === null) {
			svg.innerHTML = '<text x="500" y="500" font-size="20" fill="white" text-anchor="middle">Chart wheel requires birth time.</text>';
			return;
		}
		
		const rotation = ascendant.degrees - 180;

		const mainGroup = document.createElementNS(this.SVG_NS, 'g');
		mainGroup.setAttribute('transform', `rotate(${rotation} ${centerX} ${centerY})`);
		svg.appendChild(mainGroup);

		const degreeToCartesian = (radius, angleDegrees) => {
			const angleRadians = -angleDegrees * (Math.PI / 180);
			return { x: centerX + radius * Math.cos(angleRadians), y: centerY + radius * Math.sin(angleRadians) };
		};

		if (aspects) {
			aspects.forEach(aspect => {
				if (aspect.p1_degrees === null || aspect.p2_degrees === null) return;
				const p1Coords = degreeToCartesian(innerRadius, aspect.p1_degrees);
				const p2Coords = degreeToCartesian(innerRadius, aspect.p2_degrees);
				const line = document.createElementNS(this.SVG_NS, 'line');
				line.setAttribute('x1', p1Coords.x); line.setAttribute('y1', p1Coords.y);
				line.setAttribute('x2', p2Coords.x); line.setAttribute('y2', p2Coords.y);
				const aspectClass = aspect.type.toLowerCase().replace(' ', '-');
				line.setAttribute('class', `aspect-line aspect-${aspectClass}`);
				mainGroup.appendChild(line);
			});
		}

		[zodiacRadius, houseRingRadius, innerRadius].forEach(r => {
			const circle = document.createElementNS(this.SVG_NS, 'circle');
			circle.setAttribute('cx', centerX); circle.setAttribute('cy', centerY);
			circle.setAttribute('r', r);
			circle.setAttribute('class', 'wheel-circle');
			mainGroup.appendChild(circle);
		});
		
		const glyphRadius = houseRingRadius + (zodiacRadius - houseRingRadius) / 2;
		if (chartType === 'sidereal' && data.true_sidereal_signs) {
			data.true_sidereal_signs.forEach(sign => {
				const [name, start, end] = sign;
				const p1 = degreeToCartesian(houseRingRadius, start);
				const p2 = degreeToCartesian(zodiacRadius, start);
				const line = document.createElementNS(this.SVG_NS, 'line');
				line.setAttribute('x1', p1.x); line.setAttribute('y1', p1.y);
				line.setAttribute('x2', p2.x); line.setAttribute('y2', p2.y);
				line.setAttribute('class', 'zodiac-divider');
				mainGroup.appendChild(line);

				const midAngle = start + ((end - start + 360) % 360) / 2;
				const textCoords = degreeToCartesian(glyphRadius, midAngle);
				const text = document.createElementNS(this.SVG_NS, 'text');
				text.setAttribute('x', textCoords.x); text.setAttribute('y', textCoords.y);
				text.setAttribute('class', 'zodiac-glyph');
				text.setAttribute('transform', `rotate(${-rotation} ${textCoords.x} ${textCoords.y})`);
				text.textContent = this.ZODIAC_GLYPHS[name];
				mainGroup.appendChild(text);
			});
		} else { // Tropical Signs
			for (let i = 0; i < 12; i++) {
				const start = i * 30;
				const p1 = degreeToCartesian(houseRingRadius, start);
				const p2 = degreeToCartesian(zodiacRadius, start);
				const line = document.createElementNS(this.SVG_NS, 'line');
				line.setAttribute('x1', p1.x); line.setAttribute('y1', p1.y);
				line.setAttribute('x2', p2.x); line.setAttribute('y2', p2.y);
				line.setAttribute('class', 'zodiac-divider');
				mainGroup.appendChild(line);

				const midAngle = start + 15;
				const textCoords = degreeToCartesian(glyphRadius, midAngle);
				const text = document.createElementNS(this.SVG_NS, 'text');
				text.setAttribute('x', textCoords.x); text.setAttribute('y', textCoords.y);
				text.setAttribute('class', 'zodiac-glyph');
				text.setAttribute('transform', `rotate(${-rotation} ${textCoords.x} ${textCoords.y})`);
				text.textContent = this.TROPICAL_ZODIAC_ORDER[i];
				mainGroup.appendChild(text);
			}
		}


		if (houseCusps && houseCusps.length === 12) {
			houseCusps.forEach((cuspDegrees, i) => {
				const p1 = degreeToCartesian(innerRadius, cuspDegrees);
				const p2 = degreeToCartesian(houseRingRadius, cuspDegrees);
				const line = document.createElementNS(this.SVG_NS, 'line');
				line.setAttribute('x1', p1.x); line.setAttribute('y1', p1.y);
				line.setAttribute('x2', p2.x); line.setAttribute('y2', p2.y);
				line.setAttribute('class', (i % 3 === 0) ? 'house-cusp major' : 'house-cusp');
				mainGroup.appendChild(line);
			});
			for (let i = 0; i < 12; i++) {
				const startAngle = houseCusps[i];
				const endAngle = houseCusps[(i + 1) % 12];
				let midAngle = (startAngle + endAngle) / 2;
				if (endAngle < startAngle) midAngle = ((startAngle + endAngle + 360) / 2) % 360;
				const textCoords = degreeToCartesian(innerRadius + 25, midAngle);
				const text = document.createElementNS(this.SVG_NS, 'text');
				text.setAttribute('x', textCoords.x); text.setAttribute('y', textCoords.y);
				text.setAttribute('class', 'house-number');
				text.setAttribute('transform', `rotate(${-rotation} ${textCoords.x} ${textCoords.y})`);
				text.textContent = i + 1;
				mainGroup.appendChild(text);
			}
		}
		
		if (positions) {
			const outerGlyphRadius = zodiacRadius + 35;
			const glyphConnectorRadius = zodiacRadius;
			const minGlyphSeparation = 8;

			let planets = positions
				.filter(p => p.degrees !== null && this.PLANET_GLYPHS[p.name])
				.sort((a, b) => a.degrees - b.degrees);

			if (planets.length > 0) {
				planets.forEach(p => p.adjustedDegrees = p.degrees);
				for (let k = 0; k < 2; k++) {
					let last = planets[planets.length - 1];
					let first = planets[0];
					let angleDiffWrap = (first.adjustedDegrees + 360) - last.adjustedDegrees;
					if (angleDiffWrap < minGlyphSeparation) {
						let adjustment = (minGlyphSeparation - angleDiffWrap) / 2;
						first.adjustedDegrees += adjustment;
						last.adjustedDegrees -= adjustment;
					}
					for (let i = 1; i < planets.length; i++) {
						let prev = planets[i-1];
						let current = planets[i];
						let angleDiff = current.adjustedDegrees - prev.adjustedDegrees;
						if (angleDiff < minGlyphSeparation) {
							let adjustment = (minGlyphSeparation - angleDiff) / 2;
							prev.adjustedDegrees -= adjustment;
							current.adjustedDegrees += adjustment;
						}
					}
				}
			}

			planets.forEach(planet => {
				const lineStartCoords = degreeToCartesian(glyphConnectorRadius, planet.degrees);
				const lineEndCoords = degreeToCartesian(outerGlyphRadius, planet.adjustedDegrees);
				const line = document.createElementNS(this.SVG_NS, 'line');
				line.setAttribute('x1', lineStartCoords.x); line.setAttribute('y1', lineStartCoords.y);
				line.setAttribute('x2', lineEndCoords.x); line.setAttribute('y2', lineEndCoords.y);
				line.setAttribute('class', 'zodiac-divider');
				mainGroup.appendChild(line);

				const textCoords = degreeToCartesian(outerGlyphRadius + 20, planet.adjustedDegrees);
				const text = document.createElementNS(this.SVG_NS, 'text');
				text.setAttribute('x', textCoords.x); text.setAttribute('y', textCoords.y);
				text.setAttribute('class', 'planet-glyph');
				text.setAttribute('transform', `rotate(${-rotation} ${textCoords.x} ${textCoords.y})`);
				text.textContent = this.PLANET_GLYPHS[planet.name];
				mainGroup.appendChild(text);

				if (planet.retrograde) {
					const rxCoords = degreeToCartesian(outerGlyphRadius + 22, planet.adjustedDegrees + 4.5);
					const rxText = document.createElementNS(this.SVG_NS, 'text');
					rxText.setAttribute('x', rxCoords.x); rxText.setAttribute('y', rxCoords.y);
					rxText.setAttribute('class', 'planet-retrograde');
					rxText.setAttribute('transform', `rotate(${-rotation} ${rxCoords.x} ${rxCoords.y})`);
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

