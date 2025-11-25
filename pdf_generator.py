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
    
    # Increase viewBox to accommodate planet glyphs that extend beyond zodiac_radius
    # Planet glyphs are placed at outer_glyph_radius + 20 = zodiac_radius + 35 + 20 = 505
    # So we need viewBox to be at least 1010x1010, but we'll use 1100x1100 for safety
    svg_size = 1100
    adjusted_center_x, adjusted_center_y = svg_size // 2, svg_size // 2  # 550, 550
    
    # Original center for calculations (we'll scale everything relative to new center)
    original_center = 500
    center_x, center_y = adjusted_center_x, adjusted_center_y
    zodiac_radius = 450
    house_ring_radius = 350
    inner_radius = 150
    
    # Find ascendant for rotation
    ascendant = next((p for p in positions if p.get('name') == 'Ascendant'), None)
    if not ascendant or ascendant.get('degrees') is None:
        return f'<svg viewBox="0 0 {svg_size} {svg_size}" xmlns="http://www.w3.org/2000/svg"><text x="{adjusted_center_x}" y="{adjusted_center_y}" font-size="20" fill="white" text-anchor="middle">Chart wheel requires birth time.</text></svg>'
    
    rotation = ascendant.get('degrees', 0) - 180
    
    def degree_to_cartesian(radius, angle_degrees):
        angle_radians = math.radians(-angle_degrees)
        x = center_x + radius * math.cos(angle_radians)
        y = center_y + radius * math.sin(angle_radians)
        return x, y
    
    # Use larger viewBox to prevent clipping of planet glyphs and labels
    svg_parts = [f'<svg viewBox="0 0 {svg_size} {svg_size}" xmlns="http://www.w3.org/2000/svg" style="background-color: #242943;">']
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
        svg_parts.append(f'<circle cx="{adjusted_center_x}" cy="{adjusted_center_y}" r="{radius}" stroke="rgba(255,255,255,0.25)" stroke-width="2" fill="none"/>')
    
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


# ============================================================================
# SECTION PARSING UTILITIES
# ============================================================================

# Pre-defined sections in exact order - the PDF will use these headers regardless
# of how the AI formats them. Content is extracted by matching section boundaries.
PDF_SECTIONS = [
    {"key": "snapshot", "title": "Snapshot: What Will Feel Most True About You", "style": "major", "bullets": True},
    {"key": "what_we_know", "title": "What We Know / What We Don't Know", "style": "major", "bullets": False},
    {"key": "overview", "title": "Chart Overview & Core Themes", "style": "major", "bullets": False},
    {"key": "houses", "title": "Houses & Life Domains Summary", "style": "major", "bullets": False},
    {"key": "love", "title": "Love, Relationships & Attachment", "style": "major", "bullets": False},
    {"key": "work", "title": "Work, Money & Vocation", "style": "major", "bullets": False},
    {"key": "emotional", "title": "Emotional Life, Family & Healing", "style": "major", "bullets": False},
    {"key": "spiritual", "title": "Spiritual Path & Meaning", "style": "major", "bullets": False},
    {"key": "aspects", "title": "Major Life Dynamics: The Tightest Aspects & Patterns", "style": "major", "bullets": False},
    {"key": "shadow", "title": "Shadow, Contradictions & Growth Edges", "style": "major", "bullets": False},
    {"key": "owners_manual", "title": "Owner's Manual: Final Integration", "style": "major", "bullets": False},
    {"key": "action_checklist", "title": "Action Checklist", "style": "subsection", "bullets": True},
]

# Patterns to match section headers in the AI output (case-insensitive)
SECTION_PATTERNS = {
    "snapshot": [r"snapshot.*what will feel", r"snapshot:?\s*$", r"what will feel most true"],
    "what_we_know": [r"what we know.*what we don'?t", r"what we know.*don'?t know"],
    "overview": [r"chart overview.*core themes", r"overview.*themes", r"core themes"],
    "houses": [r"houses.*life domains", r"houses.*domains", r"life domains summary"],
    "love": [r"love.*relationships.*attachment", r"love.*relationships", r"relationships.*attachment"],
    "work": [r"work.*money.*vocation", r"work.*vocation", r"money.*vocation", r"career.*vocation"],
    "emotional": [r"emotional.*family.*healing", r"emotional life.*healing", r"family.*healing"],
    "spiritual": [r"spiritual path.*meaning", r"spiritual.*meaning", r"spiritual path"],
    "aspects": [r"major life dynamics.*aspects", r"tightest aspects.*patterns", r"aspects.*patterns"],
    "shadow": [r"shadow.*contradictions.*growth", r"shadow.*growth edges", r"contradictions.*growth"],
    "owners_manual": [r"owner'?s manual.*integration", r"final integration", r"owner'?s manual", r"operating system"],
    "action_checklist": [r"action checklist", r"checklist:?\s*$"],
}


