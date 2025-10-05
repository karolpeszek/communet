from fastapi import APIRouter, HTTPException
from security import verify
from db import report_delay as db_report_delay, Delay, DelayReason
from backend.serializers import ReportDelaySerializer, GetRouteSerializer, donotlook
from datetime import timedelta, datetime
import uuid
from db_setup import db
import random  

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from algo import *
from backend.create_lines import create_detailed_route_geometry
from typing import List, Optional
from pydantic import BaseModel

router = APIRouter()


# Modele danych dla API
class CoordinatePoint(BaseModel):
    latitude: float
    longitude: float


class DelayInfo(BaseModel):
    has_delay: bool
    delay_minutes: float
    delay_reason: str
    delay_source: str


class StopInfo(BaseModel):
    uuid: str
    name: str
    coordinates: CoordinatePoint


class VehicleInfo(BaseModel):
    uuid: str
    license_plate: str
    type: str  # "TRAM" lub "BUS"
    line_number: int
    destination: str
    capacity: int
    owner: str


class RouteSegment(BaseModel):
    segment_id: int
    type: str  # "walking" lub "transit"
    from_stop: StopInfo
    to_stop: StopInfo

    # Informacje o czasie - jako Unix timestamp
    departure_timestamp: int  # Unix timestamp (sekundy od 1970-01-01)
    arrival_timestamp: int  # Unix timestamp (sekundy od 1970-01-01)
    duration_minutes: float

    # Dla spaceru
    walking_distance_meters: Optional[int] = None

    # Dla komunikacji publicznej
    vehicle: Optional[VehicleInfo] = None

    # Informacje o opóźnieniach
    delay: Optional[DelayInfo] = None


class RouteSummary(BaseModel):
    total_duration_minutes: float
    total_walking_time_minutes: float
    total_walking_distance_meters: int
    total_wait_time_minutes: float
    total_delay_time_minutes: float
    number_of_transfers: int

    departure_timestamp: int  # Unix timestamp
    arrival_timestamp: int  # Unix timestamp

    # Statystyki
    segments_count: int
    walking_segments_count: int
    transit_segments_count: int


class RouteResponse(BaseModel):
    success: bool
    message: str
    request_info: dict

    # Główne dane trasy
    route_segments: List[RouteSegment]
    summary: RouteSummary

    # Szczegółowa geometria trasy (współrzędne wszystkich punktów)
    detailed_geometry: List[List[float]]  # Lista [lat, lon] punktów

    # Dodatkowe informacje
    alternative_routes_available: bool
    recommendations: List[str]


@router.post("/api/v1/delay/report")
def report_delay(data: ReportDelaySerializer):
    delay = Delay(uuid.UUID(data.vehicle_uuid), 500, data.delay_reason)
    vehicle = db.get_vehicle(uuid.UUID(data.vehicle_uuid))
    cur = db.get_stop(uuid.UUID(data.current_stop_uuid))
    next2 = db.get_stop(uuid.UUID(data.next_stop_uuid))
    db_report_delay(vehicle, delay, (cur, next2))

    return {"success": True}

