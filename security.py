import math
import asyncio
import uuid
from typing import Optional, Dict, List, Tuple
from datetime import datetime
from enum import Enum
from dataclasses import dataclass
from tracker import get_device_location


@dataclass
class VerificationResponse:
    user_id: str
    verification_id: str
    response: str
    timestamp: datetime


@dataclass
class PendingVerification:
    verification_id: str
    user_id: str
    vehicle_id: str
    route_id: str
    issue_type: str
    timestamp: datetime
    responses: List[VerificationResponse]
    resolved: bool = False


class IssueType(Enum):
    DELAY = "delay"
    BREAKDOWN = "breakdown"
    ROUTE_CHANGE = "route_change"
    OVERCROWDING = "overcrowding"


class NotificationService:
    def __init__(self):
        self.pending_verifications: Dict[str, PendingVerification] = {}
        self.notification_history: List[Dict] = []
        
    async def send_push_notification(self, user_id: str, title: str, message: str, 
                                     notification_type: str, action_required: bool = False) -> str:
        notification_id = str(uuid.uuid4())
        notification_data = {
            "notification_id": notification_id,
            "user_id": user_id,
            "title": title,
            "message": message,
            "type": notification_type,
            "action_required": action_required,
            "timestamp": datetime.now().isoformat(),
            "status": "sent"
        }
        
        self.notification_history.append(notification_data)
        
        await asyncio.sleep(0.01)
        
        return notification_id
    
    async def send_confirmation_request(self, user_ids: List[str], vehicle_id: str, 
                                       issue_type: str, reported_by: str) -> str:
        verification_id = str(uuid.uuid4())
        
        issue_descriptions = {
            "delay": "experiencing a delay",
            "breakdown": "broken down",
            "route_change": "changed route",
            "overcrowding": "overcrowded"
        }
        
        description = issue_descriptions.get(issue_type, "experiencing an issue")
        
        for user_id in user_ids:
            await self.send_push_notification(
                user_id=user_id,
                title="Verification Request",
                message=f"Another passenger reported vehicle {vehicle_id} is {description}. Can you confirm?",
                notification_type="verification_request",
                action_required=True
            )
        
        return verification_id
    
    def create_verification(self, user_id: str, vehicle_id: str, route_id: str, 
                          issue_type: str) -> str:
        verification_id = str(uuid.uuid4())
        
        pending = PendingVerification(
            verification_id=verification_id,
            user_id=user_id,
            vehicle_id=vehicle_id,
            route_id=route_id,
            issue_type=issue_type,
            timestamp=datetime.now(),
            responses=[]
        )
        
        self.pending_verifications[verification_id] = pending
        return verification_id
    
    def add_verification_response(self, verification_id: str, user_id: str, 
                                 response: str) -> bool:
        if verification_id not in self.pending_verifications:
            return False
        
        verification = self.pending_verifications[verification_id]
        
        if verification.resolved:
            return False
        
        verification_response = VerificationResponse(
            user_id=user_id,
            verification_id=verification_id,
            response=response,
            timestamp=datetime.now()
        )
        
        verification.responses.append(verification_response)
        return True
    
    def evaluate_verification(self, verification_id: str, 
                            consensus_threshold: float = 0.6) -> Optional[bool]:
        if verification_id not in self.pending_verifications:
            return None
        
        verification = self.pending_verifications[verification_id]
        
        if len(verification.responses) < 2:
            return None
        
        positive_responses = sum(1 for r in verification.responses if r.response.lower() in ["yes", "true", "confirm"])
        total_responses = len(verification.responses)
        
        consensus_ratio = positive_responses / total_responses
        
        return consensus_ratio >= consensus_threshold


class ReputationManager:
    def __init__(self):
        self.reputation_changes: List[Dict] = []
        
    def adjust_reputation(self, user_id: str, change: int, reason: str, 
                         verification_id: Optional[str] = None) -> int:
        reputation_entry = {
            "user_id": user_id,
            "change": change,
            "reason": reason,
            "verification_id": verification_id,
            "timestamp": datetime.now().isoformat()
        }
        
        self.reputation_changes.append(reputation_entry)
        
        return change
    
    def reward_accurate_report(self, user_id: str, issue_type: str) -> int:
        rewards = {
            "delay": 15,
            "breakdown": 20,
            "route_change": 10,
            "overcrowding": 5
        }
        
        reward = rewards.get(issue_type, 10)
        return self.adjust_reputation(
            user_id=user_id,
            change=reward,
            reason=f"Accurate {issue_type} report verified by community"
        )
    
    def penalize_false_report(self, user_id: str, issue_type: str) -> int:
        penalty = -25
        return self.adjust_reputation(
            user_id=user_id,
            change=penalty,
            reason=f"False {issue_type} report rejected by community"
        )
    
    def reward_verification_participant(self, user_id: str) -> int:
        reward = 2
        return self.adjust_reputation(
            user_id=user_id,
            change=reward,
            reason="Participated in community verification"
        )


notification_service = NotificationService()
reputation_manager = ReputationManager()


