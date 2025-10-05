# API Dokumentacja - Endpoint Planowania Trasy

## Endpoint: GET `/api/v1/plan_route`

Planuje optymalną trasę komunikacji publicznej między dwoma punktami geograficznymi z uwzględnieniem opóźnień.

### Parametry żądania (Query Parameters)

| Parametr | Typ | Opis | Wymagany | Przykład |
|----------|-----|------|----------|----------|
| `start_lat` | float | Szerokość geograficzna punktu startowego (-90 do 90) | Tak | 50.016 |
| `start_lon` | float | Długość geograficzna punktu startowego (-180 do 180) | Tak | 19.907 |
| `end_lat` | float | Szerokość geograficzna punktu docelowego (-90 do 90) | Tak | 50.067 |
| `end_lon` | float | Długość geograficzna punktu docelowego (-180 do 180) | Tak | 19.990 |
| `hour` | int | Godzina odjazdu (0-23) | Tak | 14 |
| `minute` | int | Minuta odjazdu (0-59) | Tak | 30 |
| `date` | string | Data w formacie YYYY-MM-DD | Nie | "2024-01-15" |

### Przykład żądania

```http
GET /api/v1/plan_route?start_lat=50.016&start_lon=19.907&end_lat=50.067&end_lon=19.990&hour=14&minute=30&date=2024-01-15
```

### Struktura odpowiedzi JSON

```json
{
  "success": true,
  "message": "Znaleziono optymalną trasę z 1 przesiadkami w czasie 42.5 minut",
  "request_info": {
    "start_coordinates": {
      "latitude": 50.016,
      "longitude": 19.907
    },
    "end_coordinates": {
      "latitude": 50.067,
      "longitude": 19.990
    },
    "departure_timestamp": 1705318200,
    "processing_timestamp": 1705311600
  },
  "route_segments": [
    {
      "segment_id": 1,
      "type": "transit",
      "from_stop": {
        "uuid": "abc123-def456-ghi789",
        "name": "Czerwone Maki P+R",
        "coordinates": {
          "latitude": 50.016,
          "longitude": 19.907
        }
      },
      "to_stop": {
        "uuid": "xyz789-uvw456-rst123",
        "name": "Kampus UJ",
        "coordinates": {
          "latitude": 50.026,
          "longitude": 19.912
        }
      },
      "departure_timestamp": 1705318320,
      "arrival_timestamp": 1705318450,
      "duration_minutes": 2.2,
      "walking_distance_meters": null,
      "vehicle": {
        "uuid": "vehicle-123-456",
        "license_plate": "#RZ201",
        "type": "TRAM",
        "line_number": 18,
        "destination": "Krowodrza Górka",
        "capacity": 220,
        "owner": "MPK Kraków"
      },
      "delay": {
        "has_delay": true,
        "delay_minutes": 3.5,
        "delay_reason": "TRAFFIC_JAM",
        "delay_source": "odcinek Czerwone Maki P+R → Kampus UJ"
      }
    },
    {
      "segment_id": 2,
      "type": "walking",
      "from_stop": {
        "uuid": "xyz789-uvw456-rst123",
        "name": "Kampus UJ",
        "coordinates": {
          "latitude": 50.026,
          "longitude": 19.912
        }
      },
      "to_stop": {
        "uuid": "end_point",
        "name": "Punkt docelowy",
        "coordinates": {
          "latitude": 50.067,
          "longitude": 19.990
        }
      },
      "departure_timestamp": 1705318450,
      "arrival_timestamp": 1705318920,
      "duration_minutes": 7.8,
      "walking_distance_meters": 650,
      "vehicle": null,
      "delay": null
    }
  ],
  "summary": {
    "total_duration_minutes": 42.5,
    "total_walking_time_minutes": 15.2,
    "total_walking_distance_meters": 1200,
    "total_wait_time_minutes": 5.5,
    "total_delay_time_minutes": 8.3,
    "number_of_transfers": 1,
    "departure_timestamp": 1705318200,
    "arrival_timestamp": 1705320750,
    "segments_count": 2,
    "walking_segments_count": 1,
    "transit_segments_count": 1
  },
  "alternative_routes_available": true,
  "recommendations": [
    "Trasa zawiera znaczące opóźnienia - rozważ alternatywny czas podróży",
    "Trasa zawiera dłuższe odcinki pieszo"
  ]
}
```

