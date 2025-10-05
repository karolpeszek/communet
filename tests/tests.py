from db import *
from datetime import date, datetime, timedelta

# Używamy aktualnej daty, ponieważ db_setup pobiera najnowsze pliki GTFS
test_date = datetime.now().date()
# Dla testów połączeń użyjemy konkretnej godziny, np. 8:30
test_time = datetime.now().replace(hour=8, minute=30, second=0, microsecond=0)


def db_setup_test():
    from db_setup import db as krakow_db
    print("Tworzenie bazy danych komunikacji miejskiej dla Krakowa...")

    # Utworzenie bazy danych dla dzisiejszej daty
    #krakow_db = create_krakow_database(target_day=test_date)

    # Wyświetlenie przykładowych informacji
    print(f"Baza danych została utworzona dla daty {test_date}.")
    print(f"Całkowita liczba wygenerowanych przejazdów (trips): {len(krakow_db.trips)}")

    # Znajdź i wyświetl przykładowy przejazd linii 52
    sample_trip = None
    for trip in krakow_db.trips.values():
        if trip.route.line_number == 52:
            sample_trip = trip
            break

    if sample_trip:
        print("\n--- Przykładowy przejazd (Trip) dla linii 52 ---")
        print(f"Linia: {sample_trip.route.line_number}")
        print(f"Kierunek: {sample_trip.route.destination}")
        print(f"Liczba przystanków na trasie: {len(sample_trip.route.stops)}")

        if sample_trip.timestamps:
            first_stop = sample_trip.route.stops[0]
            first_stop_time = sample_trip.timestamps[0]
            print(f"Przystanek początkowy: '{first_stop.short_name}' o godz. {first_stop_time.strftime('%H:%M:%S')}")

            last_stop = sample_trip.route.stops[-1]
            last_stop_time = sample_trip.timestamps[-1]
            print(f"Przystanek końcowy: '{last_stop.short_name}' o godz. {last_stop_time.strftime('%H:%M:%S')}")

    print("\nMożesz teraz używać obiektu 'krakow_db' w dalszej części programu.")


def db_get_route_test():
    from db_setup import db as database
    # Tworzenie bazy danych
    print("\nTworzenie bazy danych Krakowa dla testu tras...")

    if not database.trips:
        print("Baza danych jest pusta. Nie można przeprowadzić testu tras.")
        return

    # Najpierw sprawdźmy, jakie przystanki są dostępne
    print(f"\nDostępne przystanki w bazie danych ({len(database.stops)} łącznie):")
    stop_names = [stop.short_name for stop in database.stops.values()]
    stop_names.sort()

    # Wyświetl przystanki zawierające "Mogilskie" lub podobne
    mogilskie_stops = [name for name in stop_names if "mogilskie" in name.lower()]
    print(f"Przystanki zawierające 'Mogilskie': {mogilskie_stops}")

    # Wyświetl przystanki zawierające "Rondo"
    rondo_stops = [name for name in stop_names if "rondo" in name.lower()]
    print(f"Przystanki zawierające 'Rondo': {rondo_stops}")

    # Wyświetl pierwszych 20 przystanków dla przykładu
    print(f"Przykładowe przystanki (pierwsze 20): {stop_names[:20]}")

    # Znajdź przystanek - sprawdźmy różne warianty
    test_stop = None
    test_patterns = [
        "Rondo Mogilskie",
        "Mogilskie",
        "rondo mogilskie",
        "Dworzec Główny",
        "Plac Centralny"
    ]

    for pattern in test_patterns:
        for stop in database.stops.values():
            if pattern.lower() in stop.short_name.lower():
                test_stop = stop
                print(f"\nZnaleziono przystanek: '{stop.short_name}' (szukano: '{pattern}')")
                break
        if test_stop:
            break

    if not test_stop:
        print("Nie znaleziono żadnego znanego przystanku. Używam pierwszego dostępnego.")
        test_stop = list(database.stops.values())[0]
        print(f"Wybrany przystanek: '{test_stop.short_name}'")

    # Sprawdźmy, jakie linie przechodzą przez ten przystanek
    lines_through_stop = set()
    for trip in database.trips.values():
        if test_stop in trip.route.stops:
            lines_through_stop.add(trip.route.line_number)

    print(f"Linie przechodzące przez '{test_stop.short_name}': {sorted(lines_through_stop)}")

    # Testuj funkcję get_routes dla konkretnego czasu
    print(
        f"\nSzukanie połączeń z przystanku '{test_stop.short_name}' o godzinie {test_time.strftime('%H:%M:%S')} w dniu {test_date}")

    edges = get_routes(database, test_stop, test_time)

    print(f"Znaleziono {len(edges)} dostępnych połączeń:")

    # Wyświetl pierwsze 5 połączeń
    MAX_CNT = 5
    for i, edge in enumerate(edges[:MAX_CNT]):
        trip = database.trips[edge.trip_uuid]
        vehicle = database.get_vehicle(edge.vehicle_uuid) if edge.vehicle_uuid in database.vehicles else None

        print(f"\n{i + 1}. Linia {trip.route.line_number} → {trip.route.destination}")
        print(f"   Odjazd o: {edge.start_timestamp.strftime('%H:%M:%S')}")
        print(f"   Następny przystanek: {edge.next_stop.short_name}")
        print(f"   Czas przejazdu: {edge.time} sekund ({edge.time // 60} min {edge.time % 60} sek)")
        if vehicle:
            print(f"   Pojazd: {vehicle.license_plate} ({vehicle.type.name}, pojemność: {vehicle.capacity})")

    if len(edges) > MAX_CNT:
        print(f"\n... i {len(edges) - MAX_CNT} więcej połączeń")

    # Jeśli nie ma połączeń o 8:30, sprawdź wcześniejsze godziny
    if not edges:
        print(f"\nBrak połączeń o {test_time.strftime('%H:%M')}. Sprawdzam wcześniejsze godziny...")
        for hour in range(4, 24):
            early_time = test_time.replace(hour=hour, minute=0)
            early_edges = get_routes(database, test_stop, early_time)
            if early_edges:
                print(f"Znaleziono {len(early_edges)} połączeń o {early_time.strftime('%H:%M')}")
                break


if __name__ == "__main__":
    db_setup_test()
    db_get_route_test()