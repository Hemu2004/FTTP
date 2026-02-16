from __future__ import annotations

from dataclasses import dataclass
from math import radians, cos, sin, asin, sqrt
from typing import List


@dataclass
class Provider:
    name: str
    lat: float
    lon: float
    note: str
    marker_color: str
    distance_km: float = 0.0

    def model_dump(self) -> dict:
        return {
            "name": self.name,
            "lat": self.lat,
            "lon": self.lon,
            "note": self.note,
            "marker_color": self.marker_color,
            "distance_km": self.distance_km,
        }


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points."""
    r = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return r * c


# Reference dataset (demo) of enterprise points.
# In a production deployment, this would be replaced by a coverage/asset dataset.
_PROVIDERS: List[Provider] = [
    # Mumbai
    Provider("Jio", 19.0760, 72.8777, "High density zone", "blue"),
    Provider("Airtel", 19.0896, 72.8656, "Fiber core nearby", "red"),
    Provider("BSNL", 19.0176, 72.8562, "Legacy infrastructure area", "orange"),
    # Delhi NCR
    Provider("Jio", 28.6139, 77.2090, "Metro cluster", "blue"),
    Provider("Airtel", 28.4595, 77.0266, "Backbone ring nearby", "red"),
    Provider("BSNL", 28.5355, 77.3910, "Legacy exchange region", "orange"),
    # Bengaluru
    Provider("Jio", 12.9716, 77.5946, "", "blue"),
    Provider("Airtel", 12.9352, 77.6245, "", "red"),
    Provider("BSNL", 12.9141, 77.6320, "", "orange"),
]


def find_nearby_providers(lat: float, lon: float, k: int = 3) -> List[Provider]:
    items: List[Provider] = []
    for p in _PROVIDERS:
        d = _haversine_km(lat, lon, p.lat, p.lon)
        items.append(Provider(p.name, p.lat, p.lon, p.note, p.marker_color, d))
    items.sort(key=lambda x: x.distance_km)
    return items[: max(1, k)]
