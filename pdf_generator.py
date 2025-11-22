"""
PDF Generation Module for Astrology Charts
Generates PDF reports with properly formatted chart images and text.
"""

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.pdfgen import canvas
import io
import base64
import cairosvg
from typing import Dict, Any, Optional
import math
import logging

logger = logging.getLogger(__name__)


def generate_chart_wheel_svg(chart_data: Dict[str, Any], chart_type: str) -> str:
    """
    Generate SVG for a chart wheel server-side.
    Recreates the JavaScript chart drawing logic in Python.
    """
    positions = chart_data.get(f'{chart_type}_major_positions', [])
    aspects = chart_data.get(f'{chart_type}_aspects', [])
    house_cusps = chart_data.get(f'{chart_type}_house_cusps', [])
    true_sidereal_signs = chart_data.get('true_sidereal_signs', [])
    
    # Zodiac and planet glyphs
    ZODIAC_GLYPHS = {
        'Aries': '♈', 'Taurus': '♉', 'Gemini': '♊', 'Cancer': '♋',
        'Leo': '♌', 'Virgo': '♍', 'Libra': '♎', 'Scorpio': '♏',
        'Ophiuchus': '⛎', 'Sagittarius': '♐', 'Capricorn': '♑',
        'Aquarius': '♒', 'Pisces': '♓'
    }
    PLANET_GLYPHS = {
        'Sun': '☉', 'Moon': '☽', 'Mercury': '☿', 'Venus': '♀',
        'Mars': '♂', 'Jupiter': '♃', 'Saturn': '♄', 'Uranus': '♅',
        'Neptune': '♆', 'Pluto': '♇', 'Chiron': '⚷',
        'True Node': '☊', 'South Node': '☋',
        'Ascendant': 'AC', 'Midheaven (MC)': 'MC',
        'Descendant': 'DC', 'Imum Coeli (IC)': 'IC'
    }
    TROPICAL_ZODIAC_ORDER = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
                             'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces']
    
    center_x, center_y = 500, 500
    zodiac_radius = 450
    house_ring_radius = 350
    inner_radius = 150
    
    # Find ascendant for rotation
    ascendant = next((p for p in positions if p.get('name') == 'Ascendant'), None)
    if not ascendant or ascendant.get('degrees') is None:
        return f'<svg viewBox="0 0 1000 1000" xmlns="http://www.w3.org/2000/svg"><text x="500" y="500" font-size="20" fill="white" text-anchor="middle">Chart wheel requires birth time.</text></svg>'
    
    rotation = ascendant.get('degrees', 0) - 180
    
    def degree_to_cartesian(radius, angle_degrees):
        angle_radians = math.radians(-angle_degrees)
        x = center_x + radius * math.cos(angle_radians)
        y = center_y + radius * math.sin(angle_radians)
        return x, y
    
    svg_parts = [f'<svg viewBox="0 0 1000 1000" xmlns="http://www.w3.org/2000/svg" style="background-color: #242943;">']
    svg_parts.append(f'<g transform="rotate({rotation} {center_x} {center_y})">')
    
    # Draw aspect lines
    for aspect in aspects:
        p1_deg = aspect.get('p1_degrees')
        p2_deg = aspect.get('p2_degrees')
        if p1_deg is None or p2_deg is None:
            continue
        x1, y1 = degree_to_cartesian(inner_radius, p1_deg)
        x2, y2 = degree_to_cartesian(inner_radius, p2_deg)
        aspect_type = aspect.get('type', '').lower().replace(' ', '-')
        color = '#38a169' if 'conjunction' in aspect_type else '#e53e3e' if 'opposition' in aspect_type or 'square' in aspect_type else '#3182ce'
        svg_parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="1.5" opacity="0.7"/>')
    
    # Draw concentric circles
    for radius in [zodiac_radius, house_ring_radius, inner_radius]:
        svg_parts.append(f'<circle cx="{center_x}" cy="{center_y}" r="{radius}" stroke="rgba(255,255,255,0.25)" stroke-width="2" fill="none"/>')
    
    # Draw zodiac signs
    glyph_radius = house_ring_radius + (zodiac_radius - house_ring_radius) / 2
    if chart_type == 'sidereal' and true_sidereal_signs:
        for sign_data in true_sidereal_signs:
            name, start, end = sign_data[0], sign_data[1], sign_data[2]
            # Draw divider
            x1, y1 = degree_to_cartesian(house_ring_radius, start)
            x2, y2 = degree_to_cartesian(zodiac_radius, start)
            svg_parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="rgba(255,255,255,0.25)" stroke-width="1"/>')
            # Place glyph
            mid_angle = start + ((end - start + 360) % 360) / 2
            x, y = degree_to_cartesian(glyph_radius, mid_angle)
            glyph = ZODIAC_GLYPHS.get(name, '')
            svg_parts.append(f'<text x="{x}" y="{y}" font-size="30" fill="white" text-anchor="middle" dominant-baseline="middle" transform="rotate({-rotation} {x} {y})">{glyph}</text>')
    else:
        # Tropical: equal 30-degree divisions
        for i in range(12):
            start = i * 30
            x1, y1 = degree_to_cartesian(house_ring_radius, start)
            x2, y2 = degree_to_cartesian(zodiac_radius, start)
            svg_parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="rgba(255,255,255,0.25)" stroke-width="1"/>')
            mid_angle = start + 15
            x, y = degree_to_cartesian(glyph_radius, mid_angle)
            sign_name = TROPICAL_ZODIAC_ORDER[i]
            glyph = ZODIAC_GLYPHS.get(sign_name, '')
            svg_parts.append(f'<text x="{x}" y="{y}" font-size="30" fill="white" text-anchor="middle" dominant-baseline="middle" transform="rotate({-rotation} {x} {y})">{glyph}</text>')
    
    # Draw house cusps
    if house_cusps and len(house_cusps) == 12:
        for i, cusp_deg in enumerate(house_cusps):
            x1, y1 = degree_to_cartesian(inner_radius, cusp_deg)
            x2, y2 = degree_to_cartesian(house_ring_radius, cusp_deg)
            stroke_width = 3 if i % 3 == 0 else 1.5
            svg_parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="white" stroke-width="{stroke_width}"/>')
            # House numbers
            end_angle = house_cusps[(i + 1) % 12]
            mid_angle = (cusp_deg + end_angle) / 2
            if end_angle < cusp_deg:
                mid_angle = ((cusp_deg + end_angle + 360) / 2) % 360
            x, y = degree_to_cartesian(inner_radius + 25, mid_angle)
            svg_parts.append(f'<text x="{x}" y="{y}" font-size="24" fill="white" text-anchor="middle" dominant-baseline="middle" transform="rotate({-rotation} {x} {y})">{i + 1}</text>')
    
    # Draw planets
    valid_planets = [p for p in positions if p.get('degrees') is not None and PLANET_GLYPHS.get(p.get('name'))]
    valid_planets.sort(key=lambda p: p.get('degrees', 0))
    
    outer_glyph_radius = zodiac_radius + 35
    min_separation = 8
    
    # Adjust positions to prevent overlap
    adjusted_degrees = {p['name']: p['degrees'] for p in valid_planets}
    for _ in range(2):  # Two passes for better distribution
        for i in range(len(valid_planets)):
            prev_name = valid_planets[i-1]['name'] if i > 0 else valid_planets[-1]['name']
            curr_name = valid_planets[i]['name']
            prev_deg = adjusted_degrees[prev_name]
            curr_deg = adjusted_degrees[curr_name]
            if i == 0:
                angle_diff = (curr_deg + 360) - prev_deg
            else:
                angle_diff = curr_deg - prev_deg
            if angle_diff < min_separation:
                adjustment = (min_separation - angle_diff) / 2
                adjusted_degrees[prev_name] -= adjustment
                adjusted_degrees[curr_name] += adjustment
    
    for planet in valid_planets:
        name = planet.get('name')
        true_deg = planet.get('degrees')
        adj_deg = adjusted_degrees[name]
        
        # Connector line
        x1, y1 = degree_to_cartesian(zodiac_radius, true_deg)
        x2, y2 = degree_to_cartesian(outer_glyph_radius, adj_deg)
        svg_parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="rgba(255,255,255,0.25)" stroke-width="1"/>')
        
        # Planet glyph
        x, y = degree_to_cartesian(outer_glyph_radius + 20, adj_deg)
        glyph = PLANET_GLYPHS.get(name, '')
        svg_parts.append(f'<text x="{x}" y="{y}" font-size="35" fill="white" text-anchor="middle" dominant-baseline="middle" transform="rotate({-rotation} {x} {y})">{glyph}</text>')
        
        # Retrograde indicator
        if planet.get('retrograde'):
            rx_x, rx_y = degree_to_cartesian(outer_glyph_radius + 22, adj_deg + 4.5)
            svg_parts.append(f'<text x="{rx_x}" y="{rx_y}" font-size="20" fill="white" text-anchor="middle" dominant-baseline="middle" transform="rotate({-rotation} {rx_x} {rx_y})">℞</text>')
    
    svg_parts.append('</g>')
    svg_parts.append('</svg>')
    return ''.join(svg_parts)


