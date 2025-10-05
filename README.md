# 🚍 LAJKONIK - Community-Driven Public Transport Delay Management System
## HackYeah Journey Radar Project!
<div align="center">

![Communet Logo](https://img.shields.io/badge/Communet-Transport%20Intelligence-blue?style=for-the-badge)

**Real-time delay management and route optimization powered by community intelligence**

[![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)


[Features](#-key-features) • [Demo](#-demo) • [Installation](#-installation) • [API Documentation](#-api-documentation)

</div>

---

## 📖 Overview

**Lajkonik** is an innovative public transport management system that revolutionizes how passengers interact with delay information. Unlike traditional systems that rely solely on official data sources, Communet creates a collaborative ecosystem where users actively contribute to real-time delay reporting, while advanced algorithms predict and optimize routes based on actual conditions.

### 🎯 The Problem We Solve

Public transport systems face a critical communication gap:
- **Fragmented Information**: Rail and bus services lack integrated data exchange
- **Delayed Notifications**: Official delay announcements often come too late
- **Inefficient Communication**: Passengers have no reliable way to report or receive real-time disruptions
- **Poor Route Planning**: Existing systems don't account for actual, on-the-ground delays

### 💡 Our Solution

Communet bridges this gap through:
1. **Community-Driven Intelligence**: Passengers report delays in real-time
2. **Predictive Analytics**: ML-based prediction of future disruptions based on historical patterns
3. **Dynamic Route Optimization**: Modified Dijkstra's algorithm that accounts for delays, walking distances, and transfer times
4. **Unified API**: Seamless integration with dispatcher systems of transport operators

---

## ✨ Key Features

### 🎤 User-Reported Disruptions
- **Real-time reporting** of delays, accidents, and service issues
- **Gamification system** with reputation points rewarding helpful contributions
- **Verification mechanisms** to ensure report accuracy and prevent spam
- Multiple delay categories: Traffic Jams, Road Accidents, Severe Weather, Vehicle Issues

### 🔮 Predictive Delay Analysis
- **Machine learning algorithms** analyze historical delay patterns
- **Real-time delay propagation** across connected routes
- **Risk assessment** for route segments
- Integration of both vehicle-specific and route-specific delay data

### 🗺️ Intelligent Route Planning
- **Modified Dijkstra's algorithm** optimized for public transport
- Considers:
  - Real-time timetables and vehicle positions
  - Current delays and disruptions
  - Walking distances between stops (up to 800m)
  - Transfer times and wait periods
  - Maximum transfer limits (3 transfers)
- **Fallback to walking** for short distances (<2km)
- **Comprehensive route details** including:
  - Segment-by-segment breakdown
  - Delay impact analysis
  - Transfer optimization
  - Walking distance calculations

### 🚀 RESTful API
- **FastAPI-powered** backend for high performance
- **Unix timestamp-based** scheduling for universal compatibility
- Detailed route responses with:
  - Stop information (coordinates, names, zones)
  - Vehicle details (type, capacity, line numbers)
  - Delay information with reasons and sources
  - Complete route geometry for map visualization
  - Summary statistics (duration, transfers, delays)

### 📍 Interactive Maps & Navigation
- Real-time disruption visualization on routes
- Optimal connection planning with multiple alternatives
- Detailed route geometry for accurate map rendering
- Support for multiple transport types: Trams, Buses, Trains

---

## 🏗️ Architecture

### Technology Stack

```
Backend:        FastAPI (Python 3.13)
Routing:        Modified Dijkstra's Algorithm
Data Storage:   Pickle-based caching system
Geospatial:     Haversine distance calculations
API Design:     RESTful with Unix timestamps
```

### Core Components

```
communet/
├── algo.py                 # Routing algorithm & pathfinding
├── db.py                   # Database models & data structures
├── db_setup.py            # Database initialization
├── main.py                # FastAPI application entry point
├── backend/
│   ├── tochange.py        # Main API endpoints
│   ├── recurring_routes.py # Recurring route management
│   ├── create_lines.py    # Route geometry generation
│   └── serializers.py     # Request/response models
├── models.py              # Pydantic data models
├── security.py            # Authentication & verification
└── cache/                 # Cached route data
```

---

## 🚀 Installation

### Prerequisites

- Python 3.13+
- pip (Python package manager)

### Setup

1. **Clone the repository**
```bash
git clone https://github.com/karolpeszek/communet.git
cd communet
```

2. **Create virtual environment** (recommended)
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install fastapi uvicorn pydantic
```

4. **Run the application**
```bash
uvicorn main:app --reload
```

---

## 📚 API Documentation

#### 1. Plan Route
**`GET /api/v1/plan_route`**

Find the optimal public transport route between two points.

**Query Parameters:**
- `start_lat` (float): Starting latitude (-90 to 90)
- `start_lon` (float): Starting longitude (-180 to 180)
- `end_lat` (float): Destination latitude (-90 to 90)
- `end_lon` (float): Destination longitude (-180 to 180)
- `timestamp` (int): Departure time as Unix timestamp (seconds)

**Example Request:**
```bash
curl "http://localhost:8000/api/v1/plan_route?start_lat=50.063&start_lon=19.938&end_lat=50.067&end_lon=19.990&timestamp=1705320600"
```

**Response Structure:**
```json
{
  "success": true,
  "message": "Found optimal route with 2 transfers in 45.3 minutes",
  "route_segments": [
    {
      "segment_id": 1,
      "type": "transit",
      "from_stop": {
        "uuid": "abc-123",
        "name": "Main Station",
        "coordinates": {"latitude": 50.063, "longitude": 19.938}
      },
      "to_stop": {...},
      "departure_timestamp": 1705320600,
      "arrival_timestamp": 1705321800,
      "duration_minutes": 20.0,
      "vehicle": {
        "uuid": "vehicle-123",
        "license_plate": "KR-1234",
        "type": "TRAM",
        "line_number": 8,
        "destination": "Krowodrza Górka"
      },
      "delay": {
        "has_delay": true,
        "delay_minutes": 5.0,
        "delay_reason": "TRAFFIC_JAM",
        "delay_source": "vehicle KR-1234"
      }
    }
  ],
  "summary": {
    "total_duration_minutes": 45.3,
    "total_walking_time_minutes": 8.5,
    "total_walking_distance_meters": 600,
    "total_wait_time_minutes": 12.0,
    "total_delay_time_minutes": 5.0,
    "number_of_transfers": 2
  },
  "detailed_geometry": [[50.063, 19.938], [50.064, 19.940], ...],
  "recommendations": ["Route contains significant delays"]
}
```

#### 2. Report Delay
**`POST /api/v1/delay/report`**

Report a delay on a specific route segment.

**Request Body:**
```json
{
  "vehicle_uuid": "uuid-string",
  "current_stop_uuid": "stop-uuid",
  "next_stop_uuid": "stop-uuid",
  "delay_reason": "TRAFFIC_JAM"
}
```

**Delay Reasons:**
- `TRAFFIC_JAM`: Heavy traffic causing delays
- `ROAD_ACCIDENT`: Accident blocking the route
- `SEVERE_WEATHER`: Weather-related disruptions
- `VEHICLE_ISSUE`: Technical problems with the vehicle

### Interactive API Documentation

Once the server is running, visit:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

---

## 🧮 Algorithm Deep Dive

### Modified Dijkstra's Algorithm

Our routing algorithm extends the classic Dijkstra's shortest path algorithm with public transport constraints:

**Key Innovations:**

1. **Time-Dependent Edges**: Unlike traditional graphs, our edges have time-dependent costs based on:
   - Scheduled departure times
   - Current delays (vehicle and route-specific)
   - Waiting time until next departure

2. **Multi-Modal Transport**: Seamlessly combines:
   - Public transport segments (trams, buses, trains)
   - Walking segments (up to 800m between stops)
   - Transfer penalties

3. **Delay Integration**: Real-time delay data affects:
   - Edge costs (travel time increases)
   - Route feasibility (missed connections)
   - Alternative route suggestions

4. **Optimizations**:
   - Heap-based priority queue for efficient node selection
   - Early termination when destination is reached
   - Transfer limit to prevent unrealistic routes
   - Walking distance threshold for practicality

**Complexity:**
- Time: O((E + V) log V) where V = stops, E = possible connections
- Space: O(V) for tracking best times to each stop

---

## 🎨 Use Cases

### For Passengers
- Plan journeys with real-time delay awareness
- Receive alternative routes when disruptions occur
- Contribute to community knowledge by reporting issues
- Earn reputation points for helpful reports

### For Transport Operators
- Gain real-time insights from passenger reports
- Identify problematic routes and patterns
- Integrate with existing dispatcher systems via API
- Improve service quality based on community feedback

### For Urban Planners
- Analyze delay patterns across the network
- Identify infrastructure bottlenecks
- Evaluate impact of route changes
- Data-driven decision making for service improvements

---

## 📊 Data Models

### Core Entities

**User**
- UUID, name, surname
- Geographic location
- Reputation score (gamification)

**Vehicle**
- License plate, type (Tram/Bus/Train)
- Capacity, owner information
- Current delay status

**Stop**
- Coordinates (latitude/longitude)
- Short and long names
- Zone ID for fare calculation
- Supported vehicle types

**Trip**
- Route information (line number, destination)
- Scheduled timestamps for each stop
- Associated vehicles

**Delay**
- Time delay (seconds)
- Reason category
- Affected segment or vehicle

---

## 🔒 Security & Verification

### User Reputation System
- Points awarded for verified, helpful reports
- Penalties for false or spam reports
- Reputation impacts report weight in delay calculations

### Report Verification
- Cross-validation with multiple user reports
- Automated anomaly detection
- Time-decay for outdated information
- Operator confirmation for critical disruptions

---

## 🌟 Roadmap

- [ ] **Phase 1**: Core routing and delay reporting (✅ Complete)
- [ ] **Phase 2**: Mobile applications (iOS/Android)
- [ ] **Phase 3**: Machine learning delay prediction models
- [ ] **Phase 4**: Integration with official transport APIs
- [ ] **Phase 5**: Multi-city support and scalability
- [ ] **Phase 6**: Advanced analytics dashboard
- [ ] **Phase 7**: Real-time vehicle tracking integration

---

## 👥 Team

- **Team Mebers**: Michał Zagajewski, Adam Sulik, Filip Manijak, Hubert Jastrzębski, Oliwier Polak, Karol Peszek

---


<div align="center">

⭐ Dziękujemy za super Hackaton! ⭐

[⬆ Back to Top](#-communet---community-driven-public-transport-delay-management-system)

</div>