## Szczegółowy opis pól

### RouteSegment
Reprezentuje jeden etap podróży (przejazd lub spacer).

| Pole | Typ | Opis |
|------|-----|------|
| `segment_id` | int | Kolejny numer segmentu w trasie |
| `type` | string | Typ segmentu: "walking" lub "transit" |
| `from_stop` | StopInfo | Informacje o punkcie wyjścia |
| `to_stop` | StopInfo | Informacje o punkcie docelowym |
| `departure_timestamp` | int | Unix timestamp rozpoczęcia (sekundy od 1970-01-01) |
| `arrival_timestamp` | int | Unix timestamp zakończenia (sekundy od 1970-01-01) |
| `duration_minutes` | float | Czas trwania w minutach |
| `walking_distance_meters` | int\|null | Dystans spaceru w metrach (tylko dla type="walking") |
| `vehicle` | VehicleInfo\|null | Informacje o pojeździe (tylko dla type="transit") |
| `delay` | DelayInfo\|null | Informacje o opóźnieniu (jeśli występuje) |

### StopInfo
Informacje o przystanku lub punkcie.

| Pole | Typ | Opis |
|------|-----|------|
| `uuid` | string | Unikalny identyfikator |
| `name` | string | Nazwa przystanku |
| `coordinates` | CoordinatePoint | Współrzędne geograficzne |

### VehicleInfo
Szczegółowe informacje o pojeździe komunikacji publicznej.

| Pole | Typ | Opis |
|------|-----|------|
| `uuid` | string | Unikalny identyfikator pojazdu |
| `license_plate` | string | Numer rejestracyjny |
| `type` | string | Typ pojazdu ("TRAM", "BUS", "TRAIN") |
| `line_number` | int | Numer linii |
| `destination` | string | Kierunek docelowy |
| `capacity` | int | Pojemność pojazdu (liczba pasażerów) |
| `owner` | string | Operator (np. "MPK Kraków") |

### DelayInfo
Informacje o opóźnieniach na trasie.

| Pole | Typ | Opis |
|------|-----|------|
| `has_delay` | boolean | Czy występuje opóźnienie |
| `delay_minutes` | float | Wielkość opóźnienia w minutach |
| `delay_reason` | string | Przyczyna: "TRAFFIC_JAM", "ROAD_ACCIDENT", "SEVERE_WEATHER", "VEHICLE_ISSUE" |
| `delay_source` | string | Źródło opóźnienia (pojazd lub odcinek trasy) |

### RouteSummary
Podsumowanie całej trasy.

| Pole | Typ | Opis |
|------|-----|------|
| `total_duration_minutes` | float | Całkowity czas podróży |
| `total_walking_time_minutes` | float | Sumaryczny czas spaceru |
| `total_walking_distance_meters` | int | Całkowity dystans spaceru |
| `total_wait_time_minutes` | float | Czas oczekiwania na przesiadkach |
| `total_delay_time_minutes` | float | Całkowity czas opóźnień |
| `number_of_transfers` | int | Liczba przesiadek |
| `departure_timestamp` | int | Unix timestamp rzeczywistego odjazdu |
| `arrival_timestamp` | int | Unix timestamp przewidywanego przyjazdu |
| `segments_count` | int | Całkowita liczba segmentów |
| `walking_segments_count` | int | Liczba segmentów spacerowych |
| `transit_segments_count` | int | Liczba segmentów komunikacji publicznej |

## Format czasu - Unix Timestamp

Wszystkie czasy są zwracane jako **Unix timestamp** (liczba sekund od 1 stycznia 1970 UTC).

### Konwersja timestamp w różnych językach:

#### JavaScript
```javascript
// Konwersja timestamp na Date
const date = new Date(timestamp * 1000);

// Formatowanie
const time = date.toLocaleTimeString('pl-PL');
const dateStr = date.toLocaleDateString('pl-PL');

// Przykład
const departureTime = new Date(1705318200 * 1000);
console.log(departureTime.toLocaleString('pl-PL')); // "15.01.2024, 14:30:00"
```

