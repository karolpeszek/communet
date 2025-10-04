# db_setup.py
import csv
import io
import os
import pickle
import ssl
import uuid
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, date, timedelta
from typing import Dict, List, Tuple, Optional
from urllib.request import urlopen

from db import *  # Stop, Vehicle, Trip, Route, Database, VehicleType

# Adresy oficjalnych statycznych plików GTFS (ZTP Kraków)
GTFS_BASE = "https://gtfs.ztp.krakow.pl"
# Zbiór plików – w praktyce wystarczą T (tramwaje) i A/M (autobusy)
GTFS_FILES = ["GTFS_KRK_T.zip", "GTFS_KRK_A.zip", "GTFS_KRK_M.zip"]

# Linie, które chcesz mieć w bazie (rozszerzona lista głównych linii Krakowa)
TARGET_LINES = {
    # Tramwaje
    "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "14", "15", "17", "18", "19", "20", "21", "22",
    "24", "50", "52",
    # Autobusy - główne linie
    "104", "114", "124", "128", "129", "130", "139", "144", "152", "159", "164", "173", "178", "179", "194",
    "208", "209", "210", "258", "304", "424", "502", "503", "578"
}

# Cache configuration
CACHE_DIR = "cache"
DB_CACHE_FILE = os.path.join(CACHE_DIR, "krakow_database.pkl")
CACHE_EXPIRY_HOURS = 24  # Cache expires after 24 hours


def _ensure_cache_dir():
    """Ensures the cache directory exists."""
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)


def _get_cache_age_hours():
    """Returns the age of the cache file in hours, or None if file doesn't exist."""
    if not os.path.exists(DB_CACHE_FILE):
        return None

    cache_time = os.path.getmtime(DB_CACHE_FILE)
    current_time = datetime.now().timestamp()
    age_seconds = current_time - cache_time
    age_hours = age_seconds / 3600
    return age_hours


def _is_cache_valid():
    """Checks if the cache file exists and is not expired."""
    age_hours = _get_cache_age_hours()
    if age_hours is None:
        return False
    return age_hours < CACHE_EXPIRY_HOURS


def _save_database_to_cache(database: Database):
    """Saves the database to cache file."""
    try:
        _ensure_cache_dir()
        with open(DB_CACHE_FILE, 'wb') as f:
            pickle.dump(database, f)
        size_mb = os.path.getsize(DB_CACHE_FILE) / (1024 * 1024)
        print(f"Baza danych zapisana do cache ({size_mb:.1f} MB): {DB_CACHE_FILE}")
        return True
    except Exception as e:
        print(f"Błąd podczas zapisywania cache'u: {e}")
        return False


def _load_database_from_cache() -> Optional[Database]:
    """Loads the database from cache file if valid."""
    if not _is_cache_valid():
        age_hours = _get_cache_age_hours()
        if age_hours is None:
            print("Cache nie istnieje - będzie utworzony nowy")
        else:
            print(f"Cache wygasł ({age_hours:.1f}h > {CACHE_EXPIRY_HOURS}h) - będzie odświeżony")
        return None

    try:
        with open(DB_CACHE_FILE, 'rb') as f:
            database = pickle.load(f)
        age_hours = _get_cache_age_hours()
        size_mb = os.path.getsize(DB_CACHE_FILE) / (1024 * 1024)
        print(f"Załadowano bazę danych z cache ({age_hours:.1f}h, {size_mb:.1f} MB)")
        print(f" Kursy: {len(database.trips)}, Przystanki: {len(database.stops)}, Pojazdy: {len(database.vehicles)}")
        return database
    except Exception as e:
        print(f"Błąd podczas ładowania cache'u: {e}")
        print("Będzie utworzona nowa baza danych")
        return None


def _download(url: str) -> bytes:
    """Pobiera plik z sieci."""
    # print(f"Próba pobrania: {url}")
    try:
        # Tworzymy kontekst SSL, który ignoruje problemy z certyfikatem
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        with urlopen(url, context=ssl_context) as r:
            data = r.read()
            # print(f"Pobrano {len(data)} bajtów z {url}")
            return data
    except Exception as e:
        # print(f"Błąd podczas pobierania {url}: {e}")
        return b""


