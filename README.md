# Drone Operations Coordinator - Project README

## Overview

This AI agent automates the core responsibilities of a drone operations coordinator at Skylark Drones. It handles pilot roster management, drone fleet coordination, mission assignment matching, and real-time conflict detection across complex, overlapping projects.

## Core Capabilities

### 1. **Roster Management**
- Query pilots by skills, certifications, location
- Calculate mission costs based on pilot experience level
- Update pilot status (Available/On Leave/Unavailable) with Google Sheets sync
- View current assignments and capacity utilization

### 2. **Drone Inventory**
- Query fleet by capabilities, availability, location
- Weather-based drone filtering (Generic/IP42/IP43/IP45 ratings)
- Track deployment status and maintenance schedules
- Detect maintenance conflicts automatically

### 3. **Mission Assignment**
- Intelligent matching of pilots to missions using multi-factor scoring
- Intelligent matching of drones to missions with weather compatibility checks
- Track active assignments across all projects
- Calculate cost-feasibility for budget constraints

### 4. **Conflict Detection**
Automatically detects 7 types of conflicts:
- **Double-booking**: Pilot/drone assigned to overlapping missions
- **Skill mismatch**: Pilot lacks required certifications or skills
- **Equipment mismatch**: Drone lacks required capabilities
- **Maintenance conflict**: Assigned drone currently in maintenance
- **Weather risk**: Drone not rated for mission weather
- **Location mismatch**: Resource location ≠ mission location  
- **Budget overrun**: Mission cost exceeds allocated budget

### 5. **Urgent Reassignment Coordination**
- Detects critical conflicts requiring immediate attention
- Suggests qualified alternative pilots/drones ranked by match score
- Executes reassignments with automatic updates to all systems
- Maintains audit trail of all changes

### 6. **Google Sheets Integration**
- **Read**: Syncs pilot roster and drone fleet data from Google Sheets
- **Write**: Updates pilot/drone status and assignments back to sheets
- Batch queue model for reliable, non-blocking sync operations

## Project Structure

```
.
├── data/                          # CSV data files
│   ├── pilot_roster.csv          # Pilot skills, certifications, availability
│   ├── drone_fleet.csv           # Drone capabilities, weather ratings, status
│   └── missions.csv              # Mission requirements, budgets, weather
├── src/                          # Python source code
│   ├── models.py                 # Domain models (Pilot, Drone, Mission, Conflict)
│   ├── data_loader.py            # CSV parsing and loading
│   ├── roster_manager.py         # Pilot management operations
│   ├── inventory_manager.py      # Drone management operations
│   ├── assignment_matcher.py     # Matching algorithm with scoring
│   ├── conflict_detector.py      # Conflict detection engine
│   ├── reassignment_coordinator.py  # Crisis reassignment handler
│   ├── google_sheets_sync.py     # Google Sheets 2-way sync
│   └── main.py                   # Main agent application
├── docs/
│   └── DECISION_LOG.md           # Architecture and implementation decisions
├── .github/
│   └── copilot-instructions.md   # AI agent development guidelines
└── README.md                      # This file
```

## Quick Start

### 1. Load Sample Data
```python
from src.main import DroneOperationsAgent

agent = DroneOperationsAgent()
```

The agent automatically loads CSV data from the `data/` directory.

### 2. Query Available Resources
```python
# Find pilots with multirotor and thermal-imaging skills
pilots = agent.query_pilots_by_skill(["multirotor", "thermal-imaging"])

# Find drones suitable for rainy weather
drones = agent.query_drones_by_weather("Rainy")

# Get roster capacity summary
capacity = agent.get_roster_capacity()
```

### 3. Detect Conflicts
```python
# Get all conflicts
conflicts = agent.detect_all_conflicts()
print(f"Critical conflicts: {conflicts['critical']}")
print(f"Warnings: {conflicts['warnings']}")

# Get conflicts for specific mission
mission_conflicts = agent.detect_conflicts_for_mission("PROJ_ALPHA")
```

