from enum import Enum
from typing import List, Dict, Tuple
from datetime import datetime, timedelta
from uuid import UUID
from math import *

class User:
    def __init__(self, uuid: UUID, name: str, surname: str, location, reputation:int):
        self.uuid = uuid
        self.reputation = reputation
        self.location = location
        self.name = name
        self.surname = surname

class VehicleType(Enum):
    TRAM = "TRAM"
    BUS = "BUS"
    TRAIN = "TRAIN"
    OTHER = "OTHER"

class DelayReason(Enum):
    TRAFFIC_JAM = "TRAFFIC_JAM"
    ROAD_ACCIDENT = "ROAD_ACCIDENT"
    SEVERE_WEATHER = "SEVERE_WEATHER"
    VEHICLE_ISSUE = "VEHICLE_ISSUE"


class Vehicle:
    def __init__(self, uuid: UUID, license_plate: str, type: VehicleType, capacity: int, owner: str):
        self.uuid = uuid
        self.license_plate = license_plate
        self.type = type
        self.capacity = capacity
        self.owner = owner

class Stop:
    def __init__(self, uuid: UUID, latitude: float, longitude: float, short_name: str, long_name: str, zone_id: str, type: VehicleType):
        self.uuid = uuid
        self.latitude = latitude
        self.longitude = longitude
        self.short_name = short_name
        self.long_name = long_name
        self.zone_id = zone_id
        self.type = type

    def __str__(self):
        return f"Stop: {self.short_name} ({self.long_name}), lat: {self.latitude}, lon: {self.longitude}, type: {self.type.name}"

    def __repr__(self):
        return f"Stop(uuid={self.uuid}, short_name={self.short_name}, long_name={self.long_name})"

    def __lt__(self, other):
        return self.uuid.int < other.uuid.int

class Route:
    def __init__(self, uuid: UUID, line_number: int, destination: str, vehicles: List[Vehicle], stops: List[Stop]):
        self.uuid = uuid
        self.line_number = line_number
        self.destination = destination
        self.vehicles = vehicles
        self.stops = stops

class Trip:
    def __init__(self, uuid: UUID, route: Route, timestamps: List[datetime], ):
        self.uuid = uuid
        self.route = route
        self.timestamps = timestamps #contains a list of timestamps with indices corresponding with stops on the route

class Delay:
    def __init__(self, uuid: UUID, time_delay: int, reason: str):
        self.uuid = uuid
        self.time_delay = time_delay
        self.reason = reason

class Database:
    def __init__(self, users: Dict[UUID, User],
                 vehicles: Dict[UUID, Vehicle],
                 stops: Dict[UUID, Stop],
                 trips: Dict[UUID, Trip],
                 stop_delays: Dict[Tuple[Stop, Stop], int],
                 vehicle_delays: Dict[Vehicle, int]):
        self.users = users
        self.trips = trips
        self.stop_delays = stop_delays
        self.vehicle_delays = vehicle_delays
        self.vehicles = vehicles
        self.stops = stops

    def get_vehicle(self, uuid: UUID) -> Vehicle:
        if uuid in self.vehicles:
            return self.vehicles[uuid]
        else:
            return next(iter(self.vehicles.values()))

    def get_stop(self, uuid: UUID) -> Stop:
        if uuid in self.stops:
            return self.stops[uuid]
        else:
            return next(iter(self.stops.values()))

class Edge:
    def __init__(self, vehicle_uuid: UUID, trip_uuid: UUID, next_stop: Stop, start_timestamp: datetime, time: int):
        self.vehicle_uuid = vehicle_uuid
        self.trip_uuid = trip_uuid
        self.next_stop = next_stop
        self.start_timestamp = start_timestamp
        self.time = time  # in seconds

from db_setup import db

def report_delay(vehicle: Vehicle, delay: Delay, current_position: Tuple[Stop, Stop]):
    if delay.reason == "VEHICLE_ISSUE":
        #theres an issue with the vehicle, road remains unaffected
        db.vehicle_delays[vehicle] = delay
    else:
        #delay is most likely caused by the particular route between given stops
        db.stop_delays[current_position] = delay
    from db_setup import save_db
    save_db(db)


def get_routes(database: Database, stop: Stop, timestamp: datetime) -> List[Edge]:
    edges: List[Edge] = []

    for trip in database.trips.values():
        route_stops = trip.route.stops
        if stop not in route_stops:
            continue

        idx = route_stops.index(stop)
        # Can't go to next stop if it's the last stop
        if idx == len(route_stops) - 1:
            continue

        next_stop = route_stops[idx + 1]

        # Base travel time between stops
        base_time = (trip.timestamps[idx + 1] - trip.timestamps[idx]).total_seconds()

        # Get delays
        vehicle_delay = database.vehicle_delays.get(trip.route.vehicles[0], None)
        stop_delay = database.stop_delays.get((stop, next_stop), None)

        max_delay_seconds = 0
        if vehicle_delay is not None:
            max_delay_seconds = max(max_delay_seconds, vehicle_delay.time_delay)
        if stop_delay is not None:
            max_delay_seconds = max(max_delay_seconds, stop_delay.time_delay)

        # Calculate actual departure time from current stop
        departure_time = trip.timestamps[idx] + timedelta(seconds=max_delay_seconds)

        # Only include trips that have not departed yet
        if departure_time < timestamp:
            continue

        # Create edge including start_timestamp
        edges.append(Edge(
            vehicle_uuid=trip.route.vehicles[0].uuid,
            trip_uuid=trip.uuid,
            next_stop=next_stop,
            start_timestamp=departure_time,
            time=int(base_time + max_delay_seconds)
        ))

    return edges


def get_risky_routes(database: Database, stop: Stop, timestamp: datetime) -> List[Edge]:
    pass


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)

    a = sin(dlat / 2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return R * c

def find_nearest_stop(lat: float, lon: float, stops: List[Stop]) -> Stop:
    nearest = min(stops, key=lambda stop: haversine(lat, lon, stop.latitude, stop.longitude))
    return nearest
