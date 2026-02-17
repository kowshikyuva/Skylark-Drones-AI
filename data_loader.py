"""Load and parse CSV data files."""
import csv
from datetime import datetime, date
from typing import List, Dict, Tuple
from pathlib import Path

from .models import Pilot, Drone, Mission


class DataLoader:
    """Handles loading CSV data into domain models."""
    
    @staticmethod
    def parse_date(date_str: str) -> date:
        """Parse date string in YYYY-MM-DD format."""
        if not date_str:
            return None
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    
    @staticmethod
    def parse_list(list_str: str, separator: str = ",") -> List[str]:
        """Parse comma or semicolon-separated list."""
        if not list_str:
            return []
        return [item.strip() for item in list_str.split(separator)]
    
    @classmethod
    def load_pilots(cls, filepath: str) -> List[Pilot]:
        """Load pilot roster from CSV."""
        pilots = []
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                pilot = Pilot(
                    pilot_id=row['pilot_id'],
                    name=row['name'],
                    skills=cls.parse_list(row['skills']),
                    certifications=cls.parse_list(row['certifications']),
                    drone_experience_hours=float(row['drone_experience_hours']),
                    current_location=row['current_location'],
                    current_assignment=row.get('current_assignment') or None,
                    status=row.get('status', 'Available'),
                    availability_start_date=cls.parse_date(row.get('availability_start_date')),
                    availability_end_date=cls.parse_date(row.get('availability_end_date')),
                    hourly_rate=float(row.get('hourly_rate', 0)),
                    max_monthly_hours=float(row.get('max_monthly_hours', 160)),
                )
                pilots.append(pilot)
        return pilots
    
    @classmethod
    def load_drones(cls, filepath: str) -> List[Drone]:
        """Load drone fleet from CSV."""
        drones = []
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                drone = Drone(
                    drone_id=row['drone_id'],
                    model=row['model'],
                    capabilities=cls.parse_list(row['capabilities']),
                    weather_rating=row.get('weather_rating', 'Generic'),
                    current_assignment=row.get('current_assignment') or None,
                    status=row.get('status', 'Active'),
                    current_location=row.get('current_location', 'Unknown'),
                    maintenance_due_date=cls.parse_date(row.get('maintenance_due_date')),
                    acquisition_date=cls.parse_date(row.get('acquisition_date')),
                    daily_rate=float(row.get('daily_rate', 0)),
                )
                drones.append(drone)
        return drones
    
    @classmethod
    def load_missions(cls, filepath: str) -> List[Mission]:
        """Load missions from CSV."""
        missions = []
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                mission = Mission(
                    mission_id=row['mission_id'],
                    project_name=row['project_name'],
                    client_name=row['client_name'],
                    location=row['location'],
                    required_skills=cls.parse_list(row['required_skills'], separator=';'),
                    required_certifications=cls.parse_list(row['required_certifications']),
                    start_date=cls.parse_date(row['start_date']),
                    end_date=cls.parse_date(row['end_date']),
                    budget=float(row['budget']),
                    weather_forecast=row.get('weather_forecast', 'Sunny'),
                    assigned_pilot=row.get('assigned_pilot') if row.get('assigned_pilot') != 'Available' else None,
                    assigned_drone=row.get('assigned_drone') if row.get('assigned_drone') != 'Available' else None,
                    priority=row.get('priority', 'Medium'),
                    status=row.get('status', 'Pending'),
                )
                missions.append(mission)
        return missions
