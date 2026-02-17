"""Simple Flask web UI for the Drone Operations Agent.

Run with:
  python -m src.web_ui

Endpoints:
  GET /                 -> HTML UI
  GET /api/status       -> Full status report (JSON)
  GET /api/pilots       -> List pilots (optional ?skill=...)
  POST /api/pilots/<id>/status -> Update pilot status
  GET /api/drones       -> List drones (optional ?capability=...)
  GET /api/missions     -> List missions
  GET /api/match/<mid>  -> Match pilots & drones for mission
  GET /api/conflicts    -> Detect all conflicts
  POST /api/reassign    -> Execute reassignment
"""
from __future__ import annotations
import os
import json
from flask import Flask, jsonify, request, render_template
from flask_socketio import SocketIO, emit

# Import agent (support running as module or script)
try:
    from .main import DroneOperationsAgent
    from .ai_agent import AIAgent
    from .conversation import ConversationManager
except Exception:
    from src.main import DroneOperationsAgent
    from src.ai_agent import AIAgent
    from src.conversation import ConversationManager

app = Flask(__name__, template_folder="templates", static_folder="static")
# Choose Socket.IO async_mode dynamically: prefer eventlet/gevent if installed, else fall back to threading.
_async_choice = None
for _mode, _pkg in (("eventlet", "eventlet"), ("gevent", "gevent")):
    try:
        __import__(_pkg)
        _async_choice = _mode
        break
    except Exception:
        continue
if not _async_choice:
    _async_choice = "threading"
app.logger.info(f"SocketIO async_mode set to: {_async_choice}")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode=_async_choice)
agent = DroneOperationsAgent()
# AI agent (uses OPENAI_API_KEY if set). Auto-execution requires AI_AGENT_AUTO_EXECUTE=1
ai_agent = AIAgent(agent)
# Conversation manager for multi-turn chat
conv_manager = ConversationManager()


def _serialize_date(obj):
    try:
        return obj.isoformat()
    except Exception:
        return str(obj)


def jsonify_safe(obj):
    return app.response_class(json.dumps(obj, default=_serialize_date), mimetype="application/json")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/chat")
def chat():
    """Serve the new ChatGPT-like chat interface."""
    return render_template("chat.html")


@app.route("/api/status")
def api_status():
    return jsonify_safe(agent.generate_status_report())


@app.route("/api/pilots")
def api_pilots():
    skill = request.args.get("skill")
    if skill:
        return jsonify_safe(agent.query_pilots_by_skill([skill]))

    pilots = []
    for p in agent.roster.pilots.values():
        pilots.append({
            "pilot_id": p.pilot_id,
            "name": p.name,
            "skills": p.skills,
            "certifications": p.certifications,
            "experience_hours": p.drone_experience_hours,
            "current_location": p.current_location,
            "current_assignment": p.current_assignment,
            "status": p.status,
            "hourly_rate": p.hourly_rate,
        })
    return jsonify_safe(pilots)


@app.route("/api/pilots/<pilot_id>/status", methods=["POST"])
def api_update_pilot_status(pilot_id: str):
    data = request.get_json() or {}
    new_status = data.get("new_status")
    availability_start = data.get("availability_start")
    availability_end = data.get("availability_end")
    if not new_status:
        return jsonify({"error": "new_status required"}), 400

    result = agent.update_pilot_status(pilot_id, new_status, availability_start, availability_end)

    # If sync manager is enabled, process pending syncs immediately and include result
    if getattr(agent, "sync_manager", None) and agent.sync_manager.sync_enabled:
        sync_res = agent.sync_manager.process_pending_syncs()
        result["sync"] = sync_res

    return jsonify(result)


@app.route("/api/drones")
def api_drones():
    capability = request.args.get("capability")
    weather = request.args.get("weather")

    if capability:
        return jsonify_safe(agent.query_drones_by_capability([capability]))
    if weather:
        return jsonify_safe(agent.query_drones_by_weather(weather))

    drones = []
    for d in agent.inventory.drones.values():
        drones.append({
            "drone_id": d.drone_id,
            "model": d.model,
            "capabilities": d.capabilities,
            "weather_rating": d.weather_rating,
            "current_location": d.current_location,
            "current_assignment": d.current_assignment,
            "status": d.status,
            "daily_rate": d.daily_rate,
        })
    return jsonify_safe(drones)


