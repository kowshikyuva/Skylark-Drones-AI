"""Main agent application for drone operations coordination."""
import os
import json
from pathlib import Path
from datetime import date

from .data_loader import DataLoader
from .roster_manager import RosterManager
from .inventory_manager import InventoryManager
from .assignment_matcher import AssignmentMatcher
from .conflict_detector import ConflictDetector
from .reassignment_coordinator import ReassignmentCoordinator
from .google_sheets_sync import SyncManager


class DroneOperationsAgent:
    """Main AI agent for drone operations coordination."""
    
    def __init__(self, data_dir: str = "./data"):
        self.data_dir = Path(data_dir)
        
        # Load data
        self.pilots = DataLoader.load_pilots(str(self.data_dir / "pilot_roster.csv"))
        self.drones = DataLoader.load_drones(str(self.data_dir / "drone_fleet.csv"))
        self.missions = DataLoader.load_missions(str(self.data_dir / "missions.csv"))
        
        # Initialize managers
        self.roster = RosterManager(self.pilots)
        self.inventory = InventoryManager(self.drones)
        self.matcher = AssignmentMatcher(self.pilots, self.drones, self.missions)
        self.detector = ConflictDetector(self.pilots, self.drones, self.missions)
        self.reassigner = ReassignmentCoordinator(self.pilots, self.drones, self.missions)

        # Google Sheets sync manager — automatically enabled when both credentials and spreadsheet ID are present
        sync_enabled = bool(os.getenv("GOOGLE_SHEETS_API_KEY") and os.getenv("GOOGLE_SHEETS_ID"))
        self.sync_manager = SyncManager(sync_enabled=sync_enabled)
    
    # === ROSTER MANAGEMENT ===
    def query_pilots_by_skill(self, skills: list[str]) -> list[dict]:
        """Query available pilots by skills."""
        pilots = self.roster.find_pilots_by_skill(skills)
        return [{"id": p.pilot_id, "name": p.name, "skills": p.skills, 
                "experience_hours": p.drone_experience_hours} for p in pilots]
    
    def query_pilots_by_location(self, location: str) -> list[dict]:
        """Query available pilots at location."""
        pilots = self.roster.find_pilots_by_location(location)
        return [{"id": p.pilot_id, "name": p.name, "location": p.current_location,
                "status": p.status} for p in pilots]
    
    def calculate_pilot_cost(self, pilot_id: str, mission_duration_days: int) -> dict:
        """Calculate total cost for a pilot."""
        pilot = self.roster.get_pilot(pilot_id)
        if not pilot:
            return {"error": f"Pilot {pilot_id} not found"}
        
        total_cost = pilot.calculate_mission_cost(mission_duration_days)
        return {
            "pilot_id": pilot_id,
            "name": pilot.name,
            "hourly_rate": pilot.hourly_rate,
            "duration_days": mission_duration_days,
            "work_hours": mission_duration_days * 8,
            "total_cost": total_cost
        }
    
    def view_pilot_assignments(self) -> list[dict]:
        """View current pilot assignments."""
        assignments = []
        for pilot in self.roster.pilots.values():
            if pilot.current_assignment:
                assignments.append({
                    "pilot_id": pilot.pilot_id,
                    "name": pilot.name,
                    "assignment": pilot.current_assignment
                })
        return assignments
    
    def update_pilot_status(self, pilot_id: str, new_status: str, 
                          availability_start: str = None, 
                          availability_end: str = None) -> dict:
        """Update pilot status and sync to Google Sheets."""
        pilot = self.roster.get_pilot(pilot_id)
        if not pilot:
            return {"error": f"Pilot {pilot_id} not found"}
        
        self.roster.update_pilot_status(pilot_id, new_status)
        
        # Queue sync if sync manager is enabled
        if getattr(self, "sync_manager", None) and self.sync_manager.sync_enabled:
            self.sync_manager.queue_pilot_status_sync(pilot_id, new_status, pilot.name)

        result = {
            "pilot_id": pilot_id,
            "name": pilot.name,
            "new_status": new_status,
            "requires_sync": True,  # Flag for Google Sheets sync
            "sync_note": f"Update {pilot.name} status to {new_status}"
        }
        return result
    
    def get_roster_capacity(self) -> dict:
        """Get roster capacity summary."""
        return self.roster.calculate_roster_capacity()
    
    # === ASSIGNMENT TRACKING ===
    def match_pilots_to_mission(self, mission_id: str) -> dict:
        """Find and rank pilots for a mission."""
        mission = next((m for m in self.missions if m.mission_id == mission_id), None)
        if not mission:
            return {"error": f"Mission {mission_id} not found"}
        
        candidates = self.roster.find_pilots_for_mission(
            mission.required_skills,
            mission.required_certifications,
            mission.location,
            mission.start_date,
            mission.end_date
        )
        
        results = []
        for pilot in candidates:
            cost = pilot.calculate_mission_cost(mission.duration_days)
            results.append({
                "pilot_id": pilot.pilot_id,
                "name": pilot.name,
                "experience_hours": pilot.drone_experience_hours,
                "location": pilot.current_location,
                "mission_cost": cost,
                "within_budget": cost <= mission.budget
            })
        
        return {
            "mission_id": mission_id,
            "mission_name": mission.project_name,
            "candidate_pilots": results
        }
    
    def match_drones_to_mission(self, mission_id: str) -> dict:
        """Find and rank drones for a mission."""
        mission = next((m for m in self.missions if m.mission_id == mission_id), None)
        if not mission:
            return {"error": f"Mission {mission_id} not found"}
        
        candidates = self.inventory.find_drones_for_mission(
            mission.required_skills,
            mission.weather_forecast,
            mission.location
        )
        
        results = []
        for drone in candidates:
            cost = drone.daily_rate * mission.duration_days
            results.append({
                "drone_id": drone.drone_id,
                "model": drone.model,
                "weather_rating": drone.weather_rating,
                "location": drone.current_location,
                "daily_rate": drone.daily_rate,
                "mission_cost": cost,
                "within_budget": cost <= mission.budget
            })
        
        return {
            "mission_id": mission_id,
            "mission_name": mission.project_name,
            "candidate_drones": results
        }
    
    def get_active_assignments(self) -> list[dict]:
        """Get all active assignments."""
        return self.matcher.get_active_assignments()
    
    # === DRONE INVENTORY ===
    def query_drones_by_capability(self, capabilities: list[str]) -> list[dict]:
        """Query drones by capabilities."""
        drones = self.inventory.find_drones_by_capability(capabilities)
        return [{"id": d.drone_id, "model": d.model, "capabilities": d.capabilities,
                "status": d.status, "location": d.current_location} for d in drones]
    
    def query_drones_by_weather(self, weather: str) -> list[dict]:
        """Query drones suitable for weather conditions."""
        drones = self.inventory.find_drones_by_weather(weather)
        return [{"id": d.drone_id, "model": d.model, "weather_rating": d.weather_rating,
                "status": d.status} for d in drones]
    
    def filter_drones_by_location(self, location: str) -> list[dict]:
        """Filter available drones by location."""
        drones = self.inventory.find_drones_by_location(location)
        return [{"id": d.drone_id, "model": d.model, "location": d.current_location,
                "status": d.status} for d in drones]
    
    def get_fleet_summary(self) -> dict:
        """Get drone fleet summary."""
        return self.inventory.get_fleet_summary()
    
    def get_maintenance_alerts(self) -> list[dict]:
        """Flag drones with maintenance issues."""
        drones = self.inventory.get_maintenance_alerts()
        return [{"id": d.drone_id, "model": d.model, "maintenance_due": str(d.maintenance_due_date),
                "status": d.status} for d in drones]
    
    def update_drone_status(self, drone_id: str, new_status: str) -> dict:
        """Update drone status and sync to Google Sheets."""
        drone = self.inventory.get_drone(drone_id)
        if not drone:
            return {"error": f"Drone {drone_id} not found"}
        
        self.inventory.update_drone_status(drone_id, new_status)

        # Queue sync if enabled
        if getattr(self, "sync_manager", None) and self.sync_manager.sync_enabled:
            self.sync_manager.queue_drone_status_sync(drone_id, new_status, drone.model)

        result = {
            "drone_id": drone_id,
            "model": drone.model,
            "new_status": new_status,
            "requires_sync": True,  # Flag for Google Sheets sync
            "sync_note": f"Update {drone.model} status to {new_status}"
        }
        return result
    
    # === CONFLICT DETECTION ===
    def detect_all_conflicts(self) -> dict:
        """Detect all conflicts in current state."""
        conflicts = self.detector.detect_all_conflicts()
        
        critical = self.detector.get_conflicts_by_severity("Critical")
        warnings = self.detector.get_conflicts_by_severity("Warning")
        info = self.detector.get_conflicts_by_severity("Info")
        
        return {
            "total_conflicts": len(conflicts),
            "critical": len(critical),
            "warnings": len(warnings),
            "info": len(info),
            "conflicts": [
                {
                    "id": c.conflict_id,
                    "type": c.conflict_type,
                    "severity": c.severity,
                    "mission": c.affected_mission,
                    "pilot": c.affected_pilot,
                    "drone": c.affected_drone,
                    "description": c.description,
                    "suggested_action": c.suggested_action
                } for c in conflicts
            ]
        }
    
    def detect_conflicts_for_mission(self, mission_id: str) -> list[dict]:
        """Detect conflicts for a specific mission."""
        self.detector.detect_all_conflicts()
        conflicts = self.detector.get_conflicts_by_mission(mission_id)
        
        return [
            {
                "conflict_type": c.conflict_type,
                "severity": c.severity,
                "description": c.description,
                "suggested_action": c.suggested_action
            } for c in conflicts
        ]
    
    # === URGENT REASSIGNMENT ===
    def get_priority_reassignments(self) -> list[dict]:
        """Get missions needing urgent reassignment."""
        return self.reassigner.get_priority_reassignments()
    
    def suggest_reassignments(self, mission_id: str) -> list[dict]:
        """Suggest reassignments for a mission."""
        suggestions = self.reassigner.suggest_reassignments(mission_id)
        
        return [
            {
                "reason": s.reason,
                "suggested_pilot": s.suggested_pilot,
                "suggested_drone": s.suggested_drone,
                "urgency": s.urgency
            } for s in suggestions
        ]
    
    def execute_reassignment(self, mission_id: str, new_pilot_id: str = None, 
                           new_drone_id: str = None) -> dict:
        """Execute a reassignment."""
        success = self.reassigner.execute_reassignment(mission_id, new_pilot_id, new_drone_id)

        # Queue assignment sync (pilot/drone assignment updates)
        if getattr(self, "sync_manager", None) and self.sync_manager.sync_enabled:
            self.sync_manager.queue_assignment_sync(mission_id, pilot_id=new_pilot_id, drone_id=new_drone_id)

        return {
            "success": success,
            "mission_id": mission_id,
            "new_pilot": new_pilot_id,
            "new_drone": new_drone_id,
            "requires_sync": True
        }
    
    # === REPORTING ===
    def generate_status_report(self) -> dict:
        """Generate comprehensive status report."""
        return {
            "roster_capacity": self.roster.calculate_roster_capacity(),
            "fleet_summary": self.inventory.get_fleet_summary(),
            "active_assignments": self.get_active_assignments(),
            "conflicts_summary": self.detect_all_conflicts(),
            "priority_reassignments": self.get_priority_reassignments()
        }


if __name__ == "__main__":
    # Initialize agent
    agent = DroneOperationsAgent()
    
    # Example: Generate status report
    report = agent.generate_status_report()
    print(json.dumps(report, indent=2, default=str))
