from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from enum import Enum
from datetime import datetime, time

# Dodaj importy z algo i plan_route
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from algo import find_fastest_route
from db_setup import db
from backend.plan_route import RouteResponse, RouteSegment, RouteSummary, StopInfo, VehicleInfo, DelayInfo
from backend.create_lines import create_detailed_route_geometry

router = APIRouter()


# Modele danych
class RecurringFrequency(str, Enum):
    DAILY = "daily"
    WEEKDAYS = "weekdays"  # Poniedziałek-Piątek
    WEEKENDS = "weekends"  # Sobota-Niedziela
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


class CoordinatePoint(BaseModel):
    latitude: float
    longitude: float


class RecurringRouteBasic(BaseModel):
    id: str
    name: str
    from_location_name: str
    to_location_name: str
    departure_time: str  # Format: "HH:MM"
    frequency: RecurringFrequency
    is_active: bool
    average_duration_minutes: float


class RouteStatistics(BaseModel):
    total_trips: int
    on_time_percentage: float
    average_delay_minutes: float
    most_common_delay_reason: Optional[str]


class RecurringRouteDetail(BaseModel):
    id: str
    name: str
    description: Optional[str]

    # Lokalizacje
    from_location_name: str
    from_coordinates: CoordinatePoint
    to_location_name: str
    to_coordinates: CoordinatePoint

    # Harmonogram
    departure_time: str  # Format: "HH:MM"
    frequency: RecurringFrequency
    is_active: bool

    # Szczegóły trasy
    average_duration_minutes: float
    average_walking_time_minutes: float
    average_walking_distance_meters: int
    typical_transfers: int

    # Statystyki
    statistics: RouteStatistics

    # Rekomendacje
    best_departure_time: str  # Sugerowany najlepszy czas odjazdu
    alternative_times: List[str]  # Alternatywne czasy
    tips: List[str]  # Wskazówki dla użytkownika


class RecurringRoutesListResponse(BaseModel):
    success: bool
    total_routes: int
    active_routes: int
    routes: List[RecurringRouteBasic]


class RecurringRouteDetailResponse(BaseModel):
    success: bool
    route: RecurringRouteDetail


