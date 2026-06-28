from collections import deque
import time
from enum import Enum
from dataclasses import dataclass
import heapq
from typing import List, Optional
import random

class Direction(Enum):
    UP = "UP"
    DOWN = "DOWN"
    IDLE = "IDLE"

class ElevatorStatus(Enum):
    MOVING = "MOVING"
    IDLE = "IDLE"
    FAULT = "FAULT"
    DOOR_OPEN = "DOOR_OPEN"
    DOOR_CLOSE = "DOOR_CLOSE"
    LOADING = "LOADING"
    UNLOADING = "UNLOADING"

class RequestType(Enum):
    CALL = "CALL"
    FAN = "FAN"
    DOOR = "DOOR"
    FLOOR_SELECT = "FLOOR_SELECT"

@dataclass
class Passenger:
    id: str
    current_floor: int
    destination_floor: int
    direction_selected: Direction

@dataclass
class Request:
    id: str
    req_type: RequestType

    floor: Optional[int] = None
    direction: Optional[Direction] = None
    destination_floor: Optional[int] = None

    elevator_id: Optional[int] = None
    action: Optional[str] = None

    status: str = "PENDING"
    assigned_elevator: Optional[int] = None

@dataclass
class Response:
    request_id: str
    assigned_elevator_id: Optional[int] = None
    status: str = "ASSIGNED"
    message: str = ""
    success: bool = True

class RequestQueue:
    def __init__(self):
        self.queue = deque()
        self.pending_keys = set()

    def add_request(self, request: Request):
        if request.req_type == RequestType.CALL:
            key = (request.floor, request.direction)
            if key in self.pending_keys:
                return Response(request_id=request.id,status="ASSIGNED",success=False,message="Request already processed")    
            self.pending_keys.add(key)
        self.queue.append(request)

    def get_request(self):
        if not self.queue:
            return None
        request = self.queue.popleft()
        if request.req_type == RequestType.CALL:
            self.pending_keys.discard((request.floor, request.direction))
        return request

    def queue_size(self):
        return len(self.queue)