### 4. Match Mission to Resources
```python
# Find qualified pilots for mission
pilot_matches = agent.match_pilots_to_mission("PROJ_ALPHA")
for candidate in pilot_matches["candidate_pilots"]:
    print(f"{candidate['name']}: ${candidate['mission_cost']}")

# Find suitable drones for mission
drone_matches = agent.match_drones_to_mission("PROJ_ALPHA")
for candidate in drone_matches["candidate_drones"]:
    print(f"{candidate['model']}: ${candidate['mission_cost']}")
```

### 5. Handle Urgent Reassignments
```python
# Get missions needing urgent reassignment
priority = agent.get_priority_reassignments()
for mission in priority:
    print(f"Mission {mission['mission_id']}: {mission['conflicts']} conflicts")

# Get suggestions for a specific mission
suggestions = agent.suggest_reassignments("PROJ_ALPHA")
for suggestion in suggestions:
    print(f"Reassign to {suggestion['suggested_pilot']}: {suggestion['reason']}")

# Execute reassignment
result = agent.execute_reassignment("PROJ_ALPHA", 
                                   new_pilot_id="P005",
                                   new_drone_id="D005")
```

### 6. Generate Status Report
```python
report = agent.generate_status_report()
print(f"Roster utilization: {report['roster_capacity']}")
print(f"Fleet status: {report['fleet_summary']}")
print(f"Total conflicts: {report['conflicts_summary']['total_conflicts']}")
```

## Data Schema

### Pilot Roster (`pilot_roster.csv`)
```
pilot_id, name, skills, certifications, drone_experience_hours,
current_location, current_assignment, status, availability_start_date,
availability_end_date, hourly_rate, max_monthly_hours
```

**Example**:
```
P001,Alice Johnson,"multirotor,thermal-imaging",Part 107,500,New York,PROJ_ALPHA,Available,2026-02-17,2026-12-31,75,160
```

### Drone Fleet (`drone_fleet.csv`)
```
drone_id, model, capabilities, weather_rating, current_assignment, status,
current_location, maintenance_due_date, acquisition_date, daily_rate
```

**Example**:
```
D001,DJI Matrice 300 RTK,"multirotor,thermal-imaging,LiDAR",IP45,PROJ_ALPHA,Active,New York,2026-06-15,2024-01-10,500
```

### Missions (`missions.csv`)
```
mission_id, project_name, client_name, location, required_skills,
required_certifications, start_date, end_date, duration_days, budget,
weather_forecast, assigned_pilot, assigned_drone, priority, status
```

**Example**:
```
PROJ_ALPHA,Warehouse Thermal Survey,CoolBox Logistics,New York,multirotor;thermal-imaging,Part 107,2026-02-20,2026-02-27,7,3000,Sunny,P001,D001,High,Active
```

## Google Sheets Sync

### Setup
1. Create a Google Sheets spreadsheet with sheets: "Pilot Roster", "Drone Fleet", "Missions"
2. Obtain Google Sheets API credentials (service account JSON)
3. Set environment variables:
   ```bash
   export GOOGLE_SHEETS_API_KEY=/path/to/service-account.json
   export GOOGLE_SHEETS_ID=<spreadsheet-id>
   ```

### Enable Sync
```python
from src.main import DroneOperationsAgent
from src.google_sheets_sync import SyncManager

agent = DroneOperationsAgent()
agent.sync_manager = SyncManager(sync_enabled=True)
```

### Queue and Execute Syncs
```python
# Queue operations
agent.update_pilot_status("P001", "On Leave")  # Automatically queued
agent.execute_reassignment("PROJ_ALPHA", new_pilot_id="P005")  # Queues sync

# Process pending syncs
results = agent.sync_manager.process_pending_syncs()
print(f"Synced {results['successful']}/{results['total']} operations")
```

## Key Algorithms

### Multi-Factor Pilot Matching
Scoring = 50 (base) + experience(0-20) + location(10) + cost_efficiency(0-20)
- **Base 50 pts**: Meets all requirements (skills, certs, availability)
- **Experience 0-20 pts**: More experience = higher score
- **Location 10 pts**: Bonus if already at mission location
- **Cost 0-20 pts**: Bonus if mission cost << budget

