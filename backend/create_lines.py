import requests
from openrouteservice import convert
from typing import List, Tuple, Dict
import hashlib
import json
import os

api_key = "..."  # from ORS dashboard
#noted, thanks

# Cache globalny dla tras (w pamięci)
_route_cache: Dict[str, List[Tuple[float, float]]] = {}

# Plik dla cache'u perzystentnego
CACHE_FILE = "route_cache.json"


def _load_cache_from_file():
    """Ładuje cache z pliku przy starcie aplikacji."""
    global _route_cache
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                file_cache = json.load(f)
                # Konwertuj z powrotem na tuple (JSON nie obsługuje tuple)
                _route_cache = {
                    key: [tuple(coord) for coord in coords]
                    for key, coords in file_cache.items()
                }
                # print(f"Załadowano {len(_route_cache)} tras z cache'u")
        except Exception as e:
            # print(f"Błąd podczas ładowania cache'u: {e}")
            _route_cache = {}


def _save_cache_to_file():
    """Zapisuje cache do pliku."""
    try:
        # Konwertuj tuple na listy dla JSON
        file_cache = {
            key: [list(coord) for coord in coords]
            for key, coords in _route_cache.items()
        }
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(file_cache, f, indent=2)
        # print(f"Zapisano {len(_route_cache)} tras do cache'u")
    except Exception as e:
        print(f"Błąd podczas zapisywania cache'u: {e}")


def _create_cache_key(start_coords: Tuple[float, float], end_coords: Tuple[float, float], mode: str) -> str:
    """
    Tworzy unikalny klucz dla cache'u na podstawie współrzędnych i trybu.
    Używa zaokrąglenia do 6 miejsc po przecinku (~1m dokładność).
    """
    start_rounded = (round(start_coords[0], 6), round(start_coords[1], 6))
    end_rounded = (round(end_coords[0], 6), round(end_coords[1], 6))

    # Tworzymy hash z parametrów
    cache_data = f"{start_rounded[0]},{start_rounded[1]}|{end_rounded[0]},{end_rounded[1]}|{mode}"
    return hashlib.md5(cache_data.encode()).hexdigest()


def _is_route_cached(cache_key: str) -> bool:
    """Sprawdza czy trasa jest w cache'u."""
    return cache_key in _route_cache


def _get_cached_route(cache_key: str) -> List[Tuple[float, float]]:
    """Pobiera trasę z cache'u."""
    return _route_cache.get(cache_key, [])


def _cache_route(cache_key: str, route: List[Tuple[float, float]]):
    """Zapisuje trasę do cache'u."""
    _route_cache[cache_key] = route

    # Zapisz do pliku co 10 nowych tras (żeby nie zapisywać za często)
    if len(_route_cache) % 10 == 0:
        _save_cache_to_file()


def get_cache_stats() -> Dict[str, int]:
    """Zwraca statystyki cache'u."""
    return {
        "cached_routes": len(_route_cache),
        "cache_size_kb": len(json.dumps({k: [list(coord) for coord in v] for k, v in _route_cache.items()})) // 1024
    }


def clear_cache():
    """Czyści cache (przydatne do testów)."""
    global _route_cache
    _route_cache = {}
    if os.path.exists(CACHE_FILE):
        os.remove(CACHE_FILE)
    # print("Cache został wyczyszczony")


import requests
from openrouteservice import convert
from typing import List, Tuple, Dict
import hashlib
import json

api_key = "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6Ijc4NTRiZDc0MWUwNzQyNGI4NDJkYmYzMTRmYWFkMjc4IiwiaCI6Im11cm11cjY0In0="  # from ORS dashboard

# Global cache dictionary to store routes between points
# Format: {route_key: [(lat, lon), ...]}
_route_cache: Dict[str, List[Tuple[float, float]]] = {}


