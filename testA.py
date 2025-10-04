from datetime import datetime, timedelta
from uuid import uuid4
from typing import List
from db import *
from heapq import heappop, heappush
from db_setup import *


class RouteStep:
    def __init__(self, from_stop, to_stop, vehicle_uuid=None, depart_time=None, arrival_time=None):
        self.from_stop = from_stop
        self.to_stop = to_stop
        self.vehicle_uuid = vehicle_uuid  # None = pieszo
        self.depart_time = depart_time
        self.arrival_time = arrival_time

    def __lt__(self, other):
        return (self.from_stop.short_name, self.to_stop.short_name) < (other.from_stop.short_name,
                                                                       other.to_stop.short_name)

def find_route_with_transfers(database: Database, start_lat: float, start_lon: float,
                              end_lat: float, end_lon: float, current_time: datetime) -> List[RouteStep]:
    # Wszystkie przystanki w bazie
    all_stops = [stop for trip in database.trips.values() for stop in trip.route.stops]

    # Najbliższe przystanki do punktu startowego i końcowego
    start_stop = find_nearest_stop(start_lat, start_lon, all_stops)
    end_stop = find_nearest_stop(end_lat, end_lon, all_stops)
    print("startowa ")
    print(start_stop.short_name)
    print("koncowa ")
    print(end_stop.short_name)

    # Dijkstra: heap = (czas_totalny, aktualny przystanek, ścieżka, poprzedni pojazd, obecny czas)
    heap = [(0, start_stop, [], None, current_time)]
    visited = {}

    while heap:
        total_time, current_stop, path, prev_vehicle, now_time = heappop(heap)
        print(current_stop.short_name)
        if current_stop in visited and visited[current_stop] <= total_time:
            continue
        visited[current_stop] = total_time

        if current_stop == end_stop:
            walking_distance_km = haversine(end_stop.latitude, end_stop.longitude, end_lat, end_lon)
            #walking_time_sec = walking_distance_km / 5.0 * 3600  # pieszo 5 km/h
            walking_time_sec = 0
            path.append(RouteStep(
                from_stop=current_stop,
                to_stop="punkt końcowy",
                vehicle_uuid=None,
                depart_time=now_time,
                arrival_time=now_time + timedelta(seconds=walking_time_sec)
            ))
            return path

        # Pobierz możliwe połączenia z aktualnego przystanku
        edges = get_routes(database, current_stop, now_time)
        print(f"{current_stop.short_name} -> {[e.next_stop for e in edges]}")

        for edge in edges:
            depart_time = edge.start_timestamp
            arrival_time = depart_time + timedelta(seconds=edge.time)
            step = RouteStep(
                from_stop=current_stop,
                to_stop=edge.next_stop,
                vehicle_uuid=edge.vehicle_uuid,
                depart_time=depart_time,
                arrival_time=arrival_time
            )
            heappush(heap, (total_time + edge.time, edge.next_stop, path + [step], edge.vehicle_uuid, arrival_time))

    return []  # jeśli nie znaleziono trasy

def print_full_route(route_steps: List[RouteStep], database: Database):
    print("Trasa:")
    for step in route_steps:
        depart = step.depart_time.strftime("%H:%M:%S")
        arrival = step.arrival_time.strftime("%H:%M:%S")
        if step.vehicle_uuid is None:
            print(f"Pieszo z {step.from_stop.long_name if hasattr(step.from_stop,'long_name') else step.from_stop} "
                  f"do {step.to_stop if isinstance(step.to_stop, str) else step.to_stop.long_name} "
                  f"({depart} -> {arrival})")
        else:
            vehicle = next((v for trip in database.trips.values() for v in trip.route.vehicles if v.uuid == step.vehicle_uuid), None)
            vehicle_info = f"{vehicle.type.name} {vehicle.license_plate}" if vehicle else "pojazd"
            print(f"{vehicle_info} z {step.from_stop.long_name} do {step.to_stop.long_name} "
                  f"({depart} -> {arrival})")
    if route_steps:
        total_time_sec = (route_steps[-1].arrival_time - route_steps[0].depart_time).total_seconds()
        print(f"\nŁączny czas podróży: {total_time_sec/60:.1f} min")
    else:
        print("Nie znaleziono trasy!")

if __name__ == "__main__":
    now = datetime.now()
    start_lat, start_lon = 50.014623, 19.888062
    end_lat, end_lon = 50.067366, 19.990079
    from db_setup import db
    route_steps = find_route_with_transfers(db, start_lat, start_lon, end_lat, end_lon, now)
    print_full_route(route_steps, db)
