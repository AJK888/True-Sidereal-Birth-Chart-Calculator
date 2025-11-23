# natal_chart.py

from datetime import datetime, timezone
import math
from itertools import combinations
from typing import List, Tuple, Dict, Any, Union, Optional
import swisseph as swe

# --- Constants ---
TRUE_SIDEREAL_SIGNS = [("Aries",0.0,19.7286),("Taurus",19.7286,56.5875),("Gemini",56.5875,86.0412),("Cancer",86.0412,103.19),("Leo",103.19,141.6065),("Virgo",141.6065,191.32),("Libra",191.32,210.1972),("Scorpio",210.1972,223.4245),("Ophiuchus",223.4245,235.7818),("Sagittarius",235.7818,269.2677),("Capricorn",269.2677,294.8435),("Aquarius",294.8435,318.0103),("Pisces",318.0103,360.0)]
SIGN_RULERS: Dict[str, str] = {"Aries":"Mars","Taurus":"Venus","Gemini":"Mercury","Cancer":"Moon","Leo":"Sun","Virgo":"Mercury","Libra":"Venus","Scorpio":"Pluto","Ophiuchus":"Chiron","Sagittarius":"Jupiter","Capricorn":"Saturn","Aquarius":"Uranus","Pisces":"Neptune"}
ELEMENT_MAPPING: Dict[str, str] = {"Aries":"Fire","Leo":"Fire","Sagittarius":"Fire","Ophiuchus":"Fire","Taurus":"Earth","Virgo":"Earth","Capricorn":"Earth","Gemini":"Air","Libra":"Air","Aquarius":"Air","Cancer":"Water","Scorpio":"Water","Pisces":"Water"}
MODALITY_MAPPING: Dict[str, str] = {"Aries":"Cardinal","Cancer":"Cardinal","Libra":"Cardinal","Capricorn":"Cardinal","Taurus":"Fixed","Leo":"Fixed","Scorpio":"Fixed","Aquarius":"Fixed","Gemini":"Mutable","Virgo":"Mutable","Sagittarius":"Mutable","Pisces":"Mutable","Ophiuchus":"Mutable"}
PLANETS_CONFIG: List[Tuple[str, int]] = [("Sun",swe.SUN),("Moon",swe.MOON),("Mercury",swe.MERCURY),("Venus",swe.VENUS),("Mars",swe.MARS),("Jupiter",swe.JUPITER),("Saturn",swe.SATURN),("Uranus",swe.URANUS),("Neptune",swe.NEPTUNE),("Pluto",swe.PLUTO),("Chiron",swe.CHIRON),("True Node",swe.TRUE_NODE)]
ADDITIONAL_BODIES_CONFIG: List[Tuple[str, int]] = [("Lilith",swe.MEAN_APOG),("Vertex",swe.VERTEX),("Ceres",swe.CERES),("Pallas",swe.PALLAS),("Juno",swe.JUNO),("Vesta",swe.VESTA)]
ASPECTS_CONFIG: List[Tuple[str, float, float]] = [("Conjunction",0,8),("Opposition",180,8),("Trine",120,6),("Square",90,6),("Sextile",60,4),("Quincunx",150,3),("Semisextile",30,2),("Semisquare",45,2),("Sesquiquadrate",135,2),("Quintile",72,1),("Biquintile",144,1)]
ASPECT_LUMINARY_ORBS: Dict[str, float] = {"Conjunction":10,"Opposition":10,"Trine":8,"Square":8,"Sextile":6}
ASPECT_SCORES: Dict[str, float] = {"Conjunction":5,"Opposition":4,"Trine":3.5,"Square":3,"Sextile":2.5,"Quincunx":2,"Semisextile":1.5,"Semisquare":1.5,"Sesquiquadrate":1.5,"Quintile":1.8,"Biquintile":1.8}

# --- Helper Functions ---
def format_true_sidereal_placement(degrees: float) -> str:
    for sign, start, end in TRUE_SIDEREAL_SIGNS:
        if start <= degrees < end:
            deg_into_sign = degrees - start; d = int(deg_into_sign); m = int(round((deg_into_sign - d) * 60))
            return f"{d}°{m:02d}′ {sign}"
    return "Out of Bounds"
def get_sign_and_ruler(degrees: float) -> Tuple[str, str]:
    for sign, start, end in TRUE_SIDEREAL_SIGNS:
        if start <= degrees < end: return sign, SIGN_RULERS.get(sign, "Unknown")
    return "Unknown", "Unknown"
def get_sign_from_degrees(degrees: float) -> str:
    for sign, start, end in TRUE_SIDEREAL_SIGNS:
        if start <= degrees < end: return sign
    return "Unknown"

