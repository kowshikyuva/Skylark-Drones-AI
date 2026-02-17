"""Pilot roster management functionality."""
from typing import List, Optional
from datetime import date

from .models import Pilot


class RosterManager:
    """Manages pilot roster queries and operations."""
    
    def __init__(self, pilots: List[Pilot]):
        self.pilots = {p.pilot_id: p for p in pilots}
    
    def get_pilot(self, pilot_id: str) -> Optional[Pilot]:
        """Get pilot by ID."""
        return self.pilots.get(pilot_id)
    
    def get_available_pilots(self) -> List[Pilot]:
        """Get all currently available pilots."""
        return [p for p in self.pilots.values() if p.status == "Available"]
    
    def find_pilots_by_skill(self, required_skills: List[str]) -> List[Pilot]:
        """Find pilots with specified skills."""
        return [p for p in self.get_available_pilots() if p.has_skill(required_skills)]
    
    def find_pilots_by_certification(self, required_certs: List[str]) -> List[Pilot]:
        """Find pilots with specified certifications."""
        return [p for p in self.get_available_pilots() if p.has_certification(required_certs)]
    
    def find_pilots_by_location(self, location: str) -> List[Pilot]:
        """Find available pilots at specified location."""
        return [p for p in self.get_available_pilots() if p.current_location == location]
    
    def find_pilots_for_mission(self, required_skills: List[str], 
                               required_certs: List[str], 
                               location: str,
                               start_date: date,
                               end_date: date) -> List[Pilot]:
        """Find qualified pilots available for a mission."""
        candidates = []
        for pilot in self.get_available_pilots():
            if (pilot.has_skill(required_skills) and 
                pilot.has_certification(required_certs) and
                pilot.is_available(start_date, end_date)):
                candidates.append(pilot)
        
        # Sort by location match (same location first) and experience
        candidates.sort(key=lambda p: (p.current_location != location, -p.drone_experience_hours))
        return candidates
    
    def update_pilot_status(self, pilot_id: str, new_status: str) -> bool:
        """Update pilot status (Available/On Leave/Unavailable)."""
        if pilot_id not in self.pilots:
            return False
        self.pilots[pilot_id].status = new_status
        return True
    
    def assign_pilot_to_mission(self, pilot_id: str, mission_id: str) -> bool:
        """Assign pilot to mission."""
        if pilot_id not in self.pilots:
            return False
        self.pilots[pilot_id].current_assignment = mission_id
        return True
    
    def unassign_pilot(self, pilot_id: str) -> bool:
        """Remove pilot from current assignment."""
        if pilot_id not in self.pilots:
            return False
        self.pilots[pilot_id].current_assignment = None
        return True
    
    def get_pilot_hours_summary(self, pilot_id: str) -> dict:
        """Get pilot's hours and cost information."""
        pilot = self.get_pilot(pilot_id)
        if not pilot:
            return None
        
        return {
            "pilot_id": pilot.pilot_id,
            "name": pilot.name,
            "hourly_rate": pilot.hourly_rate,
            "max_monthly_hours": pilot.max_monthly_hours,
            "experience_hours": pilot.drone_experience_hours,
        }
    
    def calculate_roster_capacity(self) -> dict:
        """Calculate current roster capacity and utilization."""
        available = len(self.get_available_pilots())
        on_leave = len([p for p in self.pilots.values() if p.status == "On Leave"])
        unavailable = len([p for p in self.pilots.values() if p.status == "Unavailable"])
        assigned = len([p for p in self.get_available_pilots() if p.current_assignment])
        
        return {
            "total_pilots": len(self.pilots),
            "available": available,
            "assigned": assigned,
            "unassigned": available - assigned,
            "on_leave": on_leave,
            "unavailable": unavailable,
        }
