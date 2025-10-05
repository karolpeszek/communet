import json
import os
from datetime import datetime, timedelta, time
from typing import List, Dict, Optional
from pydantic import BaseModel
from enum import Enum
import uuid as uuid_module
from algo import find_fastest_route
from db_setup import db


class DayOfWeek(Enum):
    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2
    THURSDAY = 3
    FRIDAY = 4
    SATURDAY = 5
    SUNDAY = 6


class RecurringRoute(BaseModel):
    id: str
    name: str
    description: str

    # Lokalizacje
    start_lat: float
    start_lon: float
    start_name: str
    end_lat: float
    end_lon: float
    end_name: str

    # Harmonogram
    days_of_week: List[int]  # 0-6 (poniedziałek-niedziela)
    departure_time: str  # Format: "HH:MM"
    target_arrival_time: str  # Format: "HH:MM"

    # Bazowe informacje o trasie
    normal_duration_minutes: float
    normal_route_segments: List[dict]  # Zapisana bazowa trasa

    # Ustawienia monitorowania
    delay_threshold_minutes: float = 5.0  # Próg opóźnienia do powiadomienia
    advance_departure_buffer_minutes: float = 10.0  # Bufor na wcześniejszy wyjazd

    # Metadane
    created_at: str
    last_checked: Optional[str] = None
    is_active: bool = True


class RouteAlternative(BaseModel):
    original_duration: float
    new_duration: float
    delay_minutes: float
    suggested_departure_time: str
    route_segments: List[dict]
    recommendations: List[str]