def _zip_has(zb: bytes, name: str) -> bool:
    with zipfile.ZipFile(io.BytesIO(zb)) as z:
        return any(i.filename.endswith(name) for i in z.infolist())


def _open_from_zip(zb: bytes, name: str):
    z = zipfile.ZipFile(io.BytesIO(zb))
    # znajdź dokładną ścieżkę do pliku (czasem bywa prefiks katalogu)
    for i in z.infolist():
        if i.filename.endswith(name):
            return z, z.open(i.filename)
    return z, None


def _read_csv_from_zip(zdata: bytes, name: str) -> List[Dict[str, str]]:
    """
    Czyta plik CSV z archiwum ZIP, usuwa BOM, normalizuje nagłówki (lower + trim).
    Zwraca listę słowników z kluczami w lower-case.
    """
    z, fh = _open_from_zip(zdata, name)
    if fh is None:
        z.close()
        return []

    try:
        reader = csv.DictReader(io.TextIOWrapper(fh, encoding="utf-8-sig"))
        rows: List[Dict[str, str]] = []
        for row in reader:
            norm = {}
            for k, v in (row or {}).items():
                if k is None:
                    continue
                nk = k.strip().lstrip("\ufeff").lower()
                nv = v.strip() if isinstance(v, str) else v
                norm[nk] = nv
            if any(val not in (None, "", []) for val in norm.values()):
                rows.append(norm)
        return rows
    finally:
        fh.close()
        z.close()


def _parse_gtfs_date(yyyymmdd: str) -> date:
    return date(int(yyyymmdd[0:4]), int(yyyymmdd[4:6]), int(yyyymmdd[6:8]))


def _time_to_datetime(day: date, hhmmss: str) -> datetime:
    """Konwertuje czas GTFS (może przekraczać 24h) na datetime."""
    h, m, s = [int(x) for x in hhmmss.split(":")]
    extra_days, h = divmod(h, 24)
    base = datetime.combine(day, datetime.min.time())
    return base + timedelta(days=extra_days, hours=h, minutes=m, seconds=s)


def _service_ids_for_day(calendar_rows, calendar_dates_rows, target_day: date) -> set:
    """
    Wyznacza zestaw service_id aktywnych w danym dniu na podstawie calendar.txt i calendar_dates.txt.
    Odporne na BOM, brakujące kolumny oraz brak któregokolwiek z plików.
    """
    weekday_map = {
        0: "monday", 1: "tuesday", 2: "wednesday",
        3: "thursday", 4: "friday", 5: "saturday", 6: "sunday"
    }
    wkey = weekday_map[target_day.weekday()]
    active = set()

    # calendar.txt
    for row in calendar_rows or []:
        sid = row.get("service_id")
        if not sid:
            continue
        try:
            start = _parse_gtfs_date(row["start_date"])
            end = _parse_gtfs_date(row["end_date"])
        except KeyError:
            # brak wymaganych pól – pomijamy
            continue
        if start <= target_day <= end and row.get(wkey) == "1":
            active.add(sid)

    # calendar_dates.txt
    for row in calendar_dates_rows or []:
        sid = row.get("service_id")
        d_str = row.get("date")
        if not sid or not d_str:
            continue
        d = _parse_gtfs_date(d_str)
        if d != target_day:
            continue
        et = row.get("exception_type")
        if et == "1":
            active.add(sid)
        elif et == "2":
            active.discard(sid)

    return active


def _safe_line_number(route_short_name: str) -> Optional[int]:
    """Konwertuje route_short_name na int (dla alfanumerycznych zwraca None)."""
    try:
        return int(route_short_name)
    except Exception:
        return None


