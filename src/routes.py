"""
Routes: React app serving and episode search API.

To enable AI chat, set USE_LLM = True below. See llm_routes.py for AI code.
"""
import json
import os
from flask import send_from_directory, request, jsonify
from models import db, Episode, Review
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# ── AI toggle ────────────────────────────────────────────────────────────────
USE_LLM = False
# USE_LLM = True
# ─────────────────────────────────────────────────────────────────────────────

# ── Global ML references ──────────────────────────────────────────────────────
vectorizer = None
tfidf_matrix = None
episode_ids_order = []  
# ─────────────────────────────────────────────────────────────────────────────

def init_vectorizer():
    global vectorizer, tfidf_matrix, episode_ids_order
    if vectorizer is not None:
        return
        
    episodes = db.session.query(Episode).all()
    texts = [f"{ep.title} {ep.descr}" for ep in episodes]
    episode_ids_order = [ep.id for ep in episodes]
    
    vectorizer = TfidfVectorizer(stop_words='english')
    if texts:
        tfidf_matrix = vectorizer.fit_transform(texts)
    else:
        tfidf_matrix = None

def json_search(query):
    init_vectorizer()
    
    if not query or not query.strip():
        query = "Kardashian"

    # Fetch all with reviews
    results = db.session.query(Episode, Review).join(
        Review, Episode.id == Review.id
    ).all()
    
    # Pre-structure dictionary for fast lookup
    ep_data_map = {}
    for ep, rev in results:
        ep_data_map[ep.id] = {
            'title': ep.title,
            'descr': ep.descr,
            'imdb_rating': rev.imdb_rating
        }
    
    if tfidf_matrix is None:
        return list(ep_data_map.values())

    query_vec = vectorizer.transform([query])
    sim_scores = cosine_similarity(query_vec, tfidf_matrix).flatten()
    
    scored = []
    for idx, sim in enumerate(sim_scores):
        if sim > 0:
            ep_id = episode_ids_order[idx]
            if ep_id in ep_data_map:
                scored.append((sim, ep_id))
                
    scored.sort(key=lambda x: x[0], reverse=True)
    
    matches = []
    for sim, ep_id in scored:
        data = ep_data_map[ep_id].copy()
        data['similarity_score'] = float(sim)
        matches.append(data)
        
    # fallback to just ilike if no cosine matches to not completely break the user's intent if they type something weird
    if not matches:
        return [
            {
                'title': ep.title,
                'descr': ep.descr,
                'imdb_rating': rev.imdb_rating,
                'similarity_score': 0.0
            }
            for ep, rev in db.session.query(Episode, Review).join(Review, Episode.id == Review.id).filter(Episode.title.ilike(f'%{query}%')).all()
        ]
        
    return matches

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
