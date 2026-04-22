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
from search_filters import (
    filter_options_payload,
    normalize_combined_text,
    parse_request_filters,
    passes_filters,
    tag_boost_bonus,
    tags_matched,
)

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

# Sentence boundaries for extractive summaries (no extra dependencies)
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|\n{2,}")
_WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z']+")
_SUMMARY_STOPWORDS = frozenset(
    """
    the a an and or but if in on at to for of as is was are be been being
    i me my we our you your he she it they them their what which who whom this that
    do does did have has had not no yes so very just than then too also about into
    out up down can could would should will with from by any some all each both
    when where why how there here more most much such own same other only own
    need get got go going went like just really even ever still ever
    """.split()
)

# Optional CSV columns (if present) with pre-fetched comment text for deleted/short bodies
_COMMENT_TEXT_COLUMNS = ("comments_text", "top_comments", "comments_sample")


def _is_placeholder_body(text):
    """Reddit often stores [deleted] / [removed] when the OP text is gone."""
    t = (text or "").strip().lower()
    if not t:
        return True
    inner = t.strip("[]").strip()
    if inner in ("deleted", "removed", "unavailable"):
        return True
    if t in ("[deleted]", "[removed]"):
        return True
    return False


def _query_term_set(query):
    return {
        t.lower()
        for t in _WORD_RE.findall(query or "")
        if len(t) > 2 and t.lower() not in _SUMMARY_STOPWORDS
    }


def _split_sentences(raw):
    return [p.strip() for p in _SENT_SPLIT.split(raw) if p.strip() and len(p.strip()) > 12]


def _first_sentences(parts, max_sentences, max_chars):
    out, length = [], 0
    for chunk in parts[: max_sentences * 3]:
        prospective = length + len(chunk) + (1 if out else 0)
        if prospective > max_chars:
            if not out:
                out.append(chunk[: max_chars - 3].rsplit(" ", 1)[0] + "...")
            break
        out.append(chunk)
        length = prospective
        if len(out) >= max_sentences:
            break
    return out


_MAX_SENTS_FOR_SUMMARY = 220


def _sentence_centrality(subs):
    """
    Score each sentence by how much it resembles other sentences in the same post
    (TF-IDF cosine similarity graph → row sum). Uses the full list up to cap.
    """
    n = len(subs)
    if n == 0:
        return np.array([])
    if n == 1:
        return np.array([1.0])
    use = subs[:_MAX_SENTS_FOR_SUMMARY]
    nu = len(use)
    try:
        vec = TfidfVectorizer(
            stop_words="english",
            min_df=1,
            max_df=min(0.98, 1.0),
            ngram_range=(1, 2),
        )
        X = vec.fit_transform(use)
    except ValueError:
        return np.ones(n)
    if X.shape[0] < 2 or X.shape[1] == 0:
        return np.ones(n)
    sim = np.asarray(sklearn_cosine_similarity(X), dtype=float)
    np.fill_diagonal(sim, 0.0)
    cent = np.asarray(sim.sum(axis=1)).ravel()
    cmin, cmax = float(cent.min()), float(cent.max())
    if cmax > cmin:
        cent = (cent - cmin) / (cmax - cmin)
    else:
        cent = np.ones(nu)
    if nu < n:
        full = np.zeros(n)
        full[:nu] = cent
        full[nu:] = cent.mean() if nu else 0.3
        return full
    return cent


def _query_overlap_scores(subs, boost):
    scores = []
    for s in subs:
        st = {t.lower() for t in _WORD_RE.findall(s) if len(t) > 2}
        if not boost:
            scores.append(0.0)
        else:
            scores.append(len(boost & st) / max(len(boost), 1))
    return np.array(scores, dtype=float)


