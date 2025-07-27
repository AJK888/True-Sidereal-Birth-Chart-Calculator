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
def get_chinese_zodiac(year: int, month: int, day: int) -> str:
    zodiac_animals = ["Rat","Ox","Tiger","Rabbit","Dragon","Snake","Horse","Goat","Monkey","Rooster","Dog","Pig"]
    return zodiac_animals[(year - 1924) % 12]
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
    def __init__(self, name: str, year: int, month: int, day: int, hour: int, minute: int, latitude: float, longitude: float):
        self.name = name; self.latitude, self.longitude = latitude, longitude
        self.birth_year, self.birth_hour, self.birth_minute = year, hour, minute
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
        self._calculate_ascendant_mc_data();
        if self.ascendant_data.get("sidereal_asc") is None: return
        self._determine_day_night(); self._calculate_all_points()
        self._calculate_aspects(); self._detect_aspect_patterns()
        self._calculate_house_sign_distributions(); self._analyze_dominance()
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
        if sun_s and moon_s and self.day_night_info.get('status') != 'Undetermined':
            is_day = self.day_night_info.get('status') == 'Day Birth'
            s_pof_deg = (s_asc.degree + moon_s.degree - sun_s.degree + 360) % 360 if is_day else (s_asc.degree + sun_s.degree - moon_s.degree + 360) % 360
            t_pof_deg = (t_asc.degree + moon_t.degree - sun_t.degree + 360) % 360 if is_day else (t_asc.degree + sun_t.degree - moon_t.degree + 360) % 360
            points_to_add.append((SiderealBody("Part of Fortune", s_pof_deg, False, sidereal_asc, False), TropicalBody("Part of Fortune", t_pof_deg, False, tropical_asc, False)))
        nn_s = next((p for p in self.sidereal_bodies if p.name == 'True Node'), None); nn_t = next((p for p in self.tropical_bodies if p.name == 'True Node'), None)
        if nn_s and nn_t:
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
        # Sidereal Patterns
        planets_s = {b.name: b for b in self.sidereal_bodies if b.is_main_planet and b.degree is not None}; names_s = list(planets_s.keys())
        def find_aspect_s(p1, p2, type): return any(a.type == type and ((a.p1.name == p1 and a.p2.name == p2) or (a.p1.name == p2 and a.p2.name == p1)) for a in self.sidereal_aspects)
        if len(names_s) >= 3:
            for p1, p2, p3 in combinations(names_s, 3):
                if find_aspect_s(p1, p2, 'Opposition') and find_aspect_s(p1, p3, 'Square') and find_aspect_s(p2, p3, 'Square'):
                    modalities = {MODALITY_MAPPING.get(planets_s[p].sign) for p in [p1, p2, p3]}; modality = modalities.pop() if len(modalities) == 1 else "Mixed"
                    self.sidereal_aspect_patterns.append({"description": f"{p1} opp {p2}, focal {p3} ({modality} T-Square)"})
        sign_groups_s = {};
        for name, p in planets_s.items(): sign_groups_s.setdefault(p.sign, []).append(name)
        for sign, members in sign_groups_s.items():
            if len(members) >= 3:
                el = ELEMENT_MAPPING.get(sign, ''); mod = MODALITY_MAPPING.get(sign, '')
                self.sidereal_aspect_patterns.append({"description": f"{len(members)} bodies in {sign} ({el}, {mod} Sign Stellium)"})
        # --- NEW: Sidereal House Stelliums ---
        house_groups_s = {}
        for body in self.all_sidereal_points:
            if body.is_main_planet and body.house_num > 0:
                house_groups_s.setdefault(body.house_num, []).append(body.name)
        for house, members in house_groups_s.items():
            if len(members) >= 3:
                self.sidereal_aspect_patterns.append({"description": f"{len(members)} bodies in House {house} (House Stellium)"})

        # Tropical Patterns
        planets_t = {b.name: b for b in self.tropical_bodies if b.is_main_planet and b.degree is not None}; names_t = list(planets_t.keys())
        def find_aspect_t(p1, p2, type): return any(a.type == type and ((a.p1.name == p1 and a.p2.name == p2) or (a.p1.name == p2 and a.p2.name == p1)) for a in self.tropical_aspects)
        if len(names_t) >= 3:
            for p1, p2, p3 in combinations(names_t, 3):
                if find_aspect_t(p1, p2, 'Opposition') and find_aspect_t(p1, p3, 'Square') and find_aspect_t(p2, p3, 'Square'):
                    modalities = {MODALITY_MAPPING.get(planets_t[p].sign) for p in [p1, p2, p3]}; modality = modalities.pop() if len(modalities) == 1 else "Mixed"
                    self.tropical_aspect_patterns.append({"description": f"{p1} opp {p2}, focal {p3} ({modality} T-Square)"})
        sign_groups_t = {};
        for name, p in planets_t.items(): sign_groups_t.setdefault(p.sign, []).append(name)
        for sign, members in sign_groups_t.items():
            if len(members) >= 3:
                el = ELEMENT_MAPPING.get(sign, ''); mod = MODALITY_MAPPING.get(sign, '')
                self.tropical_aspect_patterns.append({"description": f"{len(members)} bodies in {sign} ({el}, {mod} Sign Stellium)"})
        # --- NEW: Tropical House Stelliums ---
        house_groups_t = {}
        for body in self.all_tropical_points:
            if body.is_main_planet and body.house_num > 0:
                house_groups_t.setdefault(body.house_num, []).append(body.name)
        for house, members in house_groups_t.items():
            if len(members) >= 3:
                self.tropical_aspect_patterns.append({"description": f"{len(members)} bodies in House {house} (House Stellium)"})

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
        # Sidereal
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
        # Tropical
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
