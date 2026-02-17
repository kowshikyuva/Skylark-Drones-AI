"""Google Sheets integration for 2-way sync."""
import os
import json
from typing import List, Dict, Any
from datetime import date

# Optional Google Sheets libraries — handle gracefully if not present
try:
    import gspread
    from google.oauth2.service_account import Credentials
    _GSHEETS_AVAILABLE = True
except Exception:
    gspread = None
    Credentials = None
    _GSHEETS_AVAILABLE = False

class GoogleSheetsSync:
    """Handles 2-way sync with Google Sheets.

    This class attempts to authenticate with Google Sheets when a service account
    JSON and spreadsheet ID are provided. If the environment does not include the
    required libraries/credentials it falls back to the existing console-stub
    behaviour so the app remains usable in demo mode.
    """

    def __init__(self, sheets_api_key: str = None, spreadsheet_id: str = None):
        """Initialize Google Sheets sync.

        Args:
            sheets_api_key: Path to Google Sheets API service account JSON (or JSON string)
            spreadsheet_id: ID of the Google Sheets spreadsheet
        """
        self.sheets_api_key = sheets_api_key or os.getenv("GOOGLE_SHEETS_API_KEY")
        self.spreadsheet_id = spreadsheet_id or os.getenv("GOOGLE_SHEETS_ID")
        self.client = None
        self.spreadsheet = None

        if self.sheets_api_key and self.spreadsheet_id and _GSHEETS_AVAILABLE:
            try:
                self._authenticate()
            except Exception as e:
                print(f"[GSHEETS] Authentication failed: {e}")
        elif not _GSHEETS_AVAILABLE:
            print("[GSHEETS] google-auth/gspread not available — running in stub mode")
        else:
            print("[GSHEETS] Sheets API key or spreadsheet ID not set — running in stub mode")
    
    def _authenticate(self):
        """Authenticate with Google Sheets API (service account).

        Supports either a path to a service-account JSON file or a raw JSON string
        provided in the environment variable. Uses `gspread` +
        `google.oauth2.service_account.Credentials`.
        """
        if not _GSHEETS_AVAILABLE:
            raise RuntimeError("gspread/google-auth not available")

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]

        # sheets_api_key may be a path or the raw JSON contents
        if os.path.exists(self.sheets_api_key):
            creds = Credentials.from_service_account_file(self.sheets_api_key, scopes=scopes)
        else:
            info = json.loads(self.sheets_api_key)
            creds = Credentials.from_service_account_info(info, scopes=scopes)

        self.client = gspread.authorize(creds)
        self.spreadsheet = self.client.open_by_key(self.spreadsheet_id)
        print("[GSHEETS] Authenticated and opened spreadsheet")
    
    def sync_pilot_status_to_sheets(self, pilot_id: str, new_status: str, 
                                   pilot_name: str = None) -> bool:
        """Sync pilot status update to the `Pilot Roster` sheet.

        Behaviour:
        - Locate pilot row by `pilot_id` (fall back to `name` when available)
        - Update the `status` column in-place
        - Return True on success, False otherwise
        """
        try:
            if not self.spreadsheet:
                print("[SYNC] Spreadsheet client not initialized — stub mode")
                return False

            worksheet = self.spreadsheet.worksheet("Pilot Roster")
            records = worksheet.get_all_records()

            # Try to find row by pilot_id (case-insensitive)
            row_index = None
            for i, r in enumerate(records, start=2):
                pid = str(r.get("pilot_id") or r.get("Pilot ID") or r.get("id") or "").strip()
                if pid and pid.strip().upper() == str(pilot_id).strip().upper():
                    row_index = i
                    break

            # If not found by id, try by name
            if row_index is None and pilot_name:
                for i, r in enumerate(records, start=2):
                    name = str(r.get("name") or r.get("Name") or "").strip()
                    if name and name.lower() == pilot_name.strip().lower():
                        row_index = i
                        break

            if row_index is None:
                print(f"[SYNC] Pilot {pilot_id} not found in sheet")
                return False

            headers = worksheet.row_values(1)
            try:
                status_col = next(idx for idx, h in enumerate(headers, start=1) if h.strip().lower() == "status")
            except StopIteration:
                print("[SYNC] 'status' column not found in Pilot Roster sheet")
                return False

            worksheet.update_cell(row_index, status_col, new_status)
            self.write_sync_log("PILOT_UPDATE", pilot_id, {"status": new_status})
            return True

        except Exception as e:
            print(f"[ERROR] Failed to sync pilot status: {e}")
            return False
    
    def sync_drone_status_to_sheets(self, drone_id: str, new_status: str,
                                   model: str = None) -> bool:
        """Sync drone status in the `Drone Fleet` sheet."""
        try:
            if not self.spreadsheet:
                print("[SYNC] Spreadsheet client not initialized — stub mode")
                return False

            worksheet = self.spreadsheet.worksheet("Drone Fleet")
            records = worksheet.get_all_records()

            row_index = None
            for i, r in enumerate(records, start=2):
                did = str(r.get("drone_id") or r.get("Drone ID") or r.get("id") or "").strip()
                if did and did.strip().upper() == str(drone_id).strip().upper():
                    row_index = i
                    break

            if row_index is None:
                print(f"[SYNC] Drone {drone_id} not found in sheet")
                return False

            headers = worksheet.row_values(1)
            try:
                status_col = next(idx for idx, h in enumerate(headers, start=1) if h.strip().lower() == "status")
            except StopIteration:
                print("[SYNC] 'status' column not found in Drone Fleet sheet")
                return False

            worksheet.update_cell(row_index, status_col, new_status)
            self.write_sync_log("DRONE_UPDATE", drone_id, {"status": new_status})
            return True
        except Exception as e:
            print(f"[ERROR] Failed to sync drone status: {e}")
            return False
    
    def sync_assignment_to_sheets(self, mission_id: str, pilot_id: str = None,
                                 drone_id: str = None) -> bool:
        """Update assignment fields in both `Pilot Roster` and `Drone Fleet` sheets."""
        try:
            if not self.spreadsheet:
                print("[SYNC] Spreadsheet client not initialized — stub mode")
                return False

            # Update pilot current_assignment if provided
            if pilot_id:
                worksheet = self.spreadsheet.worksheet("Pilot Roster")
                records = worksheet.get_all_records()
                for i, r in enumerate(records, start=2):
                    pid = str(r.get("pilot_id") or r.get("Pilot ID") or "").strip()
                    if pid and pid.strip().upper() == str(pilot_id).strip().upper():
                        headers = worksheet.row_values(1)
                        try:
                            assign_col = next(idx for idx, h in enumerate(headers, start=1) if h.strip().lower() in ("current_assignment", "current assignment", "assignment"))
                        except StopIteration:
                            assign_col = None
                        if assign_col:
                            worksheet.update_cell(i, assign_col, mission_id)
                        break

            # Update drone current_assignment if provided
            if drone_id:
                worksheet = self.spreadsheet.worksheet("Drone Fleet")
                records = worksheet.get_all_records()
                for i, r in enumerate(records, start=2):
                    did = str(r.get("drone_id") or r.get("Drone ID") or "").strip()
                    if did and did.strip().upper() == str(drone_id).strip().upper():
                        headers = worksheet.row_values(1)
                        try:
                            assign_col = next(idx for idx, h in enumerate(headers, start=1) if h.strip().lower() in ("current_assignment", "current assignment", "assignment"))
                        except StopIteration:
                            assign_col = None
                        if assign_col:
                            worksheet.update_cell(i, assign_col, mission_id)
                        break

            self.write_sync_log("ASSIGNMENT", mission_id, {"pilot": pilot_id, "drone": drone_id})
            return True
        except Exception as e:
            print(f"[ERROR] Failed to sync assignment: {e}")
            return False
    
    def read_pilot_roster_sheet(self) -> List[Dict[str, Any]]:
        """Read and return all pilot records from `Pilot Roster` sheet."""
        try:
            if not self.spreadsheet:
                print("[READ] Spreadsheet client not initialized — stub mode")
                return []
            worksheet = self.spreadsheet.worksheet("Pilot Roster")
            return worksheet.get_all_records()
        except Exception as e:
            print(f"[ERROR] Failed to read pilot roster: {e}")
            return []
    
    def read_drone_fleet_sheet(self) -> List[Dict[str, Any]]:
        """Read and return all drone records from `Drone Fleet` sheet."""
        try:
            if not self.spreadsheet:
                print("[READ] Spreadsheet client not initialized — stub mode")
                return []
            worksheet = self.spreadsheet.worksheet("Drone Fleet")
            return worksheet.get_all_records()
        except Exception as e:
            print(f"[ERROR] Failed to read drone fleet: {e}")
            return []
    
    def read_missions_sheet(self) -> List[Dict[str, Any]]:
        """Read and return all mission records from `Missions` sheet."""
        try:
            if not self.spreadsheet:
                print("[READ] Spreadsheet client not initialized — stub mode")
                return []
            worksheet = self.spreadsheet.worksheet("Missions")
            return worksheet.get_all_records()
        except Exception as e:
            print(f"[ERROR] Failed to read missions: {e}")
            return []
    
    def write_sync_log(self, action: str, resource_id: str, details: Dict[str, Any]) -> bool:
        """
        Write sync operation to audit log.
        
        Example:
            write_sync_log("PILOT_UPDATE", "P001", {"status": "On Leave"})
        """
        try:
            # In production: Write to a "Sync Log" sheet
            print(f"[LOG] {action}: {resource_id} - {details}")
            return True
        except Exception as e:
            print(f"[ERROR] Failed to write sync log: {e}")
            return False


