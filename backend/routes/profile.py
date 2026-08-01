"""
Stage 6: a lightweight, login-free session profile so a user's declared
type (영주권자 등) persists across questions without re-typing it every time.

No accounts, no auth. The client generates a random session_id (e.g.
`crypto.randomUUID()`) once and stores it locally (localStorage); this is a
convenience cache keyed by that id, not a user-identity system. Treat it as
disposable -- if the client loses/clears the id, the profile is just gone,
and that's fine.
"""
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify

from db.mongo import get_db
from classifier.model import USER_TYPE_KEYWORDS

profile_bp = Blueprint("profile", __name__)

# Same vocabulary as classifier.model.USER_TYPE_KEYWORDS (영주권자/재외동포2세/
# 이중국적자/유학생) plus a catch-all for anyone who doesn't fit those four --
# kept in sync by deriving from the same source dict rather than a separate
# literal list.
VALID_USER_TYPES = set(USER_TYPE_KEYWORDS.keys()) | {"기타"}


def _profiles():
    return get_db()["profiles"]


def _serialize(doc, session_id):
    if not doc:
        return {"session_id": session_id, "user_type": None}
    return {"session_id": doc["_id"], "user_type": doc.get("user_type")}


@profile_bp.route("/api/profile", methods=["POST"])
def upsert_profile():
    data = request.get_json(silent=True) or {}
    session_id = (data.get("session_id") or "").strip()
    user_type = (data.get("user_type") or "").strip()

    if not session_id:
        return jsonify({"error": "session_id is required"}), 400
    if user_type and user_type not in VALID_USER_TYPES:
        return jsonify({
            "error": f"user_type must be one of {sorted(VALID_USER_TYPES)}"
        }), 400

    now = datetime.now(timezone.utc)
    update = {"updated_at": now}
    if user_type:
        update["user_type"] = user_type

    _profiles().update_one(
        {"_id": session_id},
        {"$set": update, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )

    return jsonify(_serialize(_profiles().find_one({"_id": session_id}), session_id))


@profile_bp.route("/api/profile/<session_id>", methods=["GET"])
def get_profile(session_id):
    return jsonify(_serialize(_profiles().find_one({"_id": session_id}), session_id))