def _pick_summary_sentences(subs, boost, max_sentences=3, max_chars=450):
    """
    Whole-post extractive summary: combine (1) intra-post centrality and
    (2) query/title overlap; pick best sentences, restore reading order.
    """
    if not subs:
        return ""
    full_text = " ".join(subs)

    cent = _sentence_centrality(subs)
    qscr = _query_overlap_scores(subs, boost)

    if len(boost) == 0:
        combined = cent
    else:
        qn = qscr.copy()
        qmin, qmax = float(qn.min()), float(qn.max())
        if qmax > qmin:
            qn = (qn - qmin) / (qmax - qmin)
        else:
            qn = np.zeros(len(subs))
        combined = 0.55 * cent + 0.45 * qn

    order_by_score = np.argsort(-combined)
    picked_idx = []
    for j in order_by_score:
        if len(picked_idx) >= max_sentences:
            break
        ji = int(j)
        if ji not in picked_idx:
            picked_idx.append(ji)

    picked_idx.sort()
    sentences = [subs[i] for i in picked_idx]
    joined = " ".join(sentences)
    if len(joined) > max_chars:
        trimmed = []
        length = 0
        for s in sentences:
            prospective = length + len(s) + (1 if trimmed else 0)
            if prospective > max_chars and trimmed:
                break
            if prospective > max_chars and not trimmed:
                trimmed.append(s[: max_chars - 3].rsplit(" ", 1)[0] + "...")
                break
            trimmed.append(s)
            length = prospective
        joined = " ".join(trimmed)
    if len(full_text) > len(joined) + 20:
        if not joined.endswith("..."):
            joined += "..."
    return joined


def summarize_reddit_body(text, max_sentences=2, max_chars=280):
    """
    Extractive fallback: TL;DR line (trimmed), else first 1–2 sentence chunks.
    """
    raw = (text or "").strip()
    if not raw:
        return ""

    lower = raw.lower()
    for marker in ("tl;dr", "tldr", "tl dr"):
        idx = lower.rfind(marker)
        if idx != -1:
            after = raw[idx + len(marker) :].strip()
            after = re.sub(r"^[:;\-\s]+", "", after)
            if after:
                block = after.split("\n\n")[0].strip()
                subs = _split_sentences(block) or [block.split("\n")[0].strip()]
                picked = _first_sentences(subs, max_sentences, max_chars)
                joined = " ".join(picked)
                if len(block) > len(joined) + 10:
                    joined += "..."
                return joined

    parts = _split_sentences(raw)
    if not parts:
        tail = "..." if len(raw) > max_chars else ""
        return raw[:max_chars] + tail

    out = _first_sentences(parts, max_sentences, max_chars)
    if not out:
        tail = "..." if len(raw) > max_chars else ""
        return raw[:max_chars] + tail

    joined = " ".join(out)
    if len(joined) < len(raw.strip()) - 15:
        joined += "..."
    return joined


def summarize_for_query(text, query, title_hint="", max_sentences=3, max_chars=450):
    """
    Extractive summary using the whole post: sentences are scored by similarity to
    all other sentences in the post (centrality) plus query/title overlap.
    Not an LLM paraphrase — always verbatim sentences from the text.
    """
    raw = (text or "").strip()
    if not raw:
        return ""

    q_terms = _query_term_set(query)
    title_terms = _query_term_set(title_hint)
    boost = q_terms | title_terms

    lower = raw.lower()
    for marker in ("tl;dr", "tldr", "tl dr"):
        idx = lower.rfind(marker)
        if idx != -1:
            after = raw[idx + len(marker) :].strip()
            after = re.sub(r"^[:;\-\s]+", "", after)
            if after:
                block = after.split("\n\n")[0].strip()
                subs = _split_sentences(block) or [block.split("\n")[0].strip()]
                return _pick_summary_sentences(subs, boost, max_sentences, max_chars)

    parts = _split_sentences(raw)
    if not parts:
        tail = "..." if len(raw) > max_chars else ""
        return raw[:max_chars] + tail

    return _pick_summary_sentences(parts, boost, max_sentences, max_chars)


