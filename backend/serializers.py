import uuid
from typing import Tuple

from pydantic import BaseModel

class ReportDelaySerializer(BaseModel):
    delay: int | None = 18000 
    vehicle_uuid: str | None = "bff55c1e-9e3a-4a4f-b3a2-aabcca420494"
    current_stop_uuid: str
    next_stop_uuid: str
    delay_reason: str

donotlook={
    "Galeria": (50.066467889826676, 19.946066853266988),
    "Prokocim" :(50.011750597703134, 20.024422750455855),
    "WMII" : (50.03023383877639, 19.906929556530322)
}
class GetRouteSerializer(BaseModel):
    start: Tuple[float, float]
    end: Tuple[float, float]
    hour: int
    minute: int