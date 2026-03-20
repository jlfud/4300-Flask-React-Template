import csv
import json
import re

INPUT_CSV = "relationship_advice.csv"
OUTPUT_JSON = "src/init.json"

DIMENSION_VOCAB = {
    "abusive": {"abuse", "abusive", "abused", "toxic", "violent", "violence", "harass", "harassment"},
    "time": {"time", "busy", "schedule", "week", "weeks", "month", "months", "hour", "hours"},
    "talking": {"talk", "talking", "communicate", "communication", "conversation", "argue", "arguing"},
    "school": {"school", "college", "class", "classes", "campus", "homework", "university"},
}

TOKEN_RE = re.compile(r"[a-zA-Z0-9_']+")


def count_dimension_terms(text):
    counts = {k: 0 for k in DIMENSION_VOCAB}
    tokens = [t.lower() for t in TOKEN_RE.findall(text or "")]
    for token in tokens:
        for dim, vocab in DIMENSION_VOCAB.items():
            if token in vocab:
                counts[dim] += 1
    return counts


episodes = []
reviews = []

with open(INPUT_CSV, newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)

    for i, row in enumerate(reader, start=1):
        title = (row.get("title") or "").strip()
        body = (row.get("body") or "").strip()
        full_text = f"{title} {body}"
        dim_counts = count_dimension_terms(full_text)

        episodes.append(
            {
                "id": i,
                "title": title,
                "descr": body,
                "abusive": dim_counts["abusive"],
                "time": dim_counts["time"],
                "talking": dim_counts["talking"],
                "school": dim_counts["school"],
            }
        )

        try:
            score = float(row.get("score", 0))
        except (TypeError, ValueError):
            score = 0.0

        reviews.append({"id": i, "imdb_rating": score})

data = {"episodes": episodes, "reviews": reviews}

with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)

print(f"JSON file created: {OUTPUT_JSON}")