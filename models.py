"""Data models for drone operations coordinator."""
from dataclasses import dataclass, field
from typing import List, Optional, Set
from datetime import datetime, date


@dataclass
class Pilot:
    """Represents a drone pilot."""
    pilot_id: str
    name: str
    skills: List[str]
    certifications: List[str]
    drone_experience_hours: float
    current_location: str
    current_assignment: Optional[str] = None
    status: str = "Available"  # Available, On Leave, Unavailable
    availability_start_date: Optional[date] = None
    availability_end_date: Optional[date] = None
    hourly_rate: float = 0.0
    max_monthly_hours: float = 160.0
    
    def is_available(self, start_date: date, end_date: date) -> bool:
        """Check if pilot is available for the entire date range."""
        if self.status != "Available":
            return False
        if self.availability_start_date and start_date < self.availability_start_date:
            return False
        if self.availability_end_date and end_date > self.availability_end_date:
            return False
        return True
    
    def has_skill(self, required_skills: List[str]) -> bool:
        """Check if pilot has all required skills."""
        return all(skill in self.skills for skill in required_skills)
    
    def has_certification(self, required_certs: List[str]) -> bool:
        """Check if pilot has all required certifications."""
        return all(cert in self.certifications for cert in required_certs)
    
    def calculate_mission_cost(self, duration_days: int) -> float:
        """Calculate total cost for a mission."""
        hours = duration_days * 8  # Assume 8-hour workday
        return hours * self.hourly_rate


@dataclass
class Drone:
    """Represents a drone in the fleet."""
    drone_id: str
    model: str
    capabilities: List[str]
    weather_rating: str  # Generic, IP42, IP43, IP45
    current_assignment: Optional[str] = None
    status: str = "Active"  # Active, Maintenance, Standby
    current_location: str = "Unknown"
    maintenance_due_date: Optional[date] = None
    acquisition_date: Optional[date] = None
    daily_rate: float = 0.0
    
    def is_available(self) -> bool:
        """Check if drone is available for assignment."""
        return self.status == "Active" and self.current_assignment is None
    
    def has_capability(self, required_capabilities: List[str]) -> bool:
        """Check if drone has all required capabilities."""
        return all(cap in self.capabilities for cap in required_capabilities)
    
    def can_fly_in_weather(self, weather: str) -> bool:
        """Check if drone can fly in given weather conditions."""
        weather_rating_map = {
            "Sunny": ["Generic", "IP42", "IP43", "IP45"],
            "Cloudy": ["Generic", "IP42", "IP43", "IP45"],
            "Rainy": ["IP42", "IP43", "IP45"],  # Generic cannot fly in rain
            "Stormy": ["IP45"],  # Only top-rated drones
        }
        allowed_ratings = weather_rating_map.get(weather, [])
        return self.weather_rating in allowed_ratings
    
    def is_maintenance_due(self) -> bool:
        """Check if maintenance is overdue."""
        if not self.maintenance_due_date:
            return False
        return date.today() > self.maintenance_due_date


@dataclass
class Mission:
    """Represents a mission/project."""
    mission_id: str
    project_name: str
    client_name: str
    location: str
    required_skills: List[str]
    required_certifications: List[str]
    start_date: date
    end_date: date
    budget: float
    weather_forecast: str
    assigned_pilot: Optional[str] = None
    assigned_drone: Optional[str] = None
    priority: str = "Medium"  # Low, Medium, High
    status: str = "Pending"  # Pending, Scheduled, Active, Completed
    
    @property
    def duration_days(self) -> int:
        """Calculate mission duration."""
        return (self.end_date - self.start_date).days + 1
    
    def overlaps_with(self, other: "Mission") -> bool:
        """Check if this mission overlaps with another."""
        return not (self.end_date < other.start_date or self.start_date > other.end_date)


@dataclass
class Conflict:
    """Represents a detected conflict or issue."""
    conflict_id: str
    conflict_type: str  # double_booking, skill_mismatch, equipment_mismatch, 
                        # maintenance_conflict, weather_risk, location_mismatch, budget_overrun
    severity: str  # Critical, Warning, Info
    affected_mission: str
    affected_pilot: Optional[str] = None
    affected_drone: Optional[str] = None
    description: str = ""
    suggested_action: str = ""


@dataclass
class ReassignmentSuggestion:
    """Represents a suggested reassignment to resolve conflicts."""
    mission_id: str
    current_pilot: Optional[str]
    suggested_pilot: Optional[str]
    current_drone: Optional[str]
    suggested_drone: Optional[str]
    reason: str
    urgency: str  # Low, Medium, High, Critical