### Weather Compatibility
```
Generic:  Sunny, Cloudy
IP42:     Sunny, Cloudy, Rainy
IP43:     Sunny, Cloudy, Rainy
IP45:     Sunny, Cloudy, Rainy, Stormy
```

### Conflict Detection
Each of 7 conflict types checked independently, severity assigned:
- **Critical**: Must fix immediately (double-booking, maintenance, cert mismatch)
- **Warning**: Should address (skill gap, weather risk, budget overrun)
- **Info**: Context only (location mismatch)

## Edge Cases Handled

✅ Pilot assigned to overlapping missions (double-booking conflict)
✅ Pilot lacks required certification for mission (critical conflict)
✅ Pilot too expensive for mission budget (budget overrun conflict)
✅ Drone currently in maintenance (can't assign, maintenance conflict)
✅ Drone not weather-rated for mission (weather risk conflict)
✅ Pilot and drone at different locations (location mismatch info)
✅ Mission with no available qualified resources (waiting suggestion)

## Decision Log

See [docs/DECISION_LOG.md](docs/DECISION_LOG.md) for architectural decisions including:
- Multi-factor scoring system design
- 7-type conflict detection strategy
- Urgent reassignment suggestion model
- Weather rating classification
- Pilot cost calculation method
- Google Sheets sync architecture
- CSV vs. direct Sheets data sourcing

## Development Notes

### Running Tests
```bash
python -m src.main  # Loads sample data and prints status report
```

### Debugging Conflicts
```python
agent.detector.detect_all_conflicts()
for conflict in agent.detector.conflicts:
    print(f"{conflict.conflict_type}: {conflict.description}")
```

### Performance
- Pilot/drone lookups: O(1) via index
- Conflict detection: O(n²) in mission count
- Matching: O(n) iterating candidates
- Typical fleet: <100 pilots, <50 drones, <200 missions = fast execution

## Future Enhancements

1. **ML-based Matching**: Learn from historical assignment quality
2. **Predictive Maintenance**: Forecast maintenance needs based on usage patterns
3. **Real-time Sync**: WebSocket connection for live Google Sheets updates
4. **Scheduling Optimization**: Genetic algorithms for multi-mission assignment
5. **Dynamic Pricing**: Cost adjustments based on demand and pilot experience
6. **Audit Trail**: Complete history of all decisions and changes

## Contact & Support

For questions about the codebase architecture or development, see [.github/copilot-instructions.md](.github/copilot-instructions.md).

For implementation decisions, see [docs/DECISION_LOG.md](docs/DECISION_LOG.md).

## Web UI (new)

A lightweight web UI is included (Flask). It exposes the agent API and lets you view status, conflicts, pilots, drones, mission matches and perform updates/reassignments.

Run the UI:

1. Install dependencies: `pip install -r requirements.txt`
2. Start server: `python -m src.web_ui`
3. Open: `http://127.0.0.1:5000`

The UI calls endpoints under `/api/*` (see `src/web_ui.py`).

## AI Agent (OpenAI)

A conversational AI agent is available via `/api/ai`. It can interpret natural-language requests (match missions, detect conflicts, suggest or execute reassignments, update pilot status, etc.).

Important:
- Requires `OPENAI_API_KEY` environment variable to call OpenAI.
- Auto-execution (agent applies changes) is disabled by default. To enable: set `AI_AGENT_AUTO_EXECUTE=1`.

Example request (no execution):

```bash
curl -X POST -H "Content-Type: application/json" -d '{"query":"Find qualified pilots for PROJ_ALPHA"}' http://127.0.0.1:5000/api/ai
```

Example request (attempt execute — requires opt-in):

```bash
export OPENAI_API_KEY="sk-..."
export AI_AGENT_AUTO_EXECUTE=1
curl -X POST -H "Content-Type: application/json" -d '{"query":"Reassign PROJ_ALPHA to P005 and D002","execute":true}' http://127.0.0.1:5000/api/ai
```