def _create_route_key(start_coords: Tuple[float, float], end_coords: Tuple[float, float], mode: str) -> str:
    """
    Tworzy unikalny klucz dla trasy na podstawie punktów startowych, końcowych i trybu transportu.

    Args:
        start_coords: (lon, lat) punkt startowy
        end_coords: (lon, lat) punkt końcowy
        mode: tryb transportu

    Returns:
        Unikalny string reprezentujący trasę
    """
    # Zaokrąglij współrzędne do 6 miejsc po przecinku (dokładność ~0.1m)
    start_rounded = (round(start_coords[0], 6), round(start_coords[1], 6))
    end_rounded = (round(end_coords[0], 6), round(end_coords[1], 6))

    # Utwórz klucz z danych trasy
    route_data = {
        'start': start_rounded,
        'end': end_rounded,
        'mode': mode
    }

    # Stwórz hash z danych
    route_string = json.dumps(route_data, sort_keys=True)
    route_hash = hashlib.md5(route_string.encode()).hexdigest()

    return route_hash


def clear_route_cache():
    """Czyści cache tras."""
    global _route_cache
    _route_cache.clear()
    # print("Cache tras został wyczyszczony")


def get_cache_stats():
    """Zwraca statystyki cache'a."""
    return {
        'cached_routes': len(_route_cache),
        'total_points': sum(len(route) for route in _route_cache.values())
    }


def save_cache_to_file(filename: str = "route_cache.json"):
    """Zapisuje cache do pliku JSON."""
    try:
        # Konwertuj cache do formatu JSON (tuple -> list)
        cache_for_json = {}
        for key, coords in _route_cache.items():
            cache_for_json[key] = [[lat, lon] for lat, lon in coords]

        with open(filename, 'w') as f:
            json.dump(cache_for_json, f, indent=2)
        # print(f"Cache zapisany do {filename}")
    except Exception as e:
        print(f"Błąd podczas zapisywania cache: {e}")


def load_cache_from_file(filename: str = "route_cache.json"):
    """Ładuje cache z pliku JSON."""
    global _route_cache
    try:
        with open(filename, 'r') as f:
            cache_from_json = json.load(f)

        # Konwertuj z formatu JSON (list -> tuple)
        _route_cache = {}
        for key, coords in cache_from_json.items():
            _route_cache[key] = [(lat, lon) for lat, lon in coords]

        # print(f"Cache załadowany z {filename}: {len(_route_cache)} tras")
    except FileNotFoundError:
        print(f"Plik {filename} nie istnieje - rozpoczynam z pustym cache")
    except Exception as e:
        print(f"Błąd podczas ładowania cache: {e}")


def get_route_between_points(start_coords: Tuple[float, float], end_coords: Tuple[float, float],
                             mode: str = "foot-walking") -> List[Tuple[float, float]]:
    """
    Pobiera szczegółową trasę między dwoma punktami używając OpenRouteService.
    Automatycznie cache'uje wyniki dla ponownego użycia.

    Args:
        start_coords: (lon, lat) punkt startowy
        end_coords: (lon, lat) punkt końcowy
        mode: rodzaj transportu ("foot-walking", "driving-car", etc.)

    Returns:
        Lista współrzędnych [(lat, lon), ...] trasy
    """
    # Sprawdź cache
    cache_key = _create_cache_key(start_coords, end_coords, mode)

    if _is_route_cached(cache_key):
        # print(f"  🎯 Użyto cache'u dla {mode}")
        return _get_cached_route(cache_key)

    # print(f"  🌐 Pobieranie z API dla {mode}")

    try:
        url = f"https://api.openrouteservice.org/v2/directions/{mode}"
        headers = {"Authorization": api_key, "Content-Type": "application/json"}
        body = {"coordinates": [list(start_coords), list(end_coords)]}

        response = requests.post(url, json=body, headers=headers)
        data = response.json()

        if response.status_code != 200:
            # print(f"Błąd ORS API: {data}")
            # Fallback - zwróć prostą linię między punktami
            fallback_route = [(start_coords[1], start_coords[0]), (end_coords[1], end_coords[0])]
            _cache_route(cache_key, fallback_route)  # Cache'uj też fallback
            return fallback_route

        # ORS returns an encoded polyline
        encoded_polyline = data['routes'][0]['geometry']

        # Decode into [(lat, lon), ...]
        coords = convert.decode_polyline(encoded_polyline)['coordinates']
        route_latlon = [(lat, lon) for lon, lat in coords]  # ORS gives [lon, lat], we want [lat, lon]

        # Cache'uj wynik
        _cache_route(cache_key, route_latlon)
        return route_latlon

    except Exception as e:
        # print(f"Błąd podczas pobierania trasy: {e}")
        # Fallback - zwróć prostą linię między punktami
        fallback_route = [(start_coords[1], start_coords[0]), (end_coords[1], end_coords[0])]
        _cache_route(cache_key, fallback_route)  # Cache'uj też fallback
        return fallback_route


