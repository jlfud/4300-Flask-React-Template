"""
Routes: React app serving and episode search API.

To enable AI chat, set USE_LLM = True below. See llm_routes.py for AI code.
"""
import json
import os
from flask import send_from_directory, request, jsonify
<<<<<<< Updated upstream
from models import db, Episode, Review

=======
from models import db, Episode
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
 
>>>>>>> Stashed changes
# ── AI toggle ────────────────────────────────────────────────────────────────
USE_LLM = False
# USE_LLM = True
# ─────────────────────────────────────────────────────────────────────────────
<<<<<<< Updated upstream


def json_search(query):
    if not query or not query.strip():
        query = "Kardashian"
    results = db.session.query(Episode, Review).join(
        Review, Episode.id == Review.id
    ).filter(
        Episode.title.ilike(f'%{query}%')
    ).all()
    matches = []
    for episode, review in results:
        matches.append({
            'title': episode.title,
            'descr': episode.descr,
            'imdb_rating': review.imdb_rating
        })
    return matches


=======
 
 
# ── Global ML references ──────────────────────────────────────────────────────
vectorizer = None
tfidf_matrix = None
episode_ids_order = []  # To map row indices to episode IDs
# ─────────────────────────────────────────────────────────────────────────────

def init_vectorizer():
    global vectorizer, tfidf_matrix, episode_ids_order
    if vectorizer is not None:
        return
        
    episodes = db.session.query(Episode).all()
    # Build text for each episode: title + description
    texts = [f"{ep.title} {ep.descr}" for ep in episodes]
    episode_ids_order = [ep.id for ep in episodes]
    
    vectorizer = TfidfVectorizer(stop_words='english')
    # If there are no episodes yet, handle gracefully
    if texts:
        tfidf_matrix = vectorizer.fit_transform(texts)
    else:
        tfidf_matrix = None

def keyword_search(query, filters=None):
    """
    Search episodes using TF-IDF Cosine Similarity.
    """
    init_vectorizer()
    
    # Base query — apply metadata filters first
    q = db.session.query(Episode)
    if filters:
        if filters.get('abusive') is not None:
            q = q.filter(Episode.abusive == filters['abusive'])
        if filters.get('time') is not None:
            q = q.filter(Episode.time == filters['time'])
        if filters.get('talking') is not None:
            q = q.filter(Episode.talking == filters['talking'])
        if filters.get('school') is not None:
            q = q.filter(Episode.school == filters['school'])
            
    filtered_episodes = q.all()
    filtered_ids = {ep.id: ep for ep in filtered_episodes}
    
    results = []
    if not query or not query.strip() or tfidf_matrix is None:
        # If no query, just return everything that passes filters
        for ep in filtered_episodes:
            results.append({
                'id': ep.id,
                'title': ep.title,
                'descr': ep.descr,
                'abusive': ep.abusive,
                'time': ep.time,
                'talking': ep.talking,
                'school': ep.school,
                'similarity_score': 0.0,
            })
        return results
        
    # Transform the query
    query_vec = vectorizer.transform([query])
    
    # Compute cosine similarities against all stored vectors
    sim_scores = cosine_similarity(query_vec, tfidf_matrix).flatten()
    
    scored = []
    # Match the row index back to episode ID
    for idx, sim in enumerate(sim_scores):
        if sim > 0:
            ep_id = episode_ids_order[idx]
            if ep_id in filtered_ids:
                scored.append((sim, filtered_ids[ep_id]))
                
    # Sort by similarity score descending
    scored.sort(key=lambda x: x[0], reverse=True)
    
    for sim, ep in scored:
        results.append({
            'id': ep.id,
            'title': ep.title,
            'descr': ep.descr,
            'abusive': ep.abusive,
            'time': ep.time,
            'talking': ep.talking,
            'school': ep.school,
            'similarity_score': float(sim),
        })
        
    return results
 
 
def _parse_int_param(value):
    """Return int if value is a valid integer string, else None."""
    if value is not None:
        try:
            return int(value)
        except ValueError:
            pass
    return None
 
 
>>>>>>> Stashed changes
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