def parse_reading_into_sections(reading_text: str) -> Dict[str, str]:
    """
    Parse the AI reading into pre-defined sections.
    Returns a dict mapping section keys to their content.
    """
    sections = {}
    lines = reading_text.split('\n')
    
    # Clean up lines - remove markdown artifacts
    cleaned_lines = []
    for line in lines:
        # Remove markdown bold markers
        line = line.replace('**', '')
        # Remove decorative stars/dashes
        line = re.sub(r'^\*{2,}$', '', line)
        line = re.sub(r'^-{3,}$', '', line)
        line = re.sub(r'^\#{1,6}\s*', '', line)  # Remove markdown headers
        cleaned_lines.append(line)
    
    # Find section boundaries
    section_starts = []  # [(line_idx, section_key), ...]
    
    for i, line in enumerate(cleaned_lines):
        line_lower = line.strip().lower()
        if not line_lower:
            continue
        
        for section_key, patterns in SECTION_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, line_lower):
                    section_starts.append((i, section_key))
                    break
            else:
                continue
            break
    
    # Sort by line index and remove duplicates (keep first occurrence)
    section_starts.sort(key=lambda x: x[0])
    seen_keys = set()
    unique_starts = []
    for idx, key in section_starts:
        if key not in seen_keys:
            seen_keys.add(key)
            unique_starts.append((idx, key))
    section_starts = unique_starts
    
    # Extract content for each section
    for i, (start_idx, section_key) in enumerate(section_starts):
        # Find end index (next section start or end of document)
        if i + 1 < len(section_starts):
            end_idx = section_starts[i + 1][0]
        else:
            end_idx = len(cleaned_lines)
        
        # Extract content (skip the header line itself)
        content_lines = cleaned_lines[start_idx + 1:end_idx]
        content = '\n'.join(content_lines).strip()
        sections[section_key] = content
    
    # If no sections found, put everything in a fallback
    if not sections:
        sections["_fallback"] = '\n'.join(cleaned_lines)
    
    return sections


