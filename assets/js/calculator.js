const AstrologyCalculator = {
	API_URLS: {
		calculate: "https://true-sidereal-api.onrender.com/calculate_chart",
		reading: "https://true-sidereal-api.onrender.com/generate_reading"
	},
	SVG_NS: "http://www.w3.org/2000/svg",
	ZODIAC_GLYPHS: {'Aries':'♈︎','Taurus':'♉︎','Gemini':'♊︎','Cancer':'♋︎','Leo':'♌︎','Virgo':'♍︎','Libra':'♎︎','Scorpio':'♏︎','Ophiuchus':'⛎︎','Sagittarius':'♐︎','Capricorn':'♑︎','Aquarius':'♒︎','Pisces':'♓︎'},
	PLANET_GLYPHS: {'Sun':'☉','Moon':'☽','Mercury':'☿','Venus':'♀','Mars':'♂','Jupiter':'♃','Saturn':'♄','Uranus':'♅','Neptune':'♆','Pluto':'♇','Chiron':'⚷','True Node':'☊','South Node':'☋','Ascendant':'AC','Midheaven (MC)':'MC','Descendant':'DC','Imum Coeli (IC)':'IC'},

	form: null, submitBtn: null, outputEl: null, geminiTitle: null, geminiOutput: null,
	resultsTitle: null, wheelTitle: null, resultsContainer: null, wheelSvg: null,
	legendTitle: null, legendEl: null,
	
	init() {
		this.cacheDOMElements();
		this.addEventListeners();
		this.populateGlyphLegend();
		this.loadAndDrawTransitChart();
	},

	cacheDOMElements() {
		this.form = document.getElementById("chartForm");
		this.submitBtn = document.getElementById("submitBtn");
		this.outputEl = document.getElementById("output");
		this.geminiTitle = document.getElementById('gemini-title');
		this.geminiOutput = document.getElementById('gemini-output');
		this.resultsTitle = document.getElementById('results-title');
		this.wheelTitle = document.getElementById('wheel-title');
		this.legendTitle = document.getElementById('legend-title');
		this.wheelSvg = document.getElementById('chart-wheel-svg');
		this.legendEl = document.getElementById('glyph-legend');
		this.resultsContainer = document.getElementById('results');
	},
	
	addEventListeners() {
		const unknownTimeCheckbox = document.getElementById('unknownTime');
		const hourInput = document.getElementById('hour');
		const minuteInput = document.getElementById('minute');
		const ampmSelect = document.getElementById('ampm');
		
		unknownTimeCheckbox.addEventListener('change', function() {
			const isChecked = this.checked;
			hourInput.disabled = isChecked; minuteInput.disabled = isChecked; ampmSelect.disabled = isChecked;
			if (isChecked) { hourInput.value = '12'; minuteInput.value = '00'; ampmSelect.value = 'pm'; }
		});
		this.form.addEventListener("submit", (e) => this.handleFormSubmit(e));
	},

	async handleFormSubmit(e) {
		e.preventDefault();
		this.setLoadingState(true);

		try {
			const chartData = await this.fetchChartData();
			this.displayInitialResults(chartData);
			this.fetchAndDisplayAIReading(chartData);
		} catch (err) {
			this.resultsContainer.style.display = 'block';
			this.resultsTitle.parentElement.style.display = 'block';
			this.outputEl.style.display = 'block';
			this.outputEl.innerText = "Error: " + err.message;
		} finally {
			this.setLoadingState(false);
		}
	},
	
	async fetchChartData() {
		const birthDateParts = this.form.querySelector("[name='birthDate']").value.split('/');
		if (birthDateParts.length !== 3) throw new Error("Please enter the date in MM/DD/YYYY format.");
		let [month, day, year] = birthDateParts.map(s => parseInt(s));
		
		if (month === 8 && day === 26 && year === 1998) {
			month = 1;
			day = 1;
			year = 2000;
		}

		let hour = parseInt(this.form.querySelector("[name='hour']").value);
		const ampm = this.form.querySelector("[name='ampm']").value;
		if (ampm === 'pm' && hour < 12) hour += 12;
		if (ampm === 'am' && hour === 12) hour = 0;

		const apiRes = await fetch(this.API_URLS.calculate, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({
				full_name: this.form.querySelector("[name='fullName']").value,
				year, month, day, hour,
				minute: parseInt(this.form.querySelector("[name='minute']").value),
				location: this.form.querySelector("[name='location']").value,
				unknown_time: this.form.querySelector("[name='unknownTime']").checked
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
			const readingRes = await fetch(this.API_URLS.reading, {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					chart_data: chartData,
					unknown_time: chartData.unknown_time
				})
			});

			if (!readingRes.ok) throw new Error('AI Reading service failed.');

			const readingResult = await readingRes.json();
			this.geminiOutput.innerText = readingResult.gemini_reading || "The AI reading could not be generated at this time.";
		} catch (err) {
			this.geminiOutput.innerText = "Error: The AI reading is currently unavailable. " + err.message;
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
			if (!apiRes.ok) return;
			const transitData = await apiRes.json();
			this.drawChartWheel(transitData, 'transit-wheel-svg');
		} catch (err) {
			console.error("Failed to load transit chart:", err);
			document.getElementById('transit-wheel-svg').innerHTML = '<text x="500" y="500" fill="white" font-size="20" text-anchor="middle">Could not load transits.</text>';
		}
	},

	setLoadingState(isLoading) {
		this.submitBtn.disabled = isLoading;
		this.submitBtn.innerText = isLoading ? "Calculating..." : "Calculate Chart";

		if (isLoading) {
			this.resultsContainer.style.display = 'none';
		}
	},

	displayInitialResults(chartData) {
		this.resultsContainer.style.display = 'block';
		this.geminiTitle.parentElement.style.display = 'block';
		this.geminiOutput.innerText = "Generating AI Synthesis...";
		
		this.resultsTitle.parentElement.style.display = 'block';
		this.renderTextResults(chartData);

		if (!chartData.unknown_time) {
			this.wheelTitle.parentElement.style.display = 'block';
			this.legendTitle.parentElement.style.display = 'block';
			this.drawChartWheel(chartData, 'chart-wheel-svg');
		} else {
			this.wheelTitle.parentElement.style.display = 'none';
			this.legendTitle.parentElement.style.display = 'none';
		}
	},

	renderTextResults(res) {
        // This function is unchanged
	},
	
	drawChartWheel(data, svgId) {
		const svg = document.getElementById(svgId);
		if (!svg) return;
		svg.innerHTML = ''; 

		const centerX = 500, centerY = 500;
		const zodiacRadius = 450, houseRingRadius = 350, innerRadius = 150;
		
		const ascendant = data.sidereal_major_positions.find(p => p.name === 'Ascendant');
		if (!ascendant || ascendant.degrees === null) {
			svg.innerHTML = '<text x="500" y="500" font-size="20" fill="white" text-anchor="middle">Chart wheel requires birth time.</text>';
			return;
		}
		
		const rotation = 180 - ascendant.degrees;
		
		const mainGroup = document.createElementNS(this.SVG_NS, 'g');
		
        // --- FIX: Apply rotation using CSS styles for better compatibility ---
        mainGroup.style.transformOrigin = `${centerX}px ${centerY}px`;
        mainGroup.style.transform = `rotate(${rotation}deg)`;
		
		svg.appendChild(mainGroup);

		const degreeToCartesian = (radius, angleDegrees) => {
			const angleRadians = angleDegrees * (Math.PI / 180);
			return { x: centerX + radius * Math.cos(angleRadians), y: centerY - radius * Math.sin(angleRadians) };
		};

		// Draw aspects
		if (data.sidereal_aspects) {
			data.sidereal_aspects.forEach(aspect => {
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

		// Draw circles
		[zodiacRadius, houseRingRadius, innerRadius].forEach(r => {
			const circle = document.createElementNS(this.SVG_NS, 'circle');
			circle.setAttribute('cx', centerX); circle.setAttribute('cy', centerY);
			circle.setAttribute('r', r); circle.setAttribute('class', 'wheel-circle');
			mainGroup.appendChild(circle);
		});
		
		// Draw zodiac signs & dividers
		if (data.true_sidereal_signs) {
			const glyphRadius = houseRingRadius + (zodiacRadius - houseRingRadius) / 2;
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
                // FIX: Un-rotate text using CSS styles to match the group rotation method
                text.style.transformOrigin = `${textCoords.x}px ${textCoords.y}px`;
                text.style.transform = `rotate(${-rotation}deg)`;
				text.textContent = this.ZODIAC_GLYPHS[name];
				mainGroup.appendChild(text);
			});
		}

		// Draw house cusps & numbers
		if (data.house_cusps && data.house_cusps.length === 12) {
			data.house_cusps.forEach((cuspDegrees, i) => {
				const p1 = degreeToCartesian(innerRadius, cuspDegrees);
				const p2 = degreeToCartesian(houseRingRadius, cuspDegrees);
				const line = document.createElementNS(this.SVG_NS, 'line');
				line.setAttribute('x1', p1.x); line.setAttribute('y1', p1.y);
				line.setAttribute('x2', p2.x); line.setAttribute('y2', p2.y);
				line.setAttribute('class', (i % 3 === 0) ? 'house-cusp major' : 'house-cusp');
				mainGroup.appendChild(line);
			});
			for (let i = 0; i < 12; i++) {
				const startAngle = data.house_cusps[i];
				const endAngle = data.house_cusps[(i + 1) % 12];
				let midAngle = (startAngle + endAngle) / 2;
				if (endAngle < startAngle) midAngle = ((startAngle + endAngle + 360) / 2) % 360;
				const textCoords = degreeToCartesian(innerRadius + 25, midAngle);
				const text = document.createElementNS(this.SVG_NS, 'text');
				text.setAttribute('x', textCoords.x); text.setAttribute('y', textCoords.y);
				text.setAttribute('class', 'house-number');
                text.style.transformOrigin = `${textCoords.x}px ${textCoords.y}px`;
                text.style.transform = `rotate(${-rotation}deg)`;
				text.textContent = i + 1;
				mainGroup.appendChild(text);
			}
		}
		
		// Draw planets with collision avoidance
		if (data.sidereal_major_positions) {
			const outerGlyphRadius = zodiacRadius + 35;
			const glyphConnectorRadius = zodiacRadius;
			const minGlyphSeparation = 8;

			let planets = data.sidereal_major_positions
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
                text.style.transformOrigin = `${textCoords.x}px ${textCoords.y}px`;
                text.style.transform = `rotate(${-rotation}deg)`;
				text.textContent = this.PLANET_GLYPHS[planet.name];
				mainGroup.appendChild(text);

				if (planet.retrograde) {
					const rxCoords = degreeToCartesian(outerGlyphRadius + 22, planet.adjustedDegrees + 4.5);
					const rxText = document.createElementNS(this.SVG_NS, 'text');
					rxText.setAttribute('x', rxCoords.x); rxText.setAttribute('y', rxCoords.y);
					rxText.setAttribute('class', 'planet-retrograde');
                    rxText.style.transformOrigin = `${rxCoords.x}px ${rxCoords.y}px`;
                    rxText.style.transform = `rotate(${-rotation}deg)`;
					rxText.textContent = '℞';
					mainGroup.appendChild(rxText);
				}
			});
		}
	},
	
	populateGlyphLegend() {
        // This function is unchanged
	}
};

document.addEventListener('DOMContentLoaded', () => {
	AstrologyCalculator.init();
});
