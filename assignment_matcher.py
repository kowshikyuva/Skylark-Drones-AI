"""Assignment matching and tracking."""
from typing import List, Optional, Tuple
from datetime import date
import uuid

from .models import Pilot, Drone, Mission


class AssignmentMatcher:
    """Matches pilots and drones to missions."""
    
    def __init__(self, pilots: List[Pilot], drones: List[Drone], missions: List[Mission]):
        self.pilots = {p.pilot_id: p for p in pilots}
        self.drones = {d.drone_id: d for d in drones}
        self.missions = {m.mission_id: m for m in missions}
    
    def find_best_pilot_match(self, mission: Mission) -> Optional[Tuple[Pilot, float]]:
        """Find best pilot for mission, returning (pilot, match_score)."""
        best_pilot = None
        best_score = -1
        
        for pilot in self.pilots.values():
            if pilot.status != "Available":
                continue
            if not pilot.is_available(mission.start_date, mission.end_date):
                continue
            if not pilot.has_skill(mission.required_skills):
                continue
            if not pilot.has_certification(mission.required_certifications):
                continue
            
            # Calculate match score
            score = 0
            
            # Skill match (base 50 points)
            score += 50
            
            # Experience bonus (max 20 points)
            experience_score = min(pilot.drone_experience_hours / 500 * 20, 20)
            score += experience_score
            
            # Location match (10 points)
            if pilot.current_location == mission.location:
                score += 10
            
            # Cost efficiency (max 20 points) - prefer cheaper pilots
            mission_cost = pilot.calculate_mission_cost(mission.duration_days)
            if mission_cost <= mission.budget:
                cost_efficiency = (1 - mission_cost / mission.budget) * 20
                score += max(0, cost_efficiency)
            
            # Already assigned penalty
            if pilot.current_assignment:
                score -= 5
            
            if score > best_score:
                best_score = score
                best_pilot = pilot
        
        return (best_pilot, best_score) if best_pilot else None
    
    def find_best_drone_match(self, mission: Mission) -> Optional[Tuple[Drone, float]]:
        """Find best drone for mission, returning (drone, match_score)."""
        best_drone = None
        best_score = -1
        
        for drone in self.drones.values():
            if not drone.is_available():
                continue
            if drone.is_maintenance_due():
                continue
            if not drone.has_capability(mission.required_skills):
                continue
            if not drone.can_fly_in_weather(mission.weather_forecast):
                continue
            
            # Calculate match score
            score = 0
            
            # Capability match (base 50 points)
            score += 50
            
            # Weather rating bonus (max 20 points)
            weather_rating_rank = {"Generic": 0, "IP42": 7, "IP43": 14, "IP45": 20}
            score += weather_rating_rank.get(drone.weather_rating, 0)
            
            # Location match (10 points)
            if drone.current_location == mission.location:
                score += 10
            
            # Cost efficiency (max 20 points)
            daily_cost = drone.daily_rate * mission.duration_days
            if daily_cost <= mission.budget:
                cost_efficiency = (1 - daily_cost / mission.budget) * 20
                score += max(0, cost_efficiency)
            
            if score > best_score:
                best_score = score
                best_drone = drone
        
        return (best_drone, best_score) if best_drone else None
    
    def match_mission(self, mission_id: str) -> Tuple[Optional[Pilot], Optional[Drone], dict]:
        """Match both pilot and drone to a mission."""
        mission = self.missions.get(mission_id)
        if not mission:
            return None, None, {"error": "Mission not found"}
        
        pilot_match = self.find_best_pilot_match(mission)
        drone_match = self.find_best_drone_match(mission)
        
        result = {
            "mission_id": mission_id,
            "pilot_match": pilot_match[0].pilot_id if pilot_match else None,
            "pilot_score": pilot_match[1] if pilot_match else 0,
            "drone_match": drone_match[0].drone_id if drone_match else None,
            "drone_score": drone_match[1] if drone_match else 0,
        }
        
        return pilot_match[0] if pilot_match else None, drone_match[0] if drone_match else None, result
    
    def get_active_assignments(self) -> List[dict]:
        """Get all active pilot and drone assignments."""
        assignments = []
        
        for mission in self.missions.values():
            if mission.assigned_pilot or mission.assigned_drone:
                assignment = {
                    "mission_id": mission.mission_id,
                    "project": mission.project_name,
                    "pilot": mission.assigned_pilot,
                    "drone": mission.assigned_drone,
                    "start_date": mission.start_date,
                    "end_date": mission.end_date,
                    "status": mission.status,
                }
                assignments.append(assignment)
        
        return assignments
    
    def reassign_pilot(self, mission_id: str, new_pilot_id: str) -> bool:
        """Reassign mission to different pilot."""
        if mission_id not in self.missions or new_pilot_id not in self.pilots:
            return False
        
        mission = self.missions[mission_id]
        
        # Unassign old pilot
        if mission.assigned_pilot and mission.assigned_pilot in self.pilots:
            old_pilot = self.pilots[mission.assigned_pilot]
            if old_pilot.current_assignment == mission_id:
                old_pilot.current_assignment = None
        
        # Assign new pilot
        mission.assigned_pilot = new_pilot_id
        self.pilots[new_pilot_id].current_assignment = mission_id
        return True
    
    def reassign_drone(self, mission_id: str, new_drone_id: str) -> bool:
        """Reassign mission to different drone."""
        if mission_id not in self.missions or new_drone_id not in self.drones:
            return False
        
        mission = self.missions[mission_id]
        
        # Unassign old drone
        if mission.assigned_drone and mission.assigned_drone in self.drones:
            old_drone = self.drones[mission.assigned_drone]
            if old_drone.current_assignment == mission_id:
                old_drone.current_assignment = None
        
        # Assign new drone
        mission.assigned_drone = new_drone_id
        self.drones[new_drone_id].current_assignment = mission_id
        return True
