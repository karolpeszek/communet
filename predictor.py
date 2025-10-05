"""
Delay Prediction System for Public Transportation
Combines multiple prediction methods:
1. Prophet - Seasonal and trend-based predictions
2. Flow Networks - Traffic propagation between connected routes
3. Google Maps API - Real-time traffic predictions
4. LSTM - Deep learning with spatial context from nearby streets
"""

from typing import List, Dict, Tuple, Optional
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from collections import defaultdict
import pickle
import json
import os

# Prophet for time series forecasting
from prophet import Prophet

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader

import networkx as nx

import googlemaps

from db import Database, Stop, Route, Trip, Delay, DelayReason, Vehicle, Edge
from uuid import UUID


class ProphetDelayPredictor:
    """
    Uses Facebook Prophet to predict delays based on historical patterns.
    Captures seasonal trends, weekly patterns, and special events.
    """

    def __init__(self):
        self.models: Dict[Tuple[UUID, UUID], Prophet] = {}  # (stop1_uuid, stop2_uuid) -> model
        self.trained = False

    def prepare_training_data(self, database: Database) -> Dict[Tuple[UUID, UUID], pd.DataFrame]:
        """
        Convert delay history into Prophet-compatible format.
        Prophet expects columns: 'ds' (datetime) and 'y' (value to predict)
        """
        route_delays = defaultdict(list)

        # Aggregate delays by route segment
        for (stop1, stop2), delay in database.stop_delays.items():
            route_delays[(stop1.uuid, stop2.uuid)].append({
                'timestamp': datetime.now(),  # Should come from delay history
                'delay_seconds': delay.time_delay.total_seconds()
            })

        # Convert to Prophet format
        prophet_data = {}
        for route_key, delays in route_delays.items():
            df = pd.DataFrame(delays)
            if len(df) > 2:  # Need at least some data points
                df = df.rename(columns={'timestamp': 'ds', 'delay_seconds': 'y'})
                prophet_data[route_key] = df

        return prophet_data

    def train(self, database: Database):
        """Train Prophet models for each route segment."""
        if Prophet is None:
            print("Prophet not available, skipping training")
            return

        training_data = self.prepare_training_data(database)

        for route_key, df in training_data.items():
            try:
                model = Prophet(
                    daily_seasonality=True,
                    weekly_seasonality=True,
                    yearly_seasonality=True,
                    changepoint_prior_scale=0.05
                )
                model.fit(df)
                self.models[route_key] = model
            except Exception as e:
                print(f"Failed to train model for route {route_key}: {e}")

        self.trained = True

    def predict(self, stop1: Stop, stop2: Stop, timestamp: datetime) -> float:
        """Predict delay in seconds for a route segment at given time."""
        route_key = (stop1.uuid, stop2.uuid)

        if route_key not in self.models:
            return 0.0

        model = self.models[route_key]
        future = pd.DataFrame({'ds': [timestamp]})

        try:
            forecast = model.predict(future)
            predicted_delay = max(0, forecast['yhat'].values[0])  # No negative delays
            return predicted_delay
        except Exception as e:
            print(f"Prediction failed: {e}")
            return 0.0

    def save(self, filepath: str):
        """Save trained models."""
        with open(filepath, 'wb') as f:
            pickle.dump(self.models, f)

    def load(self, filepath: str):
        """Load trained models."""
        if os.path.exists(filepath):
            with open(filepath, 'rb') as f:
                self.models = pickle.load(f)
            self.trained = True


