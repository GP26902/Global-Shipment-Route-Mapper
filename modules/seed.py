"""Illustrative seed routes (hardcoded coordinates, city level only).

These are made-up examples, not real shipments. They are never part of KPIs.
"""
import pandas as pd

from modules.data_model import COLUMNS, SOURCE_SEED, STAGE_TYPES

# key: (city, state/region, country, lat, lon)
CITIES = {
    "shenzhen": ("Shenzhen", "Guangdong", "China", 22.5431, 114.0579),
    "anchorage": ("Anchorage", "AK", "United States", 61.2181, -149.9003),
    "memphis": ("Memphis", "TN", "United States", 35.1495, -90.0490),
    "denver": ("Denver", "CO", "United States", 39.7392, -104.9903),
    "boulder": ("Boulder", "CO", "United States", 40.0150, -105.2705),
    "stuttgart": ("Stuttgart", "Baden-Württemberg", "Germany", 48.7758, 9.1829),
    "cologne": ("Cologne", "North Rhine-Westphalia", "Germany", 50.9375, 6.9603),
    "louisville": ("Louisville", "KY", "United States", 38.2527, -85.7585),
    "houston": ("Houston", "TX", "United States", 29.7604, -95.3698),
    "beaumont": ("Beaumont", "TX", "United States", 30.0802, -94.1266),
    "portarthur": ("Port Arthur", "TX", "United States", 29.8850, -93.9399),
    "dhaka": ("Dhaka", "Dhaka Division", "Bangladesh", 23.8103, 90.4125),
    "leipzig": ("Leipzig", "Saxony", "Germany", 51.3397, 12.3731),
    "cincinnati": ("Cincinnati", "OH", "United States", 39.1031, -84.5120),
    "columbus": ("Columbus", "OH", "United States", 39.9612, -82.9988),
    "dayton": ("Dayton", "OH", "United States", 39.7589, -84.1916),
    "fortworth": ("Fort Worth", "TX", "United States", 32.7555, -97.3308),
    "dallas": ("Dallas", "TX", "United States", 32.7767, -96.7970),
    "plano": ("Plano", "TX", "United States", 33.0198, -96.6989),
    "frisco": ("Frisco", "TX", "United States", 33.1507, -96.8236),
    "losangeles": ("Los Angeles", "CA", "United States", 34.0522, -118.2437),
    "phoenix": ("Phoenix", "AZ", "United States", 33.4484, -112.0740),
    "albuquerque": ("Albuquerque", "NM", "United States", 35.0844, -106.6504),
    "santafe": ("Santa Fe", "NM", "United States", 35.6870, -105.9378),
    "santiago": ("Santiago", "Santiago Metropolitan", "Chile", -33.4489, -70.6693),
    "miami": ("Miami", "FL", "United States", 25.7617, -80.1918),
    "atlanta": ("Atlanta", "GA", "United States", 33.7490, -84.3880),
    "charlotte": ("Charlotte", "NC", "United States", 35.2271, -80.8431),
    "raleigh": ("Raleigh", "NC", "United States", 35.7796, -78.6382),
    "nairobi": ("Nairobi", "Nairobi County", "Kenya", -1.2921, 36.8219),
    "dubai": ("Dubai", "Dubai", "United Arab Emirates", 25.2048, 55.2708),
    "london": ("London", "England", "United Kingdom", 51.5074, -0.1278),
    "manchester": ("Manchester", "England", "United Kingdom", 53.4808, -2.2426),
    "leeds": ("Leeds", "England", "United Kingdom", 53.8008, -1.5491),
    "sydney": ("Sydney", "New South Wales", "Australia", -33.8688, 151.2093),
    "singapore": ("Singapore", "Singapore", "Singapore", 1.3521, 103.8198),
    "paris": ("Paris", "Île-de-France", "France", 48.8566, 2.3522),
    "lyon": ("Lyon", "Auvergne-Rhône-Alpes", "France", 45.7640, 4.8357),
    "grenoble": ("Grenoble", "Auvergne-Rhône-Alpes", "France", 45.1885, 5.7245),
    "osaka": ("Osaka", "Osaka Prefecture", "Japan", 34.6937, 135.5023),
    "seattle": ("Seattle", "WA", "United States", 47.6062, -122.3321),
    "slc": ("Salt Lake City", "UT", "United States", 40.7608, -111.8910),
    "boise": ("Boise", "ID", "United States", 43.6150, -116.2023),
    "nampa": ("Nampa", "ID", "United States", 43.5407, -116.5635),
    "mumbai": ("Mumbai", "Maharashtra", "India", 19.0760, 72.8777),
    "istanbul": ("Istanbul", "Istanbul Province", "Turkey", 41.0082, 28.9784),
    "brussels": ("Brussels", "Brussels-Capital Region", "Belgium", 50.8503, 4.3517),
    "ghent": ("Ghent", "Flanders", "Belgium", 51.0543, 3.7174),
    "kl": ("Kuala Lumpur", "Kuala Lumpur", "Malaysia", 3.1390, 101.6869),
    "bangkok": ("Bangkok", "Bangkok", "Thailand", 13.7563, 100.5018),
    "chiangmai": ("Chiang Mai", "Chiang Mai Province", "Thailand", 18.7883, 98.9853),
    "minneapolis": ("Minneapolis", "MN", "United States", 44.9778, -93.2650),
    "chicago": ("Chicago", "IL", "United States", 41.8781, -87.6298),
    "cleveland": ("Cleveland", "OH", "United States", 41.4993, -81.6944),
    "pittsburgh": ("Pittsburgh", "PA", "United States", 40.4406, -79.9959),
    "altoona": ("Altoona", "PA", "United States", 40.5187, -78.3947),
    "guangzhou": ("Guangzhou", "Guangdong", "China", 23.1291, 113.2644),
    "riverside": ("Riverside", "CA", "United States", 33.9533, -117.3962),
    "sandiego": ("San Diego", "CA", "United States", 32.7157, -117.1611),
    "chulavista": ("Chula Vista", "CA", "United States", 32.6401, -117.0842),
    "monterrey": ("Monterrey", "Nuevo León", "Mexico", 25.6866, -100.3161),
    "laredo": ("Laredo", "TX", "United States", 27.5306, -99.4803),
    "indianapolis": ("Indianapolis", "IN", "United States", 39.7684, -86.1581),
    "detroit": ("Detroit", "MI", "United States", 42.3314, -83.0458),
    "auckland": ("Auckland", "Auckland Region", "New Zealand", -36.8485, 174.7633),
    "honolulu": ("Honolulu", "HI", "United States", 21.3069, -157.8583),
    "sf": ("San Francisco", "CA", "United States", 37.7749, -122.4194),
    "sacramento": ("Sacramento", "CA", "United States", 38.5816, -121.4944),
    "davis": ("Davis", "CA", "United States", 38.5449, -121.7405),
    "katy": ("Katy", "TX", "United States", 29.7858, -95.8244),
    "sugarland": ("Sugar Land", "TX", "United States", 29.6197, -95.6349),
    "austin": ("Austin", "TX", "United States", 30.2672, -97.7431),
    "sanantonio": ("San Antonio", "TX", "United States", 29.4241, -98.4936),
    "waco": ("Waco", "TX", "United States", 31.5493, -97.1467),
    "woodlands": ("The Woodlands", "TX", "United States", 30.1658, -95.4613),
    "pearland": ("Pearland", "TX", "United States", 29.5636, -95.2861),
    "galveston": ("Galveston", "TX", "United States", 29.3013, -94.7977),
}