@router.get("/api/v1/plan_route", response_model=RouteResponse)
def get_plan_route(
        start_lat: float,
        start_lon: float,
        end_lat: float,
        end_lon: float,
        timestamp: int  # Unix timestamp w sekundach
):
    """
    Planuje optymalną trasę komunikacji publicznej między dwoma punktami.

    **Parametry query:**
    - start_lat: Szerokość geograficzna punktu startowego (-90 do 90)
    - start_lon: Długość geograficzna punktu startowego (-180 do 180)
    - end_lat: Szerokość geograficzna punktu docelowego (-90 do 90)
    - end_lon: Długość geograficzna punktu docelowego (-180 do 180)
    - timestamp: Unix timestamp w sekundach (czas odjazdu)

    **Zwraca:**
    - Szczegółową trasę z Unix timestamps i informacjami o przystankach, pojazdach i opóźnieniach

    **Przykład:**
    ```
    GET /api/v1/plan_route?start_lat=50.063&start_lon=19.938&end_lat=50.067&end_lon=19.990&timestamp=1705320600
    ```
    """
    try:
        # Walidacja parametrów
        if not (-90 <= start_lat <= 90) or not (-180 <= start_lon <= 180):
            raise HTTPException(status_code=400, detail="Nieprawidłowe współrzędne punktu startowego")

        if not (-90 <= end_lat <= 90) or not (-180 <= end_lon <= 180):
            raise HTTPException(status_code=400, detail="Nieprawidłowe współrzędne punktu docelowego")

        # Walidacja timestamp
        try:
            departure_time = datetime.fromtimestamp(timestamp)
        except (ValueError, OSError, OverflowError):
            raise HTTPException(status_code=400, detail="Nieprawidłowy timestamp")

        # Informacje o żądaniu
        request_info = {
            "start_coordinates": {"latitude": start_lat, "longitude": start_lon},
            "end_coordinates": {"latitude": end_lat, "longitude": end_lon},
            "departure_timestamp": timestamp,
            "processing_timestamp": int(datetime.now().timestamp())
        }

        # Znajdź optymalną trasę
        route_steps = find_fastest_route(
            database=db,
            start_lat=start_lat,
            start_lon=start_lon,
            end_lat=end_lat,
            end_lon=end_lon,
            departure_time=departure_time
        )

        if not route_steps:
            return RouteResponse(
                success=False,
                message="Nie znaleziono trasy między podanymi punktami",
                request_info=request_info,
                route_segments=[],
                summary=RouteSummary(
                    total_duration_minutes=0,
                    total_walking_time_minutes=0,
                    total_walking_distance_meters=0,
                    total_wait_time_minutes=0,
                    total_delay_time_minutes=0,
                    number_of_transfers=0,
                    departure_timestamp=timestamp,
                    arrival_timestamp=timestamp,
                    segments_count=0,
                    walking_segments_count=0,
                    transit_segments_count=0
                ),
                detailed_geometry=[],
                alternative_routes_available=False,
                recommendations=["Sprawdź inne środki transportu", "Rozważ podróż w innym czasie"]
            )

        # Konwertuj kroki trasy na format API
        route_segments = []
        total_walking_time = 0
        total_walking_distance = 0
        total_wait_time = 0
        total_delay_time = 0
        transfer_count = 0
        walking_segments = 0
        transit_segments = 0
        prev_vehicle = None

        for i, step in enumerate(route_steps):
            # Podstawowe informacje o przystankach
            if hasattr(step.from_stop, 'uuid'):
                from_stop_info = StopInfo(
                    uuid=str(step.from_stop.uuid),
                    name=step.from_stop.short_name,
                    coordinates=CoordinatePoint(
                        latitude=step.from_stop.latitude,
                        longitude=step.from_stop.longitude
                    )
                )
            else:
                from_stop_info = StopInfo(
                    uuid="start_point",
                    name="Punkt startowy",
                    coordinates=CoordinatePoint(latitude=start_lat, longitude=start_lon)
                )

            if hasattr(step.to_stop, 'uuid'):
                to_stop_info = StopInfo(
                    uuid=str(step.to_stop.uuid),
                    name=step.to_stop.short_name,
                    coordinates=CoordinatePoint(
                        latitude=step.to_stop.latitude,
                        longitude=step.to_stop.longitude
                    )
                )
            else:
                to_stop_info = StopInfo(
                    uuid="end_point",
                    name="Punkt docelowy",
                    coordinates=CoordinatePoint(latitude=end_lat, longitude=end_lon)
                )

            # Oblicz czas trwania
            duration = (step.arrival_time - step.depart_time).total_seconds() / 60

            # Informacje o pojeździe i opóźnieniu
            vehicle_info = None
            delay_info = None

            if step.is_walking:
                segment_type = "walking"
                walking_segments += 1
                total_walking_time += duration
                total_walking_distance += step.walking_distance_m
            else:
                segment_type = "transit"
                transit_segments += 1

                # Informacje o pojeździe
                vehicle = db.get_vehicle(step.vehicle_uuid)
                trip = db.trips[step.trip_uuid]

                vehicle_info = VehicleInfo(
                    uuid=str(vehicle.uuid),
                    license_plate=vehicle.license_plate,
                    type=vehicle.type.name,
                    line_number=trip.route.line_number,
                    destination=trip.route.destination,
                    capacity=vehicle.capacity,
                    owner=vehicle.owner
                )

                # Sprawdź przesiadki
                if prev_vehicle and prev_vehicle != step.vehicle_uuid and i > 0:
                    if not route_steps[i - 1].is_walking:
                        transfer_count += 1
                        wait_time = (step.depart_time - route_steps[i - 1].arrival_time).total_seconds() / 60
                        total_wait_time += wait_time

                # Informacje o opóźnieniu
                if step.delay_info and step.delay_info['has_delay']:
                    delay_minutes = step.delay_info['delay_minutes']
                    total_delay_time += delay_minutes

                    delay_info = DelayInfo(
                        has_delay=True,
                        delay_minutes=delay_minutes,
                        delay_reason=step.delay_info['delay_reason'],
                        delay_source=step.delay_info['delay_source']
                    )

                prev_vehicle = step.vehicle_uuid

            # Utwórz segment trasy
            segment = RouteSegment(
                segment_id=i + 1,
                type=segment_type,
                from_stop=from_stop_info,
                to_stop=to_stop_info,
                departure_timestamp=int(step.depart_time.timestamp()),
                arrival_timestamp=int(step.arrival_time.timestamp()),
                duration_minutes=round(duration, 1),
                walking_distance_meters=step.walking_distance_m if step.is_walking else None,
                vehicle=vehicle_info,
                delay=delay_info
            )

            route_segments.append(segment)

        # Podsumowanie trasy
        total_time = (route_steps[-1].arrival_time - route_steps[0].depart_time).total_seconds() / 60

        summary = RouteSummary(
            total_duration_minutes=round(total_time, 1),
            total_walking_time_minutes=round(total_walking_time, 1),
            total_walking_distance_meters=total_walking_distance,
            total_wait_time_minutes=round(total_wait_time, 1),
            total_delay_time_minutes=round(total_delay_time, 1),
            number_of_transfers=transfer_count,
            departure_timestamp=int(route_steps[0].depart_time.timestamp()),
            arrival_timestamp=int(route_steps[-1].arrival_time.timestamp()),
            segments_count=len(route_segments),
            walking_segments_count=walking_segments,
            transit_segments_count=transit_segments
        )

        # Rekomendacje
        recommendations = []
        if total_delay_time > 5:
            recommendations.append("Trasa zawiera znaczące opóźnienia - rozważ alternatywny czas podróży")
        if transfer_count == 0:
            recommendations.append("Bezpośrednia trasa bez przesiadek")
        elif transfer_count > 2:
            recommendations.append("Trasa wymaga wielu przesiadek - sprawdź alternatywne połączenia")
        if total_walking_distance > 1000:
            recommendations.append("Trasa zawiera dłuższe odcinki pieszo")

        # Tworzenie szczegółowej geometrii trasy
        print("Tworzenie szczegółowej geometrii trasy...")
        try:
            detailed_coords = create_detailed_route_geometry(route_segments)
            # Konwertuj na format [[lat, lon], [lat, lon], ...]
            detailed_geometry = [[coord[0], coord[1]] for coord in detailed_coords]
        except Exception as e:
            print(f"Błąd podczas tworzenia szczegółowej geometrii: {e}")
            # Fallback - tylko punkty przystanków
            detailed_geometry = []
            for segment in route_segments:
                detailed_geometry.append([
                    segment.from_stop.coordinates.latitude,
                    segment.from_stop.coordinates.longitude
                ])
            # Dodaj ostatni punkt
            if route_segments:
                last_segment = route_segments[-1]
                detailed_geometry.append([
                    last_segment.to_stop.coordinates.latitude,
                    last_segment.to_stop.coordinates.longitude
                ])

        return RouteResponse(
            success=True,
            message=f"Znaleziono optymalną trasę z {transfer_count} przesiadkami w czasie {total_time:.1f} minut",
            request_info=request_info,
            route_segments=route_segments,
            summary=summary,
            detailed_geometry=detailed_geometry,
            alternative_routes_available=transfer_count > 0,
            recommendations=recommendations if recommendations else ["Optymalna trasa bez uwag"]
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Błąd podczas planowania trasy: {str(e)}")

