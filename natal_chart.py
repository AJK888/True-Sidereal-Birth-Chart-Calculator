# natal_chart.py

from datetime import datetime, timezone
import math
from itertools import combinations
from typing import List, Tuple, Dict, Any, Union, Optional
import swisseph as swe

# --- Constants ---
TRUE_SIDEREAL_SIGNS = [("Aries",0.0,19.7286),("Taurus",19.7286,56.5875),("Gemini",56.5875,86.0412),("Cancer",86.0412,103.19),("Leo",103.19,141.6065),("Virgo",141.6065,191.32),("Libra",191.32,210.1972),("Scorpio",210.1972,223.4245),("Ophiuchus",223.4245,235.7818),("Sagittarius",235.7818,269.2677),("Capricorn",269.2677,294.8435),("Aquarius",294.8435,318.0103),("Pisces",318.0103,360.0)]
TROPICAL_SIGNS = [("Aries", 0), ("Taurus", 30), ("Gemini", 60), ("Cancer", 90),("Leo", 120), ("Virgo", 150), ("Libra", 180), ("Scorpio", 210),("Sagittarius", 240), ("Capricorn", 270), ("Aquarius", 300), ("Pisces", 330)]
SIGN_RULERS: Dict[str, str] = {"Aries":"Mars","Taurus":"Venus","Gemini":"Mercury","Cancer":"Moon","Leo":"Sun","Virgo":"Mercury","Libra":"Venus","Scorpio":"Pluto","Ophiuchus":"Chiron","Sagittarius":"Jupiter","Capricorn":"Saturn","Aquarius":"Uranus","Pisces":"Neptune"}
ELEMENT_MAPPING: Dict[str, str] = {"Aries":"Fire","Leo":"Fire","Sagittarius":"Fire","Ophiuchus":"Fire","Taurus":"Earth","Virgo":"Earth","Capricorn":"Earth","Gemini":"Air","Libra":"Air","Aquarius":"Air","Cancer":"Water","Scorpio":"Water","Pisces":"Water"}
MODALITY_MAPPING: Dict[str, str] = {"Aries":"Cardinal","Cancer":"Cardinal","Libra":"Cardinal","Capricorn":"Cardinal","Taurus":"Fixed","Leo":"Fixed","Scorpio":"Fixed","Aquarius":"Fixed","Gemini":"Mutable","Virgo":"Mutable","Sagittarius":"Mutable","Pisces":"Mutable","Ophiuchus":"Mutable"}
PLANETS_CONFIG: List[Tuple[str, int]] = [("Sun",swe.SUN),("Moon",swe.MOON),("Mercury",swe.MERCURY),("Venus",swe.VENUS),("Mars",swe.MARS),("Jupiter",swe.JUPITER),("Saturn",swe.SATURN),("Uranus",swe.URANUS),("Neptune",swe.NEPTUNE),("Pluto",swe.PLUTO),("Chiron",swe.CHIRON),("True Node",swe.TRUE_NODE)]
ADDITIONAL_BODIES_CONFIG: List[Tuple[str, int]] = [("Lilith",swe.MEAN_APOG),("Vertex",swe.VERTEX),("Ceres",swe.CERES),("Pallas",swe.PALLAS),("Juno",swe.JUNO),("Vesta",swe.VESTA)]
ASPECTS_CONFIG: List[Tuple[str, float, float]] = [("Conjunction",0,8),("Opposition",180,8),("Trine",120,6),("Square",90,6),("Sextile",60,4),("Quincunx",150,3),("Semisextile",30,2),("Semisquare",45,2),("Sesquiquadrate",135,2),("Quintile",72,1),("Biquintile",144,1)]
ASPECT_LUMINARY_ORBS: Dict[str, float] = {"Conjunction":10,"Opposition":10,"Trine":8,"Square":8,"Sextile":6}
ASPECT_SCORES: Dict[str, float] = {"Conjunction":5,"Opposition":4,"Trine":3.5,"Square":3,"Sextile":2.5,"Quincunx":2,"Semisextile":1.5,"Semisquare":1.5,"Sesquiquadrate":1.5,"Quintile":1.8,"Biquintile":1.8}
CHINESE_LUNAR_NEW_YEAR = {
    1930:(1,30), 1931:(2,17), 1932:(2,6), 1933:(1,26), 1934:(2,14), 1935:(2,4), 1936:(1,24), 1937:(2,11), 1938:(1,31), 1939:(2,19),
    1940:(2,8), 1941:(1,27), 1942:(2,15), 1943:(2,5), 1944:(1,25), 1945:(2,13), 1946:(2,2), 1947:(1,22), 1948:(2,10), 1949:(1,29),
    1950:(2,17), 1951:(2,6), 1952:(1,27), 1953:(2,14), 1954:(2,3), 1955:(1,24), 1956:(2,12), 1957:(1,31), 1958:(2,18), 1959:(2,8),
    1960:(1,28), 1961:(2,15), 1962:(2,5), 1963:(1,25), 1964:(2,13), 1965:(2,2), 1966:(1,21), 1967:(2,9), 1968:(1,30), 1969:(2,17),
    1970:(2,6), 1971:(1,27), 1972:(2,15), 1973:(2,3), 1974:(1,23), 1975:(2,11), 1976:(1,31), 1977:(2,18), 1978:(2,7), 1979:(1,28),
    1980:(2,16), 1981:(2,5), 1982:(1,25), 1983:(2,13), 1984:(2,2), 1985:(2,20), 1986:(2,9), 1987:(1,29), 1988:(2,17), 1989:(2,6),
    1990:(1,27), 1991:(2,15), 1992:(2,4), 1993:(1,23), 1994:(2,10), 1995:(1,31), 1996:(2,19), 1997:(2,7), 1998:(1,28), 1999:(2,16),
    2000:(2,5), 2001:(1,24), 2002:(2,12), 2003:(2,1), 2004:(1,22), 2005:(2,9), 2006:(1,29), 2007:(2,18), 2008:(2,7), 2009:(1,26),
    2010:(2,14), 2011:(2,3), 2012:(1,23), 2013:(2,10), 2014:(1,31), 2015:(2,19), 2016:(2,8), 2017:(1,28), 2018:(2,16), 2019:(2,5),
    2020:(1,25), 2021:(2,12), 2022:(2,1), 2023:(1,22), 2024:(2,10), 2025:(1,29), 2026:(2,17), 2027:(2,6), 2028:(1,26), 2029:(2,13)
}

