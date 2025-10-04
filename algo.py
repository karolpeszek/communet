from datetime import datetime, timedelta
from uuid import uuid4
from typing import List, Dict, Set
from db import *
from heapq import heappop, heappush
from db_setup import db as database


class RouteStep:
    def __init__(self, from_stop, to_stop, vehicle_uuid=None, trip_uuid=None, depart_time=None, arrival_time=None,
                 is_walking=False, walking_distance_m=0, delay_info=None):
        self.from_stop = from_stop
        self.to_stop = to_stop
        self.vehicle_uuid = vehicle_uuid
        self.trip_uuid = trip_uuid
        self.depart_time = depart_time
        self.arrival_time = arrival_time
        self.is_walking = is_walking
        self.walking_distance_m = walking_distance_m
        self.delay_info = delay_info  # Dict z informacjami o opóźnieniu

    def __lt__(self, other):
        return self.arrival_time < other.arrival_time if self.arrival_time and other.arrival_time else False


def check_delays_for_segment(database: Database, vehicle_uuid: str, from_stop: Stop, to_stop: Stop) -> dict:
    """
    Sprawdza czy na danym odcinku są opóźnienia i zwraca informacje o nich.
    """
    delay_info = {
        'has_delay': False,
        'delay_minutes': 0,
        'delay_reason': '',
        'delay_source': '',
        'normal_time_minutes': 0,
        'delayed_time_minutes': 0
    }

    # Sprawdź opóźnienia pojazdu
    vehicle = database.get_vehicle(vehicle_uuid)
    vehicle_delay = database.vehicle_delays.get(vehicle)

    # Sprawdź opóźnienia na odcinku drogi
    stop_pair = (from_stop, to_stop)
    stop_delay = database.stop_delays.get(stop_pair)

    # Znajdź największe opóźnienie
    max_delay = None
    delay_source = ""

    if vehicle_delay and stop_delay:
        if vehicle_delay.time_delay > stop_delay.time_delay:
            max_delay = vehicle_delay
            delay_source = f"pojazd {vehicle.license_plate}"
        else:
            max_delay = stop_delay
            delay_source = f"odcinek {from_stop.short_name} → {to_stop.short_name}"
    elif vehicle_delay:
        max_delay = vehicle_delay
        delay_source = f"pojazd {vehicle.license_plate}"
    elif stop_delay:
        max_delay = stop_delay
        delay_source = f"odcinek {from_stop.short_name} → {to_stop.short_name}"

    if max_delay:
        delay_minutes = max_delay.time_delay.total_seconds() / 60
        delay_info.update({
            'has_delay': True,
            'delay_minutes': delay_minutes,
            'delay_reason': max_delay.reason.name,
            'delay_source': delay_source
        })

    return delay_info


