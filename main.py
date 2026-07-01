from fastapi import FastAPI,HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List
import uuid

from elevator_scheduler import (
    Direction, ElevatorStatus, RequestType,
    Request, RequestQueue, Scheduler,
    Floor, Building, Elevator, Simulation,
)

def default_elevator(n):
    return [{"max_capacity": 800.0, "speed": 1.0} for x in range(n)]

def default_floor(n):
    labels = [f"Floor {i}" for i in range(0, n)]
    return [{"height": 3.0, "label": labels[i]} for i in range(n)]

cfg = {
    "num_floors":      10,
    "num_elevators":   3,
    "total_energy":    10_000.0,
    "elevator_configs": default_elevator(3),
    "floor_configs":    default_floor(10),
}

def system(cfg):
    num_floors    = cfg["num_floors"]
    num_elevators = cfg["num_elevators"]
    elev_cfgs     = cfg["elevator_configs"]
    floor_cfgs    = cfg["floor_configs"]

    rq = RequestQueue()

    elevators = []
    for i in range(num_elevators):
           lift = Elevator(rq,elevator_id=i,max_capacity=elev_cfgs[i]["max_capacity"],speed=elev_cfgs[i].get("speed", 1.0),)
           elevators.append(lift)

    floors = []
    for f in range(num_floors):
        floor = Floor(number=f,height=floor_cfgs[f]["height"],request_queue=rq,)
        floors.append(floor)

    building  = Building(num_floors, num_elevators, cfg["total_energy"])
    building.initialize(floors, elevators)

    scheduler = Scheduler(rq, elevators)

    simulator   = Simulation(building, scheduler)
    return rq, elevators, floors, building, scheduler, simulator

request_queue, elevators, floors, building, scheduler, simulation = system(cfg)


app = FastAPI(title="SOES")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"], allow_headers=["*"],
)

class ElevatorConfiguration(BaseModel):
    max_capacity: float = Field(800.0, gt=0)
    speed:        float = Field(1.0,   gt=0)

class FloorConfiguration(BaseModel):
    height: float = Field(3.0, gt=0)
    label:  str   = ""

class Configuration(BaseModel):
    num_floors:      int   = Field(10,       ge=2,  le=100)
    num_elevators:   int   = Field(3,        ge=1,  le=20)
    total_energy:    float = Field(10_000.0, gt=0)
    elevator_configs: Optional[List[ElevatorConfiguration]] = None
    floor_configs:    Optional[List[FloorConfiguration]]    = None

class FloorRequest(BaseModel):
    floor:     int = Field(..., ge=0)
    direction: str = Field(..., pattern="^(UP|DOWN)$")

class SelectFloorRequest(BaseModel):
    elevator_id:       int = Field(..., ge=0)
    destination_floor: int = Field(..., ge=0)

class DoorRequest(BaseModel):
    elevator_id: int = Field(..., ge=0)
    action:      str = Field(..., pattern="^(OPEN|CLOSE)$")

class FanRequest(BaseModel):
    elevator_id: int = Field(..., ge=0)
    action:      str = Field(..., pattern="^(ON|OFF)$")

class TickRequest(BaseModel):
    steps: int = Field(1, ge=1, le=100)

def make_req(req_type, **kw):
    return Request(id=str(uuid.uuid1()), req_type=req_type, **kw)

def elevator_status(e: Elevator) -> dict:
    return dict(
        id=e.id,
        current_floor=e.current_floor,
        direction=e.direction.value,
        status=e.status.value,
        current_capacity=round(e.current_capacity, 2),
        remaining_capacity=round(e.max_capacity - e.current_capacity, 2),
        max_capacity=e.max_capacity,
        speed=e.speed,
        is_overloaded=e.is_overloaded,
        lift_score=round(e.lift_score, 2),
        working=e.working,
        fan_on=e.fan_on,
        up_stops=sorted(e.up_stops),
        down_stops=sorted([-x for x in e.down_stops]),
        pick_up=sorted(e.pick_up),
        drop_off=sorted(e.drop_off),
        passenger_count=len(e.passengers),
    )

def response(r) -> dict:
    return dict(request_id=r.request_id, assigned_elevator_id=r.assigned_elevator_id,
                status=r.status, success=r.success, message=r.message)

def ticks():
    responses = scheduler.check_queue()
    for elevator in elevators:
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
                    elevator.status = ElevatorStatus.IDLE
        elevator.move()
    simulation.tick_count += 1
    return responses


@app.get("/")
def root():
    return {"project": "SOES", "status": "running"}