# --- Helper Functions ---
def format_true_sidereal_placement(degrees: float) -> str:
    for sign, start, end in TRUE_SIDEREAL_SIGNS:
        if start <= degrees < end:
            deg_into_sign = degrees - start; d = int(deg_into_sign); m = int(round((deg_into_sign - d) * 60))
            return f"{d}°{m:02d}′ {sign}"
    return "Out of Bounds"
def format_tropical_placement(degrees: float) -> str:
    sign_index = int(degrees / 30); sign = TROPICAL_SIGNS[sign_index][0]
    deg_into_sign = degrees % 30; d = int(deg_into_sign); m = int(round((deg_into_sign - d) * 60))
    return f"{d}°{m:02d}′ {sign}"
def get_sign_and_ruler(degrees: float) -> Tuple[str, str]:
    for sign, start, end in TRUE_SIDEREAL_SIGNS:
        if start <= degrees < end: return sign, SIGN_RULERS.get(sign, "Unknown")
    return "Unknown", "Unknown"
def get_sign_from_degrees(degrees: float, zodiac_type: str = "sidereal") -> str:
    if zodiac_type == "sidereal":
        for sign, start, end in TRUE_SIDEREAL_SIGNS:
            if start <= degrees < end: return sign
    else: # Tropical
        if 0 <= degrees < 360: return TROPICAL_SIGNS[int(degrees / 30)][0]
    return "Unknown"
def find_house_equal(deg: float, asc: float) -> Tuple[int, float]:
    for i in range(12):
        house_start = (asc + i * 30) % 360; house_end = (house_start + 30) % 360
        if house_end < house_start:
            if deg >= house_start or deg < house_end: return i + 1, (deg - house_start + 360) % 360
        elif house_start <= deg < house_end: return i + 1, (deg - house_start) % 360
    return -1, 0
def calculate_numerology(day: int, month: int, year: int) -> dict:
    def reduce_number(n: int) -> str:
        final_num = n
        while final_num > 9 and final_num not in [11, 22, 33]: final_num = sum(int(digit) for digit in str(final_num))
        if final_num in [11, 22, 33]: return f"{final_num}/{sum(int(digit) for digit in str(final_num))}"
        else:
            while final_num > 9: final_num = sum(int(digit) for digit in str(final_num))
            return str(final_num)
    life_path = reduce_number(sum(int(digit) for digit in f"{day}{month}{year}"))
    day_number = reduce_number(sum(int(digit) for digit in str(day)))
    return {"life_path": life_path, "day_number": day_number}