@app.route("/api/missions")
def api_missions():
    missions = []
    for m in agent.missions:
        missions.append({
            "mission_id": m.mission_id,
            "project_name": m.project_name,
            "client_name": m.client_name,
            "location": m.location,
            "required_skills": m.required_skills,
            "required_certifications": m.required_certifications,
            "start_date": m.start_date,
            "end_date": m.end_date,
            "duration_days": m.duration_days,
            "budget": m.budget,
            "weather_forecast": m.weather_forecast,
            "assigned_pilot": m.assigned_pilot,
            "assigned_drone": m.assigned_drone,
            "priority": m.priority,
            "status": m.status,
        })
    return jsonify_safe(missions)


@app.route("/api/match/<mission_id>")
def api_match(mission_id: str):
    pilots = agent.match_pilots_to_mission(mission_id)
    drones = agent.match_drones_to_mission(mission_id)
    return jsonify({"pilots": pilots, "drones": drones})


@app.route("/api/conflicts")
def api_conflicts():
    return jsonify_safe(agent.detect_all_conflicts())


@app.route("/api/sync/process", methods=["POST"])
def api_process_syncs():
    """Process all pending Google Sheets sync operations."""
    if not getattr(agent, "sync_manager", None) or not agent.sync_manager.sync_enabled:
        return jsonify({"error": "Sync manager not enabled"}), 400

    res = agent.sync_manager.process_pending_syncs()
    return jsonify(res)


@app.route("/api/sync/pending")
def api_sync_pending():
    """Return pending sync operations (without processing)."""
    if not getattr(agent, "sync_manager", None) or not agent.sync_manager.sync_enabled:
        return jsonify({"pending": 0, "message": "Sync manager not enabled"})

    return jsonify({"pending": len(agent.sync_manager.pending_syncs), "ops": agent.sync_manager.pending_syncs})


@app.route("/api/reassign", methods=["POST"])
def api_reassign():
    data = request.get_json() or {}
    mission_id = data.get("mission_id")
    new_pilot = data.get("new_pilot_id")
    new_drone = data.get("new_drone_id")
    if not mission_id:
        return jsonify({"error": "mission_id required"}), 400

    result = agent.execute_reassignment(mission_id, new_pilot, new_drone)
    return jsonify(result)


# === AI agent endpoint ===
@app.route("/api/ai", methods=["POST"])
def api_ai():
    """Accepts: { "query": "text", "execute": false }
    If execute=true the server will attempt to run the mapped action — only allowed when
    AI_AGENT_AUTO_EXECUTE=1 is set in environment (safety opt-in).
    """
    data = request.get_json() or {}
    query = data.get("query")
    execute = bool(data.get("execute", False))
    if not query:
        return jsonify({"error": "query is required"}), 400

    try:
        res = ai_agent.handle_query(query, execute=execute)
        return jsonify_safe(res)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# === Chat API (multi-turn conversation) ===