def find_fastest_route(database: Database, start_lat: float, start_lon: float,
                       end_lat: float, end_lon: float, departure_time: datetime) -> List[RouteStep]:
    """
    Znajduje najszybszą trasę używając zmodyfikowanego algorytmu Dijkstry.
    Uwzględnia rzeczywiste czasy odjazdu, czasy oczekiwania, chodzenie pieszo i opóźnienia.
    """

    # Pobierz wszystkie unikalne przystanki
    all_stops = list(database.stops.values())

    # Znajdź najbliższe przystanki
    start_stop = find_nearest_stop(start_lat, start_lon, all_stops)
    end_stop = find_nearest_stop(end_lat, end_lon, all_stops)

    # Sprawdź czy można dojść pieszo (jeśli dystans < 2km)
    direct_distance = haversine(start_lat, start_lon, end_lat, end_lon) * 1000  # w metrach
    if direct_distance < 2000:  # 2km
        walking_time_min = direct_distance / 83.33  # 5 km/h = 83.33 m/min
        walking_arrival = departure_time + timedelta(minutes=walking_time_min)
        walking_step = RouteStep(
            from_stop=Stop(uuid4(), start_lat, start_lon, "Start", "Punkt startowy", "I", VehicleType.OTHER),
            to_stop=Stop(uuid4(), end_lat, end_lon, "Cel", "Punkt docelowy", "I", VehicleType.OTHER),
            depart_time=departure_time,
            arrival_time=walking_arrival,
            is_walking=True,
            walking_distance_m=int(direct_distance)
        )
        print(f"🚶 Można dojść pieszo w {walking_time_min:.1f} min ({direct_distance:.0f}m)")
        return [walking_step]

    print(f"🚩 Start: {start_stop.short_name}")
    print(f"🎯 Cel: {end_stop.short_name}")
    print(f"⏰ Czas startu: {departure_time.strftime('%H:%M:%S')}")
    print(f"📏 Dystans: {direct_distance:.0f}m")
    print("-" * 50)

    # Heap: (czas_dotarcia_timestamp, przystanek_uuid, ścieżka_kroków, aktualny_czas, liczba_przesiadek)
    heap = [(departure_time.timestamp(), start_stop.uuid, [], departure_time, 0)]

    # Najlepszy czas dotarcia do każdego przystanku
    best_time: Dict[str, datetime] = {}
    visited_stops: Set[str] = set()

    MAX_TRANSFERS = 3  # Maksymalnie 3 przesiadki
    MAX_WALKING_DISTANCE = 800  # Maksymalny dystans spaceru między przystankami (800m)

    while heap:
        arrival_timestamp, current_stop_uuid, path, current_time, transfers = heappop(heap)
        arrival_time = datetime.fromtimestamp(arrival_timestamp)

        # Ograniczenie liczby przesiadek
        if transfers > MAX_TRANSFERS:
            continue

        # Sprawdź czy już mamy lepszy czas do tego przystanku
        if current_stop_uuid in best_time:
            if best_time[current_stop_uuid] <= arrival_time:
                continue

        best_time[current_stop_uuid] = arrival_time
        current_stop = database.get_stop(current_stop_uuid)

        # Jeśli dotarliśmy do celu
        if current_stop_uuid == end_stop.uuid:
            print(f"✅ Znaleziono trasę do {current_stop.short_name} w {transfers} przesiadkach")
            return path

        # Opcja 1: Chodzenie pieszo do pobliskich przystanków
        for nearby_stop in all_stops:
            if nearby_stop.uuid == current_stop.uuid:
                continue

            walking_distance = haversine(current_stop.latitude, current_stop.longitude,
                                         nearby_stop.latitude, nearby_stop.longitude) * 1000

            if walking_distance <= MAX_WALKING_DISTANCE:
                walking_time_min = walking_distance / 83.33  # 5 km/h
                walking_arrival = current_time + timedelta(minutes=walking_time_min)

                # Sprawdź czy to już odwiedzaliśmy z lepszym czasem
                if nearby_stop.uuid in best_time:
                    if best_time[nearby_stop.uuid] <= walking_arrival:
                        continue

                # Utwórz krok spacerowy
                walking_step = RouteStep(
                    from_stop=current_stop,
                    to_stop=nearby_stop,
                    depart_time=current_time,
                    arrival_time=walking_arrival,
                    is_walking=True,
                    walking_distance_m=int(walking_distance)
                )

                new_path = path + [walking_step]
                heappush(heap, (
                    walking_arrival.timestamp(),
                    nearby_stop.uuid,
                    new_path,
                    walking_arrival,
                    transfers  # Spacer nie zwiększa liczby przesiadek
                ))

        # Opcja 2: Komunikacja publiczna
        available_edges = get_routes(database, current_stop, current_time)

        for edge in available_edges:
            next_stop = edge.next_stop

            # Sprawdź czy to nie jest krok wstecz
            if len(path) >= 2 and path[-1].to_stop.uuid == next_stop.uuid:
                continue

            # Oblicz czasy
            depart_time = edge.start_timestamp
            trip_arrival_time = depart_time + timedelta(seconds=edge.time)

            # Sprawdź czy pojazd jeszcze nie odjechał
            if depart_time < current_time:
                continue

            # Oblicz czas oczekiwania
            wait_time_sec = (depart_time - current_time).total_seconds()

            # Pomiń jeśli czas oczekiwania > 2 godziny (nierealistyczne)
            if wait_time_sec > 7200:
                continue

            # Sprawdź czy to już odwiedzaliśmy z lepszym czasem
            if next_stop.uuid in best_time:
                if best_time[next_stop.uuid] <= trip_arrival_time:
                    continue

            # Sprawdź czy to przesiadka (zmiana pojazdu)
            new_transfers = transfers
            if path and not path[-1].is_walking:
                if path[-1].vehicle_uuid != edge.vehicle_uuid:
                    new_transfers += 1

            # Sprawdź opóźnienia na tym odcinku
            delay_info = check_delays_for_segment(database, edge.vehicle_uuid, current_stop, next_stop)

            # Utwórz krok trasy z informacją o opóźnieniu
            step = RouteStep(
                from_stop=current_stop,
                to_stop=next_stop,
                vehicle_uuid=edge.vehicle_uuid,
                trip_uuid=edge.trip_uuid,
                depart_time=depart_time,
                arrival_time=trip_arrival_time,
                is_walking=False,
                delay_info=delay_info
            )

            # Dodaj do heap
            new_path = path + [step]
            heappush(heap, (
                trip_arrival_time.timestamp(),
                next_stop.uuid,
                new_path,
                trip_arrival_time,
                new_transfers
            ))

    print("❌ Nie znaleziono trasy!")
    return []