def create_detailed_route_geometry(route_segments) -> List[Tuple[float, float]]:
    """
    Tworzy szczegółową geometrię trasy na podstawie segmentów.
    Używa cache'u dla optymalizacji.

    Args:
        route_segments: Lista segmentów trasy z plan_route.py

    Returns:
        Lista wszystkich współrzędnych [(lat, lon), ...] całej trasy
    """
    # Załaduj cache z pliku (jeśli jeszcze nie załadowany)
    if not _route_cache:
        _load_cache_from_file()

    all_coordinates = []
    cache_hits = 0
    api_calls = 0

    # print(f"Przetwarzanie {len(route_segments)} segmentów...")

    for i, segment in enumerate(route_segments):
        start_lat = segment.from_stop.coordinates.latitude
        start_lon = segment.from_stop.coordinates.longitude
        end_lat = segment.to_stop.coordinates.latitude
        end_lon = segment.to_stop.coordinates.longitude

        # print(f"Segment {i+1}: {segment.from_stop.name} → {segment.to_stop.name}")

        # Określ tryb transportu dla ORS
        if segment.type == "walking":
            mode = "foot-walking"
        else:
            # Dla komunikacji publicznej używamy driving-car jako aproksymacji
            # (ORS nie ma dedykowanego trybu dla tramwajów/autobusów)
            mode = "driving-car"

        # Sprawdź czy to będzie hit czy miss cache'u
        cache_key = _create_cache_key((start_lon, start_lat), (end_lon, end_lat), mode)
        if _is_route_cached(cache_key):
            cache_hits += 1
        else:
            api_calls += 1

        # Pobierz szczegółową trasę między przystankami
        segment_coords = get_route_between_points(
            start_coords=(start_lon, start_lat),
            end_coords=(end_lon, end_lat),
            mode=mode
        )

        # Dodaj współrzędne do ogólnej listy
        # Jeśli to nie pierwszy segment, pomiń pierwszy punkt (żeby uniknąć duplikatów)
        if i > 0 and segment_coords:
            segment_coords = segment_coords[1:]

        all_coordinates.extend(segment_coords)

        # print(f"  Dodano {len(segment_coords)} punktów")

    # Zapisz cache do pliku po zakończeniu
    _save_cache_to_file()

    # Statystyki
    total_requests = cache_hits + api_calls
    cache_ratio = (cache_hits / total_requests * 100) if total_requests > 0 else 0

    return all_coordinates


# Testowa funkcja (stary kod)
def test_single_route():
    start = [19.9372, 50.0614]  # lon, lat
    end = [19.9368, 50.0544]  # lon, lat

    url = "https://api.openrouteservice.org/v2/directions/foot-walking"
    headers = {"Authorization": api_key, "Content-Type": "application/json"}
    body = {"coordinates": [[19.9372, 50.0614], [19.9368, 50.0544]]}

    response = requests.post(url, json=body, headers=headers)
    data = response.json()

    # ORS returns an encoded polyline
    encoded_polyline = data['routes'][0]['geometry']

    # Decode into [(lat, lon), ...]
    coords = convert.decode_polyline(encoded_polyline)['coordinates']
    route_latlon = [(lat, lon) for lon, lat in coords]  # ORS gives [lon, lat]

    # print(route_latlon)