def build_post_summary(title, body, comments_text=None, query="", max_chars=450):
    """
    Extractive summary for the card UI. Uses body when usable; otherwise optional
    comments_text (must live in CSV — we do not fetch Reddit at request time).
    Returns (summary_text, source, content_length_for_hint).
    """
    body = (body or "").strip()
    title = (title or "").strip()
    comments_text = (comments_text or "").strip() if comments_text else ""

    if not _is_placeholder_body(body):
        inner = summarize_for_query(body, query, title_hint=title, max_chars=max_chars)
        return inner, "body", len(body)

    if comments_text and not _is_placeholder_body(comments_text):
        label = "Summary from saved comments (OP text was removed): "
        budget = max_chars - len(label)
        inner = summarize_for_query(
            comments_text, query, title_hint=title, max_chars=max(budget, 80)
        )
        return label + inner, "comments", len(comments_text)

    if title:
        prefix = "Original post text is unavailable (removed or deleted). Title: "
        inner = summarize_reddit_body(title, max_sentences=2, max_chars=max_chars - len(prefix))
        return prefix + inner, "title_only", 0

    return (
        "Original post text unavailable. Open the Reddit link to see any remaining discussion.",
        "unavailable",
        0,
    )


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

    comment_column = next((c for c in _COMMENT_TEXT_COLUMNS if c in df.columns), None)
    if comment_column:
        df[comment_column] = df[comment_column].fillna('').astype(str)

    # Create combined text (indexing uses title + body only — same semantic model as main)

    docs = df['title'] + " " + df['body']
    
    from nltk.stem.snowball import SnowballStemmer
    stemmer = SnowballStemmer("english")
    
    class StemmedTfidfVectorizer(TfidfVectorizer):
        def build_analyzer(self):
            analyzer = super(StemmedTfidfVectorizer, self).build_analyzer()
            return lambda doc: [stemmer.stem(w) for w in analyzer(doc)]
            
    # TF-IDF (Now with Stemming!)
    vectorizer = StemmedTfidfVectorizer(stop_words='english', max_df=0.8, min_df=5)
    tfidf_matrix = vectorizer.fit_transform(docs)
    
    # SVD
    # Increased components to 500 to retain more granular variance for words like "cheats"
    n_components = min(500, tfidf_matrix.shape[1] - 1)
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
        "dim_top_words": dim_top_words,
        "comment_column": comment_column,
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


