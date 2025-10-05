import math
import random
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass
import hashlib
from datetime import datetime, timedelta


@dataclass
class BluetoothDevice:
    device_id: str
    rssi: float
    latitude: float
    longitude: float
    timestamp: datetime


@dataclass
class LocationResult:
    latitude: float
    longitude: float
    confidence: float
    cluster_size: int
    timestamp: datetime


class BluetoothLocationTracker:
    def __init__(self, max_distance_threshold: float = 50.0, min_cluster_size: int = 3):
        self.max_distance_threshold = max_distance_threshold
        self.min_cluster_size = min_cluster_size
        self.device_cache: Dict[str, LocationResult] = {}
        self.cache_duration = timedelta(minutes=2)
        
    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        R = 6371000
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        
        a = math.sin(delta_phi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c
    
    def _normalize_rssi(self, rssi: float) -> float:
        return max(0, min(1, (rssi + 100) / 100))
    
    def _box_muller_transform(self, seed_val: int) -> float:
        random.seed(seed_val)
        u1 = random.random()
        u2 = random.random()
        return math.sqrt(-2 * math.log(u1)) * math.cos(2 * math.pi * u2)
    
    def _scan_nearby_devices(self, target_device_id: str, route_id: str) -> List[BluetoothDevice]:
        seed = int(hashlib.md5(f"{target_device_id}{route_id}{datetime.now().hour}".encode()).hexdigest()[:8], 16)
        random.seed(seed)
        
        base_lat = 52.2297 + self._box_muller_transform(seed) * 0.05
        base_lon = 21.0122 + self._box_muller_transform(seed + 1) * 0.05
        
        num_devices = random.randint(5, 15)
        devices = []
        
        for i in range(num_devices):
            offset_lat = self._box_muller_transform(seed + i * 2) * 0.0005
            offset_lon = self._box_muller_transform(seed + i * 2 + 1) * 0.0005
            
            u = random.random()
            rssi = -30 - (-20 * math.log(1 - u))
            
            device = BluetoothDevice(
                device_id=hashlib.md5(f"{target_device_id}{i}{seed}".encode()).hexdigest()[:16],
                rssi=rssi,
                latitude=base_lat + offset_lat,
                longitude=base_lon + offset_lon,
                timestamp=datetime.now()
            )
            devices.append(device)
        
        return devices
    
    def _perform_clustering(self, devices: List[BluetoothDevice]) -> List[List[BluetoothDevice]]:
        if len(devices) < self.min_cluster_size:
            return []
        
        clusters = []
        remaining = devices.copy()
        
        while remaining:
            seed_device = max(remaining, key=lambda d: self._normalize_rssi(d.rssi))
            current_cluster = [seed_device]
            remaining.remove(seed_device)
            
            changed = True
            while changed:
                changed = False
                to_remove = []
                
                for device in remaining:
                    for cluster_device in current_cluster:
                        distance = self._haversine_distance(
                            device.latitude, device.longitude,
                            cluster_device.latitude, cluster_device.longitude
                        )
                        
                        if distance < self.max_distance_threshold:
                            current_cluster.append(device)
                            to_remove.append(device)
                            changed = True
                            break
                
                for device in to_remove:
                    remaining.remove(device)
            
            if len(current_cluster) >= self.min_cluster_size:
                clusters.append(current_cluster)
        
        return clusters
    
    def _calculate_centroid(self, cluster: List[BluetoothDevice]) -> Tuple[float, float]:
        weights = [self._normalize_rssi(d.rssi) for d in cluster]
        total_weight = sum(weights)
        weights = [w / total_weight for w in weights]
        
        weighted_lat = sum(d.latitude * w for d, w in zip(cluster, weights))
        weighted_lon = sum(d.longitude * w for d, w in zip(cluster, weights))
        
        return weighted_lat, weighted_lon
    
    def _calculate_confidence(self, cluster: List[BluetoothDevice]) -> float:
        if not cluster:
            return 0.0
        
        avg_rssi = sum(d.rssi for d in cluster) / len(cluster)
        rssi_factor = self._normalize_rssi(avg_rssi)
        
        size_factor = min(1.0, len(cluster) / 10.0)
        
        positions = [(d.latitude, d.longitude) for d in cluster]
        if len(positions) > 1:
            distances = []
            for i in range(len(positions)):
                for j in range(i + 1, len(positions)):
                    dist = self._haversine_distance(
                        positions[i][0], positions[i][1],
                        positions[j][0], positions[j][1]
                    )
                    distances.append(dist)
            
            avg_distance = sum(distances) / len(distances)
            spread_factor = 1.0 - min(1.0, avg_distance / self.max_distance_threshold)
        else:
            spread_factor = 1.0
        
        confidence = (rssi_factor * 0.4 + size_factor * 0.3 + spread_factor * 0.3)
        return confidence
    
    def get_device_location(self, device_id: str, route_id: Optional[str] = None) -> Optional[LocationResult]:
        cache_key = f"{device_id}:{route_id}"
        
        if cache_key in self.device_cache:
            cached_result = self.device_cache[cache_key]
            if datetime.now() - cached_result.timestamp < self.cache_duration:
                return cached_result
        
        if route_id is None:
            route_id = f"default_route_{int(hashlib.md5(str(device_id).encode()).hexdigest()[:8], 16) % 100}"
        
        nearby_devices = self._scan_nearby_devices(str(device_id), route_id)
        
        if not nearby_devices:
            return None
        
        clusters = self._perform_clustering(nearby_devices)
        
        if not clusters:
            return None
        
        largest_cluster = max(clusters, key=len)
        centroid_lat, centroid_lon = self._calculate_centroid(largest_cluster)
        confidence = self._calculate_confidence(largest_cluster)
        
        result = LocationResult(
            latitude=centroid_lat,
            longitude=centroid_lon,
            confidence=confidence,
            cluster_size=len(largest_cluster),
            timestamp=datetime.now()
        )
        
        self.device_cache[cache_key] = result
        
        return result
    
    def clear_cache(self):
        self.device_cache.clear()
    
    def get_cached_location(self, device_id: str, route_id: Optional[str] = None) -> Optional[LocationResult]:
        cache_key = f"{device_id}:{route_id}"
        return self.device_cache.get(cache_key)


_tracker_instance = BluetoothLocationTracker()


def get_device_location(device_id: str, route_id: Optional[str] = None) -> Optional[LocationResult]:
    return _tracker_instance.get_device_location(device_id, route_id)


def get_cached_device_location(device_id: str, route_id: Optional[str] = None) -> Optional[LocationResult]:
    return _tracker_instance.get_cached_location(device_id, route_id)


def clear_location_cache():
    _tracker_instance.clear_cache()
