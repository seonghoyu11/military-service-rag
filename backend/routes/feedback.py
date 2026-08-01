"""
Stage 6: thumbs-up/down (+ optional free-text comment) on a given /api/query
response. Two uses:
  1. a basic usage/quality signal for the HYS demo story
  2. raw material for curating RAGAS ground_truth later -- a 👍 with the
     question/answer/results snapshot attached is a candidate labeled
     example; a 👎 flags a case worth writing a corrected answer for.

Stores a snapshot of the question/answer/results at feedback time rather
than a foreign key into /api/query (which is stateless and persists
nothing), since the underlying retrieval/generation can change between
when the answer was shown and when someone reads the feedback later.
"""
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify

from db.mongo import get_db

feedback_bp = Blueprint("feedback", __name__)

VALID_RATINGS = {"up", "down"}


def _feedback():
    return get_db()["feedback"]


@feedback_bp.route("/api/feedback", methods=["POST"])
def submit_feedback():
    data = request.get_json(silent=True) or {}
    session_id = (data.get("session_id") or "").strip() or None
    question = (data.get("question") or "").strip()
    rating = (data.get("rating") or "").strip()
    comment = (data.get("comment") or "").strip() or None
    results = data.get("results")
    answer = data.get("answer")

    if not question:
        return jsonify({"error": "question is required"}), 400
    if rating not in VALID_RATINGS:
        return jsonify({"error": f"rating must be one of {sorted(VALID_RATINGS)}"}), 400

    doc = {
        "session_id": session_id,
        "question": question,
        "rating": rating,
        "comment": comment,
        "results": results,
        "answer": answer,
        "created_at": datetime.now(timezone.utc),
    }
    inserted = _feedback().insert_one(doc)

    return jsonify({"id": str(inserted.inserted_id)}), 201