# (shipment_id, carrier, product_class, [(stage_type, city_key), ...])
# A mix of long international freight and short local parcels.
ROUTES = [
    ("SEED-001", "FedEx", "Electronics", [
        ("Origin", "shenzhen"), ("Customs Facility", "anchorage"),
        ("Sorting Hub", "memphis"), ("Last-Mile Facility", "denver"),
        ("Final Destination", "boulder")]),
    ("SEED-002", "UPS", "Machinery & Industrial", [
        ("Origin", "stuttgart"), ("Sorting Hub", "cologne"),
        ("Customs Facility", "louisville"), ("Regional Distribution", "houston"),
        ("Last-Mile Facility", "beaumont"), ("Final Destination", "portarthur")]),
    ("SEED-003", "DHL", "Apparel", [
        ("Origin", "dhaka"), ("Sorting Hub", "leipzig"),
        ("Customs Facility", "cincinnati"), ("Last-Mile Facility", "columbus"),
        ("Final Destination", "dayton")]),
    ("SEED-004", "Amazon Logistics", "General Merchandise", [
        ("Origin", "fortworth"), ("Regional Distribution", "dallas"),
        ("Last-Mile Facility", "plano"), ("Final Destination", "frisco")]),
    ("SEED-005", "USPS", "Apparel", [
        ("Origin", "losangeles"), ("Sorting Hub", "phoenix"),
        ("Regional Distribution", "albuquerque"), ("Final Destination", "santafe")]),
    ("SEED-006", "UPS", "Food & Perishables", [
        ("Origin", "santiago"), ("Customs Facility", "miami"),
        ("Sorting Hub", "atlanta"), ("Last-Mile Facility", "charlotte"),
        ("Final Destination", "raleigh")]),
    ("SEED-007", "DHL", "Food & Perishables", [
        ("Origin", "nairobi"), ("Sorting Hub", "dubai"),
        ("Customs Facility", "london"), ("Last-Mile Facility", "manchester"),
        ("Final Destination", "leeds")]),
    ("SEED-008", "FedEx", "General Merchandise", [
        ("Origin", "sydney"), ("Sorting Hub", "singapore"),
        ("Customs Facility", "paris"), ("Last-Mile Facility", "lyon"),
        ("Final Destination", "grenoble")]),
    ("SEED-009", "Amazon Logistics", "Machinery & Industrial", [
        ("Origin", "osaka"), ("Customs Facility", "seattle"),
        ("Regional Distribution", "slc"), ("Last-Mile Facility", "boise"),
        ("Final Destination", "nampa")]),
    ("SEED-010", "UPS", "General Merchandise", [
        ("Origin", "mumbai"), ("Customs Facility", "istanbul"),
        ("Sorting Hub", "cologne"), ("Last-Mile Facility", "brussels"),
        ("Final Destination", "ghent")]),
    ("SEED-011", "DHL", "Electronics", [
        ("Origin", "singapore"), ("Sorting Hub", "kl"),
        ("Regional Distribution", "bangkok"), ("Final Destination", "chiangmai")]),
    ("SEED-012", "USPS", "General Merchandise", [
        ("Origin", "minneapolis"), ("Sorting Hub", "chicago"),
        ("Regional Distribution", "cleveland"), ("Last-Mile Facility", "pittsburgh"),
        ("Final Destination", "altoona")]),
    ("SEED-013", "Amazon Logistics", "Apparel", [
        ("Origin", "guangzhou"), ("Customs Facility", "losangeles"),
        ("Regional Distribution", "riverside"), ("Last-Mile Facility", "sandiego"),
        ("Final Destination", "chulavista")]),
    ("SEED-014", "FedEx", "Machinery & Industrial", [
        ("Origin", "monterrey"), ("Customs Facility", "laredo"),
        ("Sorting Hub", "memphis"), ("Regional Distribution", "indianapolis"),
        ("Final Destination", "detroit")]),
    ("SEED-015", "Other", "Food & Perishables", [
        ("Origin", "auckland"), ("Customs Facility", "honolulu"),
        ("Regional Distribution", "sf"), ("Last-Mile Facility", "sacramento"),
        ("Final Destination", "davis")]),
    # Short local deliveries inside Texas, so State and City views have content.
    ("SEED-016", "Amazon Logistics", "Apparel", [
        ("Origin", "houston"), ("Last-Mile Facility", "katy"),
        ("Final Destination", "sugarland")]),
    ("SEED-017", "UPS", "Machinery & Industrial", [
        ("Origin", "houston"), ("Sorting Hub", "austin"),
        ("Final Destination", "sanantonio")]),
    ("SEED-018", "FedEx", "Electronics", [
        ("Origin", "dallas"), ("Sorting Hub", "waco"),
        ("Regional Distribution", "houston"), ("Final Destination", "woodlands")]),
    ("SEED-019", "USPS", "Food & Perishables", [
        ("Origin", "houston"), ("Sorting Hub", "pearland"),
        ("Final Destination", "galveston")]),
    ("SEED-020", "DHL", "General Merchandise", [
        ("Origin", "austin"), ("Regional Distribution", "houston"),
        ("Last-Mile Facility", "beaumont"), ("Final Destination", "portarthur")]),
]


def _facility_name(stage: str, city: str) -> str:
    if stage == "Origin":
        return f"{city} (origin)"
    if stage == "Final Destination":
        return f"{city} (destination)"
    return f"{city} {stage}"


def get_seed_frame() -> pd.DataFrame:
    """Return all illustrative seed routes as a checkpoint table."""
    rows = []
    for shipment_id, carrier, product_class, stops in ROUTES:
        for order, (stage, key) in enumerate(stops, start=1):
            city, state, country, lat, lon = CITIES[key]
            assert stage in STAGE_TYPES, stage
            rows.append({
                "shipment_id": shipment_id, "stop_order": order,
                "stage_type": stage, "facility": _facility_name(stage, city),
                "city": city, "state": state, "country": country,
                "postal_code": "", "lat": lat, "lon": lon,
                "arrived": pd.NaT, "departed": pd.NaT,
                "carrier": carrier, "product_class": product_class,
                "status": "approved", "source": SOURCE_SEED,
                "created_at": pd.NaT,
            })
    return pd.DataFrame(rows, columns=COLUMNS)
