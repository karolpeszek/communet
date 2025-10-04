from pydantic import BaseModel

class User(BaseModel):
    id: int

    def get_location(self):
        pass

    def change_reputation(self, diff):
        self.reputation+=diff

class Vehicle(BaseModel):
    id: int


    def get_location(self):
        pass


class Location(BaseModel):
    longitude: float
    latitude: float