class SyncManager:
    """Manages all sync operations with Google Sheets."""
    
    def __init__(self, sync_enabled: bool = False):
        self.sync_enabled = sync_enabled
        self.sync_client = GoogleSheetsSync() if sync_enabled else None
        self.pending_syncs = []
    
    def queue_pilot_status_sync(self, pilot_id: str, new_status: str, pilot_name: str = None):
        """Queue a pilot status sync operation."""
        if not self.sync_enabled:
            return
        
        sync_op = {
            "type": "pilot_status",
            "pilot_id": pilot_id,
            "new_status": new_status,
            "pilot_name": pilot_name
        }
        self.pending_syncs.append(sync_op)
    
    def queue_drone_status_sync(self, drone_id: str, new_status: str, model: str = None):
        """Queue a drone status sync operation."""
        if not self.sync_enabled:
            return
        
        sync_op = {
            "type": "drone_status",
            "drone_id": drone_id,
            "new_status": new_status,
            "model": model
        }
        self.pending_syncs.append(sync_op)
    
    def queue_assignment_sync(self, mission_id: str, pilot_id: str = None, drone_id: str = None):
        """Queue an assignment sync operation."""
        if not self.sync_enabled:
            return
        
        sync_op = {
            "type": "assignment",
            "mission_id": mission_id,
            "pilot_id": pilot_id,
            "drone_id": drone_id
        }
        self.pending_syncs.append(sync_op)
    
    def process_pending_syncs(self) -> Dict[str, int]:
        """Execute all pending sync operations."""
        if not self.sync_enabled or not self.sync_client:
            return {"total": 0, "successful": 0, "failed": 0}
        
        successful = 0
        failed = 0
        
        for sync_op in self.pending_syncs:
            try:
                if sync_op["type"] == "pilot_status":
                    if self.sync_client.sync_pilot_status_to_sheets(
                        sync_op["pilot_id"], sync_op["new_status"], sync_op.get("pilot_name")
                    ):
                        successful += 1
                    else:
                        failed += 1
                
                elif sync_op["type"] == "drone_status":
                    if self.sync_client.sync_drone_status_to_sheets(
                        sync_op["drone_id"], sync_op["new_status"], sync_op.get("model")
                    ):
                        successful += 1
                    else:
                        failed += 1
                
                elif sync_op["type"] == "assignment":
                    if self.sync_client.sync_assignment_to_sheets(
                        sync_op["mission_id"], sync_op.get("pilot_id"), sync_op.get("drone_id")
                    ):
                        successful += 1
                    else:
                        failed += 1
            
            except Exception as e:
                print(f"[ERROR] Sync operation failed: {e}")
                failed += 1
        
        self.pending_syncs = []
        
        return {
            "total": successful + failed,
            "successful": successful,
            "failed": failed
        }