def format_section_content(content: str, is_bullet_section: bool, styles_dict: dict, story: list):
    """
    Format section content and add to story.
    Handles bullets, theme headings, subsections, and regular paragraphs.
    """
    lines = content.split('\n')
    current_para = []
    
    body_style = styles_dict['body']
    bullet_style = styles_dict['bullet']
    heading_style = styles_dict['heading']
    subsection_style = styles_dict['subsection']
    theme_style = styles_dict['theme']
    
    def is_bullet_line(line: str) -> tuple:
        """Check if line is a bullet point."""
        line_clean = line.strip()
        patterns = [
            r'^[-•*]\s+(.+)',
            r'^\d+[.)]\s+(.+)',
        ]
        for pattern in patterns:
            match = re.match(pattern, line_clean)
            if match:
                return True, match.group(1).strip()
        return False, line
    
    def is_theme_heading(line: str) -> bool:
        """Check if line is a Theme heading."""
        return bool(re.match(r'^Theme \d+\s*[–—\-]\s+\w', line.strip(), re.IGNORECASE))
    
    def is_subsection_heading(line: str) -> bool:
        """Check for specific subsection patterns."""
        patterns = [
            r'^why this shows up in your chart:?\s*$',
            r'^how it tends to feel and play out:?\s*$',
            r'^internal process:?\s*$',
            r'^external expression:?\s*$',
            r'^the core (conflict|dynamic|pattern):?\s*$',
            r'^concrete.*scenario:?\s*$',
            r'^guidance:?\s*$',
            r'^integration:?\s*$',
        ]
        line_lower = line.strip().lower()
        return any(re.match(p, line_lower) for p in patterns)
    
    def is_planet_heading(line: str) -> bool:
        """Check if line is a planet/body heading."""
        planets = ['sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn', 
                   'uranus', 'neptune', 'pluto', 'chiron', 'north node', 'south node',
                   'ascendant', 'midheaven', 'mc', 'ic', 'descendant']
        line_clean = line.strip().lower()
        # Match patterns like "The Sun:" or "--- SUN ---" or just "SUN" on its own
        if re.match(r'^---\s+\w+\s+---$', line.strip()):
            return True
        if line_clean.startswith('the '):
            line_clean = line_clean[4:]
        for planet in planets:
            if line_clean.startswith(planet) and len(line_clean) < 50:
                return True
        return False
    
    for line in lines:
        line = line.strip()
        if not line:
            # Flush current paragraph
            if current_para:
                para_text = ' '.join(current_para)
                story.append(Paragraph(para_text, body_style))
                story.append(Spacer(1, 0.1*inch))
                current_para = []
            continue
        
        # Check for bullets first
        is_bullet, bullet_text = is_bullet_line(line)
        if is_bullet or (is_bullet_section and len(line) < 150 and not line.endswith(':')):
            if current_para:
                para_text = ' '.join(current_para)
                story.append(Paragraph(para_text, body_style))
                story.append(Spacer(1, 0.08*inch))
                current_para = []
            
            text_to_use = bullet_text if is_bullet else line
            story.append(Paragraph(f"• {text_to_use}", bullet_style))
            continue
        
        # Check for theme headings
        if is_theme_heading(line):
            if current_para:
                para_text = ' '.join(current_para)
                story.append(Paragraph(para_text, body_style))
                story.append(Spacer(1, 0.1*inch))
                current_para = []
            story.append(Spacer(1, 0.15*inch))
            story.append(Paragraph(f"<b>{line}</b>", theme_style))
            story.append(Spacer(1, 0.08*inch))
            continue
        
        # Check for subsection headings
        if is_subsection_heading(line):
            if current_para:
                para_text = ' '.join(current_para)
                story.append(Paragraph(para_text, body_style))
                story.append(Spacer(1, 0.08*inch))
                current_para = []
            story.append(Paragraph(f"<i>{line}</i>", subsection_style))
            story.append(Spacer(1, 0.05*inch))
            continue
        
        # Check for planet headings
        if is_planet_heading(line):
            if current_para:
                para_text = ' '.join(current_para)
                story.append(Paragraph(para_text, body_style))
                story.append(Spacer(1, 0.1*inch))
                current_para = []
            # Clean up "--- BODY ---" format
            clean_heading = re.sub(r'^---\s+|\s+---$', '', line).strip()
            story.append(Spacer(1, 0.12*inch))
            story.append(Paragraph(f"<b>{clean_heading}</b>", heading_style))
            story.append(Spacer(1, 0.08*inch))
            continue
        
        # Regular paragraph text
        current_para.append(line)
    
    # Flush remaining paragraph
    if current_para:
        para_text = ' '.join(current_para)
        story.append(Paragraph(para_text, body_style))
        story.append(Spacer(1, 0.1*inch))


