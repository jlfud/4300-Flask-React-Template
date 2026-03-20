"""
Routes: React app serving and episode search API.

To enable AI chat, set USE_LLM = True below. See llm_routes.py for AI code.
"""
import json
import os
import math
import re
from flask import send_from_directory, request, jsonify
from models import db, Episode, Review

# ── AI toggle ────────────────────────────────────────────────────────────────
USE_LLM = False
# USE_LLM = True
# ─────────────────────────────────────────────────────────────────────────────


DIMENSIONS = ["abusive", "time", "talking", "school"]
TOKEN_RE = re.compile(r"[a-zA-Z0-9_'/\-]+")
_EPISODE_VECTOR_CACHE = None

# Query terms that should count toward each baseline dimension.
QUERY_DIMENSION_SYNONYMS = {
    "abusive": {"abusive", "abuse", "abused", "toxic", "violent", "violence", "harassment"},
    "time": {"time", "busy", "schedule", "hours", "week", "weeks", "month", "months"},
    "talking": {"talking", "talk", "communication", "communicate", "conversation", "argue", "arguing"},
    "school": {"school", "college", "class", "classes", "university", "campus", "homework"},
}


def zero_vector():
    return {dim: 0.0 for dim in DIMENSIONS}


def safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def normalize_token(token):
    return token.lower().strip("_'/-")


def query_to_vector(query):
    vec = zero_vector()
    for token in TOKEN_RE.findall(query or ""):
        normalized = normalize_token(token)
        if not normalized:
            continue
        for dim, vocab in QUERY_DIMENSION_SYNONYMS.items():
            if normalized in vocab:
                vec[dim] += 1.0
    return vec


def load_episode_vectors():
    global _EPISODE_VECTOR_CACHE
    if _EPISODE_VECTOR_CACHE is not None:
        return _EPISODE_VECTOR_CACHE

    current_dir = os.path.dirname(os.path.abspath(__file__))
    init_path = os.path.join(current_dir, "init.json")
    cache = {}
    if os.path.exists(init_path):
        with open(init_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for row in data.get("episodes", []):
            episode_id = row.get("id")
            if episode_id is None:
                continue
            cache[int(episode_id)] = {
                "abusive": safe_float(row.get("abusive", 0)),
                "time": safe_float(row.get("time", 0)),
                "talking": safe_float(row.get("talking", 0)),
                "school": safe_float(row.get("school", 0)),
            }
    _EPISODE_VECTOR_CACHE = cache
    return _EPISODE_VECTOR_CACHE


def cosine_similarity(vec_a, vec_b):
    dot_product = 0.0
    norm_a_sq = 0.0
    norm_b_sq = 0.0
    for dim in DIMENSIONS:
        a_val = safe_float(vec_a.get(dim, 0.0))
        b_val = safe_float(vec_b.get(dim, 0.0))
        dot_product += a_val * b_val
        norm_a_sq += a_val * a_val
        norm_b_sq += b_val * b_val

    denominator = math.sqrt(norm_a_sq) * math.sqrt(norm_b_sq)
    if denominator == 0:
        return 0.0
    return round(dot_product / denominator, 4)


def json_search(query):
    if not query or not query.strip():
        query = "need relationship advice"

    query_vector = query_to_vector(query)
    episode_vectors = load_episode_vectors()
    results = db.session.query(Episode, Review).join(Review, Episode.id == Review.id).all()
    matches = []
    for episode, review in results:
        doc_vector = episode_vectors.get(episode.id, zero_vector())
        cosine_score = cosine_similarity(query_vector, doc_vector)
        matches.append({
            "title": episode.title,
            "descr": episode.descr,
            # Keep legacy key for existing frontend compatibility.
            "imdb_rating": review.imdb_rating,
            # Baseline output fields requested by assignment.
            "upvote_score": review.imdb_rating,
            "cosine_similarity": cosine_score,
            "similarity_score": cosine_score,
            "query_vector": query_vector,
            "post_vector": doc_vector,
        })
    matches.sort(key=lambda item: (item["cosine_similarity"], item["upvote_score"]), reverse=True)
    return matches[:10]


def register_routes(app):
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve(path):
        if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
            return send_from_directory(app.static_folder, path)
        else:
            return send_from_directory(app.static_folder, 'index.html')

    @app.route("/api/config")
    def config():
        return jsonify({"use_llm": USE_LLM})

    @app.route("/api/episodes")
    def episodes_search():
        text = request.args.get("title", "")
        return jsonify(json_search(text))

    if USE_LLM:
        from llm_routes import register_chat_route
        register_chat_route(app, json_search)