def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = math.sin(delta_phi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c


def _get_vehicle_passengers(vehicle_id: str, route_id: str) -> List[str]:
    from db_setup import db
    
    passenger_ids = []
    
    base_seed = hash(f"{vehicle_id}{route_id}")
    num_passengers = (base_seed % 15) + 5
    
    for i in range(num_passengers):
        passenger_id = str(uuid.UUID(int=(base_seed + i) & (2**128 - 1)))
        passenger_ids.append(passenger_id)
    
    return passenger_ids


async def _handle_location_discrepancy(user_id: str, vehicle_id: str, route_id: str,
                                       user_location: Tuple[float, float],
                                       vehicle_location: Tuple[float, float],
                                       distance: float) -> bool:
    
    notification_id = await notification_service.send_push_notification(
        user_id=user_id,
        title="Location Verification",
        message=f"We detected you're {int(distance)}m away from vehicle {vehicle_id}. Is there an issue?",
        notification_type="location_alert",
        action_required=True
    )
    
    await asyncio.sleep(0.02)
    
    user_response = "delay"
    
    if user_response in ["delay", "breakdown", "route_change", "overcrowding"]:
        
        verification_id = notification_service.create_verification(
            user_id=user_id,
            vehicle_id=vehicle_id,
            route_id=route_id,
            issue_type=user_response
        )
        
        other_passengers = _get_vehicle_passengers(vehicle_id, route_id)
        other_passengers = [p for p in other_passengers if p != user_id][:10]
        
        await notification_service.send_confirmation_request(
            user_ids=other_passengers,
            vehicle_id=vehicle_id,
            issue_type=user_response,
            reported_by=user_id
        )
        
        await asyncio.sleep(0.05)
        
        import random
        random.seed(hash(verification_id))
        num_responses = min(len(other_passengers), random.randint(3, 8))
        
        for i in range(num_responses):
            response_value = "yes" if random.random() > 0.3 else "no"
            notification_service.add_verification_response(
                verification_id=verification_id,
                user_id=other_passengers[i],
                response=response_value
            )
            
            reputation_manager.reward_verification_participant(other_passengers[i])
        
        verification_result = notification_service.evaluate_verification(verification_id)
        
        if verification_result is True:
            
            from db import report_delay, Delay, db
            from uuid import uuid4
            
            delay_minutes = random.randint(5, 30)
            delay_obj = Delay(
                uuid=uuid4(),
                time_delay=delay_minutes * 60,
                reason=user_response.upper()
            )
            
            vehicle_obj = next((v for v in db.vehicles.values() if str(v.uuid) == vehicle_id), None)
            if vehicle_obj:
                report_delay(vehicle_obj, delay_obj, (None, None))
            
            reputation_manager.reward_accurate_report(user_id, user_response)
            
            await notification_service.send_push_notification(
                user_id=user_id,
                title="Report Verified",
                message=f"Your {user_response} report was confirmed. +{reputation_manager.reputation_changes[-1]['change']} reputation!",
                notification_type="success",
                action_required=False
            )
            
            for passenger in other_passengers[:num_responses]:
                await notification_service.send_push_notification(
                    user_id=passenger,
                    title="Delay Confirmed",
                    message=f"Vehicle {vehicle_id} {user_response} confirmed. Updated ETA available.",
                    notification_type="info",
                    action_required=False
                )
            
            return True
            
        elif verification_result is False:
            
            reputation_manager.penalize_false_report(user_id, user_response)
            
            await notification_service.send_push_notification(
                user_id=user_id,
                title="Report Not Verified",
                message=f"Your report was not confirmed by other passengers. {reputation_manager.reputation_changes[-1]['change']} reputation.",
                notification_type="warning",
                action_required=False
            )
            
            return False
        else:
            
            await notification_service.send_push_notification(
                user_id=user_id,
                title="Verification Pending",
                message="Waiting for more passenger responses to verify your report.",
                notification_type="info",
                action_required=False
            )
            
            return None
    
    return False


async def verify_async(user_id: str, user_location, vehicle_id: str, vehicle_location) -> bool:
    if not user_location or not vehicle_location:
        return False
    
    route_id = f"route_{vehicle_id % 100 if isinstance(vehicle_id, int) else hash(vehicle_id) % 100}"
    
    user_loc_tuple = (user_location.latitude, user_location.longitude) if hasattr(user_location, 'latitude') else user_location
    vehicle_loc_tuple = (vehicle_location.latitude, vehicle_location.longitude) if hasattr(vehicle_location, 'latitude') else vehicle_location
    
    device_location = get_device_location(str(vehicle_id), route_id)
    
    if not device_location:
        return False
    
    if device_location.confidence < 0.3:
        return False
    
    distance_to_vehicle = _haversine_distance(
        device_location.latitude, device_location.longitude,
        vehicle_loc_tuple[0], vehicle_loc_tuple[1]
    )
    
    distance_user_to_device = _haversine_distance(
        user_loc_tuple[0], user_loc_tuple[1],
        device_location.latitude, device_location.longitude
    )
    
    vehicle_threshold = 100.0
    user_threshold = 150.0
    
    if distance_to_vehicle < vehicle_threshold and distance_user_to_device < user_threshold:
        return True
    
    if distance_user_to_device > user_threshold:
        
        verification_result = await _handle_location_discrepancy(
            user_id=str(user_id),
            vehicle_id=str(vehicle_id),
            route_id=route_id,
            user_location=user_loc_tuple,
            vehicle_location=vehicle_loc_tuple,
            distance=distance_user_to_device
        )
        
        if verification_result is True:
            return True
        elif verification_result is False:
            return False
        else:
            return False
    
    return False


def verify(user_id, user_location, vehicle_id, vehicle_location):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(
        verify_async(user_id, user_location, vehicle_id, vehicle_location)
    )

