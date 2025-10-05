# API Dokumentacja - Regularne Przejazdy

## Spis treści
1. [Wprowadzenie](#wprowadzenie)
2. [Endpointy](#endpointy)
3. [Modele danych](#modele-danych)
4. [Przykłady użycia](#przykłady-użycia)
5. [Obsługa błędów](#obsługa-błędów)
6. [Integracja z frontendem](#integracja-z-frontendem)

---

## Wprowadzenie

API regularnych przejazdów umożliwia zarządzanie i planowanie cyklicznych tras komunikacji miejskiej. System zawiera 5 predefiniowanych tras:
- `work_morning` - Poranna trasa do pracy (dni robocze)
- `work_evening` - Powrót z pracy (dni robocze)
- `gym_evening` - Trasa na siłownię (wtorki)
- `weekend_shopping` - Zakupy weekendowe (soboty)
- `parents_sunday` - Wizyta u rodziców (niedziele)

---

## Endpointy

### 1. Lista wszystkich regularnych tras

**GET** `/api/v1/recurring-routes`

Pobiera listę wszystkich regularnych tras użytkownika z podstawowymi informacjami.

#### Parametry query (opcjonalne):
| Parametr | Typ | Opis | Przykład |
|----------|-----|------|----------|
| `active_only` | boolean | Tylko aktywne trasy | `?active_only=true` |
| `frequency` | string | Filtruj po częstotliwości | `?frequency=weekdays` |

#### Wartości dla `frequency`:
- `daily` - Codziennie
- `weekdays` - Dni robocze (Pon-Pt)
- `weekends` - Weekendy (Sob-Niedz)
- `monday`, `tuesday`, `wednesday`, `thursday`, `friday`, `saturday`, `sunday` - Konkretne dni

#### Odpowiedź:
```json
{
  "success": true,
  "total_routes": 5,
  "active_routes": 5,
  "routes": [
    {
      "id": "work_morning",
      "name": "Do pracy - poranek",
      "from_location_name": "Dom - ul. Krakowska 50",
      "to_location_name": "Praca - Rondo Mogilskie",
      "departure_time": "09:00",
      "frequency": "weekdays",
      "is_active": true,
      "average_duration_minutes": 25.5
    }
  ]
}
```

---

### 2. Szczegóły regularnej trasy

**GET** `/api/v1/recurring-routes/{route_id}`

Pobiera szczegółowe informacje o konkretnej regularnej trasie, w tym statystyki i rekomendacje.

#### Parametry ścieżki:
| Parametr | Typ | Opis | Wymagane |
|----------|-----|------|----------|
| `route_id` | string | ID trasy | Tak |

#### Przykłady:
```
GET /api/v1/recurring-routes/work_morning
GET /api/v1/recurring-routes/gym_evening
```

#### Odpowiedź:
```json
{
  "success": true,
  "route": {
    "id": "work_morning",
    "name": "Do pracy - poranek",
    "description": "Codzienna trasa do pracy o godzinie 9:00",
    "from_location_name": "Dom - ul. Krakowska 50",
    "from_coordinates": {
      "latitude": 50.0632,
      "longitude": 19.9380
    },
    "to_location_name": "Praca - Rondo Mogilskie",
    "to_coordinates": {
      "latitude": 50.0697,
      "longitude": 19.9530
    },
    "departure_time": "09:00",
    "frequency": "weekdays",
    "is_active": true,
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
      "W piątki średnie opóźnienie wynosi 5 minut"
    ]
  }
}
```

---

### 3. Parametry do planowania trasy

**GET** `/api/v1/recurring-routes/{route_id}/plan-now`

Zwraca parametry potrzebne do wywołania endpointa planowania trasy (`/api/v1/plan_route`).

#### Parametry ścieżki:
| Parametr | Typ | Opis | Wymagane |
|----------|-----|------|----------|
| `route_id` | string | ID trasy | Tak |

#### Odpowiedź:
```json
{
  "success": true,
  "route_id": "work_morning",
  "route_name": "Do pracy - poranek",
  "planning_parameters": {
    "start_lat": 50.0632,
    "start_lon": 19.9380,
    "end_lat": 50.0697,
    "end_lon": 19.9530,
    "timestamp": 1705395600
  },
  "scheduled_departure_time": "09:00",
  "scheduled_timestamp": 1705395600,
  "current_timestamp": 1705392000,
  "message": "Użyj tych parametrów w /api/v1/plan_route aby zaplanować trasę",
  "api_call_example": "/api/v1/plan_route?start_lat=50.0632&start_lon=19.9380&end_lat=50.0697&end_lon=19.9530&timestamp=1705395600"
}
```

---

### 4. Oblicz optymalną trasę (GŁÓWNY ENDPOINT) ⭐

**GET** `/api/v1/recurring-routes/{route_id}/calculate-route`

**To jest główny endpoint do użycia!** Bezpośrednio oblicza optymalną trasę używając algorytmu pathfinding i zwraca pełne szczegóły z segmentami, pojazdami, opóźnieniami i geometrią.

#### Parametry ścieżki:
| Parametr | Typ | Opis | Wymagane |
|----------|-----|------|----------|
| `route_id` | string | ID trasy | Tak |

#### Parametry query (opcjonalne):
| Parametr | Typ | Opis | Domyślnie | Przykład |
|----------|-----|------|-----------|----------|
| `use_now` | boolean | Użyj aktualnego czasu zamiast zaplanowanego | `false` | `?use_now=true` |

#### Przykłady:
```
GET /api/v1/recurring-routes/work_morning/calculate-route
GET /api/v1/recurring-routes/work_morning/calculate-route?use_now=true
GET /api/v1/recurring-routes/gym_evening/calculate-route
```

#### Odpowiedź:
```json
{
  "success": true,
  "message": "Obliczona trasa dla 'Do pracy - poranek' w czasie 26.5 min",
  "request_info": {
    "recurring_route_id": "work_morning",
    "recurring_route_name": "Do pracy - poranek",
    "start_coordinates": {
      "latitude": 50.0632,
      "longitude": 19.9380
    },
    "end_coordinates": {
      "latitude": 50.0697,
      "longitude": 19.9530
    },
    "departure_timestamp": 1705395600,
    "processing_timestamp": 1705392000,
    "used_scheduled_time": true,
    "scheduled_departure_time": "09:00"
  },
  "route_segments": [
    {
      "segment_id": 1,
      "type": "walking",
      "from_stop": {
        "uuid": "start_point",
        "name": "Dom - ul. Krakowska 50",
        "coordinates": {
          "latitude": 50.0632,
          "longitude": 19.9380
        }
      },
      "to_stop": {
        "uuid": "abc123",
        "name": "Przystanek Tramwajowy",
        "coordinates": {
          "latitude": 50.0635,
          "longitude": 19.9385
        }
      },
      "departure_timestamp": 1705395600,
      "arrival_timestamp": 1705395720,
      "duration_minutes": 2.0,
      "walking_distance_meters": 150,
      "vehicle": null,
      "delay": null
    },
    {
      "segment_id": 2,
      "type": "transit",
      "from_stop": {
        "uuid": "abc123",
        "name": "Przystanek Tramwajowy",
        "coordinates": {
          "latitude": 50.0635,
          "longitude": 19.9385
        }
      },
      "to_stop": {
        "uuid": "def456",
        "name": "Rondo Mogilskie",
        "coordinates": {
          "latitude": 50.0697,
          "longitude": 19.9530
        }
      },
      "departure_timestamp": 1705395840,
      "arrival_timestamp": 1705397280,
      "duration_minutes": 24.0,
      "walking_distance_meters": null,
      "vehicle": {
        "uuid": "vehicle-001",
        "license_plate": "KR-12345",
        "type": "TRAM",
        "line_number": 4,
        "destination": "Wzgórza Krzesławickie",
        "capacity": 200,
        "owner": "MPK Kraków"
      },
      "delay": {
        "has_delay": true,
        "delay_minutes": 2.0,
        "delay_reason": "Duże natężenie ruchu",
        "delay_source": "real_time"
      }
    }
  ],
  "summary": {
    "total_duration_minutes": 26.5,
    "total_walking_time_minutes": 2.0,
    "total_walking_distance_meters": 150,
    "total_wait_time_minutes": 2.0,
    "total_delay_time_minutes": 2.0,
    "number_of_transfers": 0,
    "departure_timestamp": 1705395600,
    "arrival_timestamp": 1705397190,
    "segments_count": 2,
    "walking_segments_count": 1,
    "transit_segments_count": 1
  },
  "detailed_geometry": [
    [50.0632, 19.9380],
    [50.0635, 19.9385],
    [50.0640, 19.9390],
    [50.0697, 19.9530]
  ],
  "alternative_routes_available": false,
  "recommendations": [
    "✅ Typowy czas podróży (~25.5 min)",
    "✅ Bezpośrednie połączenie bez przesiadek",
    "Tramwaj o 9:00 zazwyczaj jest zatłoczony - rozważ wyjazd 5 minut wcześniej",
    "W piątki średnie opóźnienie wynosi 5 minut"
  ]
}
```

---

## Modele danych

### RecurringRouteBasic
Podstawowe informacje o trasie (lista tras).

```typescript
interface RecurringRouteBasic {
  id: string;                          // Unikalny identyfikator
  name: string;                        // Nazwa trasy
  from_location_name: string;          // Nazwa punktu startowego
  to_location_name: string;            // Nazwa punktu docelowego
  departure_time: string;              // Czas odjazdu "HH:MM"
  frequency: RecurringFrequency;       // Częstotliwość
  is_active: boolean;                  // Czy trasa jest aktywna
  average_duration_minutes: number;    // Średni czas przejazdu
}
```

### RecurringRouteDetail
Szczegółowe informacje o trasie.

```typescript
interface RecurringRouteDetail {
  id: string;
  name: string;
  description: string | null;

  // Lokalizacje
  from_location_name: string;
  from_coordinates: CoordinatePoint;
  to_location_name: string;
  to_coordinates: CoordinatePoint;

  // Harmonogram
  departure_time: string;
  frequency: RecurringFrequency;
  is_active: boolean;

  // Szczegóły trasy
  average_duration_minutes: number;
  average_walking_time_minutes: number;
  average_walking_distance_meters: number;
  typical_transfers: number;

  // Statystyki
  statistics: RouteStatistics;

  // Rekomendacje
  best_departure_time: string;
  alternative_times: string[];
  tips: string[];
}
```

### RouteStatistics
Statystyki historyczne trasy.

```typescript
interface RouteStatistics {
  total_trips: number;                 // Liczba przebytych tras
  on_time_percentage: number;          // % punktualności (0-100)
  average_delay_minutes: number;       // Średnie opóźnienie
  most_common_delay_reason: string | null;  // Najczęstszy powód opóźnień
}
```

### RouteSegment
Segment obliczonej trasy (spacer lub przejazd).

```typescript
interface RouteSegment {
  segment_id: number;
  type: "walking" | "transit";
  from_stop: StopInfo;
  to_stop: StopInfo;
  departure_timestamp: number;         // Unix timestamp (sekundy)
  arrival_timestamp: number;           // Unix timestamp (sekundy)
  duration_minutes: number;

  // Dla spaceru
  walking_distance_meters?: number;

  // Dla transportu publicznego
  vehicle?: VehicleInfo;
  delay?: DelayInfo;
}
```

---

## Przykłady użycia

### React / TypeScript

#### 1. Pobierz listę regularnych tras

```typescript
import { useState, useEffect } from 'react';

interface RecurringRoute {
  id: string;
  name: string;
  from_location_name: string;
  to_location_name: string;
  departure_time: string;
  frequency: string;
  is_active: boolean;
  average_duration_minutes: number;
}

const RecurringRoutesList = () => {
  const [routes, setRoutes] = useState<RecurringRoute[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchRoutes = async () => {
      try {
        const response = await fetch('/api/v1/recurring-routes?active_only=true');
        const data = await response.json();

        if (data.success) {
          setRoutes(data.routes);
        }
      } catch (error) {
        console.error('Błąd pobierania tras:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchRoutes();
  }, []);

  if (loading) return <div>Ładowanie tras...</div>;

  return (
    <div>
      <h2>Moje regularne trasy ({routes.length})</h2>
      {routes.map(route => (
        <div key={route.id} className="route-card">
          <h3>{route.name}</h3>
          <p>🚏 {route.from_location_name} → {route.to_location_name}</p>
          <p>🕐 Odjazd: {route.departure_time}</p>
          <p>⏱️ Średni czas: {route.average_duration_minutes} min</p>
          <p>📅 {route.frequency}</p>
        </div>
      ))}
    </div>
  );
};
```

#### 2. Szczegóły trasy z statystykami

```typescript
const RouteDetails = ({ routeId }: { routeId: string }) => {
  const [routeDetail, setRouteDetail] = useState(null);

  useEffect(() => {
    const fetchDetails = async () => {
      const response = await fetch(`/api/v1/recurring-routes/${routeId}`);
      const data = await response.json();

      if (data.success) {
        setRouteDetail(data.route);
      }
    };

    fetchDetails();
  }, [routeId]);

  if (!routeDetail) return <div>Ładowanie...</div>;

  return (
    <div>
      <h2>{routeDetail.name}</h2>
      <p>{routeDetail.description}</p>

      {/* Statystyki */}
      <div className="statistics">
        <h3>📊 Statystyki</h3>
        <p>Liczba przejazdów: {routeDetail.statistics.total_trips}</p>
        <p>Punktualność: {routeDetail.statistics.on_time_percentage}%</p>
        <p>Średnie opóźnienie: {routeDetail.statistics.average_delay_minutes} min</p>
      </div>

      {/* Rekomendacje */}
      <div className="tips">
        <h3>💡 Wskazówki</h3>
        <ul>
          {routeDetail.tips.map((tip, i) => (
            <li key={i}>{tip}</li>
          ))}
        </ul>
      </div>

      {/* Alternatywne czasy */}
      <div className="alternatives">
        <h3>⏰ Alternatywne czasy odjazdu</h3>
        <p>Najlepszy: {routeDetail.best_departure_time}</p>
        <p>Inne opcje: {routeDetail.alternative_times.join(', ')}</p>
      </div>
    </div>
  );
};
```

#### 3. Oblicz i wyświetl trasę (GŁÓWNA FUNKCJONALNOŚĆ)

```typescript
import { useState } from 'react';

const CalculateRoute = ({ routeId }: { routeId: string }) => {
  const [route, setRoute] = useState(null);
  const [loading, setLoading] = useState(false);

  const calculateRoute = async (useNow = false) => {
    setLoading(true);
    try {
      const url = `/api/v1/recurring-routes/${routeId}/calculate-route${useNow ? '?use_now=true' : ''}`;
      const response = await fetch(url);
      const data = await response.json();

      if (data.success) {
        setRoute(data);
      } else {
        console.error('Nie znaleziono trasy');
      }
    } catch (error) {
      console.error('Błąd obliczania trasy:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <button onClick={() => calculateRoute(false)} disabled={loading}>
        Oblicz trasę (zaplanowany czas)
      </button>
      <button onClick={() => calculateRoute(true)} disabled={loading}>
        Oblicz trasę (teraz)
      </button>

      {loading && <div>Obliczanie trasy...</div>}

      {route && (
        <div className="route-result">
          <h3>{route.message}</h3>

          {/* Podsumowanie */}
          <div className="summary">
            <p>⏱️ Całkowity czas: {route.summary.total_duration_minutes} min</p>
            <p>🚶 Spacer: {route.summary.total_walking_time_minutes} min ({route.summary.total_walking_distance_meters}m)</p>
            <p>🔄 Przesiadki: {route.summary.number_of_transfers}</p>
            {route.summary.total_delay_time_minutes > 0 && (
              <p>⚠️ Opóźnienia: {route.summary.total_delay_time_minutes} min</p>
            )}
          </div>

          {/* Segmenty trasy */}
          <div className="segments">
            <h4>📍 Trasa krok po kroku:</h4>
            {route.route_segments.map((segment, index) => (
              <div key={segment.segment_id} className="segment">
                {segment.type === 'walking' ? (
                  <div className="walking">
                    <p>🚶 Spacer: {segment.duration_minutes} min ({segment.walking_distance_meters}m)</p>
                    <p>Z: {segment.from_stop.name}</p>
                    <p>Do: {segment.to_stop.name}</p>
                  </div>
                ) : (
                  <div className="transit">
                    <p>🚊 Linia {segment.vehicle.line_number} - {segment.vehicle.type}</p>
                    <p>🚏 Z: {segment.from_stop.name}</p>
                    <p>🚏 Do: {segment.to_stop.name}</p>
                    <p>⏱️ Czas: {segment.duration_minutes} min</p>
                    <p>🕐 Odjazd: {new Date(segment.departure_timestamp * 1000).toLocaleTimeString()}</p>
                    <p>🕐 Przyjazd: {new Date(segment.arrival_timestamp * 1000).toLocaleTimeString()}</p>

                    {segment.delay?.has_delay && (
                      <p className="delay">
                        ⚠️ Opóźnienie: {segment.delay.delay_minutes} min - {segment.delay.delay_reason}
                      </p>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Rekomendacje */}
          <div className="recommendations">
            <h4>💡 Rekomendacje:</h4>
            <ul>
              {route.recommendations.map((rec, i) => (
                <li key={i}>{rec}</li>
              ))}
            </ul>
          </div>

          {/* Mapa (jeśli używasz biblioteki map) */}
          <div className="map">
            {/* Tutaj możesz wyświetlić mapę używając detailed_geometry */}
            {/* route.detailed_geometry to tablica [[lat, lon], [lat, lon], ...] */}
          </div>
        </div>
      )}
    </div>
  );
};
```

#### 4. Pełny komponent z mapą (Leaflet)

```typescript
import { MapContainer, TileLayer, Polyline, Marker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

const RouteMap = ({ routeData }) => {
  // Konwertuj geometry do formatu Leaflet
  const polylinePositions = routeData.detailed_geometry.map(coord => [coord[0], coord[1]]);

  // Wyciągnij przystanki
  const stops = routeData.route_segments.map(segment => ({
    position: [segment.from_stop.coordinates.latitude, segment.from_stop.coordinates.longitude],
    name: segment.from_stop.name,
    type: segment.type
  }));

  // Dodaj ostatni przystanek
  const lastSegment = routeData.route_segments[routeData.route_segments.length - 1];
  stops.push({
    position: [lastSegment.to_stop.coordinates.latitude, lastSegment.to_stop.coordinates.longitude],
    name: lastSegment.to_stop.name,
    type: 'end'
  });

  return (
    <MapContainer
      center={polylinePositions[0]}
      zoom={13}
      style={{ height: '400px', width: '100%' }}
    >
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; OpenStreetMap contributors'
      />

      {/* Linia trasy */}
      <Polyline positions={polylinePositions} color="blue" weight={4} />

      {/* Markery przystanków */}
      {stops.map((stop, i) => (
        <Marker key={i} position={stop.position}>
          <Popup>{stop.name}</Popup>
        </Marker>
      ))}
    </MapContainer>
  );
};
```

### JavaScript (Vanilla)

```javascript
// Pobierz listę tras
async function loadRecurringRoutes() {
  const response = await fetch('/api/v1/recurring-routes?active_only=true');
  const data = await response.json();

  const container = document.getElementById('routes-list');

  data.routes.forEach(route => {
    const div = document.createElement('div');
    div.className = 'route-card';
    div.innerHTML = `
      <h3>${route.name}</h3>
      <p>${route.from_location_name} → ${route.to_location_name}</p>
      <p>Odjazd: ${route.departure_time}</p>
      <button onclick="calculateRoute('${route.id}')">Oblicz trasę</button>
    `;
    container.appendChild(div);
  });
}

// Oblicz konkretną trasę
async function calculateRoute(routeId) {
  const response = await fetch(`/api/v1/recurring-routes/${routeId}/calculate-route`);
  const data = await response.json();

  if (data.success) {
    displayRoute(data);
  }
}

function displayRoute(routeData) {
  const container = document.getElementById('route-details');

  let html = `
    <h3>${routeData.message}</h3>
    <p>Czas: ${routeData.summary.total_duration_minutes} min</p>
    <p>Przesiadki: ${routeData.summary.number_of_transfers}</p>
    <h4>Trasa:</h4>
  `;

  routeData.route_segments.forEach(segment => {
    if (segment.type === 'walking') {
      html += `<p>🚶 Spacer ${segment.duration_minutes} min</p>`;
    } else {
      html += `<p>🚊 Linia ${segment.vehicle.line_number} - ${segment.duration_minutes} min</p>`;
    }
  });

  container.innerHTML = html;
}
```

---

## Obsługa błędów

### Kody odpowiedzi HTTP

| Kod | Znaczenie | Przykład |
|-----|-----------|----------|
| `200` | Sukces | Trasa znaleziona |
| `404` | Nie znaleziono | Nieprawidłowe `route_id` |
| `500` | Błąd serwera | Problem z algorytmem |

### Przykład obsługi błędów

```typescript
async function fetchRoute(routeId: string) {
  try {
    const response = await fetch(`/api/v1/recurring-routes/${routeId}/calculate-route`);

    if (!response.ok) {
      if (response.status === 404) {
        throw new Error('Nie znaleziono trasy o podanym ID');
      } else if (response.status === 500) {
        throw new Error('Błąd serwera - spróbuj ponownie później');
      }
    }

    const data = await response.json();

    if (!data.success) {
      throw new Error(data.message || 'Nie udało się obliczyć trasy');
    }

    return data;
  } catch (error) {
    console.error('Błąd:', error);
    // Wyświetl użytkownikowi komunikat o błędzie
    alert(error.message);
  }
}
```

---

## Integracja z frontendem

### Przepływ pracy (Recommended Flow)

```
1. Użytkownik otwiera aplikację
   ↓
2. Załaduj listę tras: GET /api/v1/recurring-routes
   ↓
3. Wyświetl listę tras z kartami
   ↓
4. Użytkownik klika "Zobacz szczegóły"
   ↓
5. Pobierz szczegóły: GET /api/v1/recurring-routes/{id}
   ↓
6. Wyświetl statystyki, tipy, alternatywne czasy
   ↓
7. Użytkownik klika "Oblicz trasę"
   ↓
8. Oblicz trasę: GET /api/v1/recurring-routes/{id}/calculate-route
   ↓
9. Wyświetl szczegółową trasę z segmentami i mapą
```

### Komponenty UI do zbudowania

1. **RoutesList** - Lista kart z regularnymi trasami
2. **RouteCard** - Pojedyncza karta trasy
3. **RouteDetails** - Szczegóły trasy ze statystykami
4. **CalculatedRoute** - Obliczona trasa z segmentami
5. **RouteMap** - Mapa z trasą i przystankami
6. **RouteTimeline** - Timeline z krokami trasy

### Przykład struktury stanów (React)

```typescript
interface AppState {
  routes: RecurringRoute[];           // Lista tras
  selectedRoute: RecurringRouteDetail | null;  // Wybrana trasa
  calculatedRoute: RouteResponse | null;       // Obliczona trasa
  loading: boolean;
  error: string | null;
}
```

### Cache i optymalizacja

```typescript
// Cache dla szczegółów tras
const routeDetailsCache = new Map<string, RecurringRouteDetail>();

async function getRouteDetails(routeId: string) {
  // Sprawdź cache
  if (routeDetailsCache.has(routeId)) {
    return routeDetailsCache.get(routeId);
  }

  // Pobierz z API
  const response = await fetch(`/api/v1/recurring-routes/${routeId}`);
  const data = await response.json();

  // Zapisz w cache
  routeDetailsCache.set(routeId, data.route);

  return data.route;
}
```

---

## Dodatkowe funkcjonalności do zaimplementowania

### 1. Powiadomienia o opóźnieniach

```typescript
async function checkDelaysForRoute(routeId: string) {
  const data = await fetch(`/api/v1/recurring-routes/${routeId}/calculate-route?use_now=true`);
  const route = await data.json();

  if (route.summary.total_delay_time_minutes > 5) {
    // Wyślij powiadomienie push
    new Notification('Opóźnienie na trasie!', {
      body: `Twoja trasa "${route.request_info.recurring_route_name}" ma opóźnienie ${route.summary.total_delay_time_minutes} min`,
      icon: '/icon.png'
    });
  }
}
```

### 2. Automatyczne przypomnienia

```typescript
// Ustaw przypomnienie 15 min przed odjazdem
function setRouteReminder(route: RecurringRouteDetail) {
  const [hours, minutes] = route.departure_time.split(':').map(Number);
  const reminderTime = new Date();
  reminderTime.setHours(hours, minutes - 15, 0);

  const now = new Date();
  const delay = reminderTime.getTime() - now.getTime();

  if (delay > 0) {
    setTimeout(async () => {
      // Oblicz trasę 15 min przed odjazdem
      const response = await fetch(`/api/v1/recurring-routes/${route.id}/calculate-route`);
      const data = await response.json();

      // Wyświetl powiadomienie z czasem trasy i opóźnieniami
      showNotification(data);
    }, delay);
  }
}
```

### 3. Porównanie tras

```typescript
async function compareRouteTimes(routeId: string) {
  // Oblicz trasę na zaplanowany czas
  const scheduled = await fetch(`/api/v1/recurring-routes/${routeId}/calculate-route`);
  const scheduledData = await scheduled.json();

  // Oblicz trasę na teraz
  const now = await fetch(`/api/v1/recurring-routes/${routeId}/calculate-route?use_now=true`);
  const nowData = await now.json();

  // Porównaj czasy
  const timeDiff = nowData.summary.total_duration_minutes - scheduledData.summary.total_duration_minutes;

  console.log(`Różnica w czasie: ${timeDiff} min`);
}
```

---

## FAQ

### Q: Jak często powinienem odświeżać dane?
A:
- Lista tras: Przy otwarciu aplikacji (dane statyczne)
- Szczegóły trasy: Przy kliknięciu na trasę (dane statyczne)
- Obliczona trasa: Przed każdą podróżą lub co 5-10 min (dane dynamiczne)

### Q: Czy mogę dodać własne trasy?
A: Obecnie trasy są hardcoded. W przyszłości można dodać endpointy POST/PUT/DELETE.

### Q: Co oznacza `use_now=true`?
A: Oblicza trasę na aktualny czas zamiast zaplanowanego czasu odjazdu trasy.

### Q: Jak interpretować `detailed_geometry`?
A: To tablica punktów `[[lat, lon], ...]` do narysowania linii na mapie.

### Q: Co zrobić gdy `success: false`?
A: Wyświetl użytkownikowi `message` i sprawdź `recommendations` dla podpowiedzi.

---

## Podsumowanie

**Główny endpoint do użycia:** `/api/v1/recurring-routes/{route_id}/calculate-route`

Ten endpoint:
- ✅ Używa algorytmu pathfinding (`algo.py`)
- ✅ Zwraca pełną trasę z segmentami
- ✅ Zawiera informacje o pojazdach i opóźnieniach
- ✅ Porównuje z historycznymi statystykami
- ✅ Dostarcza geometrię do wyświetlenia na mapie
- ✅ Daje inteligentne rekomendacje

**Przykładowy pełny przepływ:**
```
1. GET /api/v1/recurring-routes → Lista tras
2. User wybiera trasę "work_morning"
3. GET /api/v1/recurring-routes/work_morning → Szczegóły i statystyki
4. User klika "Oblicz trasę"
5. GET /api/v1/recurring-routes/work_morning/calculate-route → Pełna trasa
6. Wyświetl trasę z segmentami, mapą, rekomendacjami
```

---

**Kontakt:** Jeśli masz pytania lub problemy, sprawdź logi backendu lub skontaktuj się z zespołem.
