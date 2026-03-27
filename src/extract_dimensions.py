from routes import get_search_models
import numpy as np

def extract_top_words_for_dimensions():
    print("Loading models and data (this might take a few seconds)...")
    models = get_search_models()
    vectorizer = models["vectorizer"]
    svd = models["svd"]
    
    # Get the words (feature names) from the TF-IDF vectorizer
    feature_names = vectorizer.get_feature_names_out()
    
    # For demonstration, we'll just look at the first 15 dimensions 
    # instead of all 100 to avoid overwhelming output.
    num_dimensions_to_show = 10
    top_n_words = 15
    
    print("\n--- Latent Dimensions (Top Words) ---\n")
    for i, component in enumerate(svd.components_[:num_dimensions_to_show]):
        # Get the indices of the top words sorted by weight (highest first)
        top_word_indices = component.argsort()[::-1][:top_n_words]
        
        # Map indices back to the actual string words
        top_words = [feature_names[index] for index in top_word_indices]
        
        print(f"Dimension {i}:")
        print(", ".join(top_words))
        print("-" * 50)

if __name__ == "__main__":
    extract_top_words_for_dimensions()
