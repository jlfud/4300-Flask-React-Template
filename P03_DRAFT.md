# P03 Write-Up Draft

## Abstract

**Live Prototype:** [PASTE_LIVE_PROTOTYPE_URL](https://example.com)  
**Repository (optional):** [PASTE_REPO_URL](https://example.com)

This prototype helps users find relationship discussions from Reddit that are similar to their own situation. Users input a short free-text description of a relationship issue, and the system returns the top ten related posts. Each result includes the discussion title, cosine similarity score, and an upvote-based score so users can see both relevance and community signal.

The current baseline method is intentionally simple and functional. We represent each post with four count-based dimensions (`abusive`, `time`, `talking`, `school`) and map the user query into the same four-dimensional space. We compute cosine similarity between query and post vectors, rank results, and show the top ten in the UI.

---

## Baseline Method Description

Our baseline retrieval pipeline uses count-based vector similarity (no embeddings yet). We first preprocess `relationship_advice.csv` into `src/init.json`, where each post has four numeric features: `abusive`, `time`, `talking`, and `school`. At query time, the user input is tokenized and mapped to the same four dimensions using keyword groups, producing a query vector. Each document already has a stored four-dimensional vector from preprocessing.

We score each post using cosine similarity:

`cosine_similarity = (q · d) / (||q|| * ||d||)`

Then we rank by similarity and return the top ten posts. The output shown in the prototype includes:
- discussion title
- cosine similarity score
- upvote score (currently sourced from the available score field in our data)

This gives us a working baseline that matches the final input/output shape while remaining simple enough for early-stage evaluation.

---

## TA Meta Review Feedback: What We Implemented

From TA feedback, we focused on making the system both feasible and clearly different from manually searching Reddit. We clarified the input and output contract: input is a natural-language relationship description, and output is an automatically ranked top-ten list with interpretable fields (title, cosine score, upvote score). We also moved from plain keyword title matching to vector-based similarity with explicit dimensions so ranking behavior is measurable and explainable.

We have not yet implemented advanced retrieval methods (e.g., embeddings) or multi-source forum ingestion in this milestone, because P03 prioritizes a functional baseline method on our current dataset.

---

## Five Input-Output Examples (Add Screenshots)

> Add one screenshot per example showing both the query and returned results in your running prototype.

### Example 1 (works well)
**Input:** "My partner is abusive and controlling."  
**Screenshot:** `[INSERT SCREENSHOT 1 HERE]`  
**Brief note (1-2 sentences):** Results prioritize posts with strong `abusive` signal and relevant discussion titles, which matches expectations.

### Example 2 (works well)
**Input:** "We keep arguing and have communication issues."  
**Screenshot:** `[INSERT SCREENSHOT 2 HERE]`  
**Brief note (1-2 sentences):** `talking`-related posts appear at the top, indicating expected behavior for communication-heavy queries.

### Example 3 (mixed)
**Input:** "We never have enough time for each other."  
**Screenshot:** `[INSERT SCREENSHOT 3 HERE]`  
**Brief note (1-2 sentences):** Time-related posts are retrieved, but some generic relationship posts may still rank high.

### Example 4 (weaker)
**Input:** "School stress is affecting our relationship."  
**Screenshot:** `[INSERT SCREENSHOT 4 HERE]`  
**Brief note (1-2 sentences):** School-related matches appear but are less consistent due fewer school-focused posts.

### Example 5 (edge case)
**Input:** "I feel disconnected and unsure what to do."  
**Screenshot:** `[INSERT SCREENSHOT 5 HERE]`  
**Brief note (1-2 sentences):** Broad emotional queries can have weaker dimension signal, so results may be less targeted.

---

## Submission Steps (P03 + P02 Combined PDF)

1. Fill in the live prototype link at the top of the abstract.
2. Add the 5 screenshots and short notes above.
3. Export this file to `p03.pdf`.
4. Merge PDFs in this order:
   - `p03.pdf`
   - `p02.pdf`
5. Save merged file as `COMBINED_PDF.pdf`.
6. Replace your existing HotCRP submission with `COMBINED_PDF.pdf` (do not create a new submission).

### Quick merge command
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