class RecurringRouteManager:
    def __init__(self, json_file_path: str = "recurring_routes.json"):
        self.json_file_path = json_file_path
        self.routes: Dict[str, RecurringRoute] = {}
        self.load_routes()

    def load_routes(self):
        """Ładuje trasy z pliku JSON"""
        if os.path.exists(self.json_file_path):
            try:
                with open(self.json_file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for route_data in data.get('routes', []):
                        route = RecurringRoute(**route_data)
                        self.routes[route.id] = route
                print(f"📚 Załadowano {len(self.routes)} tras cyklicznych")
            except Exception as e:
                print(f"❌ Błąd podczas ładowania tras: {e}")
                self.routes = {}
        else:
            print("📄 Brak pliku tras cyklicznych - tworzę nowy")
            self.routes = {}

    def save_routes(self):
        """Zapisuje trasy do pliku JSON"""
        try:
            data = {
                'routes': [route.dict() for route in self.routes.values()],
                'last_updated': datetime.now().isoformat()
            }
            with open(self.json_file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"💾 Zapisano {len(self.routes)} tras cyklicznych")
        except Exception as e:
            print(f"❌ Błąd podczas zapisywania tras: {e}")

    def add_route(self, route: RecurringRoute) -> str:
        """Dodaje nową trasę cykliczną"""
        if not route.id:
            route.id = str(uuid_module.uuid4())

        route.created_at = datetime.now().isoformat()
        self.routes[route.id] = route
        self.save_routes()
        print(f"➕ Dodano nową trasę cykliczną: {route.name}")
        return route.id

    def get_active_routes_for_today(self) -> List[RecurringRoute]:
        """Zwraca aktywne trasy dla dzisiejszego dnia tygodnia"""
        today = datetime.now().weekday()
        active_routes = []

        for route in self.routes.values():
            if route.is_active and today in route.days_of_week:
                active_routes.append(route)

        return active_routes

    def check_route_delays(self, route: RecurringRoute) -> Optional[RouteAlternative]:
        """Sprawdza czy trasa ma opóźnienia i sugeruje alternatywy"""
        print(f"\n🔍 Sprawdzam trasę: {route.name}")

        # Oblicz czas odjazdu na dzisiaj
        now = datetime.now()
        departure_time_obj = datetime.strptime(route.departure_time, "%H:%M").time()
        departure_datetime = datetime.combine(now.date(), departure_time_obj)

        # Jeśli czas już minął, sprawdź na jutro
        if departure_datetime < now:
            departure_datetime += timedelta(days=1)

        # Znajdź aktualną trasę z uwzględnieniem opóźnień
        current_route = find_fastest_route(
            database=db,
            start_lat=route.start_lat,
            start_lon=route.start_lon,
            end_lat=route.end_lat,
            end_lon=route.end_lon,
            departure_time=departure_datetime
        )

        if not current_route:
            print(f"❌ Nie znaleziono trasy dla {route.name}")
            return None

        # Oblicz aktualny czas trasy
        current_duration = (current_route[-1].arrival_time - current_route[0].depart_time).total_seconds() / 60

        # Sprawdź czy jest opóźnienie
        delay_minutes = current_duration - route.normal_duration_minutes

        if delay_minutes > route.delay_threshold_minutes:
            print(f"⚠️ OPÓŹNIENIE WYKRYTE!")
            print(f"   Normalna trasa: {route.normal_duration_minutes:.1f} min")
            print(f"   Aktualna trasa: {current_duration:.1f} min")
            print(f"   Opóźnienie: +{delay_minutes:.1f} min")

            # Oblicz sugerowany czas wyjazdu
            target_arrival = datetime.strptime(route.target_arrival_time, "%H:%M").time()
            target_arrival_datetime = datetime.combine(departure_datetime.date(), target_arrival)

            # Odejmij aktualny czas trasy i bufor
            suggested_departure = target_arrival_datetime - timedelta(
                minutes=current_duration + route.advance_departure_buffer_minutes
            )

            # Konwertuj segmenty trasy na format słownikowy
            route_segments = []
            for i, step in enumerate(current_route):
                segment_data = {
                    "segment_id": i + 1,
                    "type": "walking" if step.is_walking else "transit",
                    "from_stop": {
                        "name": step.from_stop.short_name if hasattr(step.from_stop, 'short_name') else "Start",
                        "coordinates": {
                            "latitude": step.from_stop.latitude,
                            "longitude": step.from_stop.longitude
                        }
                    },
                    "to_stop": {
                        "name": step.to_stop.short_name if hasattr(step.to_stop, 'short_name') else "Cel",
                        "coordinates": {
                            "latitude": step.to_stop.latitude,
                            "longitude": step.to_stop.longitude
                        }
                    },
                    "departure_time": step.depart_time.strftime("%H:%M:%S"),
                    "arrival_time": step.arrival_time.strftime("%H:%M:%S"),
                    "duration_minutes": (step.arrival_time - step.depart_time).total_seconds() / 60
                }

                if step.delay_info and step.delay_info.get('has_delay'):
                    segment_data["delay"] = step.delay_info

                route_segments.append(segment_data)

            recommendations = [
                f"Wyjdź wcześniej o {delay_minutes:.1f} min",
                f"Sugerowany czas wyjazdu: {suggested_departure.strftime('%H:%M')}",
                "Monitoruj sytuację komunikacyjną"
            ]

            if delay_minutes > 15:
                recommendations.append("Rozważ alternatywny środek transportu")

            alternative = RouteAlternative(
                original_duration=route.normal_duration_minutes,
                new_duration=current_duration,
                delay_minutes=delay_minutes,
                suggested_departure_time=suggested_departure.strftime("%H:%M"),
                route_segments=route_segments,
                recommendations=recommendations
            )

            # Aktualizuj czas ostatniego sprawdzenia
            route.last_checked = datetime.now().isoformat()
            self.save_routes()

            return alternative

        else:
            print(f"✅ Trasa bez opóźnień (różnica: {delay_minutes:.1f} min)")
            route.last_checked = datetime.now().isoformat()
            self.save_routes()
            return None

    def check_all_routes_for_delays(self) -> Dict[str, RouteAlternative]:
        """Sprawdza wszystkie aktywne trasy na dzisiaj pod kątem opóźnień"""
        print("\n" + "=" * 60)
        print("🚦 SPRAWDZANIE TRAS CYKLICZNYCH")
        print("=" * 60)

        today_routes = self.get_active_routes_for_today()
        alternatives = {}

        if not today_routes:
            print("📅 Brak aktywnych tras na dzisiaj")
            return alternatives

        print(f"📋 Sprawdzam {len(today_routes)} tras na dzisiaj...")

        for route in today_routes:
            alternative = self.check_route_delays(route)
            if alternative:
                alternatives[route.id] = alternative
                print(f"🚨 Wysyłam powiadomienie o opóźnieniu dla trasy: {route.name}")

        return alternatives


# Globalna instancja managera tras
route_manager = RecurringRouteManager()


def on_delay_report_received():
    """Funkcja wywoływana po otrzymaniu raportu o opóźnieniu"""
    print("\n🚨 Otrzymano raport o opóźnieniu - sprawdzam trasy cykliczne...")
    alternatives = route_manager.check_all_routes_for_delays()

    if alternatives:
        print(f"\n📢 Znaleziono {len(alternatives)} tras z opóźnieniami!")
        for route_id, alternative in alternatives.items():
            route = route_manager.routes[route_id]
            print(f"\n📍 Trasa: {route.name}")
            print(f"⏰ Opóźnienie: +{alternative.delay_minutes:.1f} min")
            print(f"🕐 Sugerowany wyjazd: {alternative.suggested_departure_time}")
            print(f"💡 Rekomendacje: {', '.join(alternative.recommendations)}")
    else:
        print("✅ Wszystkie trasy bez znaczących opóźnień")

    return alternatives
