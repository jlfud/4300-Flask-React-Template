import csv
import json

input_csv = "relationship_advice.csv"
output_json = "reddit_posts.json"

episodes = []
reviews = []

with open(input_csv, newline='', encoding="utf-8") as f:
    reader = csv.DictReader(f)

    for i, row in enumerate(reader, start=1):
        title = row.get("title", "")
        body = row.get("body", "")

        episodes.append({
            "id": i,
            "title": title,
            "descr": body
        })

        reviews.append({
            "id": i,
            "imdb_rating": 0
        })

data = {
    "episodes": episodes,
    "reviews": reviews
}

with open(output_json, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)

print("JSON file created:", output_json)