"""Urgent reassignment coordinator for crisis management."""
from typing import List, Optional, Tuple
from datetime import date
import uuid

from .models import Pilot, Drone, Mission, ReassignmentSuggestion, Conflict
from .assignment_matcher import AssignmentMatcher
from .conflict_detector import ConflictDetector


class ReassignmentCoordinator:
    """Handles urgent reassignments to resolve critical conflicts."""
    
    def __init__(self, pilots: List[Pilot], drones: List[Drone], missions: List[Mission]):
        self.pilots = {p.pilot_id: p for p in pilots}
        self.drones = {d.drone_id: d for d in drones}
        self.missions = {m.mission_id: m for m in missions}
        self.matcher = AssignmentMatcher(pilots, drones, missions)
        self.detector = ConflictDetector(pilots, drones, missions)
    
    def suggest_reassignments(self, mission_id: str, max_suggestions: int = 3) -> List[ReassignmentSuggestion]:
        """Suggest reassignments to resolve conflicts for a mission."""
        mission = self.missions.get(mission_id)
        if not mission:
            return []
        
        # Get conflicts for this mission
        self.detector.conflicts = []
        self.detector._check_pilot_conflicts(mission_id)
        self.detector._check_drone_conflicts(mission_id)
        
        conflicts = self.detector.get_conflicts_by_mission(mission_id)
        suggestions = []
        
        for conflict in conflicts:
            if conflict.conflict_type == "double_booking" and conflict.affected_pilot:
                # Find alternative pilots
                alt_pilots = self._find_pilot_alternatives(mission, max_suggestions)
                for alt_pilot in alt_pilots:
                    suggestion = ReassignmentSuggestion(
                        mission_id=mission_id,
                        current_pilot=mission.assigned_pilot,
                        suggested_pilot=alt_pilot.pilot_id,
                        current_drone=mission.assigned_drone,
                        suggested_drone=None,
                        reason=f"Pilot conflict: reassign to {alt_pilot.name}",
                        urgency="High"
                    )
                    suggestions.append(suggestion)
            
            elif conflict.conflict_type == "double_booking" and conflict.affected_drone:
                # Find alternative drones
                alt_drones = self._find_drone_alternatives(mission, max_suggestions)
                for alt_drone in alt_drones:
                    suggestion = ReassignmentSuggestion(
                        mission_id=mission_id,
                        current_pilot=mission.assigned_pilot,
                        suggested_pilot=None,
                        current_drone=mission.assigned_drone,
                        suggested_drone=alt_drone.drone_id,
                        reason=f"Drone conflict: reassign to {alt_drone.model}",
                        urgency="High"
                    )
                    suggestions.append(suggestion)
            
            elif conflict.conflict_type == "maintenance_conflict":
                # Find alternative drones
                alt_drones = self._find_drone_alternatives(mission, max_suggestions)
                for alt_drone in alt_drones:
                    suggestion = ReassignmentSuggestion(
                        mission_id=mission_id,
                        current_pilot=mission.assigned_pilot,
                        suggested_pilot=None,
                        current_drone=mission.assigned_drone,
                        suggested_drone=alt_drone.drone_id,
                        reason=f"Drone in maintenance: reassign to {alt_drone.model}",
                        urgency="Critical"
                    )
                    suggestions.append(suggestion)
            
            elif conflict.conflict_type == "skill_mismatch":
                # Find qualified pilots
                alt_pilots = self._find_pilot_alternatives(mission, max_suggestions)
                for alt_pilot in alt_pilots:
                    suggestion = ReassignmentSuggestion(
                        mission_id=mission_id,
                        current_pilot=mission.assigned_pilot,
                        suggested_pilot=alt_pilot.pilot_id,
                        current_drone=mission.assigned_drone,
                        suggested_drone=None,
                        reason=f"Pilot skill mismatch: reassign to {alt_pilot.name}",
                        urgency="High"
                    )
                    suggestions.append(suggestion)
            
            elif conflict.conflict_type == "weather_risk":
                # Find weather-rated drones
                alt_drones = self._find_drone_alternatives(mission, max_suggestions)
                for alt_drone in alt_drones:
                    suggestion = ReassignmentSuggestion(
                        mission_id=mission_id,
                        current_pilot=mission.assigned_pilot,
                        suggested_pilot=None,
                        current_drone=mission.assigned_drone,
                        suggested_drone=alt_drone.drone_id,
                        reason=f"Weather risk: reassign to weather-rated {alt_drone.model}",
                        urgency="High"
                    )
                    suggestions.append(suggestion)
        
        return suggestions[:max_suggestions]
    
    def _find_pilot_alternatives(self, mission: Mission, count: int = 3) -> List[Pilot]:
        """Find alternative pilots for a mission."""
        candidates = []
        for pilot in self.pilots.values():
            if pilot.pilot_id == mission.assigned_pilot:
                continue
            if pilot.status != "Available":
                continue
            if not pilot.is_available(mission.start_date, mission.end_date):
                continue
            if not pilot.has_skill(mission.required_skills):
                continue
            if not pilot.has_certification(mission.required_certifications):
                continue
            candidates.append(pilot)
        
        # Sort by experience (most experienced first)
        candidates.sort(key=lambda p: -p.drone_experience_hours)
        return candidates[:count]
    
    def _find_drone_alternatives(self, mission: Mission, count: int = 3) -> List[Drone]:
        """Find alternative drones for a mission."""
        candidates = []
        for drone in self.drones.values():
            if drone.drone_id == mission.assigned_drone:
                continue
            if not drone.is_available():
                continue
            if drone.is_maintenance_due():
                continue
            if not drone.has_capability(mission.required_skills):
                continue
            if not drone.can_fly_in_weather(mission.weather_forecast):
                continue
            candidates.append(drone)
        
        # Sort by daily rate (cheapest first)
        candidates.sort(key=lambda d: d.daily_rate)
        return candidates[:count]
    
    def execute_reassignment(self, mission_id: str, new_pilot: Optional[str] = None, 
                           new_drone: Optional[str] = None) -> bool:
        """Execute a reassignment."""
        mission = self.missions.get(mission_id)
        if not mission:
            return False
        
        success = True
        
        if new_pilot:
            success &= self.matcher.reassign_pilot(mission_id, new_pilot)
        
        if new_drone:
            success &= self.matcher.reassign_drone(mission_id, new_drone)
        
        return success
    
    def get_priority_reassignments(self) -> List[dict]:
        """Get missions that urgently need reassignment, prioritized by severity."""
        priority_reassignments = []
        
        self.detector.detect_all_conflicts()
        critical_conflicts = self.detector.get_critical_conflicts()
        
        # Group by mission
        missions_with_conflicts = {}
        for conflict in critical_conflicts:
            mission_id = conflict.affected_mission
            if mission_id not in missions_with_conflicts:
                missions_with_conflicts[mission_id] = []
            missions_with_conflicts[mission_id].append(conflict)
        
        # Create priority list
        for mission_id, conflicts in missions_with_conflicts.items():
            mission = self.missions.get(mission_id)
            if not mission:
                continue
            
            priority_reassignments.append({
                "mission_id": mission_id,
                "project": mission.project_name,
                "conflicts": len(conflicts),
                "conflict_types": [c.conflict_type for c in conflicts],
                "severity": "Critical",
                "suggestions": self.suggest_reassignments(mission_id, max_suggestions=2)
            })
        
        return priority_reassignments
