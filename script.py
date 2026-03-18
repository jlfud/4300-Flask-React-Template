import pandas as pd
import re

def count_keywords_in_csv(input_csv, output_csv):
    """
    Reads a CSV, counts occurrences of specific words in the 'body' column,
    and saves the counts into 4 new columns in a new CSV file.
    """
    # 1. Load the dataset
    df = pd.read_csv(input_csv)
    
    # Define the keywords we are looking for
    keywords = ["boyfriend", "girlfriend", "cheat", "abuse"]
    
    # 2. Pre-process the 'body' column to handle missing values
    df['body'] = df['body'].fillna('').astype(str)
    
    # 3. Create a new column for each keyword
    for word in keywords:
        # We use regex \b word \b to ensure we match whole words only.
        # re.IGNORECASE ensures 'Cheat' and 'cheat' are both counted.
        df[word] = df['body'].apply(
            lambda x: len(re.findall(rf'\b{word}\b', x, flags=re.IGNORECASE))
        )
    
    # 4. Save to a new CSV file
    df.to_csv(output_csv, index=False)
    print(f"Process complete. New file saved as: {output_csv}")

# Example Usage:
count_keywords_in_csv('relationship_advice_posts.csv', 'updated_with_counts.csv')