class Scheduler:
    def __init__(self, request_queue: RequestQueue, elevators: List["Elevator"]):
        self.req_queue = request_queue
        self.elevators = elevators

    def check_queue(self):
        responses = []
        n = self.req_queue.queue_size()
        for i in range(n):
            request = self.req_queue.get_request()
            if request is None:
                break
            response = self.process(request)
            if response:
                responses.append(response)
        return responses

    def process(self, request: Request):

        if request.req_type == RequestType.CALL:
            response = self.assign_elevator(request)
            if response:
                return response
            else:
                self.req_queue.add_request(request)
                return Response(request_id=request.id,status="FAILED",success=False,message="NO elevator currently available")
                
        elif request.req_type == RequestType.FAN:
            return self.handle_fan_request(request)
        
        elif request.req_type == RequestType.DOOR:
            return self.handle_door_request(request)
        
        elif request.req_type == RequestType.FLOOR_SELECT:
            return self.handle_floor_select(request)
        else:
            return Response(request_id=request.id,status="FAILED",success=False,message="Unknown Request")

    def assign_elevator(self, request):
        best_elevator = None
        best_cost = float('inf')

        for elevator in self.elevators:
            if not elevator.working or elevator.is_overloaded:
                continue
            
            dist_cost = self.distance_cost(request.floor, request.direction, elevator)
            load_cost = self.loading_cost(elevator)
            cost = dist_cost + load_cost
            
            if cost < best_cost:
                best_cost = cost
                best_elevator = elevator

        if best_elevator is None:
            return None

        best_elevator.add_stop(request.floor)
        best_elevator.pick_up.add(request.floor) 
        request.assigned_elevator = best_elevator.id
        best_elevator.status = ElevatorStatus.MOVING
        request.status = "ASSIGNED"

        return Response(request_id=request.id,assigned_elevator_id=best_elevator.id,status="ASSIGNED",success=True,message=f"Elevator {best_elevator.id} assigned")

    def distance_cost(self, floor, direction, elevator):
        distance = abs(elevator.current_floor - floor)
        if elevator.direction == Direction.IDLE:
            return distance
        if (elevator.direction == Direction.UP and direction == Direction.UP and floor >= elevator.current_floor):
            return distance
        if (elevator.direction == Direction.DOWN and direction == Direction.DOWN and floor <= elevator.current_floor):
            return distance
        if elevator.direction == Direction.UP:
            if not elevator.up_stops:
                return distance
            furthest_floor = max(elevator.up_stops)
            return abs(furthest_floor - elevator.current_floor) + abs(furthest_floor - floor)
        if elevator.direction == Direction.DOWN:
            if not elevator.down_stops:
                return distance
            furthest_floor = -min(elevator.down_stops)
            return abs(elevator.current_floor - furthest_floor) + abs(furthest_floor - floor)
        return distance

    def loading_cost(self, elevator):
        if elevator.is_overloaded:
            return 1000000
        percentage_occupied = float(elevator.current_capacity / elevator.max_capacity) * 100
        if percentage_occupied < 50:
            return 0
        else:
            return ((percentage_occupied - 50) / 50 * 10) ** 2

    def handle_floor_select(self, request: Request):
        elevator = self.elevators[request.elevator_id]
        target = request.destination_floor
        elevator.press_floor_button(target)
        elevator.drop_off.add(target) 
        return Response(request_id=request.id,status="SUCCESS",success=True,message=f"Floor {request.destination_floor} added to elevator {elevator.id}")

    def handle_fan_request(self, request: Request):
        elevator = self.elevators[request.elevator_id]
        action = request.action
        if action == "ON":
            if elevator.fan_on:
                return Response(request_id=request.id, assigned_elevator_id=elevator.id, status="SUCCESS", success=True, message="Fan already ON")
            elevator.fan_on = True
            return Response(request_id=request.id, assigned_elevator_id=elevator.id, status="SUCCESS", success=True, message="Fan turned ON")
        elif action == "OFF":
            if not elevator.fan_on:
                return Response(request_id=request.id, assigned_elevator_id=elevator.id, status="SUCCESS", success=True, message="Fan already OFF")
            elevator.fan_on = False
            return Response(request_id=request.id, assigned_elevator_id=elevator.id, status="SUCCESS", success=True, message="Fan turned OFF")
        return Response(request_id=request.id, status="FAILED", success=False, message="Invalid fan action")

    def handle_door_request(self, request: Request):
        elevator = self.elevators[request.elevator_id]
        action = request.action
        if action == "OPEN":
            if elevator.status == ElevatorStatus.DOOR_OPEN:
                return Response(request_id=request.id, assigned_elevator_id=elevator.id, status="SUCCESS", success=True, message="Doors already open")
            if elevator.status not in (ElevatorStatus.IDLE, ElevatorStatus.DOOR_CLOSE, ElevatorStatus.LOADING, ElevatorStatus.UNLOADING):
                return Response(request_id=request.id, status="FAILED", success=False, message=f"Cannot open doors while {elevator.status.value}")
            elevator.status = ElevatorStatus.DOOR_OPEN
            elevator.door_open_ticks = 0
            return Response(request_id=request.id, assigned_elevator_id=elevator.id, status="SUCCESS", success=True, message="Doors opened")
        elif action == "CLOSE":
            if elevator.status != ElevatorStatus.DOOR_OPEN:
                return Response(request_id=request.id, status="FAILED", success=False, message="Doors are not open")
            elevator.status = ElevatorStatus.DOOR_CLOSE
            return Response(request_id=request.id, assigned_elevator_id=elevator.id, status="SUCCESS", success=True, message="Doors closed")
        return Response(request_id=request.id, status="FAILED", success=False, message="Invalid door action")