def create_krakow_database(target_day: Optional[date] = None, force_refresh: bool = False) -> Database:
    """
    Tworzy i zwraca obiekt bazy danych z prawdziwymi danymi GTFS dla linii: 1, 18, 52, 128, 178, 578.
    Parametry:
      - target_day: data, dla której generujemy rozkład (domyślnie: dzisiejsza).
      - force_refresh: jeśli True, pomija cache i pobiera dane na nowo
    Uwaga: statyczny GTFS nie zawiera realnych identyfikatorów pojazdów, więc `vehicles` będzie puste.
           Jeśli chcesz mieć pojazdy/opóźnienia, dołóż krok GTFS-Realtime.
    """
    if target_day is None:
        target_day = datetime.now().date()

    # Try to load from cache first (unless force refresh)
    if not force_refresh:
        cached_db = _load_database_from_cache()
        if cached_db is not None:
            return cached_db

    # 1) Pobierz i wczytaj GTFS (T + A + M)
    # print(f"Pobieranie danych GTFS dla daty: {target_day}")
    feeds: List[Tuple[str, bytes]] = []
    for fname in GTFS_FILES:
        try:
            zbytes = _download(f"{GTFS_BASE}/{fname}")
            if zbytes:  # tylko jeśli pobrano dane
                feeds.append((fname, zbytes))
                # print(f"Pomyślnie pobrano {fname}")
            # else:
            # print(f"Nie udało się pobrać {fname}")
        except Exception as e:
            # print(f"Błąd przy pobieraniu {fname}: {e}")
            continue

    # print(f"Pobrano {len(feeds)} plików GTFS z {len(GTFS_FILES)} dostępnych")

    # Przygotuj struktury agregujące
    # Uwaga: dla prostoty nie deduplikujemy przystanków między pakietami ZIP
    # (nie jest to potrzebne, bo tripy odwołują się do stop_id w ramach tego samego ZIP).
    stops_used_set = set()  # zbiór UUID użytych przystanków
    all_stops_by_key: Dict[Tuple[str, str], Stop] = {}  # (feed, stop_id) -> Stop
    routes_cache: Dict[Tuple[str, str, str, Tuple[uuid.UUID, ...]], Route] = {}
    all_trips: List[Trip] = []

    # Tworzymy zmyślone pojazdy dla każdego typu transportu
    tram_vehicles = []
    bus_vehicles = []

    # Generujemy pojazdy tramwajowe
    for i in range(20):
        vehicle = Vehicle(
            uuid=uuid.uuid4(),
            license_plate=f"KR-T{i + 1:03d}",
            type=VehicleType.TRAM,
            capacity=180 + (i % 3) * 20,  # różne pojemności: 180, 200, 220
            owner="MPK Kraków"
        )
        tram_vehicles.append(vehicle)

    # Generujemy pojazdy autobusowe
    for i in range(30):
        vehicle = Vehicle(
            uuid=uuid.uuid4(),
            license_plate=f"KR-A{i + 1:03d}",
            type=VehicleType.BUS,
            capacity=90 + (i % 4) * 15,  # różne pojemności: 90, 105, 120, 135
            owner="MPK Kraków"
        )
        bus_vehicles.append(vehicle)

    all_vehicles = tram_vehicles + bus_vehicles
    # print(f"Utworzono {len(tram_vehicles)} tramwajów i {len(bus_vehicles)} autobusów")

    for fname, zbytes in feeds:
        # print(f"\nPrzetwarzanie pliku: {fname}")
        # Wczytaj pliki (klucze już w lower-case)
        stops = _read_csv_from_zip(zbytes, "stops.txt")
        routes = _read_csv_from_zip(zbytes, "routes.txt")
        trips = _read_csv_from_zip(zbytes, "trips.txt")
        stop_times = _read_csv_from_zip(zbytes, "stop_times.txt")
        calendar = _read_csv_from_zip(zbytes, "calendar.txt") if _zip_has(zbytes, "calendar.txt") else []
        calendar_dates = _read_csv_from_zip(zbytes, "calendar_dates.txt") if _zip_has(zbytes,
                                                                                      "calendar_dates.txt") else []

        # print(
        #    f"  Wczytano: {len(stops)} przystanków, {len(routes)} tras, {len(trips)} kursów, {len(stop_times)} czasów przystanków")
        # print(f"  Kalendarze: {len(calendar)} regularnych, {len(calendar_dates)} wyjątków")

        # Mapy pomocnicze
        routes_by_id = {r.get("route_id"): r for r in routes if r.get("route_id")}
        stops_by_id = {s.get("stop_id"): s for s in stops if s.get("stop_id")}

        active_service_ids = _service_ids_for_day(calendar, calendar_dates, target_day)
        # print(
        #    f"  Aktywne service_ids dla {target_day}: {len(active_service_ids)} ({list(active_service_ids)[:5]}{'...' if len(active_service_ids) > 5 else ''})")

        # Wybierz route_id dla interesujących linii
        wanted_route_ids = set()
        all_route_lines = set()  # Dla diagnostyki - wszystkie dostępne linie
        route_types_found = {}  # Diagnostyka typów tras
        for r in routes:
            short = (r.get("route_short_name") or "").strip()
            route_type = r.get("route_type", "3")
            all_route_lines.add(short)

            # Zapisz typ trasy dla diagnostyki
            if short not in route_types_found:
                route_types_found[short] = route_type

            if short in TARGET_LINES:
                rid = r.get("route_id")
                if rid:
                    wanted_route_ids.add(rid)

        # print(
        #    f"  Wszystkie dostępne linie w tym pliku: {sorted(all_route_lines)} (łącznie: {len(all_route_lines)})")
        # print(f"  Wybrane linie z TARGET_LINES: {[line for line in sorted(all_route_lines) if line in TARGET_LINES]}")

        # Pokaż typy tras dla wybranych linii
        selected_types = {line: route_types_found.get(line, "unknown") for line in TARGET_LINES if
                          line in route_types_found}
        # print(f"  Typy tras (route_type): {selected_types}")
        tram_lines = [line for line, rtype in selected_types.items() if rtype == "0"]
        bus_lines = [line for line, rtype in selected_types.items() if rtype in ["3", "1"]]
        # print(f"  Tramwaje (route_type=0): {tram_lines}")
        # print(f"  Autobusy (route_type=3/1): {bus_lines}")

        if not wanted_route_ids:
            # print(f"  Nie znaleziono żądanych linii {TARGET_LINES} w tym pliku")
            continue
        # else:
        # print(f"  Znaleziono {len(wanted_route_ids)} żądanych tras: {wanted_route_ids}")

        # Zbuduj Stop obiekty (raz na ZIP)
        for sid, s in stops_by_id.items():
            try:
                lat = float(s["stop_lat"])
                lon = float(s["stop_lon"])
            except Exception:
                # pomiń uszkodzone wiersze
                continue
            name = (s.get("stop_name") or "").strip()
            zone = (s.get("zone_id") or "I").strip() or "I"
            st_obj = Stop(
                uuid=uuid.uuid4(),
                latitude=lat,
                longitude=lon,
                short_name=name,
                long_name=name,
                zone_id=zone,
                # typ ustawimy niżej na podstawie route_type pierwszego tripa, który użyje tego stopu
                type=VehicleType.TRAM
            )
            all_stops_by_key[(fname, sid)] = st_obj

        # Tripy z filtrem po dacie i liniach
        trips_filtered = []
        for tr in trips:
            rid = tr.get("route_id")
            if rid not in wanted_route_ids:
                continue
            sid = tr.get("service_id")
            # jeśli mamy aktywny zestaw, filtruj; jeśli pusty (brak kalendarza), przepuść wszystko
            if active_service_ids and sid not in active_service_ids:
                continue
            trips_filtered.append(tr)

        if not trips_filtered:
            # print(f"  Brak aktywnych kursów dla daty {target_day}")
            continue
        # else:
        # print(f"  Przefiltrowano do {len(trips_filtered)} aktywnych kursów")

        # Stop_times mapowanie: trip_id -> list[rows]
        st_by_trip = defaultdict(list)
        for st in stop_times:
            tid = st.get("trip_id")
            if tid:
                st_by_trip[tid].append(st)

        # Budowa Route/Trip
        for tr in trips_filtered:
            local_trip_id = tr.get("trip_id")
            if not local_trip_id:
                continue

            times = st_by_trip.get(local_trip_id, [])
            if not times:
                continue

            # sortowanie po kolejności przystanków
            try:
                times_sorted = sorted(times, key=lambda r: int(r.get("stop_sequence") or "0"))
            except Exception:
                # jeśli wystąpi błąd konwersji, pomiń ten trip
                continue

            # Odczyt meta route’u
            r_meta = routes_by_id.get(tr.get("route_id") or "")
            if not r_meta:
                continue

            short_name = (r_meta.get("route_short_name") or "").strip()
            line_number_int = _safe_line_number(short_name)
            headsign_hint = (r_meta.get("route_long_name") or short_name or "").strip()
            try:
                route_type_val = int((r_meta.get("route_type") or "3").strip())
            except Exception:
                route_type_val = 3  # bus jako domyślne

            vtype_from_route = VehicleType.TRAM if route_type_val == 0 else VehicleType.BUS

            # Określ typ pojazdu na podstawie nazwy pliku ZIP
            if "GTFS_KRK_T.zip" in fname:
                vtype = VehicleType.TRAM  # Plik tramwajowy
            elif "GTFS_KRK_A.zip" in fname or "GTFS_KRK_M.zip" in fname:
                vtype = VehicleType.BUS  # Pliki autobusowe
            else:
                vtype = vtype_from_route  # Fallback do route_type

            # Debug: sprawdź typ trasy
            # if len(all_trips) < 5:  # Pokaż tylko dla pierwszych kilku tras
            #    print(
            #        f"    DEBUG: Plik {fname}, Linia {short_name}, route_type={route_type_val}, vtype_final={vtype.name}")

            # Sekwencja przystanków (obiekty Stop) dla tego tripa
            stop_objs: List[Stop] = []
            for r in times_sorted:
                sid = r.get("stop_id")
                st_obj = all_stops_by_key.get((fname, sid))
                if st_obj is None:
                    continue
                # ustaw typ przystanku na podstawie tego route_type (pierwsze przypisanie wygrywa)
                if st_obj.type not in (VehicleType.TRAM, VehicleType.BUS):
                    st_obj.type = vtype
                else:
                    # jeśli przystanek jeszcze ma domyślny TRAM a trasa jest BUS (albo odwrotnie),
                    # możesz zmienić logikę. Zostawiamy pierwsze przypisanie.
                    pass
                stop_objs.append(st_obj)

            if len(stop_objs) < 2:
                # zbyt krótka trasa
                continue

            direction_id = (tr.get("direction_id") or "").strip()
            headsign = (tr.get("trip_headsign") or "").strip() or headsign_hint
            route_key = (fname, tr.get("route_id") or "", direction_id, tuple(s.uuid for s in stop_objs))

            if route_key not in routes_cache:
                # jeśli line_number_int jest None (np. dla linii alfanumerycznych), ustaw -1
                ln = line_number_int if line_number_int is not None else -1

                # Przypisz pojazd na podstawie typu trasy
                if vtype == VehicleType.TRAM:
                    assigned_vehicles = [tram_vehicles[len(routes_cache) % len(tram_vehicles)]]
                    vehicle_type_assigned = "TRAM"
                else:
                    assigned_vehicles = [bus_vehicles[len(routes_cache) % len(bus_vehicles)]]
                    vehicle_type_assigned = "BUS"

                # Debug: sprawdź przypisanie pojazdu
                # if len(routes_cache) < 5:  # Pokaż tylko dla pierwszych kilku tras
                # print(
                #    f"    DEBUG: Przypisano pojazd {assigned_vehicles[0].license_plate} ({vehicle_type_assigned}) do linii {ln}")

                routes_cache[route_key] = Route(
                    uuid=uuid.uuid4(),
                    line_number=ln,
                    destination=headsign,
                    vehicles=assigned_vehicles,
                    stops=stop_objs
                )
            route_obj = routes_cache[route_key]

            # Czasy – użyj arrival_time, a gdy brak to departure_time
            timestamps: List[datetime] = []
            for r in times_sorted:
                t = (r.get("arrival_time") or r.get("departure_time") or "").strip()
                if not t:
                    continue
                try:
                    ts = _time_to_datetime(target_day, t)
                    timestamps.append(ts)
                except Exception:
                    continue

            if not timestamps:
                continue

            trip_obj = Trip(uuid=uuid.uuid4(), route=route_obj, timestamps=timestamps)
            all_trips.append(trip_obj)
            # oznacz użyte przystanki
            for s in stop_objs:
                stops_used_set.add(s.uuid)

    # 2) Złożenie finalnej bazy
    trips_dict = {t.uuid: t for t in all_trips}
    # Dodajemy zmyślone pojazdy do bazy danych
    vehicles_dict: Dict[uuid.UUID, Vehicle] = {v.uuid: v for v in all_vehicles}

    # Zbierz tylko użyte przystanki
    used_stops = [st for st in all_stops_by_key.values() if st.uuid in stops_used_set]
    stops_dict = {s.uuid: s for s in used_stops}

    print(f"\nPodsumowanie:")
    print(f"Utworzono {len(all_trips)} kursów")
    print(f"Użyto {len(used_stops)} przystanków")
    print(f"Utworzono {len(routes_cache)} tras")
    print(f"Dodano {len(vehicles_dict)} pojazdów")

    # Create the database object
    database = Database(
        users={},
        vehicles=vehicles_dict,
        stops=stops_dict,
        trips=trips_dict,
        stop_delays={},
        vehicle_delays={}
    )

    # Save to cache for future use
    _save_database_to_cache(database)

    return database