def json_search(query, filters=None):
    """
    Semantic search with main-branch TF-IDF + stemmed vectors + SVD scoring.
    Optional filters: topic tags, block words, safe mode (see search_filters).
    """
    if not query or not query.strip():
        query = "need relationship advice"

    if filters is None:
        filters = {
            "tag_ids": [],
            "tag_mode": "boost",
            "safe_mode": False,
            "extra_block_words": set(),
        }

    models = get_search_models()
    df = models["df"]
    vectorizer = models["vectorizer"]
    svd = models["svd"]
    doc_vectors = models["doc_vectors"]

    query_tfidf = vectorizer.transform([query])
    query_vec = svd.transform(query_tfidf)

    sims = sklearn_cosine_similarity(query_vec, doc_vectors)[0]

    # Widen pool only when something can drop candidates; else match original main (top 10 cosine).
    needs_wide_pool = (
        filters["safe_mode"]
        or bool(filters["extra_block_words"])
        or (bool(filters["tag_ids"]) and filters["tag_mode"] == "filter")
    )
    pool_size = 200 if needs_wide_pool else 10
    pool = min(pool_size, len(sims))
    top_indices = sims.argsort()[-pool:][::-1]

    query_norm = np.linalg.norm(query_vec[0])
    q_vec_normalized = query_vec[0] / query_norm if query_norm > 0 else query_vec[0]

    upvote_weight = 0.15
    rows = []
    dim_top_words = models["dim_top_words"]
    comment_column = models.get("comment_column")

    dim_names = [
        "Relationships", "Help-Seeking", "Reddit Engagement",
        "Social Interaction", "Attraction", "Breakup",
        "Physical Intimacy", "Friendzone", "Confusion", "Family",
    ]

    for idx in top_indices:
        row_data = df.iloc[idx]
        sim_score = float(sims[idx])
        upvote_score = float(row_data["score"])

        d_vec = doc_vectors[idx]
        d_norm = np.linalg.norm(d_vec)
        d_vec_normalized = d_vec / d_norm if d_norm > 0 else d_vec

        contributions = q_vec_normalized * d_vec_normalized
        top_contrib_indices = contributions.argsort()[-5:][::-1]

        top_matching_dimensions = []
        for d_idx in top_contrib_indices:
            top_matching_dimensions.append({
                "id": int(d_idx),
                "contribution": round(float(contributions[d_idx]), 4),
                "words": dim_top_words[d_idx],
            })

        strengths = np.abs(d_vec[:10])
        if np.max(strengths) > 0:
            strengths = strengths / np.max(strengths)

        radar_strengths = []
        for i in range(10):
            radar_strengths.append({
                "name": dim_names[i],
                "value": round(float(strengths[i]), 4),
            })

        body_full = str(row_data["body"])
        comments_extra = ""
        if comment_column:
            comments_extra = str(row_data.get(comment_column, "") or "")
        title_s = str(row_data["title"])
        text_for_filters = normalize_combined_text(title_s, body_full)
        if comment_column and _is_placeholder_body(body_full) and comments_extra:
            text_for_filters = normalize_combined_text(title_s, comments_extra)

        req_tags = filters["tag_ids"]
        tags_hit = tags_matched(text_for_filters, req_tags) if req_tags else set()

        ok, _drop_reason = passes_filters(text_for_filters, tags_hit, filters)
        if not ok:
            continue

        # Match old main JSON when no filters / wide pool: truncated body only (not extractive summary).
        if needs_wide_pool:
            body_summary, summary_source, hint_len = build_post_summary(
                title_s,
                body_full,
                comments_extra or None,
                query=query,
            )
            descr = body_summary
            summary_extra = {
                "summary_source": summary_source,
                "body_full_length": hint_len if summary_source == "comments" else len(body_full),
            }
        else:
            body_text = str(row_data["body"])
            if len(body_text) > 500:
                body_text = body_text[:500] + "..."
            descr = body_text
            summary_extra = {}

        rows.append({
            "title": title_s,
            "descr": descr,
            **summary_extra,
            "id": str(row_data["id"]),
            "url": str(row_data.get("url", "")),
            "num_comments": int(row_data.get("num_comments", 0)),
            "imdb_rating": upvote_score,
            "upvote_score": upvote_score,
            "cosine_similarity": round(sim_score, 4),
            "similarity_score": round(sim_score, 4),
            "top_matching_dimensions": top_matching_dimensions,
            "radar_strengths": radar_strengths,
            "_tags_hit": tags_hit,
        })

    cosine_scores = [row["cosine_similarity"] for row in rows]
    upvote_scores = [row["upvote_score"] for row in rows]
    final_scores, norm_upvotes = blend_scores(cosine_scores, upvote_scores, upvote_weight=upvote_weight)

    use_tag_boost = bool(filters["tag_ids"]) and filters["tag_mode"] == "boost"

    for i, row in enumerate(rows):
        row["upvote_score_norm"] = round(norm_upvotes[i], 4)
        tb = tag_boost_bonus(row["_tags_hit"], filters["tag_ids"])
        if use_tag_boost:
            base = final_scores[i]
            adj = min(1.0, base + tb)
            row["final_score"] = round(adj, 4)
            row["final_score_pct"] = round(adj * 100, 2)
            row["score_blend"] = {
                "cosine_weight": round(1.0 - upvote_weight, 2),
                "upvote_weight": round(upvote_weight, 2),
                "tag_boost": round(tb, 4),
            }
        else:
            row["final_score"] = final_scores[i]
            row["final_score_pct"] = round(final_scores[i] * 100, 2)
            row["score_blend"] = {
                "cosine_weight": round(1.0 - upvote_weight, 2),
                "upvote_weight": round(upvote_weight, 2),
            }
        del row["_tags_hit"]

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

    @app.route("/api/filter-options")
    def filter_options():
        return jsonify(filter_options_payload())

    @app.route("/api/episodes")
    def episodes_search():
        text = request.args.get("title", "")
        flt = parse_request_filters(request.args)
        return jsonify(json_search(text, filters=flt))

    if USE_LLM:
        from llm_routes import register_chat_route
        register_chat_route(app, json_search)