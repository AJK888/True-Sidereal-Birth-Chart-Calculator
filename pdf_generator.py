from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak, Table, TableStyle, KeepTogether
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.pdfgen import canvas
import io
import base64
import cairosvg
from typing import Dict, Any, Optional
import math
import logging
import re

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
        try:
            from PIL import Image, ImageDraw, ImageFont
            # Convert hex color #242943 to RGB tuple (36, 41, 67)
            bg_color = (0x24, 0x29, 0x43)
            img = Image.new('RGB', (width, height), color=bg_color)
            draw = ImageDraw.Draw(img)
            draw.text((width//2, height//2), "Chart Image Error", fill='white')
            img_bytes = io.BytesIO()
            img.save(img_bytes, format='PNG')
            return img_bytes.getvalue()
        except Exception as fallback_error:
            logger.error(f"Error creating fallback placeholder image: {fallback_error}", exc_info=True)
            # Last resort: return a minimal 1x1 pixel PNG
            return b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\nIDATx\x9cc\xf8\x00\x00\x00\x01\x00\x01\x00\x00\x00\x00IEND\xaeB`\x82'


def generate_pdf_report(chart_data: Dict[str, Any], gemini_reading: str, user_inputs: Dict[str, Any]) -> bytes:
    """
    Generate a PDF report with chart images and formatted text.
    Matches the webpage formatting as closely as possible.
    """
    buffer = io.BytesIO()
    
    # Track sections for table of contents
    toc_sections = []
    current_page = [1]  # Use list to allow modification in nested function
    
    # Custom page template for page numbers
    def add_page_number(canvas_obj, doc):
        """Add page numbers to each page."""
        page_num = canvas_obj.getPageNumber()
        current_page[0] = page_num
        text = f"Page {page_num}"
        canvas_obj.saveState()
        canvas_obj.setFont('Helvetica', 9)
        canvas_obj.setFillColor(colors.HexColor('#666666'))
        # Position at bottom right - use page width from letter size
        page_width = letter[0]  # 8.5 inches = 612 points
        x_position = page_width - 0.75*inch  # Right margin
        y_position = 0.5*inch  # Bottom margin  
        canvas_obj.drawRightString(x_position, y_position, text)
        canvas_obj.restoreState()
    
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.75*inch, bottomMargin=1.0*inch,
                            leftMargin=0.75*inch, rightMargin=0.75*inch,
                            onFirstPage=add_page_number, onLaterPages=add_page_number)
    
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
    
    section_heading_style = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading1'],
        fontSize=20,
        textColor=colors.HexColor('#1b263b'),
        alignment=TA_LEFT,
        spaceAfter=14
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
    
    cover_title_style = ParagraphStyle(
        'CoverTitle',
        parent=styles['Heading1'],
        fontSize=32,
        textColor=colors.HexColor('#0b1f3a'),
        alignment=TA_CENTER,
        spaceAfter=12
    )
    
    cover_subtitle_style = ParagraphStyle(
        'CoverSubtitle',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#1b6ca8'),
        alignment=TA_CENTER,
        spaceAfter=24
    )
    
    cover_info_style = ParagraphStyle(
        'CoverInfo',
        parent=styles['BodyText'],
        fontSize=12,
        textColor=colors.HexColor('#1f2933'),
        alignment=TA_CENTER,
        spaceAfter=8
    )
    
    bullet_style = ParagraphStyle(
        'BulletStyle',
        parent=styles['BodyText'],
        fontSize=11,
        textColor=colors.HexColor('#333333'),
        leading=16,
        alignment=TA_LEFT,
        spaceAfter=8,
        leftIndent=20,
        bulletIndent=10
    )
    
    toc_title_style = ParagraphStyle(
        'TocTitle',
        parent=styles['Heading1'],
        fontSize=22,
        textColor=colors.HexColor('#1b263b'),
        alignment=TA_CENTER,
        spaceAfter=20
    )
    
    toc_item_style = ParagraphStyle(
        'TocItem',
        parent=styles['BodyText'],
        fontSize=11,
        textColor=colors.HexColor('#333333'),
        leading=14,
        alignment=TA_LEFT,
        spaceAfter=6,
        leftIndent=0
    )
    
    story = []
    
    # Cover page
    story.append(Spacer(1, 1.5*inch))
    story.append(Paragraph("Synthesis Astrology", cover_title_style))
    story.append(Paragraph("True Sidereal Birth Chart Report", cover_subtitle_style))
    story.append(Spacer(1, 0.4*inch))
    
    cover_details = []
    if user_inputs.get('full_name'):
        cover_details.append(f"Prepared for {user_inputs['full_name']}")
    if user_inputs.get('birth_date'):
        cover_details.append(f"Birth Date: {user_inputs['birth_date']}")
    if user_inputs.get('birth_time'):
        cover_details.append(f"Birth Time: {user_inputs['birth_time']}")
    if user_inputs.get('location'):
        cover_details.append(f"Location: {user_inputs['location']}")
    
    cover_details.append("Generated by the Synthesis Astrology API")
    
    for detail in cover_details:
        story.append(Paragraph(detail, cover_info_style))
    
    story.append(PageBreak())
    
    # Table of Contents
    story.append(Paragraph("Table of Contents", toc_title_style))
    story.append(Spacer(1, 0.3*inch))
    
    # TOC items - we'll track actual page numbers as we build
    toc_items = [
        "Chart Overview",
        "AI Astrological Synthesis",
        "Glossary",
        "Full Astrological Data"
    ]
    
    # Add TOC items (page numbers will be approximate/placeholder)
    # Note: Exact page numbers require a two-pass build, so we'll use section order
    for i, item in enumerate(toc_items, start=3):  # Start at page 3 (after cover and TOC)
        # Create a simple TOC entry
        toc_text = f"{item} ................ {i}"
        story.append(Paragraph(toc_text, toc_item_style))
    
    story.append(PageBreak())
    
    # Chart overview section
    toc_sections.append(("Chart Overview", 3))  # Track for reference
    story.append(Paragraph("Chart Overview", section_heading_style))
    
    if user_inputs.get('full_name'):
        story.append(Paragraph(f"<b>Name:</b> {user_inputs.get('full_name', 'N/A')}", body_style))
    if user_inputs.get('birth_date'):
        story.append(Paragraph(f"<b>Birth Date:</b> {user_inputs.get('birth_date', 'N/A')}", body_style))
    if user_inputs.get('birth_time'):
        story.append(Paragraph(f"<b>Birth Time:</b> {user_inputs.get('birth_time', 'N/A')}", body_style))
    if user_inputs.get('location'):
        story.append(Paragraph(f"<b>Location:</b> {user_inputs.get('location', 'N/A')}", body_style))
    
    story.append(Spacer(1, 0.3*inch))
    
    # Chart Wheels with blue background
    if not chart_data.get('unknown_time'):
        story.append(Paragraph("Natal Chart Wheels", heading_style))
        
        # Generate chart wheel SVGs and convert to PNG
        sidereal_svg = generate_chart_wheel_svg(chart_data, 'sidereal')
        tropical_svg = generate_chart_wheel_svg(chart_data, 'tropical')
        
        sidereal_png = svg_to_png(sidereal_svg, width=600, height=600)
        tropical_png = svg_to_png(tropical_svg, width=600, height=600)
        
        # Create images (slightly smaller to fit within blue background with padding)
        sidereal_img = Image(io.BytesIO(sidereal_png), width=2.9*inch, height=2.9*inch)
        tropical_img = Image(io.BytesIO(tropical_png), width=2.9*inch, height=2.9*inch)
        
        chart_table = Table([
            [Paragraph("<b>Sidereal</b>", body_style), Paragraph("<b>Tropical</b>", body_style)],
            [sidereal_img, tropical_img]
        ], colWidths=[3.5*inch, 3.5*inch])
        
        blue_box = colors.HexColor('#102a43')
        chart_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 1), (-1, 1), 15),
            ('RIGHTPADDING', (0, 1), (-1, 1), 15),
            ('TOPPADDING', (0, 1), (-1, 1), 15),
            ('BOTTOMPADDING', (0, 1), (-1, 1), 15),
            ('LEFTPADDING', (0, 0), (-1, 0), 6),
            ('RIGHTPADDING', (0, 0), (-1, 0), 6),
            ('TOPPADDING', (0, 0), (-1, 0), 6),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('BACKGROUND', (0, 1), (-1, 1), blue_box),
            # Explicitly remove borders
            ('LINEBELOW', (0, 0), (-1, -1), 0, colors.white),
            ('LINEABOVE', (0, 0), (-1, -1), 0, colors.white),
            ('LINEBEFORE', (0, 0), (-1, -1), 0, colors.white),
            ('LINEAFTER', (0, 0), (-1, -1), 0, colors.white),
        ]))
        
        story.append(chart_table)
    
    story.append(PageBreak())
    
    # AI Astrological Synthesis
    toc_sections.append(("AI Astrological Synthesis", 4))  # Track for reference
    story.append(Paragraph("AI Astrological Synthesis", section_heading_style))
    story.append(Spacer(1, 0.15*inch))
    
    # Format the reading with proper paragraph breaks
    # The reading comes as plain text with headings and paragraphs
    lines = gemini_reading.split('\n')
    current_para = []
    in_bullet_section = False  # Track if we're in a section that contains bullets
    content_added = False  # Track if we've added content to avoid page break on first section
    major_sections = [
        'Snapshot: What Will Feel Most True About You',
        'Chart Overview and Core Themes',
        'Your Astrological Blueprint: Planets, Points, and Angles',
        'Major Life Dynamics: The Tightest Aspects',
        'Summary and Key Takeaways'
    ]
    
    # Sections that typically contain bullet points
    bullet_section_keywords = ['snapshot', 'action checklist', 'checklist', 'key takeaways']
    
    def is_bullet_line(line: str) -> tuple[bool, str]:
        """Check if a line is a bullet point and return (is_bullet, cleaned_text)."""
        bullet_patterns = [
            r'^[-•*]\s+(.+)',  # Starts with -, •, or *
            r'^\d+[.)]\s+(.+)',  # Starts with number followed by . or )
            r'^[•]\s+(.+)',  # Starts with bullet character
        ]
        
        for pattern in bullet_patterns:
            match = re.match(pattern, line)
            if match:
                bullet_text = match.group(1) if match.groups() else line
                return True, bullet_text.strip()
        
        return False, line
    
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            # Empty line - end current paragraph
            if current_para:
                para_text = ' '.join(current_para)
                story.append(Paragraph(para_text, body_style))
                story.append(Spacer(1, 0.12*inch))  # Space between paragraphs
                current_para = []
                content_added = True
            # Check if we should exit bullet section after empty line
            # (we'll re-enter if next line is a bullet)
            continue
        
        # Check if this is a major section header
        is_major_section = False
        matched_section = None
        line_clean = line.replace('**', '').strip()
        for section in major_sections:
            # Check various patterns for section matching
            section_keywords = section.lower().split()
            if (section.lower() in line.lower() or 
                any(keyword in line.lower() for keyword in section_keywords if len(keyword) > 4) or
                line_clean.startswith(section) or
                (len(line) < 100 and section.lower().replace(':', '') in line.lower())):
                is_major_section = True
                matched_section = section
                break
        
        # Check if this looks like a heading (very strict criteria to avoid false positives)
        # Only treat as heading if:
        # 1. It's a major section (already handled above)
        # 2. It's wrapped in ** markers (markdown bold) AND very short
        # 3. It's ALL CAPS, very short (under 40 chars), no punctuation, and looks like a title
        is_heading = False
        if is_major_section:
            is_heading = True
        elif line.startswith('**') and line.endswith('**') and len(line) < 80:
            # Markdown bold heading
            is_heading = True
        elif (len(line) < 40 and line.isupper() and 
              not line.endswith(('.', '!', '?', ':', ';', ',', ')')) and
              line.count(' ') < 6 and
              not any(char.isdigit() for char in line) and
              not line.startswith(('The ', 'A ', 'An ', 'This ', 'That ', 'These ', 'Those '))):
            # Very short ALL CAPS title-like text
            is_heading = True
        # Don't treat regular sentences as headings, even if they're short
        
        # Handle major section headers (with page breaks)
        if is_major_section:
            # Finish any current paragraph
            if current_para:
                para_text = ' '.join(current_para)
                story.append(Paragraph(para_text, body_style))
                story.append(Spacer(1, 0.12*inch))
                current_para = []
            
            # Check if entering a section that typically contains bullets
            in_bullet_section = any(keyword in line.lower() for keyword in bullet_section_keywords)
            
            # Add page break before major section (except for the very first one)
            if content_added:  # We've already added content, so this is a new section
                story.append(PageBreak())
            
            heading_text = line_clean
            story.append(Paragraph(f"<b>{heading_text}</b>", section_heading_style))
            story.append(Spacer(1, 0.12*inch))
            content_added = True
            continue
        
        if is_heading and not is_major_section:
            # Regular heading (not major section)
            if current_para:
                para_text = ' '.join(current_para)
                story.append(Paragraph(para_text, body_style))
                story.append(Spacer(1, 0.1*inch))
                current_para = []
                content_added = True
            heading_text = line.replace('**', '').strip()
            story.append(Paragraph(f"<b>{heading_text}</b>", heading_style))
            story.append(Spacer(1, 0.12*inch))
            content_added = True
            # Check if this heading indicates a bullet section
            if any(keyword in heading_text.lower() for keyword in bullet_section_keywords):
                in_bullet_section = True
        else:
            # Check if this line is a bullet point
            is_bullet, bullet_text = is_bullet_line(line)
            
            # If we detect a bullet pattern, we're definitely in a bullet section
            if is_bullet:
                in_bullet_section = True
                # Finish any current paragraph before starting bullets
                if current_para:
                    para_text = ' '.join(current_para)
                    story.append(Paragraph(para_text, body_style))
                    story.append(Spacer(1, 0.12*inch))
                    current_para = []
                    content_added = True
                # Format as bullet point
                story.append(Paragraph(f"• {bullet_text}", bullet_style))
                content_added = True
            elif in_bullet_section:
                # We were in bullet section, but this line doesn't match bullet pattern
                # Check if it's a short line that might still be part of bullet list
                # (sometimes bullets don't have explicit markers, especially in Action Checklist)
                is_likely_bullet = (len(line) < 120 and 
                                   not line.endswith('.') and 
                                   not line.endswith(':') and
                                   not line.endswith('!') and
                                   line.count('.') < 2)  # Not a full sentence
                
                if is_likely_bullet:
                    # Likely a bullet without marker, format it
                    story.append(Paragraph(f"• {line}", bullet_style))
                    content_added = True
                else:
                    # Exit bullet section, start regular paragraph
                    in_bullet_section = False
                    if current_para:
                        current_para.append(line)
                    else:
                        current_para = [line]
            else:
                # Regular text - add to current paragraph
                current_para.append(line)
    
    # Add any remaining paragraph
    if current_para:
        para_text = ' '.join(current_para)
        story.append(Paragraph(para_text, body_style))
        story.append(Spacer(1, 0.12*inch))
        content_added = True
    
    story.append(PageBreak())
    
    # Glossary Section
    toc_sections.append(("Glossary", None))  # Page number will vary
    story.append(Paragraph("Glossary", section_heading_style))
    story.append(Spacer(1, 0.2*inch))
    
    glossary_terms = [
        ("Sidereal Zodiac", "A zodiac system based on the actual positions of constellations in the sky. It represents the soul's deeper karmic blueprint and spiritual gifts."),
        ("Tropical Zodiac", "The traditional Western zodiac system based on the seasons. It represents personality expression and how the soul's purpose manifests in this lifetime."),
        ("Aspect", "A geometric angle between two planets or points in the chart, indicating how their energies interact (e.g., conjunction, square, trine)."),
        ("House", "One of 12 divisions of the chart representing different areas of life (career, relationships, home, etc.). Only available when birth time is known."),
        ("Ascendant (Rising Sign)", "The zodiac sign rising on the eastern horizon at the moment of birth. Represents how you present yourself to the world."),
        ("Midheaven (MC)", "The highest point in the chart, representing career, public image, and life direction."),
        ("North Node", "The point indicating your soul's growth direction and life lessons in this incarnation."),
        ("South Node", "The point representing past-life patterns, comfort zones, and innate gifts."),
        ("Retrograde", "When a planet appears to move backward in the sky. Indicates internalized or reflective energy."),
        ("Chart Ruler", "The planet that rules the Ascendant sign, considered the most important planet in the chart."),
        ("Aspect Pattern", "A geometric configuration formed by multiple aspects (e.g., T-Square, Grand Trine, Grand Cross)."),
        ("Stellium", "Three or more planets in the same sign or house, creating a concentration of energy."),
        ("Life Path Number", "A numerology calculation derived from your birth date, representing your life's purpose and challenges."),
        ("Expression Number", "A numerology calculation from your full name, representing your natural talents and abilities."),
    ]
    
    for term, definition in glossary_terms:
        story.append(Paragraph(f"<b>{term}</b>", heading_style))
        story.append(Paragraph(definition, body_style))
        story.append(Spacer(1, 0.15*inch))
    
    story.append(PageBreak())
    
    # Full Report Section
    toc_sections.append(("Full Astrological Data", None))  # Page number will vary
    story.append(Paragraph("Full Astrological Data", section_heading_style))
    
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