class DatabaseSingleton:
    """
    Singleton class for Krakow database instance.
    Ensures only one database is created and reused across the application.
    """
    _instance = None
    _database = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseSingleton, cls).__new__(cls)
        return cls._instance

    def get_database(self, target_day=None, force_refresh=False):
        """
        Returns the database instance. Creates it only once (singleton pattern).
        Uses caching to speed up subsequent loads.
        """
        if self._database is None or force_refresh:
            self._database = create_krakow_database(target_day, force_refresh)
        return self._database

    def reset_database(self, target_day=None, force_refresh=True):
        """
        Forces recreation of the database (useful for testing or data refresh).
        Always forces refresh to get latest data.
        """
        self._database = create_krakow_database(target_day, force_refresh)
        return self._database


# Singleton instance - tworzy się tylko raz
_db_singleton = DatabaseSingleton()


def get_db(target_day=None, force_refresh=False):
    """
    Główna funkcja do pobierania instancji bazy danych.
    Używa wzorca singleton - baza tworzy się tylko raz i wykorzystuje cache.

    Args:
        target_day: data dla której generować rozkład (domyślnie dzisiaj)
        force_refresh: czy wymusić odświeżenie danych (pomiń cache)
    """
    return _db_singleton.get_database(target_day, force_refresh)