def calculate_name_numerology(full_name: str) -> dict:
    letter_values = {'a': 1, 'b': 2, 'c': 3, 'd': 4, 'e': 5, 'f': 6, 'g': 7, 'h': 8, 'i': 9, 'j': 1, 'k': 2, 'l': 3, 'm': 4, 'n': 5, 'o': 6, 'p': 7, 'q': 8, 'r': 9, 's': 1, 't': 2, 'u': 3, 'v': 4, 'w': 5, 'x': 6, 'y': 7, 'z': 8}
    vowels = "aeiou"
    def reduce_number(n: int) -> str:
        final_num = n
        while final_num > 9 and final_num not in [11, 22, 33]: final_num = sum(int(digit) for digit in str(final_num))
        if final_num in [11, 22, 33]: return f"{final_num}/{sum(int(digit) for digit in str(final_num))}"
        else:
            while final_num > 9: final_num = sum(int(digit) for digit in str(final_num))
            return str(final_num)
    clean_name = full_name.lower().replace(" ", "")
    expression_sum = sum(letter_values.get(char, 0) for char in clean_name)
    expression_number = reduce_number(expression_sum)
    soul_urge_sum = sum(letter_values.get(char, 0) for char in clean_name if char in vowels)
    soul_urge_number = reduce_number(soul_urge_sum)
    personality_sum = sum(letter_values.get(char, 0) for char in clean_name if char not in vowels)
    personality_number = reduce_number(personality_sum)
    return {"expression_number": expression_number, "soul_urge_number": soul_urge_number, "personality_number": personality_number}

