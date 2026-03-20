"""
Routes: React app serving and episode search API.

To enable AI chat, set USE_LLM = True below. See llm_routes.py for AI code.
"""
import json
import os
import math
import re
from difflib import SequenceMatcher
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
    "abusive": {
        "abusive", "abuse", "abused", "toxic", "violent", "violence", "harassment",
        "controlling", "manipulative", "gaslight", "gaslighting",
    },
    "time": {
        "time", "busy", "schedule", "hours", "week", "weeks", "month", "months",
        "distance", "longdistance", "ignore", "ignored",
    },
    "talking": {
        "talking", "talk", "communication", "communicate", "conversation", "argue", "arguing",
        "relationship", "boyfriend", "girlfriend", "partner", "husband", "wife", "spouse",
        "issue", "issues", "problem", "problems", "trust", "cheat", "cheating", "love",
        "breakup", "break", "ex",
    },
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


def query_has_signal(query_vector):
    return any(value > 0 for value in query_vector.values())


def lexical_similarity(query, text):
    query_tokens = set(TOKEN_RE.findall((query or "").lower()))
    doc_tokens = set(TOKEN_RE.findall((text or "").lower()))
    if not query_tokens or not doc_tokens:
        return 0.0

    jaccard = len(query_tokens.intersection(doc_tokens)) / len(query_tokens.union(doc_tokens))
    fuzzy = SequenceMatcher(None, (query or "").lower(), (text or "").lower()).ratio()
    return round(0.7 * jaccard + 0.3 * fuzzy, 4)


def min_max_normalize(values):
    if not values:
        return []
    v_min = min(values)
    v_max = max(values)
    if v_max == v_min:
        return [0.0 for _ in values]
    return [(v - v_min) / (v_max - v_min) for v in values]


def blend_scores(cosine_scores, upvote_scores, upvote_weight=0.15):
    """
    Inspired by ted-finds score blending:
      combined = (1-w) * cosine + w * normalized_aux_signal
    """
    w = max(0.0, min(1.0, float(upvote_weight)))
    norm_upvotes = min_max_normalize(upvote_scores)
    blended = []
    for i, cosine_score in enumerate(cosine_scores):
        combined = (1.0 - w) * cosine_score + w * norm_upvotes[i]
        blended.append(round(combined, 4))
    return blended, norm_upvotes


def json_search(query):
    if not query or not query.strip():
        query = "need relationship advice"

    query_vector = query_to_vector(query)
    has_query_signal = query_has_signal(query_vector)
    # Optional tuning from query param (0.0 to 1.0) in /api/episodes route.
    upvote_weight = 0.15
    episode_vectors = load_episode_vectors()
    results = db.session.query(Episode, Review).join(Review, Episode.id == Review.id).all()
    rows = []
    for episode, review in results:
        doc_vector = episode_vectors.get(episode.id, zero_vector())
        if has_query_signal:
            cosine_score = cosine_similarity(query_vector, doc_vector)
        else:
            # Fallback: sentence-level lexical similarity for broad natural-language inputs.
            cosine_score = lexical_similarity(query, f"{episode.title} {episode.descr}")
        rows.append({
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
    cosine_scores = [row["cosine_similarity"] for row in rows]
    upvote_scores = [row["upvote_score"] for row in rows]
    final_scores, norm_upvotes = blend_scores(cosine_scores, upvote_scores, upvote_weight=upvote_weight)

    for i, row in enumerate(rows):
        row["upvote_score_norm"] = round(norm_upvotes[i], 4)
        row["final_score"] = final_scores[i]
        row["final_score_pct"] = round(final_scores[i] * 100, 2)
        row["score_blend"] = {
            "cosine_weight": round(1.0 - upvote_weight, 2),
            "upvote_weight": round(upvote_weight, 2),
        }

    rows.sort(key=lambda item: (item["final_score"], item["cosine_similarity"]), reverse=True)
    top_rows = rows[:10]
    for rank, row in enumerate(top_rows, start=1):
        row["rank"] = rank
    return top_rows


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