class TrafficFlowNetwork:
    """
    Models traffic as a flow network where congestion on one route
    affects connected routes based on shared stops and alternative paths.
    """

    def __init__(self, database: Database):
        self.database = database
        self.graph = nx.DiGraph() if nx else None
        self.propagation_factor = 0.3  # How much delay spreads to connected routes

    def build_network(self):
        """Build network graph from routes and stops."""
        if self.graph is None:
            return

        # Add stops as nodes
        for stop_uuid, stop in self.database.stops.items():
            self.graph.add_node(stop_uuid, stop=stop)

        # Add routes as edges with capacity and current flow
        for trip in self.database.trips.values():
            route_stops = trip.route.stops
            for i in range(len(route_stops) - 1):
                stop1, stop2 = route_stops[i], route_stops[i + 1]

                # Calculate edge weight based on base travel time
                base_time = (trip.timestamps[i + 1] - trip.timestamps[i]).total_seconds()

                # Add edge with attributes
                self.graph.add_edge(
                    stop1.uuid,
                    stop2.uuid,
                    weight=base_time,
                    capacity=trip.route.vehicles[0].capacity if trip.route.vehicles else 100,
                    trips=[trip.uuid]
                )

    def propagate_delays(self, affected_stops: List[Tuple[Stop, Stop]],
                         base_delays: Dict[Tuple[Stop, Stop], float]) -> Dict[Tuple[Stop, Stop], float]:
        """
        Propagate delays through the network.
        If route A-B is delayed, connected routes may also experience delays.
        """
        if self.graph is None:
            return base_delays

        propagated_delays = base_delays.copy()

        # Iterate to allow delays to propagate through multiple hops
        for iteration in range(3):  # 3 hops of propagation
            new_delays = {}

            for (stop1, stop2), delay in list(propagated_delays.items()):
                # Find routes that share stops with this delayed route
                # These routes might be affected by passenger overflow or rerouting

                # Routes leaving from stop2 (downstream)
                if stop2.uuid in self.graph:
                    for neighbor_uuid in self.graph.successors(stop2.uuid):
                        neighbor_stop = self.database.get_stop(neighbor_uuid)
                        route_key = (stop2, neighbor_stop)

                        # Propagate a fraction of the delay
                        propagated = delay * self.propagation_factor * (0.8 ** iteration)

                        if route_key not in propagated_delays:
                            new_delays[route_key] = propagated
                        else:
                            new_delays[route_key] = max(propagated_delays[route_key], propagated)

                # Routes arriving at stop1 (upstream backup)
                if stop1.uuid in self.graph:
                    for predecessor_uuid in self.graph.predecessors(stop1.uuid):
                        predecessor_stop = self.database.get_stop(predecessor_uuid)
                        route_key = (predecessor_stop, stop1)

                        propagated = delay * self.propagation_factor * 0.5 * (0.8 ** iteration)

                        if route_key not in propagated_delays:
                            new_delays[route_key] = propagated
                        else:
                            new_delays[route_key] = max(propagated_delays[route_key], propagated)

            propagated_delays.update(new_delays)

        return propagated_delays

    def find_alternative_routes(self, start: Stop, end: Stop, k: int = 3) -> List[List[Stop]]:
        """Find k alternative routes between two stops."""
        if self.graph is None:
            return []

        try:
            # Use k-shortest paths algorithm
            paths = list(nx.shortest_simple_paths(self.graph, start.uuid, end.uuid, weight='weight'))

            # Convert UUIDs back to Stop objects
            stop_paths = []
            for path in paths[:k]:
                stop_path = [self.database.get_stop(uuid) for uuid in path]
                stop_paths.append(stop_path)

            return stop_paths
        except nx.NetworkXNoPath:
            return []


