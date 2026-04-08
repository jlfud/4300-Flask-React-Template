from src.routes import get_search_models
from sklearn.metrics.pairwise import cosine_similarity
import sys

models = get_search_models()
query = "my boyfriend cheats on me"
query_tfidf = models["vectorizer"].transform([query])
query_vec = models["svd"].transform(query_tfidf)

# assuming models has tfidf_matrix cached! Let's check routes.py... wait, tfidf_matrix is not in _SEARCH_MODELS!