@app.get("/config", tags=["System"])
def get_config():
    return cfg

@app.post("/configure", tags=["System"])
def configure(body: Configuration):
    global cfg, request_queue, elevators, floors, building, scheduler, simulation

    if body.elevator_configs:
        elev_configuration = []
        for e in body.elevator_configs:
            elev_configuration.append(e.model_dump())
    else:
        elev_configuration = default_elevator(body.num_elevators)


    while len(elev_configuration) < body.num_elevators:
        elev_configuration.append({"max_capacity": 800.0, "speed": 1.0})
    elev_configuration = elev_configuration[:body.num_elevators]

   
    if body.floor_configs:
        floor_configuration = []
        for e in body.floor_configs:
            floor_configuration.append(e.model_dump())
    else:
        floor_configuration = default_floor(body.num_floors)

    default_labels = [f"Floor {i}" for i in range(body.num_floors)]
    while len(floor_configuration) < body.num_floors:
        i = len(floor_configuration)
        floor_configuration.append({"height": 3.0, "label": default_labels[i]})
    floor_configuration = floor_configuration[:body.num_floors]

    cfg = {
        "num_floors":      body.num_floors,
        "num_elevators":   body.num_elevators,
        "total_energy":    body.total_energy,
        "elevator_configs": elev_configuration,
        "floor_configs":    floor_configuration,
    }
    request_queue, elevators, floors, building, scheduler, simulation = system(cfg)
    return cfg

@app.get("/status", tags=["System"])
def get_status():
    return dict(
        tick=simulation.tick_count,
        queue_size=request_queue.queue_size(),
        energy_consumed=building.total_energy_consumed,
        energy_remaining=building.total_energy_remaining,
        elevators=[elevator_status(e) for e in elevators],
        floor_configuration=cfg["floor_configs"],
    )

@app.get("/status/elevator/{elevator_id}", tags=["System"])
def get_elevator(elevator_id: int):
    if elevator_id < 0 or elevator_id >= cfg["num_elevators"]:
        raise HTTPException(404, f"Elevator {elevator_id} not found")
    return elevator_status(elevators[elevator_id])

@app.post("/tick", tags=["Simulation"])
def tick(body: TickRequest):
    all_responses = []
    for _ in range(body.steps):
        all_responses.extend([response(r) for r in ticks()])
        
    return dict(
        ticks_advanced=body.steps,
        current_tick=simulation.tick_count,
        scheduler_responses=all_responses,
        elevators=[elevator_status(e) for e in elevators],
        floor_configs=cfg["floor_configs"],
    )

@app.post("/request/call", tags=["Requests"])
def hall_call(body: FloorRequest):
    if body.floor >= cfg["num_floors"]:
        raise HTTPException(400, "Floor out of range")
    
    req = make_req(RequestType.CALL, floor=body.floor, direction=Direction[body.direction])
    request_queue.add_request(req)

    return dict(request_id=req.id, scheduler_responses=[response(r) for r in scheduler.check_queue()])

@app.post("/request/floor-select", tags=["Requests"])
def floor_select(body: SelectFloorRequest):

    if body.elevator_id >= cfg["num_elevators"]:
        raise HTTPException(400, "Invalid elevator_id")
    if body.destination_floor >=cfg["num_floors"]:
        raise HTTPException(400, "Destination out of range")
    req = make_req(RequestType.FLOOR_SELECT, elevator_id=body.elevator_id, destination_floor=body.destination_floor)
    request_queue.add_request(req)

    return dict(request_id=req.id, scheduler_responses=[response(r) for r in scheduler.check_queue()])

@app.post("/request/door", tags=["Requests"])
def door(body: DoorRequest):
    req = make_req(RequestType.DOOR, elevator_id=body.elevator_id, action=body.action)
    request_queue.add_request(req)

    return dict(request_id=req.id, scheduler_responses=[response(r) for r in scheduler.check_queue()])

@app.post("/request/fan", tags=["Requests"])
def fan(body: FanRequest):
    req = make_req(RequestType.FAN, elevator_id=body.elevator_id, action=body.action)
    request_queue.add_request(req)

    return dict(request_id=req.id, scheduler_responses=[response(r) for r in scheduler.check_queue()])

@app.post("/reset", tags=["Simulation"])
def reset():
    global request_queue, elevators, floors, building, scheduler, simulation
    request_queue, elevators, floors, building, scheduler, simulation = system(cfg)                                                                                                                    
    return {"message": "Simulation reset", "tick": 0}