def svg_to_png(svg_string: str, width: int = 800, height: int = 800) -> bytes:
    """Convert SVG string to PNG bytes."""
    try:
        png_data = cairosvg.svg2png(bytestring=svg_string.encode('utf-8'), output_width=width, output_height=height)
        return png_data
    except Exception as e:
        logger.error(f"Error converting SVG to PNG: {e}", exc_info=True)
        # Return a placeholder image
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new('RGB', (width, height), color='#242943')
        draw = ImageDraw.Draw(img)
        draw.text((width//2, height//2), "Chart Image Error", fill='white')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        return img_bytes.getvalue()


def generate_pdf_report(chart_data: Dict[str, Any], gemini_reading: str, user_inputs: Dict[str, Any]) -> bytes:
    """
    Generate a PDF report with chart images and formatted text.
    Matches the webpage formatting as closely as possible.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.75*inch, bottomMargin=0.75*inch,
                            leftMargin=0.75*inch, rightMargin=0.75*inch)
    
    styles = getSampleStyleSheet()
    
    # Custom styles matching webpage
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=12,
        alignment=TA_CENTER
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=18,
        textColor=colors.HexColor('#34495e'),
        spaceAfter=10,
        spaceBefore=20
    )
    
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['BodyText'],
        fontSize=11,
        textColor=colors.HexColor('#333333'),
        leading=16,
        alignment=TA_JUSTIFY,
        spaceAfter=12
    )
    
    story = []
    
    # Title
    story.append(Paragraph("Synthesis Astrology Report", title_style))
    story.append(Spacer(1, 0.2*inch))
    
    # Chart Inputs
    if user_inputs.get('full_name'):
        story.append(Paragraph(f"<b>Name:</b> {user_inputs.get('full_name', 'N/A')}", body_style))
    if user_inputs.get('birth_date'):
        story.append(Paragraph(f"<b>Birth Date:</b> {user_inputs.get('birth_date', 'N/A')}", body_style))
    if user_inputs.get('birth_time'):
        story.append(Paragraph(f"<b>Birth Time:</b> {user_inputs.get('birth_time', 'N/A')}", body_style))
    if user_inputs.get('location'):
        story.append(Paragraph(f"<b>Location:</b> {user_inputs.get('location', 'N/A')}", body_style))
    
    story.append(Spacer(1, 0.3*inch))
    
    # Chart Wheels
    if not chart_data.get('unknown_time'):
        story.append(Paragraph("Natal Chart Wheels", heading_style))
        
        # Generate chart wheel SVGs and convert to PNG
        sidereal_svg = generate_chart_wheel_svg(chart_data, 'sidereal')
        tropical_svg = generate_chart_wheel_svg(chart_data, 'tropical')
        
        sidereal_png = svg_to_png(sidereal_svg, width=600, height=600)
        tropical_png = svg_to_png(tropical_svg, width=600, height=600)
        
        # Create images
        sidereal_img = Image(io.BytesIO(sidereal_png), width=3*inch, height=3*inch)
        tropical_img = Image(io.BytesIO(tropical_png), width=3*inch, height=3*inch)
        
        # Table to place charts side by side
        chart_table = Table([
            [Paragraph("<b>Sidereal</b>", body_style), Paragraph("<b>Tropical</b>", body_style)],
            [sidereal_img, tropical_img]
        ], colWidths=[3.5*inch, 3.5*inch])
        
        chart_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        
        story.append(chart_table)
        story.append(Spacer(1, 0.3*inch))
    
    # AI Astrological Synthesis
    story.append(Paragraph("AI Astrological Synthesis", heading_style))
    story.append(Spacer(1, 0.15*inch))
    
    # Format the reading with proper paragraph breaks
    # The reading comes as plain text with headings and paragraphs
    lines = gemini_reading.split('\n')
    current_para = []
    
    for line in lines:
        line = line.strip()
        if not line:
            # Empty line - end current paragraph
            if current_para:
                para_text = ' '.join(current_para)
                story.append(Paragraph(para_text, body_style))
                story.append(Spacer(1, 0.12*inch))  # Space between paragraphs
                current_para = []
        else:
            # Check if this looks like a heading (short line, possibly all caps or bold markers)
            is_heading = (
                len(line) < 80 and (
                    line.isupper() or 
                    line.startswith('**') and line.endswith('**') or
                    (line[0].isupper() and line.count(' ') < 5 and not line.endswith('.'))
                )
            )
            
            if is_heading and current_para:
                # Finish current paragraph first
                para_text = ' '.join(current_para)
                story.append(Paragraph(para_text, body_style))
                story.append(Spacer(1, 0.1*inch))
                current_para = []
            
            if is_heading:
                # It's a heading
                heading_text = line.replace('**', '').strip()
                story.append(Paragraph(f"<b>{heading_text}</b>", heading_style))
                story.append(Spacer(1, 0.12*inch))
            else:
                # Regular text - add to current paragraph
                current_para.append(line)
    
    # Add any remaining paragraph
    if current_para:
        para_text = ' '.join(current_para)
        story.append(Paragraph(para_text, body_style))
        story.append(Spacer(1, 0.12*inch))
    
    story.append(PageBreak())
    
    # Full Report Section
    story.append(Paragraph("Full Astrological Data", heading_style))
    
    # Sidereal Report
    story.append(Paragraph("<b>Sidereal Chart</b>", heading_style))
    sidereal_text = format_chart_text(chart_data, 'sidereal')
    for line in sidereal_text.split('\n'):
        if line.strip():
            story.append(Paragraph(line.strip(), styles['Code']))
            story.append(Spacer(1, 0.05*inch))
    
    story.append(Spacer(1, 0.2*inch))
    
    # Tropical Report
    story.append(Paragraph("<b>Tropical Chart</b>", heading_style))
    tropical_text = format_chart_text(chart_data, 'tropical')
    for line in tropical_text.split('\n'):
        if line.strip():
            story.append(Paragraph(line.strip(), styles['Code']))
            story.append(Spacer(1, 0.05*inch))
    
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def format_chart_text(chart_data: Dict[str, Any], chart_type: str) -> str:
    """Format chart data as text for PDF."""
    output = []
    
    if chart_type == 'sidereal':
        output.append(f"=== SIDEREAL CHART: {chart_data.get('name', 'N/A')} ===")
        output.append(f"Location: {chart_data.get('location', 'N/A')}")
        output.append("")
        
        if chart_data.get('numerology_analysis'):
            num = chart_data['numerology_analysis']
            output.append("--- NUMEROLOGY ---")
            output.append(f"Life Path Number: {num.get('life_path_number', 'N/A')}")
            output.append(f"Day Number: {num.get('day_number', 'N/A')}")
            output.append("")
        
        output.append("--- MAJOR POSITIONS ---")
        positions = chart_data.get(f'{chart_type}_major_positions', [])
        for p in positions:
            line = f"{p.get('name')}: {p.get('position', 'N/A')}"
            if p.get('retrograde'):
                line += " (Rx)"
            output.append(line)
        
        output.append("")
        output.append("--- MAJOR ASPECTS ---")
        aspects = chart_data.get(f'{chart_type}_aspects', [])
        for a in aspects[:20]:  # Limit to top 20
            output.append(f"{a.get('p1_name')} {a.get('type')} {a.get('p2_name')} (orb {a.get('orb')})")
    else:
        output.append("=== TROPICAL CHART ===")
        output.append("--- MAJOR POSITIONS ---")
        positions = chart_data.get(f'{chart_type}_major_positions', [])
        for p in positions:
            line = f"{p.get('name')}: {p.get('position', 'N/A')}"
            if p.get('retrograde'):
                line += " (Rx)"
            output.append(line)
        
        output.append("")
        output.append("--- MAJOR ASPECTS ---")
        aspects = chart_data.get(f'{chart_type}_aspects', [])
        for a in aspects[:20]:
            output.append(f"{a.get('p1_name')} {a.get('type')} {a.get('p2_name')} (orb {a.get('orb')})")
    
    return '\n'.join(output)

