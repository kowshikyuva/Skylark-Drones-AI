"""Drone inventory management functionality."""
from typing import List, Optional
from datetime import date

from .models import Drone


class InventoryManager:
    """Manages drone fleet inventory and queries."""
    
    def __init__(self, drones: List[Drone]):
        self.drones = {d.drone_id: d for d in drones}
    
    def get_drone(self, drone_id: str) -> Optional[Drone]:
        """Get drone by ID."""
        return self.drones.get(drone_id)
    
    def get_available_drones(self) -> List[Drone]:
        """Get all currently available drones."""
        return [d for d in self.drones.values() if d.is_available()]
    
    def find_drones_by_capability(self, required_capabilities: List[str]) -> List[Drone]:
        """Find available drones with specified capabilities."""
        return [d for d in self.get_available_drones() if d.has_capability(required_capabilities)]
    
    def find_drones_by_location(self, location: str) -> List[Drone]:
        """Find available drones at specified location."""
        return [d for d in self.get_available_drones() if d.current_location == location]
    
    def find_drones_by_weather(self, weather: str) -> List[Drone]:
        """Find available drones rated for specified weather."""
        return [d for d in self.get_available_drones() if d.can_fly_in_weather(weather)]
    
    def find_drones_for_mission(self, required_capabilities: List[str], 
                               weather: str,
                               location: str) -> List[Drone]:
        """Find drones qualified for a mission."""
        candidates = []
        for drone in self.get_available_drones():
            if (drone.has_capability(required_capabilities) and 
                drone.can_fly_in_weather(weather)):
                candidates.append(drone)
        
        # Sort by location match (same location first) and daily rate (cheaper first)
        candidates.sort(key=lambda d: (d.current_location != location, d.daily_rate))
        return candidates
    
    def assign_drone_to_mission(self, drone_id: str, mission_id: str) -> bool:
        """Assign drone to mission."""
        if drone_id not in self.drones:
            return False
        self.drones[drone_id].current_assignment = mission_id
        return True
    
    def unassign_drone(self, drone_id: str) -> bool:
        """Remove drone from current assignment."""
        if drone_id not in self.drones:
            return False
        self.drones[drone_id].current_assignment = None
        return True
    
    def update_drone_status(self, drone_id: str, new_status: str) -> bool:
        """Update drone status (Active/Maintenance/Standby)."""
        if drone_id not in self.drones:
            return False
        self.drones[drone_id].status = new_status
        return True
    
    def flag_maintenance(self, drone_id: str, maintenance_date: date) -> bool:
        """Flag drone for maintenance."""
        if drone_id not in self.drones:
            return False
        self.drones[drone_id].maintenance_due_date = maintenance_date
        self.drones[drone_id].status = "Maintenance"
        return True
    
    def get_fleet_summary(self) -> dict:
        """Get summary statistics of drone fleet."""
        active = len([d for d in self.drones.values() if d.status == "Active"])
        maintenance = len([d for d in self.drones.values() if d.status == "Maintenance"])
        standby = len([d for d in self.drones.values() if d.status == "Standby"])
        assigned = len([d for d in self.drones.values() if d.current_assignment])
        
        return {
            "total_drones": len(self.drones),
            "active": active,
            "maintenance": maintenance,
            "standby": standby,
            "available": len(self.get_available_drones()),
            "assigned": assigned,
            "unassigned": len(self.get_available_drones()) - assigned,
        }
    
    def get_maintenance_alerts(self) -> List[Drone]:
        """Get drones with upcoming or overdue maintenance."""
        overdue = []
        for drone in self.drones.values():
            if drone.is_maintenance_due():
                overdue.append(drone)
        return overdue