@app.route("/api/chat", methods=["POST"])
def api_chat():
    """Multi-turn conversation endpoint.
    
    POST body: { "user_message": "...", "conversation_id": "..." (optional) }
    Returns: { "conversation_id": "...", "agent_response": "...", "history": [...] }
    """
    data = request.get_json() or {}
    user_message = data.get("user_message")
    conversation_id = data.get("conversation_id")

    if not user_message:
        return jsonify({"error": "user_message is required"}), 400

    try:
        # Get or create conversation
        if conversation_id:
            conv = conv_manager.get_conversation(conversation_id)
            if not conv:
                return jsonify({"error": f"Conversation {conversation_id} not found"}), 404
        else:
            # Auto-generate title from first message
            title = user_message[:50].strip()
            if len(user_message) > 50:
                title += "..."
            conv = conv_manager.create_conversation(title=title)

        # Add user message to conversation
        conv.add_message("user", user_message)

        # Get AI response (using conversation context)
        ai_result = ai_agent.handle_query(user_message, execute=False)
        # Format response as a readable summary and include Sheets-based prediction if present
        suggestion_data = ai_result.get("suggestion") or ai_result.get("interpretation") or {}
        if isinstance(suggestion_data, dict):
            pred = suggestion_data.get("prediction")
            other = {k: v for k, v in suggestion_data.items() if k != "prediction"}
            pretty = json.dumps(other, indent=2, default=str) if other else ""
            if pred:
                # inline prediction shown to user
                agent_response = (pretty + "\n\nPrediction:\n" + pred).strip()
            else:
                agent_response = pretty or str(suggestion_data)
        else:
            agent_response = str(suggestion_data)

        # Add agent response to conversation
        conv.add_message("agent", agent_response)

        return jsonify_safe({
            "conversation_id": conv.id,
            "agent_response": agent_response,
            "history": conv.get_history(),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/conversations", methods=["GET"])
def api_conversations():
    """List all conversations."""
    return jsonify_safe({"conversations": conv_manager.list_conversations()})


@app.route("/api/conversations/<conversation_id>", methods=["GET"])
def api_conversation(conversation_id: str):
    """Get a specific conversation."""
    conv = conv_manager.get_conversation(conversation_id)
    if not conv:
        return jsonify({"error": "Conversation not found"}), 404
    return jsonify_safe(conv.to_dict())


@app.route("/api/conversations/<conversation_id>", methods=["DELETE"])
def api_delete_conversation(conversation_id: str):
    """Delete a conversation."""
    if conv_manager.delete_conversation(conversation_id):
        return jsonify({"success": True})
    return jsonify({"error": "Conversation not found"}), 404


@app.route("/api/conversations/<conversation_id>/title", methods=["POST"])
def api_rename_conversation(conversation_id: str):
    """Rename a conversation."""
    data = request.get_json() or {}
    new_title = data.get("title")
    if not new_title:
        return jsonify({"error": "title is required"}), 400
    
    success = conv_manager.rename_conversation(conversation_id, new_title)
    if success:
        return jsonify({"success": True, "title": new_title})
    return jsonify({"error": "Conversation not found"}), 404


@app.route("/api/conversations/<conversation_id>/export", methods=["GET"])
def api_export_conversation(conversation_id: str):
    """Export a conversation as markdown or text."""
    format_type = request.args.get("format", "markdown")
    if format_type not in ["markdown", "text"]:
        format_type = "markdown"
    
    content = conv_manager.export_conversation(conversation_id, format_type)
    if not content:
        return jsonify({"error": "Conversation not found"}), 404
    
    return app.response_class(
        response=content,
        status=200,
        mimetype="text/plain",
        headers={"Content-Disposition": f"attachment;filename=conversation_{conversation_id}.{'md' if format_type == 'markdown' else 'txt'}"}
    )


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    # Allow enabling AI auto-execute for local testing via env var AI_AGENT_AUTO_EXECUTE=1
    # Start Socket.IO for real-time assistant streaming
    @socketio.on('connect')
    def _on_connect():
        emit('connected', {'message': 'socket connected'})

    @socketio.on('ai_query')
    def _on_ai_query(data):
        query = data.get('query', '')
        try:
            result = ai_agent.handle_query(query, execute=False)
            content = result.get('suggestion') or result.get('interpretation') or result.get('error') or result
            if not isinstance(content, str):
                content = json.dumps(content, indent=2, default=str)
        except Exception as e:
            content = f"Error: {e}"
            result = {'error': str(e)}

        # stream response in chunks
        chunk_size = 200
        for i in range(0, len(content), chunk_size):
            emit('ai_chunk', {'chunk': content[i:i+chunk_size]})
            socketio.sleep(0.01)
        emit('ai_done', {'status': 'complete', 'result': result})

    socketio.run(app, debug=True, host="127.0.0.1", port=port)
