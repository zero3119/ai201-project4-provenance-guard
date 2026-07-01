from datetime import datetime, timezone
from uuid import uuid4

from flask import Flask, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from audit_log import (
    add_log_entry,
    find_submission,
    get_recent_log_entries,
    mark_submission_under_review,
)
from labels import generate_transparency_label
from scoring import combine_signal_scores, map_score_to_attribution
from signals import analyze_stylometry, classify_with_groq

app = Flask(__name__)

# Local development rate limiter. In production, this would use Redis or another
# persistent store instead of memory://.
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)


@app.get("/")
def home():
    return jsonify({
        "message": "Provenance Guard API is running.",
        "milestone": "M5: production layer",
        "routes": ["POST /submit", "POST /appeal", "GET /log"],
    })


@app.post("/submit")
@limiter.limit("10 per minute;100 per day")
def submit_content():
    data = request.get_json(silent=True) or {}
    text = data.get("text", "").strip()
    creator_id = data.get("creator_id", "").strip()

    if not text:
        return jsonify({"error": "Missing required field: text"}), 400

    if not creator_id:
        return jsonify({"error": "Missing required field: creator_id"}), 400

    content_id = str(uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    # Signal 1: Groq LLM classifier
    llm_result = classify_with_groq(text)
    llm_score = llm_result["llm_score"]

    # Signal 2: Stylometric heuristics
    style_result = analyze_stylometry(text)
    style_score = style_result["style_score"]

    # Combined confidence and final label
    confidence = combine_signal_scores(llm_score, style_score)
    attribution = map_score_to_attribution(confidence)
    label = generate_transparency_label(confidence)

    response_body = {
        "content_id": content_id,
        "creator_id": creator_id,
        "attribution": attribution,
        "confidence": confidence,
        "label": label,
        "signals": {
            "llm_score": llm_score,
            "llm_reason": llm_result.get("llm_reason"),
            "style_score": style_score,
            "style_metrics": style_result["metrics"],
        },
        "status": "classified",
    }

    log_entry = {
        "event_type": "submission",
        "timestamp": timestamp,
        "content_id": content_id,
        "creator_id": creator_id,
        "attribution": attribution,
        "confidence": confidence,
        "label": label,
        "llm_score": llm_score,
        "llm_reason": llm_result.get("llm_reason"),
        "style_score": style_score,
        "style_metrics": style_result["metrics"],
        "status": "classified",
        "appeal_filed": False,
    }
    add_log_entry(log_entry)

    return jsonify(response_body), 200


@app.post("/appeal")
def appeal_content():
    data = request.get_json(silent=True) or {}
    content_id = data.get("content_id", "").strip()
    creator_reasoning = data.get("creator_reasoning", "").strip()

    if not content_id:
        return jsonify({"error": "Missing required field: content_id"}), 400

    if not creator_reasoning:
        return jsonify({"error": "Missing required field: creator_reasoning"}), 400

    original_submission = find_submission(content_id)
    if original_submission is None:
        return jsonify({"error": "No submission found for that content_id"}), 404

    timestamp = datetime.now(timezone.utc).isoformat()
    updated_submission = mark_submission_under_review(
        content_id=content_id,
        creator_reasoning=creator_reasoning,
        appeal_timestamp=timestamp,
    )

    appeal_entry = {
        "event_type": "appeal",
        "timestamp": timestamp,
        "content_id": content_id,
        "creator_id": original_submission.get("creator_id"),
        "creator_reasoning": creator_reasoning,
        "original_attribution": original_submission.get("attribution"),
        "original_confidence": original_submission.get("confidence"),
        "llm_score": original_submission.get("llm_score"),
        "style_score": original_submission.get("style_score"),
        "status": "under_review",
    }
    add_log_entry(appeal_entry)

    return jsonify({
        "content_id": content_id,
        "status": "under_review",
        "message": "Appeal received and marked for human review.",
        "appeal_reasoning": creator_reasoning,
        "updated_submission": updated_submission,
    }), 200


@app.get("/log")
def get_log():
    return jsonify({"entries": get_recent_log_entries(limit=20)})


if __name__ == "__main__":
    app.run(debug=True)
