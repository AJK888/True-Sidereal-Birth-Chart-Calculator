/**
 * JavaScript for displaying example readings
 * Reuses chart drawing functions from the main calculator
 */

const ExampleReader = {
	// Reuse constants from AstrologyCalculator
	SVG_NS: "http://www.w3.org/2000/svg",
	ZODIAC_GLYPHS: {'Aries':'♈︎','Taurus':'♉︎','Gemini':'♊︎','Cancer':'♋︎','Leo':'♌︎','Virgo':'♍︎','Libra':'♎︎','Scorpio':'♏︎','Ophiuchus':'⛎︎','Sagittarius':'♐︎','Capricorn':'♑︎','Aquarius':'♒︎','Pisces':'♓︎'},
	TROPICAL_ZODIAC_ORDER: ['Aries','Taurus','Gemini','Cancer','Leo','Virgo','Libra','Scorpio','Sagittarius','Capricorn','Aquarius','Pisces'],
	PLANET_GLYPHS: {'Sun':'☉','Moon':'☽','Mercury':'☿','Venus':'♀','Mars':'♂','Jupiter':'♃','Saturn':'♄','Uranus':'♅','Neptune':'♆','Pluto':'♇','Chiron':'⚷','True Node':'☊','South Node':'☋','Ascendant':'AC','Midheaven (MC)':'MC','Descendant':'DC','Imum Coeli (IC)':'IC'},

	init() {
		// Get the example key from the page (set in HTML)
		const exampleKey = document.body.getAttribute('data-example');
		if (!exampleKey) {
			console.error('No example key specified');
			return;
		}

		this.loadExampleData(exampleKey);
	},

	async loadExampleData(exampleKey) {
		try {
			const response = await fetch(`data/${exampleKey}.json`);
			if (!response.ok) {
				throw new Error(`Failed to load example data: ${response.status}`);
			}
			
			const data = await response.json();
			this.displayExample(data);
		} catch (error) {
			console.error('Error loading example data:', error);
			const errorMsg = document.getElementById('error-message');
			if (errorMsg) {
				errorMsg.textContent = `Error loading example data: ${error.message}`;
				errorMsg.style.display = 'block';
			}
		}
	},

	displayExample(data) {
		const chartData = data.chart_data;
		const aiReading = data.ai_reading;
		const metadata = data.metadata;

		// Update page title with name
		if (metadata.name) {
			document.title = `${metadata.name} - Example Reading | Synthesis Astrology`;
			const nameHeader = document.getElementById('example-name');
			if (nameHeader) {
				nameHeader.textContent = metadata.name;
			}
		}

		// Display birth info
		this.displayBirthInfo(metadata);

		// Draw chart wheels
		if (!chartData.unknown_time) {
			this.drawChartWheel(chartData, 'sidereal-wheel-svg', 'sidereal');
			this.drawChartWheel(chartData, 'tropical-wheel-svg', 'tropical');
			
			const legendHtml = this.getLegendHtml();
			const chartWheelsWrapper = document.querySelector('#results .chart-wheels-wrapper');
			if (chartWheelsWrapper) {
				const oldLegend = chartWheelsWrapper.nextElementSibling;
				if (oldLegend && oldLegend.classList.contains('glyph-legend-details')) {
					oldLegend.remove();
				}
				chartWheelsWrapper.insertAdjacentHTML('afterend', legendHtml);
			}
		} else {
			const chartWheelsWrapper = document.querySelector('#results .chart-wheels-wrapper');
			const chartPlaceholder = document.getElementById('chart-placeholder');
			if (chartWheelsWrapper) chartWheelsWrapper.style.display = 'none';
			if (chartPlaceholder) chartPlaceholder.style.display = 'block';
		}

		// Display AI reading
		const geminiOutput = document.getElementById('gemini-output');
		if (geminiOutput && aiReading) {
			geminiOutput.innerHTML = aiReading.replace(/\n/g, '<br>');
		}

		// Display full reports
		this.renderTextResults(chartData);

		// Show results section
		const resultsContainer = document.getElementById('results');
		if (resultsContainer) {
			resultsContainer.style.display = 'block';
		}
	},

	displayBirthInfo(metadata) {
		const birthInfo = document.getElementById('birth-info');
		if (birthInfo) {
			let infoHtml = `<p><strong>Birth Date:</strong> ${metadata.birth_date}</p>`;
			if (!metadata.unknown_time) {
				infoHtml += `<p><strong>Birth Time:</strong> ${metadata.birth_time}</p>`;
			}
			infoHtml += `<p><strong>Birth Location:</strong> ${metadata.location}</p>`;
			birthInfo.innerHTML = infoHtml;
		}
	},

	// Reuse chart wheel drawing function from calculator.js
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

		// Draw Aspect Lines
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

		// Draw Concentric Circles
		[zodiacRadius, houseRingRadius, innerRadius].forEach(r => {
			const circle = document.createElementNS(this.SVG_NS, 'circle');
			circle.setAttribute('cx', centerX); circle.setAttribute('cy', centerY);
			circle.setAttribute('r', r);
			circle.setAttribute('class', 'wheel-circle');
			mainGroup.appendChild(circle);
		});
		
		// Draw Zodiac Signs & Dividers
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
		} else {
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
				const signName = this.TROPICAL_ZODIAC_ORDER[i];
				text.textContent = this.ZODIAC_GLYPHS[signName];
				mainGroup.appendChild(text);
			}
		}

		// Draw House Cusps & Numbers
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
		
		// Draw Planets/Points
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
	},

	// Reuse text rendering function from calculator.js
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
				if (p.orb) { line += ` (avg orb ${p.orb})`; }
				if (p.score) { line += ` (score ${p.score})`; }
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
					if (p.orb) { line += ` (avg orb ${p.orb})`; }
					if (p.score) { line += ` (score ${p.score})`; }
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
	}
};

document.addEventListener('DOMContentLoaded', () => {
	ExampleReader.init();
});