# Hardcoded dane - regularne przejazdy
RECURRING_ROUTES = {
    "work_morning": {
        "id": "work_morning",
        "name": "Do pracy - poranek",
        "description": "Codzienna trasa do pracy o godzinie 9:00",
        "from_location_name": "Dom - ul. Krakowska 50",
        "from_coordinates": {"latitude": 50.0632, "longitude": 19.9380},
        "to_location_name": "Praca - Rondo Mogilskie",
        "to_coordinates": {"latitude": 50.0697, "longitude": 19.9530},
        "departure_time": "09:00",
        "frequency": RecurringFrequency.WEEKDAYS,
        "is_active": True,
        "average_duration_minutes": 25.5,
        "average_walking_time_minutes": 8.0,
        "average_walking_distance_meters": 650,
        "typical_transfers": 1,
        "statistics": {
            "total_trips": 143,
            "on_time_percentage": 87.4,
            "average_delay_minutes": 3.2,
            "most_common_delay_reason": "Duże natężenie ruchu"
        },
        "best_departure_time": "08:55",
        "alternative_times": ["08:45", "08:50", "09:05"],
        "tips": [
            "Tramwaj o 9:00 zazwyczaj jest zatłoczony - rozważ wyjazd 5 minut wcześniej",
            "W piątki średnie opóźnienie wynosi 5 minut",
            "Alternatywna trasa przez Dworzec Główny zajmuje 3 minuty dłużej, ale ma mniej przesiadek"
        ]
    },
    "work_evening": {
        "id": "work_evening",
        "name": "Z pracy - wieczór",
        "description": "Powrót z pracy do domu o godzinie 17:30",
        "from_location_name": "Praca - Rondo Mogilskie",
        "from_coordinates": {"latitude": 50.0697, "longitude": 19.9530},
        "to_location_name": "Dom - ul. Krakowska 50",
        "to_coordinates": {"latitude": 50.0632, "longitude": 19.9380},
        "departure_time": "17:30",
        "frequency": RecurringFrequency.WEEKDAYS,
        "is_active": True,
        "average_duration_minutes": 32.0,
        "average_walking_time_minutes": 9.5,
        "average_walking_distance_meters": 720,
        "typical_transfers": 1,
        "statistics": {
            "total_trips": 138,
            "on_time_percentage": 72.1,
            "average_delay_minutes": 6.8,
            "most_common_delay_reason": "Godziny szczytu"
        },
        "best_departure_time": "17:45",
        "alternative_times": ["17:15", "17:40", "18:00"],
        "tips": [
            "Godziny szczytu - rozważ wyjazd o 17:45, aby uniknąć tłoku",
            "Linia 50 jest mniej zatłoczona niż linia 4",
            "Średnie opóźnienie w godzinach 17:00-18:00 wynosi 8 minut"
        ]
    },
    "gym_evening": {
        "id": "gym_evening",
        "name": "Na siłownię - wieczór",
        "description": "Do siłowni we wtorki i czwartki",
        "from_location_name": "Dom - ul. Krakowska 50",
        "from_coordinates": {"latitude": 50.0632, "longitude": 19.9380},
        "to_location_name": "Siłownia - Galeria Krakowska",
        "to_coordinates": {"latitude": 50.0679, "longitude": 19.9467},
        "departure_time": "18:30",
        "frequency": RecurringFrequency.TUESDAY,  # W rzeczywistości wtorek i czwartek, ale dla uproszczenia
        "is_active": True,
        "average_duration_minutes": 18.0,
        "average_walking_time_minutes": 5.5,
        "average_walking_distance_meters": 420,
        "typical_transfers": 0,
        "statistics": {
            "total_trips": 34,
            "on_time_percentage": 91.2,
            "average_delay_minutes": 2.1,
            "most_common_delay_reason": "Brak opóźnień"
        },
        "best_departure_time": "18:30",
        "alternative_times": ["18:20", "18:35", "18:45"],
        "tips": [
            "Bezpośrednie połączenie tramwajem linii 4",
            "Trasa zazwyczaj bez opóźnień",
            "Pamiętaj o karcie wstępu na siłownię"
        ]
    },
    "weekend_shopping": {
        "id": "weekend_shopping",
        "name": "Zakupy weekendowe",
        "description": "Sobotnie zakupy w centrum handlowym",
        "from_location_name": "Dom - ul. Krakowska 50",
        "from_coordinates": {"latitude": 50.0632, "longitude": 19.9380},
        "to_location_name": "Bonarka City Center",
        "to_coordinates": {"latitude": 50.0344, "longitude": 19.9532},
        "departure_time": "11:00",
        "frequency": RecurringFrequency.SATURDAY,
        "is_active": True,
        "average_duration_minutes": 28.5,
        "average_walking_time_minutes": 7.0,
        "average_walking_distance_meters": 550,
        "typical_transfers": 1,
        "statistics": {
            "total_trips": 23,
            "on_time_percentage": 95.7,
            "average_delay_minutes": 1.3,
            "most_common_delay_reason": "Brak opóźnień"
        },
        "best_departure_time": "11:00",
        "alternative_times": ["10:45", "11:15", "11:30"],
        "tips": [
            "W weekendy komunikacja jeździ rzadziej",
            "Centrum handlowe otwarte do 21:00",
            "Powrót: ostatni autobus o 20:45"
        ]
    },
    "parents_sunday": {
        "id": "parents_sunday",
        "name": "Do rodziców - niedziela",
        "description": "Niedzielny obiad u rodziców",
        "from_location_name": "Dom - ul. Krakowska 50",
        "from_coordinates": {"latitude": 50.0632, "longitude": 19.9380},
        "to_location_name": "Nowa Huta - os. Teatralne",
        "to_coordinates": {"latitude": 50.0715, "longitude": 20.0328},
        "departure_time": "13:00",
        "frequency": RecurringFrequency.SUNDAY,
        "is_active": True,
        "average_duration_minutes": 42.0,
        "average_walking_time_minutes": 12.0,
        "average_walking_distance_meters": 950,
        "typical_transfers": 2,
        "statistics": {
            "total_trips": 18,
            "on_time_percentage": 88.9,
            "average_delay_minutes": 4.5,
            "most_common_delay_reason": "Remonty torów"
        },
        "best_departure_time": "12:50",
        "alternative_times": ["12:40", "13:10", "13:20"],
        "tips": [
            "W niedziele autobusy jeżdżą co 15-20 minut",
            "Trasa wymaga dwóch przesiadek",
            "Zabierz ciasto od rodziców na powrót :)"
        ]
    }
}


