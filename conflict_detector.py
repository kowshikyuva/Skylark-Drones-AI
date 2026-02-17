"""Conflict detection system."""
from typing import List
from datetime import date
import uuid

from .models import Pilot, Drone, Mission, Conflict


class ConflictDetector:
    """Detects scheduling and resource conflicts."""
    
    def __init__(self, pilots: List[Pilot], drones: List[Drone], missions: List[Mission]):
        self.pilots = {p.pilot_id: p for p in pilots}
        self.drones = {d.drone_id: d for d in drones}
        self.missions = {m.mission_id: m for m in missions}
        self.conflicts: List[Conflict] = []
    
    def detect_all_conflicts(self) -> List[Conflict]:
        """Detect all conflicts in current assignments."""
        self.conflicts = []
        
        # Check each mission for conflicts
        for mission_id in self.missions:
            self._check_pilot_conflicts(mission_id)
            self._check_drone_conflicts(mission_id)
            self._check_budget_conflicts(mission_id)
            self._check_location_conflicts(mission_id)
        
        return self.conflicts
    
    def _check_pilot_conflicts(self, mission_id: str):
        """Check for pilot-related conflicts."""
        mission = self.missions[mission_id]
        if not mission.assigned_pilot:
            return
        
        pilot = self.pilots.get(mission.assigned_pilot)
        if not pilot:
            return
        
        # 1. Double-booking detection
        for other_mission_id, other_mission in self.missions.items():
            if other_mission_id == mission_id or not other_mission.assigned_pilot:
                continue
            if other_mission.assigned_pilot != pilot.pilot_id:
                continue
            
            if mission.overlaps_with(other_mission):
                conflict = Conflict(
                    conflict_id=str(uuid.uuid4()),
                    conflict_type="double_booking",
                    severity="Critical",
                    affected_mission=mission_id,
                    affected_pilot=pilot.pilot_id,
                    description=f"Pilot {pilot.name} assigned to overlapping missions: {mission_id} and {other_mission_id}",
                    suggested_action=f"Reassign pilot from {mission_id} or {other_mission_id}"
                )
                self.conflicts.append(conflict)
        
        # 2. Skill mismatch
        if not pilot.has_skill(mission.required_skills):
            missing_skills = [s for s in mission.required_skills if s not in pilot.skills]
            conflict = Conflict(
                conflict_id=str(uuid.uuid4()),
                conflict_type="skill_mismatch",
                severity="Warning",
                affected_mission=mission_id,
                affected_pilot=pilot.pilot_id,
                description=f"Pilot {pilot.name} lacks required skills: {', '.join(missing_skills)}",
                suggested_action=f"Find pilot with skills: {', '.join(missing_skills)}"
            )
            self.conflicts.append(conflict)
        
        # 3. Certification mismatch
        if not pilot.has_certification(mission.required_certifications):
            missing_certs = [c for c in mission.required_certifications if c not in pilot.certifications]
            conflict = Conflict(
                conflict_id=str(uuid.uuid4()),
                conflict_type="skill_mismatch",
                severity="Critical",
                affected_mission=mission_id,
                affected_pilot=pilot.pilot_id,
                description=f"Pilot {pilot.name} lacks required certifications: {', '.join(missing_certs)}",
                suggested_action=f"Find pilot with certifications: {', '.join(missing_certs)}"
            )
            self.conflicts.append(conflict)
    
    def _check_drone_conflicts(self, mission_id: str):
        """Check for drone-related conflicts."""
        mission = self.missions[mission_id]
        if not mission.assigned_drone:
            return
        
        drone = self.drones.get(mission.assigned_drone)
        if not drone:
            return
        
        # 1. Double-booking detection
        for other_mission_id, other_mission in self.missions.items():
            if other_mission_id == mission_id or not other_mission.assigned_drone:
                continue
            if other_mission.assigned_drone != drone.drone_id:
                continue
            
            if mission.overlaps_with(other_mission):
                conflict = Conflict(
                    conflict_id=str(uuid.uuid4()),
                    conflict_type="double_booking",
                    severity="Critical",
                    affected_mission=mission_id,
                    affected_drone=drone.drone_id,
                    description=f"Drone {drone.model} assigned to overlapping missions: {mission_id} and {other_mission_id}",
                    suggested_action=f"Reassign drone from {mission_id} or {other_mission_id}"
                )
                self.conflicts.append(conflict)
        
        # 2. Maintenance conflict
        if drone.is_maintenance_due():
            conflict = Conflict(
                conflict_id=str(uuid.uuid4()),
                conflict_type="maintenance_conflict",
                severity="Critical",
                affected_mission=mission_id,
                affected_drone=drone.drone_id,
                description=f"Drone {drone.model} is due for maintenance (due: {drone.maintenance_due_date})",
                suggested_action=f"Schedule maintenance before mission or reassign drone"
            )
            self.conflicts.append(conflict)
        
        # 3. Capability mismatch
        if not drone.has_capability(mission.required_skills):
            missing_caps = [s for s in mission.required_skills if s not in drone.capabilities]
            conflict = Conflict(
                conflict_id=str(uuid.uuid4()),
                conflict_type="equipment_mismatch",
                severity="Warning",
                affected_mission=mission_id,
                affected_drone=drone.drone_id,
                description=f"Drone {drone.model} lacks capabilities: {', '.join(missing_caps)}",
                suggested_action=f"Find drone with capabilities: {', '.join(missing_caps)}"
            )
            self.conflicts.append(conflict)
        
        # 4. Weather risk
        if not drone.can_fly_in_weather(mission.weather_forecast):
            conflict = Conflict(
                conflict_id=str(uuid.uuid4()),
                conflict_type="weather_risk",
                severity="Warning",
                affected_mission=mission_id,
                affected_drone=drone.drone_id,
                description=f"Drone {drone.model} (rating: {drone.weather_rating}) cannot fly in {mission.weather_forecast}",
                suggested_action=f"Find weather-rated drone or delay mission"
            )
            self.conflicts.append(conflict)
    
    def _check_budget_conflicts(self, mission_id: str):
        """Check for budget overrun risks."""
        mission = self.missions[mission_id]
        total_cost = 0
        
        if mission.assigned_pilot:
            pilot = self.pilots.get(mission.assigned_pilot)
            if pilot:
                total_cost += pilot.calculate_mission_cost(mission.duration_days)
        
        if mission.assigned_drone:
            drone = self.drones.get(mission.assigned_drone)
            if drone:
                total_cost += drone.daily_rate * mission.duration_days
        
        if total_cost > mission.budget:
            conflict = Conflict(
                conflict_id=str(uuid.uuid4()),
                conflict_type="budget_overrun",
                severity="Warning",
                affected_mission=mission_id,
                description=f"Mission budget ${mission.budget} exceeded by estimated cost ${total_cost:.2f}",
                suggested_action="Consider cheaper resources or increase budget"
            )
            self.conflicts.append(conflict)
    
    def _check_location_conflicts(self, mission_id: str):
        """Check for location mismatches."""
        mission = self.missions[mission_id]
        location_mismatch = False
        mismatched_resources = []
        
        if mission.assigned_pilot:
            pilot = self.pilots.get(mission.assigned_pilot)
            if pilot and pilot.current_location != mission.location:
                location_mismatch = True
                mismatched_resources.append(f"Pilot {pilot.name} at {pilot.current_location}")
        
        if mission.assigned_drone:
            drone = self.drones.get(mission.assigned_drone)
            if drone and drone.current_location != mission.location:
                location_mismatch = True
                mismatched_resources.append(f"Drone {drone.model} at {drone.current_location}")
        
        if location_mismatch:
            conflict = Conflict(
                conflict_id=str(uuid.uuid4()),
                conflict_type="location_mismatch",
                severity="Info",
                affected_mission=mission_id,
                description=f"Resource location mismatch: {', '.join(mismatched_resources)} != mission location {mission.location}",
                suggested_action="Consider travel time or relocation costs"
            )
            self.conflicts.append(conflict)
    
    def get_conflicts_by_severity(self, severity: str) -> List[Conflict]:
        """Get conflicts filtered by severity level."""
        return [c for c in self.conflicts if c.severity == severity]
    
    def get_conflicts_by_mission(self, mission_id: str) -> List[Conflict]:
        """Get all conflicts for a specific mission."""
        return [c for c in self.conflicts if c.affected_mission == mission_id]
    
    def get_critical_conflicts(self) -> List[Conflict]:
        """Get all critical conflicts that need immediate attention."""
        return self.get_conflicts_by_severity("Critical")