class Floor:
    def __init__(self, number: int, height: float, request_queue: RequestQueue):

        self.number = number
        self.height = height

        self.up_request_pending = False
        self.down_request_pending = False

        self.assigned_up_elevator: Optional[int] = None
        self.assigned_down_elevator: Optional[int] = None

        self.request_queue = request_queue

    def set_assigned_elevator(self, direction: Direction, elevator_id: int):
        if direction == Direction.UP:
            self.assigned_up_elevator = elevator_id
        else:
            self.assigned_down_elevator = elevator_id

    def clear_request(self, direction: Direction):
        if direction == Direction.UP:
            self.up_request_pending = False
            self.assigned_up_elevator = None
        else:
            self.down_request_pending = False
            self.assigned_down_elevator = None

    def display_status(self):
        print(f"Floor {self.number} | UP Pending: {self.up_request_pending} | DOWN Pending: {self.down_request_pending}")

class Building:
    def __init__(self, number_of_floors: int, number_of_lifts: int, total_energy: float):

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
        self.total_energy_remaining = self.total_energy - self.total_energy_consumed

    def get_global_time(self):
        return int(time.time() - self.global_start_time)

    def display_status(self):
        print("BUILDING STATUS")
        print(f"Floors: {self.num_floors} | Lifts: {self.num_of_lifts} | Time: {self.get_global_time()}")
        print(f"Energy Consumed: {self.total_energy_consumed} | Remaining: {self.total_energy_remaining}")

class Elevator:
    def __init__(self, request_queue, elevator_id, max_capacity, speed=1):
        self.id = elevator_id
        self.request_queue = request_queue
        
        self.working = True
        self.emergency = False
        
        self.current_capacity = 0
        self.max_capacity = max_capacity
        self.is_overloaded = False
        self.lift_score = 100
        
        self.current_floor = 0
        self.target_floor = None
        self.direction = Direction.IDLE
        self.status = ElevatorStatus.IDLE
        
        self.passengers = []
        
        
        self.pick_up = set()
        self.drop_off = set()
        
        self.up_stops = []
        self.down_stops = []
        
        self.speed = speed
        self.fan_on = False
        self.door_open_ticks = 0   

    def update_direction(self):
        if self.direction == Direction.IDLE:
            if self.up_stops:
                self.direction = Direction.UP
            elif self.down_stops:
                self.direction = Direction.DOWN
        elif self.direction == Direction.UP and not self.up_stops:
            self.direction = Direction.DOWN if self.down_stops else Direction.IDLE
        elif self.direction == Direction.DOWN and not self.down_stops:
            self.direction = Direction.UP if self.up_stops else Direction.IDLE

    def remaining_capacity(self):
        return self.max_capacity - self.current_capacity

    def move(self):
    
        if not self.working or self.direction == Direction.IDLE:
            self.status = ElevatorStatus.IDLE
            return
        if self.status in [ElevatorStatus.DOOR_OPEN, ElevatorStatus.LOADING, ElevatorStatus.UNLOADING]:
            return

        if self.direction == Direction.UP:
            if self.up_stops:
                next_floor = self.up_stops[0]
                if self.current_floor < next_floor:
                    self.current_floor += 1

                if self.current_floor == next_floor:
                    heapq.heappop(self.up_stops)
                    self.status = ElevatorStatus.DOOR_OPEN
                    self.door_open_ticks = 0

                    if next_floor in self.drop_off:
                        x = random.randint(0, len(self.passengers))
                        self.unload_passengers(x)
                        self.drop_off.remove(next_floor) 

                    if next_floor in self.pick_up:
                        y = random.randint(1, 5)
                        self.load_passengers(y)
                        if next_floor in self.pick_up: 
                            self.pick_up.remove(next_floor) 

                    self.update_direction()
                    self.status = ElevatorStatus.MOVING if self.direction != Direction.IDLE else ElevatorStatus.IDLE

        elif self.direction == Direction.DOWN:
            if self.down_stops:
                next_floor = -self.down_stops[0]   
                if self.current_floor > next_floor:
                    self.current_floor -= 1

                if self.current_floor == next_floor:
                    self.status = ElevatorStatus.DOOR_OPEN
                    self.door_open_ticks = 0

                    if next_floor in self.drop_off:
                        x = random.randint(0, len(self.passengers))
                        self.unload_passengers(x)
                        self.drop_off.remove(next_floor) 

                    if next_floor in self.pick_up:
                        y = random.randint(1, 5)
                        self.load_passengers(y)
                        if next_floor in self.pick_up:
                            self.pick_up.remove(next_floor)

                    heapq.heappop(self.down_stops)   
                    self.update_direction()
                    self.status = ElevatorStatus.MOVING if self.direction != Direction.IDLE else ElevatorStatus.IDLE

    def load_passengers(self, count):
        self.status = ElevatorStatus.LOADING
        for _ in range(count):
            random_weight = round(random.uniform(30, 120), 2)
            if self.current_capacity + random_weight >= self.max_capacity:
                self.is_overloaded = True
                self.lift_score = 0
                break
            self.current_capacity += random_weight
            self.passengers.append(random_weight)

        self.lift_score = ((self.max_capacity - self.current_capacity) / self.max_capacity) * 100
        if self.lift_score > 10:
            return
        else:
            floors_to_abandon = list(self.pick_up) 
            for floor in floors_to_abandon:
                reassign_req = Request(
                    id=f"R-REASSIGN-{floor}-{random.randint(1000, 9999)}",
                    req_type=RequestType.CALL,
                    floor=floor,
                    status="PENDING"
                )
                if floor in self.up_stops:
                    self.up_stops.remove(floor)
                    heapq.heapify(self.up_stops)
                    reassign_req.direction = Direction.UP
                else:
                    if -floor in self.down_stops:
                        self.down_stops.remove(-floor)
                        heapq.heapify(self.down_stops)
                        reassign_req.direction = Direction.DOWN
                
                self.request_queue.add_request(reassign_req)
            
            self.pick_up.clear() 

    def unload_passengers(self, count):
        self.status = ElevatorStatus.UNLOADING
        if count == 0:   
            return

        count = min(count, len(self.passengers))
        exiting = random.sample(self.passengers, count)
        for passenger in exiting:
            self.passengers.remove(passenger)
        self.current_capacity = sum(self.passengers)
        self.is_overloaded = False

    def add_stop(self, floor):
        if floor > self.current_floor:
            if floor not in self.up_stops:
                heapq.heappush(self.up_stops, floor)
        elif floor < self.current_floor:
            if -floor not in self.down_stops:
                heapq.heappush(self.down_stops, -floor)
        else:
            self.status = ElevatorStatus.DOOR_OPEN
            self.door_open_ticks = 0
        self.update_direction()

    def press_floor_button(self, floor: int):
        if self.working:
            self.add_stop(floor)