def get_chinese_zodiac_and_element(year: int, month: int, day: int) -> Dict[str, str]:
    zodiac_animals = ["Rat", "Ox", "Tiger", "Rabbit", "Dragon", "Snake", "Horse", "Goat", "Monkey", "Rooster", "Dog", "Pig"]
    elements = ["Metal", "Water", "Wood", "Fire", "Earth"]
    
    effective_year = year
    lunar_new_year_month, lunar_new_year_day = CHINESE_LUNAR_NEW_YEAR.get(year, (1, 1))
    if (month < lunar_new_year_month) or (month == lunar_new_year_month and day < lunar_new_year_day):
        effective_year -= 1

    animal = zodiac_animals[(effective_year - 1924) % 12]
    
    last_digit = year % 10
    element = elements[(last_digit // 2) - (1 if last_digit < 2 else 0)]

    return {"animal": animal, "element": element}

# --- Core Classes ---
class SiderealBody:
    def __init__(self, name: str, degree: Optional[float], retrograde: bool, sidereal_asc: Optional[float], is_main_planet: bool = True):
        self.name = name; self.degree = degree; self.retrograde = retrograde; self.is_main_planet = is_main_planet
        self.sign = get_sign_from_degrees(degree, "sidereal") if degree is not None else "N/A"
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
class TropicalBody:
    def __init__(self, name: str, degree: Optional[float], retrograde: bool, tropical_asc: Optional[float], is_main_planet: bool = True):
        self.name = name; self.degree = degree; self.retrograde = retrograde; self.is_main_planet = is_main_planet
        self.sign = get_sign_from_degrees(degree, "tropical") if degree is not None else "N/A"
        self.formatted_position = format_tropical_placement(degree) if degree is not None else "N/A"
        self.sign_percentage = int(round((degree % 30) / 30 * 100)) if degree is not None else 0
        self.house_num, self.house_degrees = -1, "N/A"
        if degree is not None and tropical_asc is not None:
            h_num, d_in_h = find_house_equal(degree, tropical_asc)
            self.house_num = h_num; self.house_degrees = f"{int(d_in_h)}°{int(round((d_in_h % 1) * 60)):02d}′"
        self.is_luminary = name in ["Sun", "Moon"]
class Aspect:
    def __init__(self, p1, p2, aspect_type: str, orb: float, strength: float):
        self.p1, self.p2, self.type, self.orb, self.strength = p1, p2, aspect_type, orb, strength
class NatalChart:
    MAJOR_POSITIONS_ORDER = [
        'Ascendant', 'Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn',
        'Uranus', 'Neptune', 'Pluto', 'Chiron', 'True Node', 'South Node',
        'Descendant', 'Midheaven (MC)', 'Imum Coeli (IC)'
    ]
    
    def __init__(self, name: str, year: int, month: int, day: int, hour: int, minute: int, latitude: float, longitude: float, local_hour: int):
        self.name = name; self.latitude, self.longitude = latitude, longitude
        self.birth_year, self.birth_hour, self.birth_minute = year, hour, minute
        self.local_hour = local_hour
        self.jd = swe.julday(year, month, day, hour + minute / 60.0); self.ut_decimal_hour = hour + minute / 60.0
        self.utc_datetime_str = datetime(year, month, day, hour, minute, tzinfo=timezone.utc).strftime("%Y-%m-%d %H:%M")
        self.location_str = f"{abs(latitude):.4f}° {'N' if latitude >= 0 else 'S'}, {abs(longitude):.4f}° {'E' if longitude >= 0 else 'W'}"
        self.sidereal_bodies: List[SiderealBody] = []; self.all_sidereal_points: List[SiderealBody] = []
        self.tropical_bodies: List[TropicalBody] = []; self.all_tropical_points: List[TropicalBody] = []
        self.sidereal_aspects: List[Aspect] = []; self.tropical_aspects: List[Aspect] = []
        self.sidereal_aspect_patterns: List[Dict[str, Any]] = []; self.tropical_aspect_patterns: List[Dict[str, Any]] = []
        self.house_sign_distributions: Dict[str, List[str]] = {}; self.sidereal_dominance: Dict[str, Any] = {}; self.tropical_dominance: Dict[str, Any] = {}
        self.ascendant_data: Dict[str, Any] = {}; self.day_night_info: Dict[str, Any] = {}

    def calculate_chart(self) -> None:
        self._calculate_ascendant_mc_data()
        if self.ascendant_data.get("sidereal_asc") is None:
            return

        self._determine_day_night()
        self._calculate_all_points()
        self._calculate_aspects()
        self._calculate_house_sign_distributions()
        self._analyze_dominance()
        self._detect_aspect_patterns()

    
    def _calculate_ascendant_mc_data(self) -> None:
        try:
            res = swe.houses(self.jd, self.latitude, self.longitude, b'E')
            ayanamsa = 31.38 + ((self.birth_year - 2000) / 72.0)
            self.ascendant_data = {"tropical_asc": res[1][0], "mc": res[1][1], "ayanamsa": ayanamsa, "sidereal_asc": (res[1][0] - ayanamsa + 360) % 360}
        except Exception as e: print(f"CRITICAL ERROR calculating ascendant: {e}"); self.ascendant_data = {"sidereal_asc": None}
    
    def _determine_day_night(self) -> None:
        is_day = 6 <= self.local_hour < 18
        self.day_night_info = {
            "status": "Day Birth (Approx.)" if is_day else "Night Birth (Approx.)"
        }

    def _calculate_all_points(self) -> None:
        sidereal_asc = self.ascendant_data.get("sidereal_asc"); tropical_asc = self.ascendant_data.get("tropical_asc"); ayanamsa = self.ascendant_data.get("ayanamsa")
        if sidereal_asc is None or ayanamsa is None: return
        configs = PLANETS_CONFIG + ADDITIONAL_BODIES_CONFIG
        for name, code in configs:
            try:
                res = swe.calc_ut(self.jd, code); is_retro = res[0][3] < 0; tropical_lon = res[0][0]; sidereal_lon = (tropical_lon - ayanamsa + 360) % 360
                is_main = any(name == p[0] for p in PLANETS_CONFIG)
                self.sidereal_bodies.append(SiderealBody(name, sidereal_lon, is_retro, sidereal_asc, is_main))
                self.tropical_bodies.append(TropicalBody(name, tropical_lon, is_retro, tropical_asc, is_main))
            except Exception as e: print(f"DEBUG: Failed to calculate {name}: {e}"); continue
        self.all_sidereal_points.extend(self.sidereal_bodies); self.all_tropical_points.extend(self.tropical_bodies)
        s_asc = SiderealBody("Ascendant", sidereal_asc, False, sidereal_asc, False)
        s_mc_deg = (self.ascendant_data.get('mc') - ayanamsa + 360) % 360 if self.ascendant_data.get('mc') is not None else None
        s_mc = SiderealBody("Midheaven (MC)", s_mc_deg, False, sidereal_asc, False)
        t_asc = TropicalBody("Ascendant", tropical_asc, False, tropical_asc, False)
        t_mc = TropicalBody("Midheaven (MC)", self.ascendant_data.get('mc'), False, tropical_asc, False)
        points_to_add = [
            (s_asc, t_asc), (s_mc, t_mc),
            (SiderealBody("Descendant", (s_asc.degree + 180)%360, False, sidereal_asc, False), TropicalBody("Descendant", (t_asc.degree + 180)%360, False, tropical_asc, False)),
            (SiderealBody("Imum Coeli (IC)", (s_mc.degree + 180)%360, False, sidereal_asc, False), TropicalBody("Imum Coeli (IC)", (t_mc.degree + 180)%360, False, tropical_asc, False)),
        ]
        sun_s = next((p for p in self.sidereal_bodies if p.name == 'Sun'), None); moon_s = next((p for p in self.sidereal_bodies if p.name == 'Moon'), None)
        sun_t = next((p for p in self.tropical_bodies if p.name == 'Sun'), None); moon_t = next((p for p in self.tropical_bodies if p.name == 'Moon'), None)
        if sun_s and moon_s and sun_s.degree is not None and moon_s.degree is not None and s_asc.degree is not None and t_asc.degree is not None and self.day_night_info.get('status') != 'Undetermined':
            is_day = "Day Birth" in self.day_night_info.get('status', "")
            s_pof_deg = (s_asc.degree + moon_s.degree - sun_s.degree + 360) % 360 if is_day else (s_asc.degree + sun_s.degree - moon_s.degree + 360) % 360
            t_pof_deg = (t_asc.degree + moon_t.degree - sun_t.degree + 360) % 360 if is_day else (t_asc.degree + sun_t.degree - moon_t.degree + 360) % 360
            points_to_add.append((SiderealBody("Part of Fortune", s_pof_deg, False, sidereal_asc, False), TropicalBody("Part of Fortune", t_pof_deg, False, tropical_asc, False)))
        nn_s = next((p for p in self.sidereal_bodies if p.name == 'True Node'), None); nn_t = next((p for p in self.tropical_bodies if p.name == 'True Node'), None)
        if nn_s and nn_t and nn_s.degree is not None and nn_t.degree is not None:
            points_to_add.append((SiderealBody("South Node", (nn_s.degree + 180)%360, False, sidereal_asc, False), TropicalBody("South Node", (nn_t.degree + 180)%360, False, tropical_asc, False)))
        for s_point, t_point in points_to_add:
            if s_point and s_point.degree is not None: self.all_sidereal_points.append(s_point)
            if t_point and t_point.degree is not None: self.all_tropical_points.append(t_point)
    def _calculate_aspects(self) -> None:
        main_s = [b for b in self.sidereal_bodies if b.is_main_planet and b.degree is not None]
        for p1, p2 in combinations(main_s, 2):
            diff = min(abs(p1.degree - p2.degree), 360 - abs(p1.degree - p2.degree))
            is_luminary = p1.is_luminary or p2.is_luminary
            for name, angle, orb in ASPECTS_CONFIG:
                orb_max = ASPECT_LUMINARY_ORBS.get(name, orb) if is_luminary else orb
                if abs(diff - angle) <= orb_max: self.sidereal_aspects.append(Aspect(p1, p2, name, round(diff - angle, 2), round(ASPECT_SCORES.get(name, 1) / (1 + abs(diff - angle)), 2)))
        self.sidereal_aspects.sort(key=lambda x: -x.strength)
        main_t = [b for b in self.tropical_bodies if b.is_main_planet and b.degree is not None]
        for p1, p2 in combinations(main_t, 2):
            diff = min(abs(p1.degree - p2.degree), 360 - abs(p1.degree - p2.degree))
            is_luminary = p1.is_luminary or p2.is_luminary
            for name, angle, orb in ASPECTS_CONFIG:
                orb_max = ASPECT_LUMINARY_ORBS.get(name, orb) if is_luminary else orb
                if abs(diff - angle) <= orb_max: self.tropical_aspects.append(Aspect(p1, p2, name, round(diff - angle, 2), round(ASPECT_SCORES.get(name, 1) / (1 + abs(diff - angle)), 2)))
        self.tropical_aspects.sort(key=lambda x: -x.strength)
    def _detect_aspect_patterns(self) -> None:
        # Helper function to find a specific aspect object between two planets
        def get_aspect(p1_name: str, p2_name: str, aspect_type: str, aspects_list: List[Aspect]) -> Optional[Aspect]:
            for aspect in aspects_list:
                if aspect.type == aspect_type and (
                    (aspect.p1.name == p1_name and aspect.p2.name == p2_name) or
                    (aspect.p1.name == p2_name and aspect.p2.name == p1_name)
                ):
                    return aspect
            return None

        # --- Sidereal Patterns ---
        planets_s = {b.name: b for b in self.sidereal_bodies if b.is_main_planet and b.degree is not None}
        names_s = list(planets_s.keys())
        if len(names_s) >= 3:
            for p1, p2, p3 in combinations(names_s, 3):
                opp = get_aspect(p1, p2, 'Opposition', self.sidereal_aspects)
                sq1 = get_aspect(p1, p3, 'Square', self.sidereal_aspects)
                sq2 = get_aspect(p2, p3, 'Square', self.sidereal_aspects)
                if opp and sq1 and sq2:
                    modalities = {MODALITY_MAPPING.get(planets_s[p].sign) for p in [p1, p2, p3]}
                    modality = modalities.pop() if len(modalities) == 1 else "Mixed"
                    avg_orb = (abs(opp.orb) + abs(sq1.orb) + abs(sq2.orb)) / 3
                    total_score = opp.strength + sq1.strength + sq2.strength
                    self.sidereal_aspect_patterns.append({
                        "description": f"{p1} opp {p2}, focal {p3} ({modality} T-Square)",
                        "orb": f"{avg_orb:.2f}°",
                        "score": f"{total_score:.2f}"
                    })

        sign_groups_s = {}
        for name, p in planets_s.items():
            sign_groups_s.setdefault(p.sign, []).append(name)
        for sign, members in sign_groups_s.items():
            if len(members) >= 3:
                el = ELEMENT_MAPPING.get(sign, '')
                mod = MODALITY_MAPPING.get(sign, '')
                total_score = sum(self.sidereal_dominance['strength'].get(planet_name, 0) for planet_name in members)
                self.sidereal_aspect_patterns.append({
                    "description": f"{len(members)} bodies in {sign} ({el}, {mod} Sign Stellium)",
                    "score": f"{total_score:.2f}"
                })

        house_groups_s = {}
        for body in self.all_sidereal_points:
            if body.is_main_planet and body.house_num > 0:
                house_groups_s.setdefault(body.house_num, []).append(body.name)
        for house, members in house_groups_s.items():
            if len(members) >= 3:
                total_score = sum(self.sidereal_dominance['strength'].get(planet_name, 0) for planet_name in members)
                self.sidereal_aspect_patterns.append({
                    "description": f"{len(members)} bodies in House {house} (House Stellium)",
                    "score": f"{total_score:.2f}"
                })

        # --- Tropical Patterns ---
        planets_t = {b.name: b for b in self.tropical_bodies if b.is_main_planet and b.degree is not None}
        names_t = list(planets_t.keys())
        if len(names_t) >= 3:
            for p1, p2, p3 in combinations(names_t, 3):
                opp = get_aspect(p1, p2, 'Opposition', self.tropical_aspects)
                sq1 = get_aspect(p1, p3, 'Square', self.tropical_aspects)
                sq2 = get_aspect(p2, p3, 'Square', self.tropical_aspects)
                if opp and sq1 and sq2:
                    modalities = {MODALITY_MAPPING.get(planets_t[p].sign) for p in [p1, p2, p3]}
                    modality = modalities.pop() if len(modalities) == 1 else "Mixed"
                    avg_orb = (abs(opp.orb) + abs(sq1.orb) + abs(sq2.orb)) / 3
                    total_score = opp.strength + sq1.strength + sq2.strength
                    self.tropical_aspect_patterns.append({
                        "description": f"{p1} opp {p2}, focal {p3} ({modality} T-Square)",
                        "orb": f"{avg_orb:.2f}°",
                        "score": f"{total_score:.2f}"
                    })

        sign_groups_t = {}
        for name, p in planets_t.items():
            sign_groups_t.setdefault(p.sign, []).append(name)
        for sign, members in sign_groups_t.items():
            if len(members) >= 3:
                el = ELEMENT_MAPPING.get(sign, '')
                mod = MODALITY_MAPPING.get(sign, '')
                total_score = sum(self.tropical_dominance['strength'].get(planet_name, 0) for planet_name in members)
                self.tropical_aspect_patterns.append({
                    "description": f"{len(members)} bodies in {sign} ({el}, {mod} Sign Stellium)",
                    "score": f"{total_score:.2f}"
                })

        house_groups_t = {}
        for body in self.all_tropical_points:
            if body.is_main_planet and body.house_num > 0:
                house_groups_t.setdefault(body.house_num, []).append(body.name)
        for house, members in house_groups_t.items():
            if len(members) >= 3:
                total_score = sum(self.tropical_dominance['strength'].get(planet_name, 0) for planet_name in members)
                self.tropical_aspect_patterns.append({
                    "description": f"{len(members)} bodies in House {house} (House Stellium)",
                    "score": f"{total_score:.2f}"
                })
                
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
    def _analyze_dominance(self) -> None:
        counts_s = {'sign': {}, 'element': {}, 'modality': {}}; strength_s = {}
        main_s = [b for b in self.sidereal_bodies if b.is_main_planet and b.degree is not None and b.name != "True Node"]
        for b in main_s:
            if b.sign != "Unknown":
                counts_s['sign'][b.sign] = counts_s['sign'].get(b.sign, 0) + 1
                el = ELEMENT_MAPPING.get(b.sign); counts_s['element'][el] = counts_s['element'].get(el, 0) + 1
                mod = MODALITY_MAPPING.get(b.sign); counts_s['modality'][mod] = counts_s['modality'].get(mod, 0) + 1
        for a in self.sidereal_aspects: strength_s[a.p1.name] = strength_s.get(a.p1.name, 0) + a.strength; strength_s[a.p2.name] = strength_s.get(a.p2.name, 0) + a.strength
        self.sidereal_dominance = {f"dominant_{k}": max(v, key=v.get) if v else "N/A" for k, v in counts_s.items()}
        self.sidereal_dominance['dominant_planet'] = max(strength_s, key=strength_s.get) if strength_s else "N/A"
        self.sidereal_dominance['counts'] = counts_s; self.sidereal_dominance['strength'] = {k: round(v, 2) for k, v in strength_s.items()}
        counts_t = {'sign': {}, 'element': {}, 'modality': {}}; strength_t = {}
        main_t = [b for b in self.tropical_bodies if b.is_main_planet and b.degree is not None and b.name != "True Node"]
        for b in main_t:
            if b.sign != "Unknown":
                counts_t['sign'][b.sign] = counts_t['sign'].get(b.sign, 0) + 1
                el = ELEMENT_MAPPING.get(b.sign); counts_t['element'][el] = counts_t['element'].get(el, 0) + 1
                mod = MODALITY_MAPPING.get(b.sign); counts_t['modality'][mod] = counts_t['modality'].get(mod, 0) + 1
        for a in self.tropical_aspects: strength_t[a.p1.name] = strength_t.get(a.p1.name, 0) + a.strength; strength_t[a.p2.name] = strength_t.get(a.p2.name, 0) + a.strength
        self.tropical_dominance = {f"dominant_{k}": max(v, key=v.get) if v else "N/A" for k, v in counts_t.items()}
        self.tropical_dominance['dominant_planet'] = max(strength_t, key=strength_t.get) if strength_t else "N/A"
        self.tropical_dominance['counts'] = counts_t; self.tropical_dominance['strength'] = {k: round(v, 2) for k, v in strength_t.items()}

    def get_full_chart_data(self, numerology: dict, name_numerology: dict, chinese_zodiac: dict, unknown_time: bool) -> dict:
        house_rulers_formatted = {}
        if self.ascendant_data.get("sidereal_asc") is not None:
            for i in range(12):
                cusp_deg = (self.ascendant_data['sidereal_asc'] + i * 30) % 360
                sign, ruler_name = get_sign_and_ruler(cusp_deg)
                ruler_body = next((p for p in self.sidereal_bodies if p.name == ruler_name), None)
                ruler_pos = f"– {ruler_body.formatted_position} – House {ruler_body.house_num}, {ruler_body.house_degrees}" if ruler_body and ruler_body.degree is not None else ""
                house_rulers_formatted[f"House {i+1}"] = f"{sign} (Ruler: {ruler_name} {ruler_pos})"
        
        house_cusps = []
        if self.ascendant_data.get("sidereal_asc") is not None:
            asc = self.ascendant_data['sidereal_asc']
            house_cusps = [(asc + i * 30) % 360 for i in range(12)]
            
        sidereal_retrogrades = [{"name": p.name} for p in self.all_sidereal_points if p.retrograde]
        tropical_retrogrades = [{"name": p.name} for p in self.all_tropical_points if p.retrograde]

        sidereal_chart_analysis = {
            "chart_ruler": get_sign_and_ruler(self.ascendant_data['sidereal_asc'])[1] if self.ascendant_data.get('sidereal_asc') is not None else "N/A",
            "dominant_sign": f"{self.sidereal_dominance.get('dominant_sign', 'N/A')} ({self.sidereal_dominance.get('counts', {}).get('sign', {}).get(self.sidereal_dominance.get('dominant_sign'), 0)} placements)",
            "dominant_element": f"{self.sidereal_dominance.get('dominant_element', 'N/A')} ({self.sidereal_dominance.get('counts', {}).get('element', {}).get(self.sidereal_dominance.get('dominant_element'), 0)})",
            "dominant_modality": f"{self.sidereal_dominance.get('dominant_modality', 'N/A')} ({self.sidereal_dominance.get('counts', {}).get('modality', {}).get(self.sidereal_dominance.get('dominant_modality'), 0)})",
            "dominant_planet": f"{self.sidereal_dominance.get('dominant_planet', 'N/A')} (score {self.sidereal_dominance.get('strength', {}).get(self.sidereal_dominance.get('dominant_planet'), 0.0):.2f})",
        }
        sidereal_major_positions = [
            {"name": p.name, "position": p.formatted_position, "degrees": p.degree, "percentage": p.sign_percentage, "retrograde": p.retrograde, "house_info": f"– House {p.house_num}, {p.house_degrees}" if p.house_num > 0 else ""}
            for p in sorted(self.all_sidereal_points, key=lambda x: self.MAJOR_POSITIONS_ORDER.index(x.name) if x.name in self.MAJOR_POSITIONS_ORDER else 99) if p.name in self.MAJOR_POSITIONS_ORDER
        ]
        sidereal_aspects = [
            {"p1_name": f"{a.p1.name} in {a.p1.sign}{' (Rx)' if a.p1.retrograde else ''}", "p2_name": f"{a.p2.name} in {a.p2.sign}{' (Rx)' if a.p2.retrograde else ''}", "type": a.type, "orb": f"{abs(a.orb):.2f}°", "score": f"{a.strength:.2f}", "p1_degrees": a.p1.degree, "p2_degrees": a.p2.degree} for a in self.sidereal_aspects
        ]
        sidereal_additional_points = [
            {"name": p.name, "info": f"{p.formatted_position} – House {p.house_num}, {p.house_degrees}", "retrograde": p.retrograde}
            for p in sorted(self.all_sidereal_points, key=lambda x: x.name) if p.name not in self.MAJOR_POSITIONS_ORDER
        ]

        tropical_chart_analysis = {
            "dominant_sign": f"{self.tropical_dominance.get('dominant_sign', 'N/A')} ({self.tropical_dominance.get('counts', {}).get('sign', {}).get(self.tropical_dominance.get('dominant_sign'), 0)} placements)",
            "dominant_element": f"{self.tropical_dominance.get('dominant_element', 'N/A')} ({self.tropical_dominance.get('counts', {}).get('element', {}).get(self.tropical_dominance.get('dominant_element'), 0)})",
            "dominant_modality": f"{self.tropical_dominance.get('dominant_modality', 'N/A')} ({self.tropical_dominance.get('counts', {}).get('modality', {}).get(self.tropical_dominance.get('dominant_modality'), 0)})",
            "dominant_planet": f"{self.tropical_dominance.get('dominant_planet', 'N/A')} (score {self.tropical_dominance.get('strength', {}).get(self.tropical_dominance.get('dominant_planet'), 0.0):.2f})",
        }
        tropical_major_positions = [
            {"name": p.name, "position": p.formatted_position, "percentage": p.sign_percentage, "retrograde": p.retrograde, "house_info": f"– House {p.house_num}, {p.house_degrees}" if p.house_num > 0 else ""}
            for p in sorted(self.all_tropical_points, key=lambda x: self.MAJOR_POSITIONS_ORDER.index(x.name) if x.name in self.MAJOR_POSITIONS_ORDER else 99) if p.name in self.MAJOR_POSITIONS_ORDER
        ]
        tropical_aspects = [
            {"p1_name": f"{a.p1.name} in {a.p1.sign}{' (Rx)' if a.p1.retrograde else ''}", "p2_name": f"{a.p2.name} in {a.p2.sign}{' (Rx)' if a.p2.retrograde else ''}", "type": a.type, "orb": f"{abs(a.orb):.2f}°", "score": f"{a.strength:.2f}"} for a in self.tropical_aspects
        ]
        tropical_additional_points = [
            {"name": p.name, "info": f"{p.formatted_position} – House {p.house_num}, {p.house_degrees}", "retrograde": p.retrograde}
            for p in sorted(self.all_tropical_points, key=lambda x: x.name) if p.name not in self.MAJOR_POSITIONS_ORDER
        ]

        return {
            "name": self.name, "utc_datetime": self.utc_datetime_str, "location": self.location_str,
            "day_night_status": self.day_night_info.get("status", "N/A"),
            "chinese_zodiac": f"{chinese_zodiac['element']} {chinese_zodiac['animal']}",
            "numerology_analysis": {
                "life_path_number": numerology["life_path"],
                "day_number": numerology["day_number"],
                "name_numerology": name_numerology
            },
            "unknown_time": unknown_time,
            "true_sidereal_signs": TRUE_SIDEREAL_SIGNS,
            "house_cusps": house_cusps,
            "house_rulers": house_rulers_formatted,
            "house_sign_distributions": self.house_sign_distributions,
            "sidereal_chart_analysis": sidereal_chart_analysis,
            "sidereal_major_positions": sidereal_major_positions,
            "sidereal_retrogrades": sidereal_retrogrades,
            "sidereal_aspects": sidereal_aspects,
            "sidereal_aspect_patterns": self.sidereal_aspect_patterns,
            "sidereal_additional_points": sidereal_additional_points,
            "tropical_chart_analysis": tropical_chart_analysis,
            "tropical_major_positions": tropical_major_positions,
            "tropical_retrogrades": tropical_retrogrades,
            "tropical_aspects": tropical_aspects,
            "tropical_aspect_patterns": self.tropical_aspect_patterns,
            "tropical_additional_points": tropical_additional_points
        }