#### Python
```python
from datetime import datetime

# Konwersja timestamp na datetime
dt = datetime.fromtimestamp(timestamp)

# Formatowanie
time_str = dt.strftime('%H:%M:%S')
date_str = dt.strftime('%Y-%m-%d')

# Przykład
departure_time = datetime.fromtimestamp(1705318200)
print(departure_time.strftime('%Y-%m-%d %H:%M:%S'))  # "2024-01-15 14:30:00"
```

#### Java
```java
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneId;

// Konwersja timestamp na LocalDateTime
LocalDateTime dateTime = LocalDateTime.ofInstant(
    Instant.ofEpochSecond(timestamp), 
    ZoneId.systemDefault()
);

// Przykład
LocalDateTime departureTime = LocalDateTime.ofInstant(
    Instant.ofEpochSecond(1705318200L), 
    ZoneId.systemDefault()
);
```

## Przykłady użycia

### JavaScript/Fetch z konwersją czasu
```javascript
const response = await fetch(
  '/api/v1/plan_route?start_lat=50.016&start_lon=19.907&end_lat=50.067&end_lon=19.990&hour=14&minute=30'
);
const route = await response.json();

if (route.success) {
  // Konwersja timestampów
  const departureTime = new Date(route.summary.departure_timestamp * 1000);
  const arrivalTime = new Date(route.summary.arrival_timestamp * 1000);
  
  console.log(`Odjazd: ${departureTime.toLocaleTimeString('pl-PL')}`);
  console.log(`Przyjazd: ${arrivalTime.toLocaleTimeString('pl-PL')}`);
  console.log(`Czas podróży: ${route.summary.total_duration_minutes} minut`);
  
  route.route_segments.forEach((segment, index) => {
    const segmentStart = new Date(segment.departure_timestamp * 1000);
    const segmentEnd = new Date(segment.arrival_timestamp * 1000);
    
    console.log(`${index + 1}. ${segment.type} ${segmentStart.toLocaleTimeString()} - ${segmentEnd.toLocaleTimeString()}`);
  });
}
```

### Python/Requests z konwersją czasu
```python
import requests
from datetime import datetime

params = {
    'start_lat': 50.016,
    'start_lon': 19.907,
    'end_lat': 50.067,
    'end_lon': 19.990,
    'hour': 14,
    'minute': 30
}

response = requests.get('/api/v1/plan_route', params=params)
route = response.json()

if route['success']:
    # Konwersja timestampów
    departure_time = datetime.fromtimestamp(route['summary']['departure_timestamp'])
    arrival_time = datetime.fromtimestamp(route['summary']['arrival_timestamp'])
    
    print(f"Odjazd: {departure_time.strftime('%H:%M:%S')}")
    print(f"Przyjazd: {arrival_time.strftime('%H:%M:%S')}")
    print(f"Czas podróży: {route['summary']['total_duration_minutes']} minut")
    
    for segment in route['route_segments']:
        segment_start = datetime.fromtimestamp(segment['departure_timestamp'])
        segment_end = datetime.fromtimestamp(segment['arrival_timestamp'])
        print(f"{segment['segment_id']}. {segment['type']} {segment_start.strftime('%H:%M')} - {segment_end.strftime('%H:%M')}")
```

## Zalety Unix Timestamp

1. **Uniwersalność** - Jednakowy format niezależnie od strefy czasowej
2. **Łatwość obliczeń** - Różnica między timestampami to czas w sekundach
3. **Kompatybilność** - Wspierany przez wszystkie języki programowania
4. **Wydajność** - Mniej miejsca niż stringi, szybsze porównania
5. **Precyzja** - Dokładność do sekundy

## Uwagi implementacyjne

- Wszystkie timestampy są w UTC (serwer automatycznie konwertuje)
- Frontend powinien konwertować na lokalną strefę czasową użytkownika
- API zwraca timestampy jako integer (sekundy, nie milisekundy)
- Do obliczeń różnic czasu używaj bezpośrednio timestampów
