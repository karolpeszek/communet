from enum import Enum
import math
from typing import List, Tuple, Dict
from datetime import datetime


class VehicleType(Enum):
    TRAM = 0
    BUS = 1
    TRAIN = 2


class Vehicle:
    def __init__(self, license_plate: str, type: VehicleType, capacity: int, owner: str):
        self.license_plate = license_plate
        self.type = type
        self.capacity = capacity
        self.owner = owner


class Stop:
    def __init__(self, latitude: float, longitude: float, short_name: str, long_name: str, zone_id: str, type: VehicleType):
        self.latitude = latitude
        self.longitude = longitude
        self.short_name = short_name
        self.long_name = long_name
        self.zone_id = zone_id
        self.type = type

    def __repr__(self):
        return f"Stop({self.short_name})"


class Edge:
    def __init__(self, stop1: Stop, stop2: Stop, distance: float, routes: List[int]):
        self.stop1 = stop1
        self.stop2 = stop2
        self.distance = distance
        self.routes = routes

class TransportGraph:
    def __init__(self, stops: List[Stop], edges: List[Edge]):
        self.stops = stops
        self.edges = edges