def print_route_details(route_steps: List[RouteStep], database: Database):
    """Wyświetla szczegółowe informacje o trasie z uwzględnieniem opóźnień"""

    if not route_steps:
        print("Brak trasy do wyświetlenia!")
        return

    print("\n" + "=" * 80)
    print("🗺️  SZCZEGÓŁY TRASY")
    print("=" * 80)

    total_travel_time = 0
    total_wait_time = 0
    total_walking_time = 0
    total_walking_distance = 0
    total_delay_time = 0
    transfer_count = 0
    prev_vehicle = None
    delays_encountered = []

    for i, step in enumerate(route_steps, 1):
        if step.is_walking:
            # Krok spacerowy
            walking_time = (step.arrival_time - step.depart_time).total_seconds() / 60
            total_walking_time += walking_time
            total_walking_distance += step.walking_distance_m

            print(f"\n{i}. 🚶 SPACER")
            print(f"   📍 {step.from_stop.short_name}")
            print(f"   📍 {step.to_stop.short_name}")
            print(f"   🕐 {step.depart_time.strftime('%H:%M:%S')} → {step.arrival_time.strftime('%H:%M:%S')}")
            print(f"   📏 Dystans: {step.walking_distance_m}m")
            print(f"   ⏱️  Czas spaceru: {walking_time:.1f} min")
        else:
            # Krok komunikacją publiczną
            vehicle = database.get_vehicle(step.vehicle_uuid)
            trip = database.trips[step.trip_uuid]

            # Sprawdź czy to przesiadka
            is_transfer = (prev_vehicle is not None and
                           prev_vehicle != step.vehicle_uuid and
                           not route_steps[i - 2].is_walking if i > 1 else False)

            if is_transfer:
                transfer_count += 1
                # Oblicz czas oczekiwania na przesiadce
                prev_step = route_steps[i - 2]
                wait_time = (step.depart_time - prev_step.arrival_time).total_seconds() / 60
                total_wait_time += wait_time
                print(f"\n🔄 PRZESIADKA #{transfer_count}")
                print(f"   📍 Miejsce przesiadki: {step.from_stop.short_name}")
                print(f"   ⏳ Czas oczekiwania: {wait_time:.1f} min")

            # Oblicz czas przejazdu dla tego odcinka
            travel_time = (step.arrival_time - step.depart_time).total_seconds() / 60
            total_travel_time += travel_time

            # Wyświetl szczegóły kroku
            vehicle_icon = "🚊" if vehicle.type == VehicleType.TRAM else "🚌"
            line_info = f"Linia {trip.route.line_number}" if trip.route.line_number > 0 else "Linia specjalna"
            print(f"\n{i}. {vehicle_icon} {line_info} - {vehicle.license_plate}")
            print(f"   🎯 Kierunek: {trip.route.destination}")
            print(f"   📍 Z: {step.from_stop.short_name}")
            print(f"   📍 Do: {step.to_stop.short_name}")
            print(f"   🕐 {step.depart_time.strftime('%H:%M:%S')} → {step.arrival_time.strftime('%H:%M:%S')}")
            print(f"   ⏱️  Czas przejazdu: {travel_time:.1f} min")

            # Wyświetl informacje o opóźnieniu
            if step.delay_info and step.delay_info['has_delay']:
                delay_minutes = step.delay_info['delay_minutes']
                delay_reason = step.delay_info['delay_reason']
                delay_source = step.delay_info['delay_source']

                total_delay_time += delay_minutes
                delays_encountered.append({
                    'segment': f"{step.from_stop.short_name} → {step.to_stop.short_name}",
                    'delay_minutes': delay_minutes,
                    'reason': delay_reason,
                    'source': delay_source
                })

                # Ikony dla różnych przyczyn opóźnienia
                delay_icons = {
                    'TRAFFIC_JAM': '🚦',
                    'ROAD_ACCIDENT': '🚧',
                    'SEVERE_WEATHER': '🌧️',
                    'VEHICLE_ISSUE': '⚠️'
                }

                delay_icon = delay_icons.get(delay_reason, '⏰')

                print(f"   {delay_icon} OPÓŹNIENIE: +{delay_minutes:.1f} min")
                print(f"   📝 Przyczyna: {delay_reason.replace('_', ' ').title()}")
                print(f"   🎯 Źródło: {delay_source}")
                print(f"   💡 Normalny czas przejazdu byłby o {delay_minutes:.1f} min krótszy")

            prev_vehicle = step.vehicle_uuid

    # Podsumowanie
    print("\n" + "=" * 80)
    print("📊 PODSUMOWANIE TRASY")
    print("=" * 80)

    start_time = route_steps[0].depart_time
    end_time = route_steps[-1].arrival_time
    total_time = (end_time - start_time).total_seconds() / 60

    print(f"🕐 Odjazd: {start_time.strftime('%H:%M:%S')}")
    print(f"🕐 Przyjazd: {end_time.strftime('%H:%M:%S')}")
    print(f"⏰ Całkowity czas: {total_time:.1f} min ({total_time / 60:.1f} h)")
    print(f"🚊 Czas w pojazdach: {total_travel_time:.1f} min")
    print(f"🚶 Czas spaceru: {total_walking_time:.1f} min")
    print(f"📏 Dystans spaceru: {total_walking_distance}m")
    print(f"⏳ Czas oczekiwania: {total_wait_time:.1f} min")
    print(f"🔄 Liczba przesiadek: {transfer_count}")

    # Podsumowanie opóźnień
    if total_delay_time > 0:
        print(f"⚠️  CAŁKOWITE OPÓŹNIENIE: {total_delay_time:.1f} min")
        print(f"💡 Bez opóźnień trasa zajęłaby: {total_time - total_delay_time:.1f} min")

        print(f"\n📋 SZCZEGÓŁY OPÓŹNIEŃ:")
        for j, delay in enumerate(delays_encountered, 1):
            print(
                f"   {j}. {delay['segment']}: +{delay['delay_minutes']:.1f} min ({delay['reason'].replace('_', ' ').title()})")
    else:
        print("✅ Brak opóźnień na trasie!")

    print("=" * 80)


