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


import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
from sklearn.metrics.pairwise import cosine_similarity as sklearn_cosine_similarity

_SEARCH_MODELS = None

def get_search_models():
    global _SEARCH_MODELS
    if _SEARCH_MODELS is not None:
        return _SEARCH_MODELS

    current_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(current_dir, "relationship_advice_posts2.csv")
    
    # Load data
    df = pd.read_csv(csv_path)
    df['title'] = df['title'].fillna('')
    df['body'] = df['body'].fillna('')
    df['score'] = pd.to_numeric(df['score'], errors='coerce').fillna(0)
    
    # Create combined text
    docs = df['title'] + " " + df['body']
    
    # TF-IDF
    vectorizer = TfidfVectorizer(stop_words='english', max_df=0.8, min_df=5)
    tfidf_matrix = vectorizer.fit_transform(docs)
    
    # SVD
    n_components = min(100, tfidf_matrix.shape[1] - 1)
    #THIS LINE IS REALLY IMPORTANT
    if n_components < 1:
        n_components = 1
    svd = TruncatedSVD(n_components=n_components, random_state=42)
    doc_vectors = svd.fit_transform(tfidf_matrix)
    
    # Precompute top words for each dimension
    feature_names = vectorizer.get_feature_names_out()
    dim_top_words = []
    for component in svd.components_:
        top_indices = component.argsort()[-5:][::-1]
        dim_top_words.append([str(feature_names[i]) for i in top_indices])
    
    _SEARCH_MODELS = {
        "df": df,
        "vectorizer": vectorizer,
        "svd": svd,
        "doc_vectors": doc_vectors,
        "dim_top_words": dim_top_words
    }
    return _SEARCH_MODELS


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
    Combined = (1-w) * cosine + w * normalized_aux_signal
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

    models = get_search_models()
    df = models["df"]
    vectorizer = models["vectorizer"]
    svd = models["svd"]
    doc_vectors = models["doc_vectors"]

    # Transform query
    query_tfidf = vectorizer.transform([query])
    query_vec = svd.transform(query_tfidf)

    # Compute cosine similarities between query and all docs
    sims = sklearn_cosine_similarity(query_vec, doc_vectors)[0]
    
    # Get top 10 indices
    top_indices = sims.argsort()[-10:][::-1]
    
    # Avoid zero division when normalizing query
    query_norm = np.linalg.norm(query_vec[0])
    q_vec_normalized = query_vec[0] / query_norm if query_norm > 0 else query_vec[0]
    
    upvote_weight = 0.15
    rows = []
    dim_top_words = models["dim_top_words"]
    
    for idx in top_indices:
        row_data = df.iloc[idx]
        sim_score = float(sims[idx])
        upvote_score = float(row_data['score'])
        
        # Calculate matching dimensions contribution
        d_vec = doc_vectors[idx]
        d_norm = np.linalg.norm(d_vec)
        d_vec_normalized = d_vec / d_norm if d_norm > 0 else d_vec
        
        # Element-wise product gives contribution of each dimension to cosine similarity
        contributions = q_vec_normalized * d_vec_normalized
        top_contrib_indices = contributions.argsort()[-5:][::-1]
        
        top_matching_dimensions = []
        for d_idx in top_contrib_indices:
            top_matching_dimensions.append({
                "id": int(d_idx),
                "contribution": round(float(contributions[d_idx]), 4),
                "words": dim_top_words[d_idx]
            })
        
        # Format descriptor text
        body_text = str(row_data['body'])
        if len(body_text) > 500:
            body_text = body_text[:500] + "..."
            
        rows.append({
            "title": str(row_data['title']),
            "descr": body_text,
            "id": str(row_data['id']),
            "url": str(row_data.get('url', '')),
            "num_comments": int(row_data.get('num_comments', 0)),
            # Keep legacy key for existing frontend compatibility
            "imdb_rating": upvote_score,
            "upvote_score": upvote_score,
            "cosine_similarity": round(sim_score, 4),
            "similarity_score": round(sim_score, 4),
            "top_matching_dimensions": top_matching_dimensions,
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