def generate_pdf_report(chart_data: Dict[str, Any], gemini_reading: str, user_inputs: Dict[str, Any]) -> bytes:
    """
    Generate a PDF report with chart images and formatted text.
    Uses a template-based approach with pre-defined section headers.
    """
    buffer = io.BytesIO()
    
    # Custom page template for page numbers
    def add_page_number(canvas_obj, doc):
        """Add page numbers to each page."""
        page_num = canvas_obj.getPageNumber()
        text = f"Page {page_num}"
        canvas_obj.saveState()
        canvas_obj.setFont('Helvetica', 9)
        canvas_obj.setFillColor(colors.HexColor('#666666'))
        page_width = letter[0]
        x_position = page_width - 0.75*inch
        y_position = 0.5*inch
        canvas_obj.drawRightString(x_position, y_position, text)
        canvas_obj.restoreState()
    
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.75*inch, bottomMargin=1.0*inch,
                            leftMargin=0.75*inch, rightMargin=0.75*inch,
                            onFirstPage=add_page_number, onLaterPages=add_page_number)
    
    styles = getSampleStyleSheet()
    
    # =========================================================================
    # STYLE DEFINITIONS
    # =========================================================================
    
    cover_title_style = ParagraphStyle(
        'CoverTitle', parent=styles['Heading1'],
        fontSize=32, textColor=colors.HexColor('#0b1f3a'),
        alignment=TA_CENTER, spaceAfter=12
    )
    
    cover_subtitle_style = ParagraphStyle(
        'CoverSubtitle', parent=styles['Heading2'],
        fontSize=16, textColor=colors.HexColor('#1b6ca8'),
        alignment=TA_CENTER, spaceAfter=24
    )
    
    cover_info_style = ParagraphStyle(
        'CoverInfo', parent=styles['BodyText'],
        fontSize=12, textColor=colors.HexColor('#1f2933'),
        alignment=TA_CENTER, spaceAfter=8
    )
    
    toc_title_style = ParagraphStyle(
        'TocTitle', parent=styles['Heading1'],
        fontSize=22, textColor=colors.HexColor('#1b263b'),
        alignment=TA_CENTER, spaceAfter=20
    )
    
    toc_item_style = ParagraphStyle(
        'TocItem', parent=styles['BodyText'],
        fontSize=11, textColor=colors.HexColor('#333333'),
        leading=18, alignment=TA_LEFT, spaceAfter=4
    )
    
    section_heading_style = ParagraphStyle(
        'SectionHeading', parent=styles['Heading1'],
        fontSize=18, textColor=colors.HexColor('#1b263b'),
        alignment=TA_LEFT, spaceAfter=12, spaceBefore=6
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading', parent=styles['Heading2'],
        fontSize=14, textColor=colors.HexColor('#34495e'),
        spaceAfter=8, spaceBefore=14
    )
    
    theme_style = ParagraphStyle(
        'ThemeHeading', parent=styles['Heading2'],
        fontSize=13, textColor=colors.HexColor('#2c3e50'),
        spaceAfter=6, spaceBefore=10
    )
    
    subsection_style = ParagraphStyle(
        'SubsectionStyle', parent=styles['Heading3'],
        fontSize=11, textColor=colors.HexColor('#4a5568'),
        spaceAfter=4, spaceBefore=8, leftIndent=0
    )
    
    body_style = ParagraphStyle(
        'CustomBody', parent=styles['BodyText'],
        fontSize=10, textColor=colors.HexColor('#333333'),
        leading=14, alignment=TA_JUSTIFY, spaceAfter=8
    )
    
    bullet_style = ParagraphStyle(
        'BulletStyle', parent=styles['BodyText'],
        fontSize=10, textColor=colors.HexColor('#333333'),
        leading=14, alignment=TA_LEFT, spaceAfter=6,
        leftIndent=18, bulletIndent=8
    )
    
    # Bundle styles for section formatting
    styles_dict = {
        'body': body_style,
        'bullet': bullet_style,
        'heading': heading_style,
        'theme': theme_style,
        'subsection': subsection_style,
    }
    
    story = []
    
    # =========================================================================
    # COVER PAGE
    # =========================================================================
    
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
    cover_details.append("Generated by Synthesis Astrology")
    
    for detail in cover_details:
        story.append(Paragraph(detail, cover_info_style))
    
    story.append(PageBreak())
    
    # =========================================================================
    # TABLE OF CONTENTS
    # =========================================================================
    
    story.append(Paragraph("Table of Contents", toc_title_style))
    story.append(Spacer(1, 0.3*inch))
    
    toc_entries = [
        ("Chart Overview", 3),
        ("Snapshot: What Will Feel Most True About You", 4),
        ("Chart Overview & Core Themes", 5),
        ("Houses & Life Domains", 6),
        ("Love, Relationships & Attachment", 7),
        ("Work, Money & Vocation", 8),
        ("Emotional Life, Family & Healing", 9),
        ("Spiritual Path & Meaning", 10),
        ("Major Life Dynamics: Aspects & Patterns", 11),
        ("Shadow, Contradictions & Growth Edges", 12),
        ("Owner's Manual: Final Integration", 13),
        ("Glossary", 14),
        ("Full Astrological Data", 15),
    ]
    
    for title, page_num in toc_entries:
        dots = "." * max(5, 50 - len(title))
        story.append(Paragraph(f"{title} {dots} {page_num}", toc_item_style))
    
    story.append(PageBreak())
    
    # =========================================================================
    # CHART OVERVIEW PAGE
    # =========================================================================
    
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
    
    # Chart wheels
    if not chart_data.get('unknown_time'):
        story.append(Paragraph("Natal Chart Wheels", heading_style))
        
        sidereal_svg = generate_chart_wheel_svg(chart_data, 'sidereal')
        tropical_svg = generate_chart_wheel_svg(chart_data, 'tropical')
        
        sidereal_png = svg_to_png(sidereal_svg, width=800, height=800)
        tropical_png = svg_to_png(tropical_svg, width=800, height=800)
        
        sidereal_img = Image(io.BytesIO(sidereal_png), width=2.7*inch, height=2.7*inch)
        tropical_img = Image(io.BytesIO(tropical_png), width=2.7*inch, height=2.7*inch)
        
        chart_table = Table([
            [Paragraph("<b>Sidereal</b>", body_style), Paragraph("<b>Tropical</b>", body_style)],
            [sidereal_img, tropical_img]
        ], colWidths=[3.8*inch, 3.8*inch])
        
        blue_box = colors.HexColor('#102a43')
        chart_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 1), (-1, 1), 25),
            ('RIGHTPADDING', (0, 1), (-1, 1), 25),
            ('TOPPADDING', (0, 1), (-1, 1), 25),
            ('BOTTOMPADDING', (0, 1), (-1, 1), 25),
            ('LEFTPADDING', (0, 0), (-1, 0), 6),
            ('RIGHTPADDING', (0, 0), (-1, 0), 6),
            ('TOPPADDING', (0, 0), (-1, 0), 6),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('BACKGROUND', (0, 1), (-1, 1), blue_box),
        ]))
        
        story.append(chart_table)
    
    story.append(PageBreak())
    
    # =========================================================================
    # PARSE AI READING INTO SECTIONS
    # =========================================================================
    
    parsed_sections = parse_reading_into_sections(gemini_reading)
    
    # =========================================================================
    # RENDER EACH PRE-DEFINED SECTION
    # =========================================================================
    
    for section_def in PDF_SECTIONS:
        section_key = section_def["key"]
        section_title = section_def["title"]
        is_bullet_section = section_def.get("bullets", False)
        
        # Get content for this section (may be empty)
        content = parsed_sections.get(section_key, "")
        
        # Skip empty sections (except houses which may be intentionally empty for unknown time)
        if not content and section_key != "houses":
            continue
        
        # Skip houses section for unknown time charts
        if section_key == "houses" and chart_data.get('unknown_time'):
            continue
        
        # Skip "what we know" section for known time charts
        if section_key == "what_we_know" and not chart_data.get('unknown_time'):
            continue
        
        # Add page break before major sections (not subsections)
        if section_def.get("style") == "major":
            story.append(PageBreak())
        
        # Add section header
        story.append(Paragraph(section_title, section_heading_style))
        story.append(Spacer(1, 0.1*inch))
        
        # Format and add content
        if content:
            format_section_content(content, is_bullet_section, styles_dict, story)
    
    # If we have fallback content (parsing failed), render it
    if "_fallback" in parsed_sections:
        story.append(PageBreak())
        story.append(Paragraph("Astrological Synthesis", section_heading_style))
        story.append(Spacer(1, 0.1*inch))
        format_section_content(parsed_sections["_fallback"], False, styles_dict, story)
    
    story.append(PageBreak())
    
    # Glossary Section
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
    
    # =========================================================================
    # DISCLAIMER
    # =========================================================================
    story.append(PageBreak())
    
    disclaimer_title_style = ParagraphStyle(
        'DisclaimerTitle', parent=styles['Heading2'],
        fontSize=14, textColor=colors.HexColor('#666666'),
        alignment=TA_CENTER, spaceAfter=16, spaceBefore=20
    )
    
    disclaimer_body_style = ParagraphStyle(
        'DisclaimerBody', parent=styles['BodyText'],
        fontSize=10, textColor=colors.HexColor('#555555'),
        leading=14, alignment=TA_JUSTIFY, spaceAfter=12
    )
    
    story.append(Paragraph("Disclaimer", disclaimer_title_style))
    
    disclaimer_text = """Astrology is a symbolic language and contemplative tool for self-reflection, not a deterministic science or predictive system that overrides your free will. This reading describes potentials, tendencies, and psychological patterns—not fixed outcomes or limitations. You are always the author of your own life, and this analysis is offered to support your self-awareness and personal growth, not to replace professional psychological, medical, or financial guidance. The insights presented here are interpretive in nature and should be engaged with discernment, taking what resonates and leaving what does not serve your highest understanding."""
    
    story.append(Paragraph(disclaimer_text, disclaimer_body_style))
    
    story.append(Spacer(1, 0.3*inch))
    
    # Footer with website
    footer_style = ParagraphStyle(
        'Footer', parent=styles['BodyText'],
        fontSize=10, textColor=colors.HexColor('#1b6ca8'),
        alignment=TA_CENTER
    )
    story.append(Paragraph("Generated by Synthesis Astrology • synthesisastrology.com", footer_style))
    
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