def test_routes():
    """Testuje różne trasy w Krakowie"""

    # Inicjalizuj bazę danych

    # Czas testowy (dzisiaj o 14:00)
    test_time = datetime.now().replace(hour=14, minute=0, second=0, microsecond=0)

    # Różne przypadki testowe
    test_cases = [
        # {
        #     "name": "bez przesiadki → prosze",
        #     "start": (50.098, 20.000),
        #     "end": (50.072, 20.005),
        # },
        # {
        #     "name": "Salwator → Wzgórza Krzesławickie",
        #     "start": (50.054, 19.915),  # Salwator
        #     "end": (50.093, 20.069),  # Wzgórza Krzesławickie
        # },
        # {
        #     "name": "Dworzec Główny → Mistrzejowice",
        #     "start": (50.066, 19.947),  # Dworzec Główny
        #     "end": (50.098, 20.000),  # Mistrzejowice
        # },
        {
            "name": "Czerwone Maki → Tauron Arena",
            "start": (50.014623, 19.888062),
            "end": (50.067366, 19.990079),
        }
    ]

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{'=' * 100}")
        print(f"TEST {i}: {test_case['name']}")
        print(f"{'=' * 100}")

        start_lat, start_lon = test_case["start"]
        end_lat, end_lon = test_case["end"]

        route = find_fastest_route(
            database, start_lat, start_lon, end_lat, end_lon, test_time
        )

        print_route_details(route, database)


# Export funkcji dla API
__all__ = ['find_fastest_route', 'RouteStep', 'print_route_details']

if __name__ == "__main__":
    test_routes()
