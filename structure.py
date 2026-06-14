from collections import deque
import time
from enum import Enum
from dataclasses import dataclass, field

from typing import List, Optional, Dict

class Direction(Enum):
    UP = "UP"
    DOWN = "DOWN"
    IDLE = "IDLE"

class ElevatorStatus(Enum):
    MOVING = "MOVING"
    IDLE = "IDLE"
    FAULT = "FAULT"
    DOOR_OPEN = "DOOR_OPEN"

class Building:
    def __init__(self,number_of_floors: int, number_of_lifts:int, total_energy:float):
        self.num_floors = number_of_floors
        self.num_of_lifts = number_of_lifts

        self.total_energy = total_energy
        self.total_energy_consumed = 0.0
        self.total_energy_remaining = total_energy

        self.global_start_time = time.time()
        self.floors = []
        self.lifts = []

    def initialize(self, floors, lifts):
        self.floors = floors
        self.lifts = lifts

    def update_energy(self, energy_used: float):
        self.total_energy_consumed += energy_used
        self.total_energy_remaining= self.total_energy - self.total_energy_consumed

    def get_energy_info(self):
        return self.total_energy_consumed, self.total_energy_remaining

    def get_global_time(self):
        return int(time.time() - self.global_start_time)
    
    def display_status(self):
        print("BUILDING STATUS")
        print(f"Floors: {self.num_floors}")
        print(f"Lifts: {self.num_of_lifts}")
        print(f"Global Time: {self.get_global_time()}")
        print(f"Energy Consumed: {self.total_energy_consumed}")
        print(f"Energy Remaining: {self.total_energy_remaining}")

@dataclass
class Passenger:
    id: str
    current_floor: int
    direction_selected: Direction

@dataclass
class RequestExternal:
    id: str
    floor: int
    direction: Direction
    passenger_id: str
    status: str = "PENDING"
    assigned_elevator: Optional[int] = None

#RESPONSE CLASS EMBEDDED IN A REQUEST (SE)
class Response:
    pass

class RequestQueue:
    def __init__(self):

        self.pending_floor_requests = []
        self.active_floor_requests = []

    def add_floor_request(self, request):
        if request not in self.pending_floor_requests:
                self.pending_floor_requests.append(request)

#multi threaded 
class Scheduler:
    def __init__(self):
        pass
    def submit_request(self, request: RequestExternal):
        pass

class Floor:
    def __init__(self, number: int, height: float):
        self.number = number          
        self.height = height         

        self.waiting_passengers: List[Passenger] = []
        self.up_request_pending = False
        self.down_request_pending = False
        self.assigned_elevator_id: Optional[int] = None


    def add_passenger(self, passenger: Passenger):
        self.waiting_passengers.append(passenger)
        if passenger.direction_selected == Direction.UP:
            self.up_request_pending = True
        else:
            self.down_request_pending = True

        request = RequestExternal(
        id=f"R-{passenger.id}",
        floor=self.number,
        direction=passenger.direction_selected,
        passenger_id=passenger.id)

        Scheduler.submit_request(request)

    def display_status(self):
        print(f"Floor {self.number}")
        print(f"UP Pending: {self.up_request_pending}")
        print(f"DOWN Pending: {self.down_request_pending}")
        print(f"Assigned Elevator: " f"{self.assigned_elevator_id}")


class Elevator:
    def __init__(self, elevator_id, max_capacity, speed=1):
        self.id = elevator_id

        self.working = True
        self.emergency = False

        self.current_capacity = 0
        self.max_capacity = max_capacity
        self.is_overloaded = False

        self.current_floor = 0
        self.target_floor = None

        self.direction = "IDLE"
        self.status = "IDLE"

        self.floor_queue = deque()

        self.speed = speed

        self.fan_on = False

    def remaining_capacity(self):
        return self.max_capacity - self.current_capacity

    def load_passengers(self, count):
        if self.current_capacity + count > self.max_capacity:
            self.is_overloaded = True
            print(f"Elevator {self.id} overloaded!")
            return False
        
        self.current_capacity += count
        self.status = "LOADING"
        return True

    def unload_passengers(self, count):
        self.current_capacity = self.current_capacity - count
        self.is_overloaded = False
        self.status = "UNLOADING"

    def add_stop(self, floor):
        if floor not in self.floor_queue:
            self.floor_queue.append(floor)

    def travel_time(self, destination_floor):
        floors = abs(destination_floor - self.current_floor)
        return floors / self.speed

    def move():
        return 9
    
    def trigger_emergency(self):
        self.emergency = True
        self.working = False
        self.status = "IDLE"

    def clear_emergency(self):
        self.emergency = False
        self.working = True
