# P03 Report Draft (Replace Placeholders)

## Abstract

**Live Prototype:** [PASTE_YOUR_LIVE_PROTOTYPE_URL_HERE](https://example.com)  
**Code Repository (optional):** [PASTE_REPO_URL_HERE](https://example.com)

This prototype helps users find Reddit relationship posts similar to their own relationship situation. The user input is a short natural-language description, and the system returns the top ten related discussion posts. For each result, the UI shows the post title, cosine similarity score, and an upvote-based score to approximate community signal.

Our baseline method uses four count-based dimensions (`abusive`, `time`, `talking`, `school`) that are computed for each post in `src/init.json`. We vectorize the query in the same four-dimensional space, compute cosine similarity against each post vector, and rank by similarity (with score as tie-break). This is a simple but functional baseline that runs on our data and produces the type of output we expect in later milestones.

---

## Baseline Method Description

### Data Representation
We converted `relationship_advice.csv` into `src/init.json` and added four per-post count features:

- `abusive`
- `time`
- `talking`
- `school`

Each post also has a score field (currently stored in `reviews.imdb_rating` in this template schema) that we use as an upvote-like signal.

### Query and Document Vectorization
The backend (`src/routes.py`) defines the same four dimensions for both query and document vectors.

- Query text is tokenized and mapped into those dimensions with keyword dictionaries.
- Document vectors are loaded from `src/init.json` using the precomputed four counts.

This guarantees query and documents are in the same vector space.

### Retrieval and Ranking
For each post, we compute:

`cosine_similarity = (q · d) / (||q|| * ||d||)`

Then we sort results by:
1. cosine similarity (descending)  
2. upvote score as a tie-breaker (descending)

Finally, we return the top ten results.

### Output Format
The frontend displays:

- title of the discussion post
- cosine similarity score
- upvote score

This is close to the final expected output format while still being a baseline method.

---

## TA Meta Review Feedback: What We Implemented

Based on TA feedback, we clarified both inputs and outputs and made the baseline more concrete. The input is now a free-text relationship description (the same style we expect in the final version), and the output is a ranked list of top ten posts with interpretable scores. We also moved beyond plain title keyword matching to a vector-based comparison in a shared feature space.

We still consider this a baseline implementation: it does not yet use embeddings or advanced semantic retrieval, and it currently uses a small set of handcrafted dimensions. This is intentional for P03 and provides a clear foundation for future improvements.

---

## Five Input-Output Examples (With Screenshots)

> Insert one screenshot per example showing both the input query and top returned results.

### Example 1 (works well)
**Input:** "My partner is abusive and controlling."  
**Screenshot:** `[INSERT SCREENSHOT 1 HERE]`  
**Brief analysis:** Results usually rank posts with higher `abusive` counts and relevant titles. This matches expectations for a dimension-focused query.

### Example 2 (works well)
**Input:** "We have communication problems and keep arguing."  
**Screenshot:** `[INSERT SCREENSHOT 2 HERE]`  
**Brief analysis:** `talking`-related posts are prioritized with reasonable cosine scores. This aligns with expected behavior.

### Example 3 (mixed)
**Input:** "We never have enough time for each other."  
**Screenshot:** `[INSERT SCREENSHOT 3 HERE]`  
**Brief analysis:** Time-oriented posts appear, though some broader relationship posts may still rank highly.

### Example 4 (weaker)
**Input:** "School stress is hurting our relationship."  
**Screenshot:** `[INSERT SCREENSHOT 4 HERE]`  
**Brief analysis:** School-related matches appear but are less consistent due fewer school-heavy posts.

### Example 5 (edge case)
**Input:** "I feel disconnected and unsure what to do."  
**Screenshot:** `[INSERT SCREENSHOT 5 HERE]`  
**Brief analysis:** Very broad emotional queries can have weaker dimension signal, so results are less targeted.

---

## Submission Packaging Steps (P03 + P02 Combined PDF)

1. Export this completed P03 writeup to `p03.pdf` (after adding screenshots and real links).
2. Locate your previous P02 PDF (e.g., `p02.pdf`).
3. Merge in this order: `p03.pdf` first, then `p02.pdf`.
4. Replace your existing HotCRP submission with the merged file (`COMBINED_PDF.pdf`) — do not create a new submission.

### Quick merge command (Python)
```bash
python3 -m pip install pypdf
python3 - <<'PY'
from pypdf import PdfMerger
merger = PdfMerger()
merger.append("p03.pdf")
merger.append("p02.pdf")
merger.write("COMBINED_PDF.pdf")
merger.close()
print("Wrote COMBINED_PDF.pdf")
PY
```