@router.get("/api/v1/recurring-routes", response_model=RecurringRoutesListResponse)
def get_recurring_routes(
        active_only: bool = False,
        frequency: Optional[RecurringFrequency] = None
):
    """
    Pobiera listę wszystkich regularnych tras użytkownika.

    **Parametry query:**
    - active_only: Czy zwrócić tylko aktywne trasy (domyślnie: false)
    - frequency: Filtruj po częstotliwości (opcjonalne)

    **Zwraca:**
    - Listę podstawowych informacji o regularnych trasach

    **Przykład:**
    ```
    GET /api/v1/recurring-routes
    GET /api/v1/recurring-routes?active_only=true
    GET /api/v1/recurring-routes?frequency=weekdays
    ```
    """
    try:
        routes_list = []

        for route_id, route_data in RECURRING_ROUTES.items():
            # Filtrowanie po aktywności
            if active_only and not route_data["is_active"]:
                continue

            # Filtrowanie po częstotliwości
            if frequency and route_data["frequency"] != frequency:
                continue

            route_basic = RecurringRouteBasic(
                id=route_data["id"],
                name=route_data["name"],
                from_location_name=route_data["from_location_name"],
                to_location_name=route_data["to_location_name"],
                departure_time=route_data["departure_time"],
                frequency=route_data["frequency"],
                is_active=route_data["is_active"],
                average_duration_minutes=route_data["average_duration_minutes"]
            )
            routes_list.append(route_basic)

        # Sortuj po czasie odjazdu
        routes_list.sort(key=lambda x: x.departure_time)

        active_count = sum(1 for r in routes_list if r.is_active)

        return RecurringRoutesListResponse(
            success=True,
            total_routes=len(routes_list),
            active_routes=active_count,
            routes=routes_list
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Błąd podczas pobierania tras: {str(e)}")


@router.get("/api/v1/recurring-routes/{route_id}", response_model=RecurringRouteDetailResponse)
def get_recurring_route_detail(route_id: str):
    """
    Pobiera szczegółowe informacje o konkretnej regularnej trasie.

    **Parametry ścieżki:**
    - route_id: ID regularnej trasy

    **Zwraca:**
    - Szczegółowe informacje o trasie, statystyki, rekomendacje i wskazówki

    **Przykład:**
    ```
    GET /api/v1/recurring-routes/work_morning
    GET /api/v1/recurring-routes/gym_evening
    ```
    """
    try:
        if route_id not in RECURRING_ROUTES:
            raise HTTPException(
                status_code=404,
                detail=f"Nie znaleziono regularnej trasy o ID: {route_id}"
            )

        route_data = RECURRING_ROUTES[route_id]

        route_detail = RecurringRouteDetail(
            id=route_data["id"],
            name=route_data["name"],
            description=route_data["description"],
            from_location_name=route_data["from_location_name"],
            from_coordinates=CoordinatePoint(**route_data["from_coordinates"]),
            to_location_name=route_data["to_location_name"],
            to_coordinates=CoordinatePoint(**route_data["to_coordinates"]),
            departure_time=route_data["departure_time"],
            frequency=route_data["frequency"],
            is_active=route_data["is_active"],
            average_duration_minutes=route_data["average_duration_minutes"],
            average_walking_time_minutes=route_data["average_walking_time_minutes"],
            average_walking_distance_meters=route_data["average_walking_distance_meters"],
            typical_transfers=route_data["typical_transfers"],
            statistics=RouteStatistics(**route_data["statistics"]),
            best_departure_time=route_data["best_departure_time"],
            alternative_times=route_data["alternative_times"],
            tips=route_data["tips"]
        )

        return RecurringRouteDetailResponse(
            success=True,
            route=route_detail
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Błąd podczas pobierania szczegółów trasy: {str(e)}")


@router.get("/api/v1/recurring-routes/{route_id}/plan-now")
def plan_recurring_route_now(route_id: str):
    """
    Planuje regularną trasę na bieżący moment (lub najbliższy zaplanowany czas).

    **Parametry ścieżki:**
    - route_id: ID regularnej trasy

    **Zwraca:**
    - Informacje potrzebne do przekierowania na endpoint planowania trasy

    **Przykład:**
    ```
    GET /api/v1/recurring-routes/work_morning/plan-now
    ```
    """
    try:
        if route_id not in RECURRING_ROUTES:
            raise HTTPException(
                status_code=404,
                detail=f"Nie znaleziono regularnej trasy o ID: {route_id}"
            )

        route_data = RECURRING_ROUTES[route_id]

        # Aktualny timestamp
        now = datetime.now()
        current_timestamp = int(now.timestamp())

        # Parsuj zaplanowany czas odjazdu
        scheduled_time = datetime.strptime(route_data["departure_time"], "%H:%M").time()

        # Utwórz datetime na dziś z zaplanowanym czasem
        scheduled_datetime = datetime.combine(now.date(), scheduled_time)

        # Jeśli czas już minął, zaplanuj na jutro
        if scheduled_datetime < now:
            from datetime import timedelta
            scheduled_datetime += timedelta(days=1)

        scheduled_timestamp = int(scheduled_datetime.timestamp())

        return {
            "success": True,
            "route_id": route_id,
            "route_name": route_data["name"],
            "planning_parameters": {
                "start_lat": route_data["from_coordinates"]["latitude"],
                "start_lon": route_data["from_coordinates"]["longitude"],
                "end_lat": route_data["to_coordinates"]["latitude"],
                "end_lon": route_data["to_coordinates"]["longitude"],
                "timestamp": scheduled_timestamp
            },
            "scheduled_departure_time": route_data["departure_time"],
            "scheduled_timestamp": scheduled_timestamp,
            "current_timestamp": current_timestamp,
            "message": f"Użyj tych parametrów w /api/v1/plan_route aby zaplanować trasę",
            "api_call_example": f"/api/v1/plan_route?start_lat={route_data['from_coordinates']['latitude']}&start_lon={route_data['from_coordinates']['longitude']}&end_lat={route_data['to_coordinates']['latitude']}&end_lon={route_data['to_coordinates']['longitude']}&timestamp={scheduled_timestamp}"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Błąd podczas planowania trasy: {str(e)}")


@router.get("/api/v1/recurring-routes/{route_id}/calculate-route", response_model=RouteResponse)
def calculate_recurring_route(route_id: str, use_now: bool = False):
    """
    Oblicza optymalną trasę dla regularnego przejazdu używając algorytmu pathfinding.

    **Parametry ścieżki:**
    - route_id: ID regularnej trasy

    **Parametry query:**
    - use_now: Czy użyć aktualnego czasu zamiast zaplanowanego (domyślnie: false)

    **Zwraca:**
    - Pełną obliczoną trasę z segmentami, pojazdami, opóźnieniami i geometrią

    **Przykład:**
    ```
    GET /api/v1/recurring-routes/work_morning/calculate-route
    GET /api/v1/recurring-routes/work_morning/calculate-route?use_now=true
    ```
    """
    try:
        if route_id not in RECURRING_ROUTES:
            raise HTTPException(
                status_code=404,
                detail=f"Nie znaleziono regularnej trasy o ID: {route_id}"
            )

        route_data = RECURRING_ROUTES[route_id]

        # Określ czas odjazdu
        now = datetime.now()

        if use_now:
            departure_time = now
            timestamp = int(now.timestamp())
        else:
            # Użyj zaplanowanego czasu
            scheduled_time = datetime.strptime(route_data["departure_time"], "%H:%M").time()
            departure_time = datetime.combine(now.date(), scheduled_time)

            # Jeśli czas już minął, zaplanuj na jutro
            if departure_time < now:
                from datetime import timedelta
                departure_time += timedelta(days=1)

            timestamp = int(departure_time.timestamp())

        # Pobierz współrzędne
        start_lat = route_data["from_coordinates"]["latitude"]
        start_lon = route_data["from_coordinates"]["longitude"]
        end_lat = route_data["to_coordinates"]["latitude"]
        end_lon = route_data["to_coordinates"]["longitude"]

        # Informacje o żądaniu
        request_info = {
            "recurring_route_id": route_id,
            "recurring_route_name": route_data["name"],
            "start_coordinates": {"latitude": start_lat, "longitude": start_lon},
            "end_coordinates": {"latitude": end_lat, "longitude": end_lon},
            "departure_timestamp": timestamp,
            "processing_timestamp": int(now.timestamp()),
            "used_scheduled_time": not use_now,
            "scheduled_departure_time": route_data["departure_time"] if not use_now else None
        }

        # OBLICZ OPTYMALNĄ TRASĘ używając algo.py
        print(f"Obliczanie trasy dla {route_data['name']}...")
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
                message=f"Nie znaleziono trasy dla regularnego przejazdu '{route_data['name']}'",
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
                recommendations=[
                    "Nie znaleziono połączenia - sprawdź dostępność komunikacji",
                    f"Zwykle ta trasa zajmuje ~{route_data['average_duration_minutes']:.0f} min"
                ]
            )

        # Konwertuj kroki trasy na format API (ta sama logika co w plan_route.py)
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
                    name=route_data["from_location_name"],
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
                    name=route_data["to_location_name"],
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

        # Rekomendacje z porównaniem do statystyk
        recommendations = []

        # Porównaj z typową trasą
        time_diff = total_time - route_data["average_duration_minutes"]
        if time_diff > 5:
            recommendations.append(
                f"⚠️ Trasa dłuższa o {time_diff:.0f} min od zwykłej ({route_data['average_duration_minutes']:.0f} min)")
        elif time_diff < -5:
            recommendations.append(f"✅ Trasa krótsza o {abs(time_diff):.0f} min od zwykłej!")
        else:
            recommendations.append(f"✅ Typowy czas podróży (~{route_data['average_duration_minutes']:.0f} min)")

        if total_delay_time > 5:
            recommendations.append(f"⚠️ Wykryto opóźnienia: {total_delay_time:.0f} min")

        if transfer_count == 0:
            recommendations.append("✅ Bezpośrednie połączenie bez przesiadek")
        elif transfer_count != route_data["typical_transfers"]:
            recommendations.append(f"ℹ️ Przesiadki: {transfer_count} (zwykle: {route_data['typical_transfers']})")

        # Dodaj tips z konfiguracji trasy
        recommendations.extend(route_data["tips"][:2])  # Pierwsze 2 tipy

        # Tworzenie szczegółowej geometrii trasy
        print("Tworzenie szczegółowej geometrii trasy...")
        try:
            detailed_coords = create_detailed_route_geometry(route_segments)
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
            if route_segments:
                last_segment = route_segments[-1]
                detailed_geometry.append([
                    last_segment.to_stop.coordinates.latitude,
                    last_segment.to_stop.coordinates.longitude
                ])

        return RouteResponse(
            success=True,
            message=f"Obliczona trasa dla '{route_data['name']}' w czasie {total_time:.1f} min",
            request_info=request_info,
            route_segments=route_segments,
            summary=summary,
            detailed_geometry=detailed_geometry,
            alternative_routes_available=transfer_count > 0,
            recommendations=recommendations
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Błąd podczas obliczania trasy: {str(e)}")