def get_tropical_sign_from_degrees(degrees: float) -> str:
    """Get tropical sign from degrees (equal 30-degree divisions)."""
    TROPICAL_SIGNS = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo', 
                      'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces']
    sign_index = int(degrees // 30)
    return TROPICAL_SIGNS[sign_index % 12]

def format_tropical_placement(degrees: float) -> str:
    """Format tropical position (equal 30-degree signs)."""
    sign = get_tropical_sign_from_degrees(degrees)
    deg_into_sign = degrees % 30
    d = int(deg_into_sign)
    m = int(round((deg_into_sign - d) * 60))
    return f"{d}°{m:02d}′ {sign}"

def get_tropical_sign_and_ruler(degrees: float) -> Tuple[str, str]:
    """Get tropical sign and its ruler."""
    sign = get_tropical_sign_from_degrees(degrees)
    return sign, SIGN_RULERS.get(sign, "Unknown")
def find_house_equal(sidereal_deg: float, ascendant: float) -> Tuple[int, float]:
    for i in range(12):
        house_start = (ascendant + i * 30) % 360; house_end = (house_start + 30) % 360
        if house_end < house_start:
            if sidereal_deg >= house_start or sidereal_deg < house_end: return i + 1, (sidereal_deg - house_start + 360) % 360
        elif house_start <= sidereal_deg < house_end: return i + 1, (sidereal_deg - house_start) % 360
    return -1, 0
def calculate_numerology(day: int, month: int, year: int) -> dict:
    """Calculates Life Path and Day numbers, preserving Master Numbers 11, 22, and 33."""
    
    def reduce_number(n: int) -> str:
        """
        Reduces a number by summing its digits.
        If the result is 11, 22, or 33, it stops and formats it (e.g., "33/6").
        Otherwise, it reduces to a single digit.
        """
        # First reduction loop
        reduced_num = n
        while reduced_num > 9 and reduced_num not in [11, 22, 33]:
            reduced_num = sum(int(digit) for digit in str(reduced_num))

        # Format the final output
        if reduced_num in [11, 22, 33]:
            # For Master Numbers, show both the number and its single-digit sum
            final_sum = sum(int(digit) for digit in str(reduced_num))
            return f"{reduced_num}/{final_sum}"
        else:
            # For regular numbers, ensure they are fully reduced to a single digit
            while reduced_num > 9:
                 reduced_num = sum(int(digit) for digit in str(reduced_num))
            return str(reduced_num)

    # Calculate Life Path Number
    full_date_sum = sum(int(digit) for digit in f"{day}{month}{year}")
    life_path = reduce_number(full_date_sum)
    
    # Calculate Day Number
    day_sum = sum(int(digit) for digit in str(day))
    day_number = reduce_number(day_sum)
    
    # Calculate Lucky Number (first digit + last non-zero digit, NOT reduced)
    day_str = str(day)
    first_digit = int(day_str[0]) if day_str else 0
    
    # Find last non-zero digit
    last_non_zero_digit = 0
    for digit in reversed(day_str):
        if digit != '0':
            last_non_zero_digit = int(digit)
            break
    
    # Keep as two-digit number (first digit + last non-zero digit), not reduced
    lucky_number = int(f"{first_digit}{last_non_zero_digit}")
    
    return {"life_path": life_path, "day_number": day_number, "lucky_number": lucky_number}
def get_chinese_zodiac(year: int, month: int, day: int) -> str:
    zodiac_animals = ["Rat","Ox","Tiger","Rabbit","Dragon","Snake","Horse","Goat","Monkey","Rooster","Dog","Pig"]
    return zodiac_animals[(year - 1924) % 12]

def calculate_name_numerology(full_name: str) -> dict:
    """Calculate Expression, Soul Urge, and Personality numbers from a full name."""
    name_to_number = {
        'A': 1, 'B': 2, 'C': 3, 'D': 4, 'E': 5, 'F': 6, 'G': 7, 'H': 8, 'I': 9,
        'J': 1, 'K': 2, 'L': 3, 'M': 4, 'N': 5, 'O': 6, 'P': 7, 'Q': 8, 'R': 9,
        'S': 1, 'T': 2, 'U': 3, 'V': 4, 'W': 5, 'X': 6, 'Y': 7, 'Z': 8
    }
    vowels = {'A', 'E', 'I', 'O', 'U'}
    
    def reduce_number(n):
        while n > 9 and n not in [11, 22, 33]:
            n = sum(int(d) for d in str(n))
        return n
    
    full_name_upper = full_name.upper().replace(' ', '')
    expression_sum = sum(name_to_number.get(char, 0) for char in full_name_upper)
    soul_urge_sum = sum(name_to_number.get(char, 0) for char in full_name_upper if char in vowels)
    personality_sum = sum(name_to_number.get(char, 0) for char in full_name_upper if char not in vowels)
    
    expression_number = reduce_number(expression_sum)
    soul_urge_number = reduce_number(soul_urge_sum)
    personality_number = reduce_number(personality_sum)
    
    return {"expression_number": expression_number, "soul_urge_number": soul_urge_number, "personality_number": personality_number}

def get_chinese_zodiac_and_element(year: int, month: int, day: int) -> Dict[str, str]:
    effective_year = year
    if month == 1 or (month == 2 and day < 4):
        effective_year -= 1

    zodiac_animals = ["Rat", "Ox", "Tiger", "Rabbit", "Dragon", "Snake", "Horse", "Goat", "Monkey", "Rooster", "Dog", "Pig"]
    elements = ["Wood", "Fire", "Earth", "Metal", "Water"]
    
    start_year = 4 
    year_diff = effective_year - start_year
    
    animal_index = year_diff % 12
    stem_index = year_diff % 10
    
    animal = zodiac_animals[animal_index]
    element = elements[stem_index // 2]

    return {"animal": animal, "element": element}
def _calculate_approximate_sunrise_sunset_math(jd_ut: float, latitude: float, longitude: float) -> Tuple[Optional[float], Optional[float]]:
    try:
        res = swe.calc_ut(jd_ut, swe.SUN); lon = res[0][0]; obl = 23.439
        lon_rad, obl_rad = map(math.radians, [lon, obl])
        ra_rad = math.atan2(math.cos(obl_rad) * math.sin(lon_rad), math.cos(lon_rad)); ra_deg = (math.degrees(ra_rad) + 360) % 360
        dec_rad = math.asin(math.sin(obl_rad) * math.sin(lon_rad))
        hor_rad, lat_rad = math.radians(-0.833), math.radians(latitude)
        den = math.cos(lat_rad) * math.cos(dec_rad)
        if abs(den) < 1e-9: return (None, None)
        cos_H = (math.sin(hor_rad) - math.sin(lat_rad) * math.sin(dec_rad)) / den
        if not -1 <= cos_H <= 1: return (None, None) if cos_H > 1 else (0.0, 24.0)
        h_angle = math.degrees(math.acos(cos_H)); sid_h = swe.sidtime(jd_ut) * 15
        transit_h = ((ra_deg - sid_h + longitude + 360) % 360) / 15
        return (transit_h - h_angle / 15 + 24) % 24, (transit_h + h_angle / 15 + 24) % 24
    except Exception as e: print(f"DEBUG: Sunrise/Sunset math error: {e}"); return None, None

# --- Core Classes ---
class CelestialBody:
    def __init__(self, name: str, degree: Optional[float], retrograde: bool, sidereal_asc: Optional[float], is_main_planet: bool = True):
        self.name = name; self.degree = degree; self.retrograde = retrograde; self.is_main_planet = is_main_planet
        self.sign = get_sign_from_degrees(degree) if degree is not None else "N/A"
        self.formatted_position = format_true_sidereal_placement(degree) if degree is not None else "N/A"
        self.sign_percentage = 0
        if degree is not None and self.sign != "Unknown":
            for s, start, end in TRUE_SIDEREAL_SIGNS:
                if s == self.sign: self.sign_percentage = int(round(((degree - start) / (end - start)) * 100)); break
        self.house_num, self.house_degrees = -1, "N/A"
        if degree is not None and sidereal_asc is not None:
            h_num, d_in_h = find_house_equal(degree, sidereal_asc)
            self.house_num = h_num; self.house_degrees = f"{int(d_in_h)}°{int(round((d_in_h % 1) * 60)):02d}′"
        self.is_luminary = name in ["Sun", "Moon"]

class TropicalCelestialBody:
    """Celestial body with tropical zodiac calculations."""
    def __init__(self, name: str, degree: Optional[float], retrograde: bool, tropical_asc: Optional[float], is_main_planet: bool = True):
        self.name = name
        self.degree = degree
        self.retrograde = retrograde
        self.is_main_planet = is_main_planet
        self.sign = get_tropical_sign_from_degrees(degree) if degree is not None else "N/A"
        self.formatted_position = format_tropical_placement(degree) if degree is not None else "N/A"
        self.sign_percentage = int(round((degree % 30) / 30 * 100)) if degree is not None else 0
        self.house_num, self.house_degrees = -1, "N/A"
        if degree is not None and tropical_asc is not None:
            h_num, d_in_h = find_house_equal(degree, tropical_asc)
            self.house_num = h_num
            self.house_degrees = f"{int(d_in_h)}°{int(round((d_in_h % 1) * 60)):02d}′"
        self.is_luminary = name in ["Sun", "Moon"]
class Aspect:
    def __init__(self, p1: Union[CelestialBody, TropicalCelestialBody], p2: Union[CelestialBody, TropicalCelestialBody], aspect_type: str, orb: float, strength: float):
        self.p1, self.p2, self.type, self.orb, self.strength = p1, p2, aspect_type, orb, strength
class NatalChart:
    def __init__(self, name: str, year: int, month: int, day: int, hour: int, minute: int, latitude: float, longitude: float):
        self.name = name; self.latitude, self.longitude = latitude, longitude
        self.birth_year, self.birth_hour, self.birth_minute = year, hour, minute
        self.jd = swe.julday(year, month, day, hour + minute / 60.0); self.ut_decimal_hour = hour + minute / 60.0
        self.utc_datetime_str = datetime(year, month, day, hour, minute, tzinfo=timezone.utc).strftime("%Y-%m-%d %H:%M")
        self.location_str = f"{abs(latitude):.4f}° {'N' if latitude >= 0 else 'S'}, {abs(longitude):.4f}° {'E' if longitude >= 0 else 'W'}"
        # Sidereal data
        self.celestial_bodies: List[CelestialBody] = []; self.all_points: List[CelestialBody] = []
        self.aspects: List[Aspect] = []; self.aspect_patterns: List[Dict[str, Any]] = []
        self.house_sign_distributions: Dict[str, List[str]] = {}; self.dominance_analysis: Dict[str, Any] = {}
        # Tropical data
        self.tropical_bodies: List[TropicalCelestialBody] = []; self.tropical_points: List[TropicalCelestialBody] = []
        self.tropical_aspects: List[Aspect] = []; self.tropical_aspect_patterns: List[Dict[str, Any]] = []
        self.tropical_dominance: Dict[str, Any] = {}
        self.ascendant_data: Dict[str, Any] = {}; self.day_night_info: Dict[str, Any] = {}
    def calculate_chart(self, unknown_time: bool = False) -> None:
        self._calculate_ascendant_mc_data();
        if self.ascendant_data.get("sidereal_asc") is None: return
        if not unknown_time:
            self._determine_day_night()
        self._calculate_all_points()
        self._calculate_aspects(); self._detect_aspect_patterns()
        self._calculate_tropical_aspects(); self._detect_tropical_aspect_patterns()
        if not unknown_time:
            self._calculate_house_sign_distributions()
        self._analyze_chart_dominance()
        self._analyze_tropical_dominance()
    def _calculate_ascendant_mc_data(self) -> None:
        try:
            res = swe.houses(self.jd, self.latitude, self.longitude, b'P'); ayanamsa = 31.38 + ((self.birth_year - 2000) / 72.0)
            self.ascendant_data = {"tropical_asc": res[1][0], "mc": res[1][1], "ayanamsa": ayanamsa, "sidereal_asc": (res[1][0] - ayanamsa + 360) % 360}
        except Exception as e: print(f"CRITICAL ERROR calculating ascendant: {e}"); self.ascendant_data = {"sidereal_asc": None}
    def _determine_day_night(self) -> None:
        sunrise, sunset = _calculate_approximate_sunrise_sunset_math(self.jd, self.latitude, self.longitude)
        is_day = None
        if sunrise is not None and sunset is not None: is_day = sunrise < sunset and self.ut_decimal_hour >= sunrise and self.ut_decimal_hour < sunset or sunrise > sunset and (self.ut_decimal_hour >= sunrise or self.ut_decimal_hour < sunset)
        self.day_night_info = {"sunrise": sunrise, "sunset": sunset, "status": "Day Birth" if is_day else "Night Birth" if is_day is not None else "Undetermined"}
    def _calculate_all_points(self) -> None:
        sidereal_asc = self.ascendant_data.get("sidereal_asc"); ayanamsa = self.ascendant_data.get("ayanamsa")
        tropical_asc = self.ascendant_data.get("tropical_asc")
        if sidereal_asc is None or ayanamsa is None: return
        configs = PLANETS_CONFIG + ADDITIONAL_BODIES_CONFIG
        for name, code in configs:
            try:
                res = swe.calc_ut(self.jd, code)
                is_retro = res[0][3] < 0
                # Sidereal: subtract ayanamsa
                sidereal_lon = (res[0][0] - ayanamsa + 360) % 360
                # Tropical: use raw longitude
                tropical_lon = res[0][0] % 360
                is_main = any(name == p[0] for p in PLANETS_CONFIG)
                self.celestial_bodies.append(CelestialBody(name, sidereal_lon, is_retro, sidereal_asc, is_main))
                if tropical_asc is not None:
                    self.tropical_bodies.append(TropicalCelestialBody(name, tropical_lon, is_retro, tropical_asc, is_main))
            except Exception as e: print(f"DEBUG: Failed to calculate {name}: {e}"); continue
        self.all_points.extend(self.celestial_bodies)
        self.tropical_points.extend(self.tropical_bodies)
        
        # Sidereal angles
        asc_obj = CelestialBody("Ascendant", sidereal_asc, False, sidereal_asc, False)
        mc_deg = (self.ascendant_data.get('mc') - ayanamsa + 360) % 360 if self.ascendant_data.get('mc') is not None else None
        mc_obj = CelestialBody("Midheaven (MC)", mc_deg, False, sidereal_asc, False)
        desc_obj = CelestialBody("Descendant", (sidereal_asc + 180) % 360, False, sidereal_asc, False)
        ic_deg = (mc_deg + 180) % 360 if mc_deg is not None else None
        ic_obj = CelestialBody("Imum Coeli (IC)", ic_deg, False, sidereal_asc, False)
        
        # Tropical angles
        if tropical_asc is not None:
            trop_asc_obj = TropicalCelestialBody("Ascendant", tropical_asc, False, tropical_asc, False)
            trop_mc_deg = self.ascendant_data.get('mc') % 360 if self.ascendant_data.get('mc') is not None else None
            trop_mc_obj = TropicalCelestialBody("Midheaven (MC)", trop_mc_deg, False, tropical_asc, False)
            trop_desc_obj = TropicalCelestialBody("Descendant", (tropical_asc + 180) % 360, False, tropical_asc, False)
            trop_ic_deg = (trop_mc_deg + 180) % 360 if trop_mc_deg is not None else None
            trop_ic_obj = TropicalCelestialBody("Imum Coeli (IC)", trop_ic_deg, False, tropical_asc, False)
            self.tropical_points.extend(filter(lambda p: p and p.degree is not None, [trop_asc_obj, trop_mc_obj, trop_desc_obj, trop_ic_obj]))
        
        sun = next((p for p in self.celestial_bodies if p.name == 'Sun'), None)
        moon = next((p for p in self.celestial_bodies if p.name == 'Moon'), None)
        pof_obj = None
        if sun and sun.degree is not None and moon and moon.degree is not None and self.day_night_info.get('status') != 'Undetermined':
            is_day = self.day_night_info.get('status') == 'Day Birth'
            pof_deg = (asc_obj.degree + moon.degree - sun.degree + 360) % 360 if is_day else (asc_obj.degree + sun.degree - moon.degree + 360) % 360
            pof_obj = CelestialBody("Part of Fortune", pof_deg, False, sidereal_asc, False)
            if tropical_asc is not None:
                trop_sun = next((p for p in self.tropical_bodies if p.name == 'Sun'), None)
                trop_moon = next((p for p in self.tropical_bodies if p.name == 'Moon'), None)
                if trop_sun and trop_sun.degree is not None and trop_moon and trop_moon.degree is not None:
                    trop_pof_deg = (tropical_asc + trop_moon.degree - trop_sun.degree + 360) % 360 if is_day else (tropical_asc + trop_sun.degree - trop_moon.degree + 360) % 360
                    trop_pof_obj = TropicalCelestialBody("Part of Fortune", trop_pof_deg, False, tropical_asc, False)
                    self.tropical_points.append(trop_pof_obj)
        nn = next((p for p in self.celestial_bodies if p.name == 'True Node'), None)
        sn_obj = CelestialBody("South Node", (nn.degree + 180) % 360, False, sidereal_asc, False) if nn and nn.degree is not None else None
        if nn and nn.degree is not None and tropical_asc is not None:
            trop_nn = next((p for p in self.tropical_bodies if p.name == 'True Node'), None)
            if trop_nn and trop_nn.degree is not None:
                trop_sn_obj = TropicalCelestialBody("South Node", (trop_nn.degree + 180) % 360, False, tropical_asc, False)
                self.tropical_points.append(trop_sn_obj)
        self.all_points.extend(filter(lambda p: p and p.degree is not None, [pof_obj, sn_obj, asc_obj, mc_obj, desc_obj, ic_obj]))
    def _calculate_aspects(self) -> None:
        main_planets = [b for b in self.celestial_bodies if b.is_main_planet and b.degree is not None]
        for p1, p2 in combinations(main_planets, 2):
            diff = min(abs(p1.degree - p2.degree), 360 - abs(p1.degree - p2.degree))
            is_luminary = p1.is_luminary or p2.is_luminary
            for name, angle, orb in ASPECTS_CONFIG:
                orb_max = ASPECT_LUMINARY_ORBS.get(name, orb) if is_luminary else orb
                if abs(diff - angle) <= orb_max: self.aspects.append(Aspect(p1, p2, name, round(diff - angle, 2), round(ASPECT_SCORES.get(name, 1) / (1 + abs(diff - angle)), 2)))
        self.aspects.sort(key=lambda x: -x.strength)
    def _detect_aspect_patterns(self) -> None:
        patterns: List[Dict[str, Any]] = []
        planets = {b.name: b for b in self.celestial_bodies if b.is_main_planet and b.degree is not None}; names = list(planets.keys())
        def find_aspect(p1, p2, type): return any(a.type == type and ((a.p1.name == p1 and a.p2.name == p2) or (a.p1.name == p2 and a.p2.name == p1)) for a in self.aspects)
        if len(names) >= 3:
            for p1, p2, p3 in combinations(names, 3):
                if find_aspect(p1, p2, 'Opposition') and find_aspect(p1, p3, 'Square') and find_aspect(p2, p3, 'Square'):
                    modalities = {MODALITY_MAPPING.get(planets[p].sign) for p in [p1, p2, p3]}; modality = modalities.pop() if len(modalities) == 1 else "Mixed"
                    self.aspect_patterns.append({"description": f"{p1} opp {p2}, focal {p3} ({modality} T-Square)"})
        sign_groups = {};
        for name, p in planets.items(): sign_groups.setdefault(p.sign, []).append(name)
        for sign, members in sign_groups.items():
            if len(members) >= 3:
                el = ELEMENT_MAPPING.get(sign, ''); mod = MODALITY_MAPPING.get(sign, '')
                self.aspect_patterns.append({"description": f"{len(members)} bodies in {sign} ({el}, {mod} Sign Stellium)"})
    def _calculate_house_sign_distributions(self) -> None:
        asc = self.ascendant_data.get("sidereal_asc")
        if asc is None: return
        for i in range(12):
            house_num = i + 1; house_start = (asc + i * 30) % 360; house_end = (house_start + 30) % 360
            segments = []
            house_segments = [(house_start, 360.0), (0.0, house_end)] if house_end < house_start else [(house_start, house_end)]
            for sign_name, sign_start, sign_end in TRUE_SIDEREAL_SIGNS:
                for h_start, h_end in house_segments:
                    overlap_start = max(h_start, sign_start); overlap_end = min(h_end, sign_end)
                    if overlap_start < overlap_end:
                        if abs((overlap_end - overlap_start) - (sign_end - sign_start)) < 0.01: segments.append(f"{sign_name} (complete)")
                        else: segments.append(f"{sign_name} {(overlap_start - sign_start):.1f}°–{(overlap_end - sign_start):.1f}°")
            self.house_sign_distributions[f"House {house_num}"] = segments
    def _analyze_chart_dominance(self) -> None:
        counts = {'sign': {}, 'element': {}, 'modality': {}}; strength = {}
        main_planets = [b for b in self.celestial_bodies if b.is_main_planet and b.degree is not None and b.name != "True Node"]
        for b in main_planets:
            if b.sign != "Unknown":
                counts['sign'][b.sign] = counts['sign'].get(b.sign, 0) + 1
                el = ELEMENT_MAPPING.get(b.sign); counts['element'][el] = counts['element'].get(el, 0) + 1
                mod = MODALITY_MAPPING.get(b.sign); counts['modality'][mod] = counts['modality'].get(mod, 0) + 1
        for a in self.aspects: strength[a.p1.name] = strength.get(a.p1.name, 0) + a.strength; strength[a.p2.name] = strength.get(a.p2.name, 0) + a.strength
        self.dominance_analysis = {f"dominant_{k}": max(v, key=v.get) if v else "N/A" for k, v in counts.items()}
        self.dominance_analysis['dominant_planet'] = max(strength, key=strength.get) if strength else "N/A"
        self.dominance_analysis['counts'] = counts; self.dominance_analysis['strength'] = {k: round(v, 2) for k, v in strength.items()}
    
    def _calculate_tropical_aspects(self) -> None:
        """Calculate aspects for tropical chart."""
        main_planets = [b for b in self.tropical_bodies if b.is_main_planet and b.degree is not None]
        for p1, p2 in combinations(main_planets, 2):
            diff = min(abs(p1.degree - p2.degree), 360 - abs(p1.degree - p2.degree))
            is_luminary = p1.is_luminary or p2.is_luminary
            for name, angle, orb in ASPECTS_CONFIG:
                orb_max = ASPECT_LUMINARY_ORBS.get(name, orb) if is_luminary else orb
                if abs(diff - angle) <= orb_max:
                    self.tropical_aspects.append(Aspect(p1, p2, name, round(diff - angle, 2), round(ASPECT_SCORES.get(name, 1) / (1 + abs(diff - angle)), 2)))
        self.tropical_aspects.sort(key=lambda x: -x.strength)
    
    def _detect_tropical_aspect_patterns(self) -> None:
        """Detect aspect patterns in tropical chart."""
        patterns: List[Dict[str, Any]] = []
        planets = {b.name: b for b in self.tropical_bodies if b.is_main_planet and b.degree is not None}
        names = list(planets.keys())
        def find_aspect(p1, p2, type): 
            return any(a.type == type and ((a.p1.name == p1 and a.p2.name == p2) or (a.p1.name == p2 and a.p2.name == p1)) for a in self.tropical_aspects)
        if len(names) >= 3:
            for p1, p2, p3 in combinations(names, 3):
                if find_aspect(p1, p2, 'Opposition') and find_aspect(p1, p3, 'Square') and find_aspect(p2, p3, 'Square'):
                    modalities = {MODALITY_MAPPING.get(planets[p].sign) for p in [p1, p2, p3]}
                    modality = modalities.pop() if len(modalities) == 1 else "Mixed"
                    self.tropical_aspect_patterns.append({"description": f"{p1} opp {p2}, focal {p3} ({modality} T-Square)"})
        sign_groups = {}
        for name, p in planets.items():
            sign_groups.setdefault(p.sign, []).append(name)
        for sign, members in sign_groups.items():
            if len(members) >= 3:
                el = ELEMENT_MAPPING.get(sign, '')
                mod = MODALITY_MAPPING.get(sign, '')
                self.tropical_aspect_patterns.append({"description": f"{len(members)} bodies in {sign} ({el}, {mod} Sign Stellium)"})
    
    def _analyze_tropical_dominance(self) -> None:
        """Analyze dominance in tropical chart."""
        counts = {'sign': {}, 'element': {}, 'modality': {}}
        strength = {}
        main_planets = [b for b in self.tropical_bodies if b.is_main_planet and b.degree is not None and b.name != "True Node"]
        for b in main_planets:
            if b.sign != "N/A":
                counts['sign'][b.sign] = counts['sign'].get(b.sign, 0) + 1
                el = ELEMENT_MAPPING.get(b.sign)
                counts['element'][el] = counts['element'].get(el, 0) + 1
                mod = MODALITY_MAPPING.get(b.sign)
                counts['modality'][mod] = counts['modality'].get(mod, 0) + 1
        for a in self.tropical_aspects:
            strength[a.p1.name] = strength.get(a.p1.name, 0) + a.strength
            strength[a.p2.name] = strength.get(a.p2.name, 0) + a.strength
        self.tropical_dominance = {f"dominant_{k}": max(v, key=v.get) if v else "N/A" for k, v in counts.items()}
        self.tropical_dominance['dominant_planet'] = max(strength, key=strength.get) if strength else "N/A"
        self.tropical_dominance['counts'] = counts
        self.tropical_dominance['strength'] = {k: round(v, 2) for k, v in strength.items()}
    
    def get_full_chart_data(self, numerology: dict, name_numerology: Optional[dict], chinese_zodiac: dict, unknown_time: bool) -> dict:
        """Build the full chart response dictionary."""
        # Major positions order
        MAJOR_POSITIONS_ORDER = ['Ascendant', 'Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn', 'Uranus', 'Neptune', 'Pluto', 'Chiron', 'True Node', 'South Node', 'Descendant', 'Midheaven (MC)', 'Imum Coeli (IC)']
        
        # Build sidereal major positions
        sidereal_major_positions = []
        for p in sorted(self.all_points, key=lambda x: MAJOR_POSITIONS_ORDER.index(x.name) if x.name in MAJOR_POSITIONS_ORDER else 99):
            if p.name in MAJOR_POSITIONS_ORDER:
                sidereal_major_positions.append({
                    "name": p.name,
                    "position": p.formatted_position,
                    "degrees": p.degree,
                    "percentage": p.sign_percentage,
                    "retrograde": p.retrograde,
                    "house_info": f"– House {p.house_num}, {p.house_degrees}" if p.house_num > 0 and not unknown_time else "",
                    "house_num": p.house_num
                })
        
        # Build sidereal retrogrades
        sidereal_retrogrades = [{"name": p.name} for p in self.celestial_bodies if p.retrograde and p.is_main_planet]
        
        # Build sidereal aspects
        sidereal_aspects = [{
            "p1_name": f"{a.p1.name} in {a.p1.sign}{' (Rx)' if a.p1.retrograde else ''}",
            "p2_name": f"{a.p2.name} in {a.p2.sign}{' (Rx)' if a.p2.retrograde else ''}",
            "type": a.type,
            "orb": f"{abs(a.orb):.2f}°",
            "score": f"{a.strength:.2f}",
            "p1_degrees": a.p1.degree,
            "p2_degrees": a.p2.degree
        } for a in self.aspects]
        
        # Build additional points
        sidereal_additional_points = []
        for p in sorted(self.all_points, key=lambda x: x.name):
            if p.name not in MAJOR_POSITIONS_ORDER:
                sidereal_additional_points.append({
                    "name": p.name,
                    "info": f"{p.formatted_position} – House {p.house_num}, {p.house_degrees}" if p.house_num > 0 and not unknown_time else p.formatted_position,
                    "retrograde": p.retrograde
                })
        
        # Build house rulers
        house_rulers = {}
        if not unknown_time and self.ascendant_data.get("sidereal_asc") is not None:
            for i in range(12):
                cusp_deg = (self.ascendant_data['sidereal_asc'] + i * 30) % 360
                sign, ruler_name = get_sign_and_ruler(cusp_deg)
                ruler_body = next((p for p in self.celestial_bodies if p.name == ruler_name), None)
                ruler_pos = f"– {ruler_body.formatted_position} – House {ruler_body.house_num}, {ruler_body.house_degrees}" if ruler_body and ruler_body.degree is not None else ""
                house_rulers[f"House {i+1}"] = f"{sign} (Ruler: {ruler_name} {ruler_pos})"
        
        # Build chart analysis
        chart_ruler = "N/A"
        if self.ascendant_data.get("sidereal_asc") is not None:
            _, chart_ruler = get_sign_and_ruler(self.ascendant_data['sidereal_asc'])
        
        sidereal_chart_analysis = {
            "chart_ruler": chart_ruler,
            "dominant_sign": self.dominance_analysis.get("dominant_sign", "N/A"),
            "dominant_element": self.dominance_analysis.get("dominant_element", "N/A"),
            "dominant_modality": self.dominance_analysis.get("dominant_modality", "N/A"),
            "dominant_planet": self.dominance_analysis.get("dominant_planet", "N/A")
        }
        
        # Build house cusps
        sidereal_house_cusps = []
        tropical_house_cusps = []
        if not unknown_time and self.ascendant_data.get("sidereal_asc") is not None:
            for i in range(12):
                sidereal_house_cusps.append((self.ascendant_data['sidereal_asc'] + i * 30) % 360)
                if self.ascendant_data.get("tropical_asc") is not None:
                    tropical_house_cusps.append((self.ascendant_data['tropical_asc'] + i * 30) % 360)
        
        # Build tropical major positions
        tropical_major_positions = []
        for p in sorted(self.tropical_points, key=lambda x: MAJOR_POSITIONS_ORDER.index(x.name) if x.name in MAJOR_POSITIONS_ORDER else 99):
            if p.name in MAJOR_POSITIONS_ORDER:
                tropical_major_positions.append({
                    "name": p.name,
                    "position": p.formatted_position,
                    "degrees": p.degree,
                    "percentage": p.sign_percentage,
                    "retrograde": p.retrograde,
                    "house_info": f"– House {p.house_num}, {p.house_degrees}" if p.house_num > 0 and not unknown_time else "",
                    "house_num": p.house_num
                })
        
        # Build tropical retrogrades
        tropical_retrogrades = [{"name": p.name} for p in self.tropical_bodies if p.retrograde and p.is_main_planet]
        
        # Build tropical aspects
        tropical_aspects = [{
            "p1_name": f"{a.p1.name} in {a.p1.sign}{' (Rx)' if a.p1.retrograde else ''}",
            "p2_name": f"{a.p2.name} in {a.p2.sign}{' (Rx)' if a.p2.retrograde else ''}",
            "type": a.type,
            "orb": f"{abs(a.orb):.2f}°",
            "score": f"{a.strength:.2f}",
            "p1_degrees": a.p1.degree,
            "p2_degrees": a.p2.degree
        } for a in self.tropical_aspects]
        
        # Build tropical additional points
        tropical_additional_points = []
        for p in sorted(self.tropical_points, key=lambda x: x.name):
            if p.name not in MAJOR_POSITIONS_ORDER:
                tropical_additional_points.append({
                    "name": p.name,
                    "info": f"{p.formatted_position} – House {p.house_num}, {p.house_degrees}" if p.house_num > 0 and not unknown_time else p.formatted_position,
                    "retrograde": p.retrograde
                })
        
        # Build tropical chart analysis
        tropical_chart_analysis = {
            "dominant_sign": f"{self.tropical_dominance.get('dominant_sign', 'N/A')} ({self.tropical_dominance.get('counts', {}).get('sign', {}).get(self.tropical_dominance.get('dominant_sign'), 0)} placements)" if self.tropical_dominance.get('dominant_sign') != 'N/A' else "N/A",
            "dominant_element": f"{self.tropical_dominance.get('dominant_element', 'N/A')} ({self.tropical_dominance.get('counts', {}).get('element', {}).get(self.tropical_dominance.get('dominant_element'), 0)})" if self.tropical_dominance.get('dominant_element') != 'N/A' else "N/A",
            "dominant_modality": f"{self.tropical_dominance.get('dominant_modality', 'N/A')} ({self.tropical_dominance.get('counts', {}).get('modality', {}).get(self.tropical_dominance.get('dominant_modality'), 0)})" if self.tropical_dominance.get('dominant_modality') != 'N/A' else "N/A",
            "dominant_planet": f"{self.tropical_dominance.get('dominant_planet', 'N/A')} (score {self.tropical_dominance.get('strength', {}).get(self.tropical_dominance.get('dominant_planet'), 0.0):.2f})" if self.tropical_dominance.get('dominant_planet') != 'N/A' else "N/A"
        }
        
        return {
            "name": self.name,
            "utc_datetime": self.utc_datetime_str,
            "location": self.location_str,
            "day_night_status": self.day_night_info.get("status", "N/A"),
            "chinese_zodiac": f"{chinese_zodiac.get('element', '')} {chinese_zodiac.get('animal', '')}",
            "numerology_analysis": {
                "life_path_number": numerology.get("life_path_number", "N/A"),
                "day_number": numerology.get("day_number", "N/A"),
                "name_numerology": name_numerology
            },
            "unknown_time": unknown_time,
            "true_sidereal_signs": TRUE_SIDEREAL_SIGNS,
            "sidereal_house_cusps": sidereal_house_cusps,
            "tropical_house_cusps": tropical_house_cusps,
            "house_rulers": house_rulers,
            "house_sign_distributions": self.house_sign_distributions,
            "sidereal_chart_analysis": sidereal_chart_analysis,
            "sidereal_major_positions": sidereal_major_positions,
            "sidereal_retrogrades": sidereal_retrogrades,
            "sidereal_aspects": sidereal_aspects,
            "sidereal_aspect_patterns": self.aspect_patterns,
            "sidereal_additional_points": sidereal_additional_points,
            "tropical_chart_analysis": tropical_chart_analysis,
            "tropical_major_positions": tropical_major_positions,
            "tropical_retrogrades": tropical_retrogrades,
            "tropical_aspects": tropical_aspects,
            "tropical_aspect_patterns": self.tropical_aspect_patterns,
            "tropical_additional_points": tropical_additional_points
        }