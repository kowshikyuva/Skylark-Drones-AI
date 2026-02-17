"""OpenAI-backed AI agent for Skylark Drone Operations.

Features:
- Natural-language understanding via OpenAI Chat API
- Maps user queries to structured actions (match, reassign, update status, detect conflicts)
- Can optionally execute actions against `DroneOperationsAgent` (requires opt-in env var)

Security / safety:
- Auto-execution is disabled by default. Set AI_AGENT_AUTO_EXECUTE=1 to allow changes.
- Requires OPENAI_API_KEY environment variable to call OpenAI.
"""
from __future__ import annotations
import os
import json
import logging
from typing import Any, Dict

# OpenAI import is optional — fall back to rule-based behavior when unavailable
try:
    import openai
    _OPENAI_INSTALLED = True
except Exception:
    openai = None
    _OPENAI_INSTALLED = False

try:
    from .main import DroneOperationsAgent
except Exception:
    from src.main import DroneOperationsAgent


LOG = logging.getLogger("ai_agent")
LOG.setLevel(logging.INFO)
if not LOG.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("[AI] %(asctime)s %(levelname)s: %(message)s"))
    LOG.addHandler(h)


class AIAgent:
    """Wrapper around OpenAI that maps NL -> agent actions."""

    ACTIONS = [
        "query_status",
        "match_mission",
        "detect_conflicts",
        "update_pilot_status",
        "reassign",
        "suggest_reassign",
        "help",
    ]

    def __init__(self, agent: DroneOperationsAgent | None = None, model: str | None = None):
        self.agent = agent or DroneOperationsAgent()
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o")
        self.api_key = os.getenv("OPENAI_API_KEY")
        # Only configure openai if the package is installed and key is present
        if _OPENAI_INSTALLED and self.api_key:
            openai.api_key = self.api_key
        self.auto_execute_enabled = os.getenv("AI_AGENT_AUTO_EXECUTE", "0") in ("1", "true", "yes")

    def handle_query(self, query: str, execute: bool = False) -> Dict[str, Any]:
        """Interpret a natural-language query and optionally execute the resulting action.

        Returns a dict with keys: interpretation, action, params, execution (if run).
        """
        LOG.info("Handling query: %s", query)

        interpretation = self._interpret_query(query)
        LOG.info("Interpretation: %s", interpretation)

        action = interpretation.get("action")
        params = interpretation.get("params", {})

        result = {"query": query, "interpretation": interpretation}

        if not action or action not in self.ACTIONS:
            result["error"] = "Could not map query to a supported action."
            return result

        result["action"] = action
        result["params"] = params

        # If execution requested, ensure auto-execute is enabled (safety)
        if execute:
            if not self.auto_execute_enabled:
                result["execution_allowed"] = False
                result["error"] = (
                    "Auto-execution is disabled. Set AI_AGENT_AUTO_EXECUTE=1 to allow the agent to apply changes."
                )
                return result

            exec_res = self._execute_action(action, params)
            result["execution"] = exec_res
            return result

        # Not executing — produce suggested output and a Sheets-based prediction
        suggestion = self._suggest_action(action, params)
        pred = None
        try:
            pred = self._predict(query, action, params)
            pred_text = pred.get("text") if isinstance(pred, dict) else str(pred)
            if isinstance(suggestion, dict):
                suggestion["prediction"] = pred_text
            else:
                suggestion = {"preview": suggestion, "prediction": pred_text}
            result["prediction_context"] = pred.get("context_summary") if isinstance(pred, dict) else None
        except Exception as e:
            result["prediction_context"] = None
            if isinstance(suggestion, dict):
                suggestion.setdefault("prediction", f"Prediction error: {e}")
            else:
                suggestion = {"preview": suggestion, "prediction": f"Prediction error: {e}"}

        result["suggestion"] = suggestion
        return result

    def _interpret_query(self, query: str) -> Dict[str, Any]:
        """Ask the LLM to convert the free-text query into a JSON action + params."""
        # If OpenAI isn't available or no API key is set, use rule-based fallback
        if not _OPENAI_INSTALLED or not self.api_key:
            return self._interpret_query_fallback(query)

        system = (
            "You are the Skylark Drone Operations assistant. "
            "When given a user request, output ONLY a JSON object with keys: action, params, explanation. "
            "The value of \"action\" must be one of: " + ", ".join(self.ACTIONS) + ".\n"
            "Params must be an object with only the fields needed for the action (e.g. mission_id, pilot_id, new_status, new_pilot_id, new_drone_id). "
            "Do not output any additional text or markdown — ONLY the JSON object."
        )

        prompt = f"User request: {query}\n\nRespond with JSON."

        try:
            resp = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
                max_tokens=400,
            )
            txt = resp["choices"][0]["message"]["content"].strip()
            # Parse JSON from model output
            parsed = json.loads(txt)
            # Normalize keys
            action = parsed.get("action")
            params = parsed.get("params", {})
            explanation = parsed.get("explanation", "")
            return {"action": action, "params": params, "explanation": explanation}
        except Exception as e:
            LOG.error("LLM interpretation failed: %s", e)
            return {"action": None, "params": {}, "explanation": f"LLM error: {e}"}

    def _gather_sheets_context(self, action: str, params: Dict[str, Any]) -> str:
        """Return a short textual summary of relevant Google Sheets (or local CSV) data to include in prompts."""
        try:
            parts = []
            sync = getattr(self.agent, "sync_manager", None)
            if sync and getattr(sync, "sync_enabled", False) and getattr(sync, "sync_client", None):
                client = sync.sync_client
                pilots = client.read_pilot_roster_sheet() or []
                drones = client.read_drone_fleet_sheet() or []
                missions = client.read_missions_sheet() or []
            else:
                # fallback to in-memory data
                pilots = [
                    {"pilot_id": p.pilot_id, "name": p.name, "status": p.status, "skills": p.skills, "experience_hours": p.drone_experience_hours, "current_assignment": p.current_assignment}
                    for p in getattr(self.agent, "pilots", [])
                ]
                drones = [
                    {"drone_id": d.drone_id, "model": d.model, "status": d.status, "capabilities": d.capabilities, "weather_rating": d.weather_rating, "current_assignment": d.current_assignment}
                    for d in getattr(self.agent, "drones", [])
                ]
                missions = [
                    {"mission_id": m.mission_id, "project_name": m.project_name, "location": m.location, "start_date": str(m.start_date), "end_date": str(m.end_date), "assigned_pilot": m.assigned_pilot, "assigned_drone": m.assigned_drone, "priority": m.priority}
                    for m in getattr(self.agent, "missions", [])
                ]

            parts.append(
                f"Pilots: {len(pilots)} rows — " + ", ".join([f"{r.get('pilot_id') or r.get('id') or r.get('pilot')}: {r.get('name') or r.get('pilot_id')} ({r.get('status')})" for r in pilots[:5]])
            )
            parts.append(
                f"Drones: {len(drones)} rows — " + ", ".join([f"{r.get('drone_id') or r.get('id')}: {r.get('model') or r.get('drone_id')} ({r.get('status')})" for r in drones[:5]])
            )
            parts.append(
                f"Missions: {len(missions)} rows — " + ", ".join([f"{r.get('mission_id')}: {r.get('project_name') or r.get('mission_id')} ({r.get('start_date')}→{r.get('end_date')})" for r in missions[:5]])
            )
            return "\n".join(parts)
        except Exception as e:
            LOG.exception("Failed to gather sheets context")
            return "No sheet context available."

    def _generate_prediction_with_llm(self, user_query: str, context: str) -> str:
        """Ask the LLM to produce a concise prediction using provided context."""
        if not _OPENAI_INSTALLED or not self.api_key:
            return ""
        system = (
            "You are a data-aware assistant that reads provided tabular data context and returns a concise prediction about the user's request. "
            "Output plain text only (3-5 short bullet points). Include a confidence label (High/Medium/Low)."
        )
        prompt = f"Context:\n{context}\n\nUser request: {user_query}\n\nProvide a short prediction (3 bullets) and a confidence label."
        try:
            resp = openai.ChatCompletion.create(
                model=self.model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=300,
            )
            return resp["choices"][0]["message"]["content"].strip()
        except Exception as e:
            LOG.error("LLM prediction failed: %s", e)
            return ""

    def _predict(self, query: str, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a short prediction text using Google Sheets (or local data) as context."""
        ctx = self._gather_sheets_context(action, params)
        pred_text = ""
        if _OPENAI_INSTALLED and self.api_key:
            pred_text = self._generate_prediction_with_llm(query, ctx)

        if not pred_text:
            # deterministic fallback summaries
            try:
                if action == "match_mission":
                    mid = params.get("mission_id")
                    pilots = self.agent.match_pilots_to_mission(mid).get("candidate_pilots", [])
                    drones = self.agent.match_drones_to_mission(mid).get("candidate_drones", [])
                    top_pilot = pilots[0] if pilots else None
                    top_drone = drones[0] if drones else None
                    lines = []
                    if top_pilot:
                        lines.append(f"Top pilot: {top_pilot['name']} ({top_pilot['pilot_id']}) — cost ${top_pilot.get('mission_cost')} — experience {top_pilot.get('experience_hours')} hrs.")
                    if top_drone:
                        lines.append(f"Top drone: {top_drone['model']} ({top_drone['drone_id']}) — cost ${top_drone.get('mission_cost') }.")
                    lines.append("Confidence: Medium (deterministic heuristic)")
                    pred_text = "\n".join(lines) if lines else "No candidates found — low confidence."
                elif action == "query_status":
                    rpt = self.agent.generate_status_report()
                    rc = rpt.get('roster_capacity', {})
                    fs = rpt.get('fleet_summary', {})
                    pred_text = f"Roster available: {rc.get('available')} — Fleet active: {fs.get('active')} — Conflicts: {rpt.get('conflicts_summary', {}).get('total_conflicts')}. Confidence: High."
                elif action == "detect_conflicts":
                    conflicts = self.agent.detect_all_conflicts()
                    pred_text = f"Found {conflicts.get('total_conflicts')} conflicts — {conflicts.get('critical')} critical. Confidence: High."
                else:
                    pred_text = "No specialized prediction available for this type of request."
            except Exception:
                pred_text = "Failed to generate deterministic prediction."

        return {"text": pred_text, "context_summary": ctx}

    def _interpret_query_fallback(self, query: str) -> Dict[str, Any]:
        """Simple rule-based fallback when OPENAI_API_KEY is not set."""
        q = query.lower()
        if "status" in q or "report" in q:
            return {"action": "query_status", "params": {}, "explanation": "rule: status"}
        if "match" in q or "candidates" in q or "who" in q:
            # try extract mission id
            words = q.split()
            mid = next((w.upper() for w in words if w.startswith("PROJ_")), None)
            return {"action": "match_mission", "params": {"mission_id": mid}, "explanation": "rule: match mission"}
        if "reassign" in q:
            # cannot auto-assign without more detail
            return {"action": "suggest_reassign", "params": {}, "explanation": "rule: suggest reassign"}
        return {"action": None, "params": {}, "explanation": "no rule matched"}

    def _suggest_action(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Return a preview of what running the action would do (no side effects)."""
        if action == "query_status":
            return {"preview": self.agent.generate_status_report()}
        if action == "match_mission":
            mid = params.get("mission_id")
            return {"pilots": self.agent.match_pilots_to_mission(mid), "drones": self.agent.match_drones_to_mission(mid)}
        if action == "detect_conflicts":
            return {"conflicts": self.agent.detect_all_conflicts()}
        if action == "suggest_reassign":
            mid = params.get("mission_id")
            return {"suggestions": self.agent.suggest_reassignments(mid) if mid else []}
        return {"note": "No preview available for this action."}

    def _execute_action(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a mapped action against the DroneOperationsAgent."""
        try:
            if action == "update_pilot_status":
                pilot_id = params.get("pilot_id")
                new_status = params.get("new_status")
                return self.agent.update_pilot_status(pilot_id, new_status)

            if action == "reassign":
                mission_id = params.get("mission_id")
                new_pilot = params.get("new_pilot_id")
                new_drone = params.get("new_drone_id")
                return {"success": self.agent.execute_reassignment(mission_id, new_pilot, new_drone)}

            if action == "match_mission":
                mid = params.get("mission_id")
                return {"pilots": self.agent.match_pilots_to_mission(mid), "drones": self.agent.match_drones_to_mission(mid)}

            if action == "detect_conflicts":
                return {"conflicts": self.agent.detect_all_conflicts()}

            if action == "query_status":
                return {"status": self.agent.generate_status_report()}

            if action == "suggest_reassign":
                mid = params.get("mission_id")
                return {"suggestions": self.agent.suggest_reassignments(mid)}

            return {"error": "Unsupported action for execution"}
        except Exception as e:
            LOG.exception("Execution failed")
            return {"error": str(e)}