class GoogleMapsTrafficPredictor:
    """
    Fetches real-time and predicted traffic data from Google Maps API.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get('GOOGLE_MAPS_API_KEY')
        self.client = googlemaps.Client(key=self.api_key) if googlemaps and self.api_key else None
        self.cache = {}
        self.cache_duration = timedelta(minutes=5)

    def get_traffic_prediction(self, stop1: Stop, stop2: Stop,
                               departure_time: datetime) -> Optional[Dict]:
        """
        Get traffic prediction from Google Maps Directions API.
        Returns travel time with traffic.
        """
        if self.client is None:
            return None

        cache_key = (stop1.uuid, stop2.uuid, departure_time.replace(second=0, microsecond=0))

        # Check cache
        if cache_key in self.cache:
            cached_time, cached_data = self.cache[cache_key]
            if datetime.now() - cached_time < self.cache_duration:
                return cached_data

        try:
            # Query Google Maps
            result = self.client.directions(
                origin=(stop1.latitude, stop1.longitude),
                destination=(stop2.latitude, stop2.longitude),
                mode="driving",
                departure_time=departure_time,
                traffic_model="best_guess"
            )

            if result and len(result) > 0:
                leg = result[0]['legs'][0]
                data = {
                    'duration': leg['duration']['value'],  # seconds
                    'duration_in_traffic': leg.get('duration_in_traffic', {}).get('value', leg['duration']['value']),
                    'distance': leg['distance']['value']  # meters
                }

                # Cache result
                self.cache[cache_key] = (datetime.now(), data)
                return data
        except Exception as e:
            print(f"Google Maps API error: {e}")

        return None

    def predict_delay(self, stop1: Stop, stop2: Stop,
                      base_time: float, departure_time: datetime) -> float:
        """
        Predict additional delay based on Google Maps traffic.
        Returns delay in seconds.
        """
        traffic_data = self.get_traffic_prediction(stop1, stop2, departure_time)

        if traffic_data:
            traffic_time = traffic_data['duration_in_traffic']
            predicted_delay = max(0, traffic_time - base_time)
            return predicted_delay

        return 0.0


class SpatialLSTMPredictor:
    """
    LSTM model that considers nearby streets and routes as spatial context.
    Predicts delays based on patterns in neighboring areas.
    """

    def __init__(self, input_size: int = 10, hidden_size: int = 64,
                 num_layers: int = 2, sequence_length: int = 12):
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.sequence_length = sequence_length
        self.model = None
        self.scaler_mean = None
        self.scaler_std = None

        if torch is not None and nn is not None:
            self._build_model()

    def _build_model(self):
        """Build LSTM architecture."""

        class LSTMModel(nn.Module):
            def __init__(self, input_size, hidden_size, num_layers, output_size=1):
                super(LSTMModel, self).__init__()
                self.hidden_size = hidden_size
                self.num_layers = num_layers

                self.lstm = nn.LSTM(input_size, hidden_size, num_layers,
                                    batch_first=True, dropout=0.2)
                self.fc1 = nn.Linear(hidden_size, hidden_size // 2)
                self.relu = nn.ReLU()
                self.fc2 = nn.Linear(hidden_size // 2, output_size)

            def forward(self, x):
                # Initialize hidden state
                h0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size)
                c0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size)

                # Forward propagate LSTM
                out, _ = self.lstm(x, (h0, c0))

                # Get last time step
                out = out[:, -1, :]

                # Fully connected layers
                out = self.fc1(out)
                out = self.relu(out)
                out = self.fc2(out)

                return out

        self.model = LSTMModel(self.input_size, self.hidden_size,
                               self.num_layers, output_size=1)

    def get_nearby_routes(self, stop: Stop, database: Database,
                          radius_km: float = 2.0) -> List[Tuple[Stop, Stop]]:
        """Find routes within radius of given stop."""
        from db import haversine

        nearby_routes = []

        for (stop1, stop2) in database.stop_delays.keys():
            # Check if either stop is within radius
            dist1 = haversine(stop.latitude, stop.longitude,
                              stop1.latitude, stop1.longitude)
            dist2 = haversine(stop.latitude, stop.longitude,
                              stop2.latitude, stop2.longitude)

            if dist1 <= radius_km or dist2 <= radius_km:
                nearby_routes.append((stop1, stop2))

        return nearby_routes

    def prepare_features(self, stop1: Stop, stop2: Stop,
                         timestamp: datetime, database: Database) -> np.ndarray:
        """
        Prepare feature vector including:
        - Time features (hour, day of week, month)
        - Current delays on this route
        - Delays on nearby routes (spatial context)
        - Weather indicators (if available)
        """
        features = []

        # Temporal features
        features.append(timestamp.hour / 24.0)
        features.append(timestamp.weekday() / 7.0)
        features.append(timestamp.month / 12.0)
        features.append(timestamp.day / 31.0)

        # Current route delay
        current_delay = database.stop_delays.get((stop1, stop2))
        features.append(current_delay.time_delay.total_seconds() / 3600.0 if current_delay else 0.0)

        # Nearby routes context (average delay)
        nearby_routes = self.get_nearby_routes(stop1, database, radius_km=2.0)
        nearby_delays = []
        for route in nearby_routes[:5]:  # Limit to 5 nearest
            delay = database.stop_delays.get(route)
            if delay:
                nearby_delays.append(delay.time_delay.total_seconds() / 3600.0)

        # Pad or truncate to fixed size
        while len(nearby_delays) < 5:
            nearby_delays.append(0.0)
        features.extend(nearby_delays[:5])

        return np.array(features[:self.input_size])

    def prepare_training_data(self, database: Database,
                              history_hours: int = 168) -> Tuple[np.ndarray, np.ndarray]:
        """
        Prepare sequences for LSTM training.
        For each route, create sequences of historical data.
        """
        X, y = [], []

        # This is a simplified version - in practice, you'd need actual historical data
        # with timestamps to create proper sequences

        for (stop1, stop2), delay in database.stop_delays.items():
            # Create a mock sequence (in real implementation, fetch from database)
            sequence = []
            for i in range(self.sequence_length):
                mock_timestamp = datetime.now() - timedelta(hours=i)
                features = self.prepare_features(stop1, stop2, mock_timestamp, database)
                sequence.append(features)

            sequence.reverse()  # Oldest to newest
            X.append(sequence)
            y.append(delay.time_delay.total_seconds() / 3600.0)  # Normalize to hours

        return np.array(X), np.array(y)

    def train(self, database: Database, epochs: int = 50, batch_size: int = 32):
        """Train the LSTM model."""
        if self.model is None or torch is None:
            print("PyTorch not available, skipping LSTM training")
            return

        X, y = self.prepare_training_data(database)

        if len(X) == 0:
            print("No training data available")
            return

        # Normalize
        self.scaler_mean = X.mean(axis=(0, 1))
        self.scaler_std = X.std(axis=(0, 1)) + 1e-8
        X = (X - self.scaler_mean) / self.scaler_std

        # Convert to tensors
        X_tensor = torch.FloatTensor(X)
        y_tensor = torch.FloatTensor(y).reshape(-1, 1)

        # Training setup
        criterion = nn.MSELoss()
        optimizer = torch.optim.Adam(self.model.parameters(), lr=0.001)

        # Training loop
        self.model.train()
        for epoch in range(epochs):
            optimizer.zero_grad()
            outputs = self.model(X_tensor)
            loss = criterion(outputs, y_tensor)
            loss.backward()
            optimizer.step()

            if (epoch + 1) % 10 == 0:
                print(f'Epoch [{epoch + 1}/{epochs}], Loss: {loss.item():.4f}')

    def predict(self, stop1: Stop, stop2: Stop, timestamp: datetime,
                database: Database) -> float:
        """Predict delay using trained LSTM model."""
        if self.model is None or torch is None:
            return 0.0

        # Create sequence
        sequence = []
        for i in range(self.sequence_length):
            past_timestamp = timestamp - timedelta(hours=(self.sequence_length - i))
            features = self.prepare_features(stop1, stop2, past_timestamp, database)
            sequence.append(features)

        sequence = np.array(sequence)

        # Normalize
        if self.scaler_mean is not None:
            sequence = (sequence - self.scaler_mean) / self.scaler_std

        # Predict
        self.model.eval()
        with torch.no_grad():
            X_tensor = torch.FloatTensor(sequence).unsqueeze(0)
            prediction = self.model(X_tensor)
            delay_hours = prediction.item()
            delay_seconds = max(0, delay_hours * 3600)  # Convert back to seconds

        return delay_seconds

    def save(self, filepath: str):
        """Save model weights."""
        if self.model is not None:
            torch.save({
                'model_state_dict': self.model.state_dict(),
                'scaler_mean': self.scaler_mean,
                'scaler_std': self.scaler_std
            }, filepath)

    def load(self, filepath: str):
        """Load model weights."""
        if self.model is not None and os.path.exists(filepath):
            checkpoint = torch.load(filepath)
            self.model.load_state_dict(checkpoint['model_state_dict'])
            self.scaler_mean = checkpoint['scaler_mean']
            self.scaler_std = checkpoint['scaler_std']


class UnifiedDelayPredictor:
    """
    Combines all prediction methods into a single interface.
    Uses ensemble learning to weight different predictions.
    """

    def __init__(self, database: Database, google_maps_api_key: Optional[str] = None):
        self.database = database

        # Initialize all predictors
        self.prophet_predictor = ProphetDelayPredictor()
        self.flow_network = TrafficFlowNetwork(database)
        self.gmaps_predictor = GoogleMapsTrafficPredictor(google_maps_api_key)
        self.lstm_predictor = SpatialLSTMPredictor()

        # Weights for ensemble (can be tuned)
        self.weights = {
            'prophet': 0.25,
            'flow': 0.20,
            'gmaps': 0.35,
            'lstm': 0.20
        }

        self.trained = False

    def train_all(self, epochs: int = 50):
        """Train all machine learning models."""
        print("Training Prophet models...")
        self.prophet_predictor.train(self.database)

        print("Building flow network...")
        self.flow_network.build_network()

        print("Training LSTM model...")
        self.lstm_predictor.train(self.database, epochs=epochs)

        self.trained = True
        print("All models trained successfully!")

    def predict_delay(self, stop1: Stop, stop2: Stop,
                      timestamp: datetime, base_time: float) -> Dict[str, float]:
        """
        Predict delay using all methods and return ensemble prediction.

        Returns:
            Dict with individual predictions and weighted ensemble prediction
        """
        predictions = {}

        # Prophet prediction
        prophet_delay = self.prophet_predictor.predict(stop1, stop2, timestamp)
        predictions['prophet'] = prophet_delay

        # Flow network propagation (based on current delays)
        current_delays = {(stop1, stop2): 0.0}
        propagated = self.flow_network.propagate_delays([(stop1, stop2)], current_delays)
        flow_delay = propagated.get((stop1, stop2), 0.0)
        predictions['flow'] = flow_delay

        # Google Maps prediction
        gmaps_delay = self.gmaps_predictor.predict_delay(stop1, stop2, base_time, timestamp)
        predictions['gmaps'] = gmaps_delay

        # LSTM prediction
        lstm_delay = self.lstm_predictor.predict(stop1, stop2, timestamp, self.database)
        predictions['lstm'] = lstm_delay

        # Ensemble prediction (weighted average)
        ensemble = sum(predictions[k] * self.weights[k] for k in predictions.keys())
        predictions['ensemble'] = ensemble

        return predictions

    def get_routes_with_predictions(self, stop: Stop, timestamp: datetime) -> List[Edge]:
        """
        Enhanced version of get_routes that includes predicted delays.
        """
        from db import get_routes

        # Get base routes
        edges = get_routes(self.database, stop, timestamp)

        # Add predictions to each edge
        enhanced_edges = []
        for edge in edges:
            trip = self.database.trips[edge.trip_uuid]
            route_stops = trip.route.stops
            idx = route_stops.index(stop)
            next_stop = route_stops[idx + 1]

            # Get base time
            base_time = (trip.timestamps[idx + 1] - trip.timestamps[idx]).total_seconds()

            # Predict delays
            predictions = self.predict_delay(stop, next_stop, edge.start_timestamp, base_time)

            # Update edge time with predicted delay
            predicted_delay = predictions['ensemble']
            edge.time = int(base_time + predicted_delay)

            enhanced_edges.append(edge)

        return enhanced_edges

    def save_models(self, directory: str = './models'):
        """Save all trained models."""
        os.makedirs(directory, exist_ok=True)

        self.prophet_predictor.save(os.path.join(directory, 'prophet_models.pkl'))
        self.lstm_predictor.save(os.path.join(directory, 'lstm_model.pth'))

        print(f"Models saved to {directory}")

    def load_models(self, directory: str = './models'):
        """Load all trained models."""
        self.prophet_predictor.load(os.path.join(directory, 'prophet_models.pkl'))
        self.lstm_predictor.load(os.path.join(directory, 'lstm_model.pth'))
        self.flow_network.build_network()

        self.trained = True
        print(f"Models loaded from {directory}")


# Example usage
if __name__ == "__main__":
    from db_setup import db

    # Initialize predictor
    predictor = UnifiedDelayPredictor(
        database=db,
        google_maps_api_key=os.environ.get('GOOGLE_MAPS_API_KEY')
    )

    # Train models (do this once, then save)
    # predictor.train_all(epochs=50)
    # predictor.save_models('./models')

    # Or load pre-trained models
    # predictor.load_models('./models')

    # Make predictions
    if len(db.stops) >= 2:
        stops = list(db.stops.values())
        stop1, stop2 = stops[0], stops[1]

        predictions = predictor.predict_delay(
            stop1, stop2,
            timestamp=datetime.now() + timedelta(hours=1),
            base_time=300  # 5 minutes base time
        )

        print(f"\nDelay predictions for {stop1.short_name} -> {stop2.short_name}:")
        print(f"  Prophet: {predictions['prophet']:.1f} seconds")
        print(f"  Flow Network: {predictions['flow']:.1f} seconds")
        print(f"  Google Maps: {predictions['gmaps']:.1f} seconds")
        print(f"  LSTM: {predictions['lstm']:.1f} seconds")
        print(f"  Ensemble: {predictions['ensemble']:.1f} seconds")

        # Get enhanced routes with predictions
        enhanced_routes = predictor.get_routes_with_predictions(stop1, datetime.now())
        print(f"\nFound {len(enhanced_routes)} routes from {stop1.short_name}")