def reset_db(target_day=None):
    """
    Funkcja do resetowania bazy danych (przydatne do testów).
    Zawsze wymusza odświeżenie danych.
    """
    return _db_singleton.reset_database(target_day)


def clear_cache():
    """
    Usuwa plik cache bazy danych.
    """
    try:
        if os.path.exists(DB_CACHE_FILE):
            os.remove(DB_CACHE_FILE)
            return True
        else:
            return False
    except Exception as e:
        return False


def get_cache_info():
    """
    Zwraca informacje o stanie cache'u.
    """
    info = {
        "cache_exists": os.path.exists(DB_CACHE_FILE),
        "cache_path": DB_CACHE_FILE,
        "expiry_hours": CACHE_EXPIRY_HOURS
    }

    if info["cache_exists"]:
        info["cache_age_hours"] = _get_cache_age_hours()
        info["cache_valid"] = _is_cache_valid()
        info["cache_size_mb"] = os.path.getsize(DB_CACHE_FILE) / (1024 * 1024)
        info["cache_modified"] = datetime.fromtimestamp(os.path.getmtime(DB_CACHE_FILE)).isoformat()

    return info


# Kompatybilność wsteczna - automatyczne utworzenie db przy imporcie
# Za usunięcie tej linijki grozi kara śmierci przez rozjechanie tramwajem
db = get_db()