class Simulation:
    def __init__(self, building: Building, scheduler: Scheduler):
        self.building = building
        self.scheduler = scheduler
        self.tick_count = 0

    def print_status(self):
        print(f"STATE  {self.tick_count} ")
        for elevator in self.building.lifts:
            down = [-x for x in elevator.down_stops]

            print(f"  Lift: {elevator.id}: Floor: {elevator.current_floor} "
                  f"Dir: {elevator.direction.value} Status: {elevator.status.value} "
                  f"{elevator.current_capacity:.2f} Remaining:{(elevator.max_capacity - elevator.current_capacity):.2f} "
                  f"up_stops {elevator.up_stops} down_stops {down}")

    def run(self, ticks=100):
        for i in range(ticks):
            self.step()
            self.print_status()         
            time.sleep(0.5)              

    def step(self):
        self.scheduler.check_queue()

        for elevator in self.building.lifts:
            if not elevator.working:
                continue

            if elevator.status == ElevatorStatus.DOOR_OPEN:
                elevator.door_open_ticks += 1
                if elevator.door_open_ticks >= 2:
                    elevator.status = ElevatorStatus.DOOR_CLOSE
                    elevator.update_direction()
                    if elevator.direction != Direction.IDLE:
                        elevator.status = ElevatorStatus.MOVING
                    else:
                        ElevatorStatus.IDLE

            elevator.move()

        self.tick_count += 1


