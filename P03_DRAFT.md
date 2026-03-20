# P03 Report Draft (Replace Placeholders)

## Abstract

**Live Prototype:** [PASTE_YOUR_LIVE_PROTOTYPE_URL_HERE](https://example.com)  
**Code Repository (optional):** [PASTE_REPO_URL_HERE](https://example.com)

This prototype helps users find Reddit relationship posts that are most similar to their own relationship situation. Users provide a short free-text description (for example, conflict with a partner, trust concerns, or breakup uncertainty), and the system returns the top ten most relevant posts with a similarity score and matched-topic signals. The goal is to help users feel understood by surfacing comparable experiences from other people rather than generic advice.

Our current baseline method uses normalized text similarity and cosine ranking over a Reddit-derived corpus stored in the app database. We preprocess both user query text and post text with the same normalization pipeline, compute weighted sparse vectors, and return top-ranked results. We also include interpretable output metadata (e.g., key topics and matched terms) so users can understand why each result was retrieved.

---

## Baseline Method (Current Output Generator)

### 1) Retrieval Setup
The system stores Reddit post `title` and `descr` text in the backend database (`Episode` rows in `src/init.json` and `instance/data.db`).  
At query time, each document is represented as:

- document text = `title + descr`
- query text = user input from the search bar

Why this matters: concatenating title and body gives both short-topic cues (title) and richer context (description), improving retrieval recall.

### 2) Shared Text Normalization
Both query and documents are passed through the same preprocessing in `src/routes.py`:

- tokenization (`TOKEN_RE`)
- lowercasing + punctuation cleanup
- stopword filtering (`STOPWORDS`)
- synonym mapping (`SYNONYM_GROUPS`)  
  examples: `boyfriend -> bf`, `girlfriend -> gf`, `fighting -> argue`

Why this matters: shared preprocessing puts query/doc text into a common feature space so semantically similar wording can match even when exact wording differs.

### 3) Weighted Vectorization
For each normalized term:

- raw count is computed (`term_counts`)
- optional importance boost is applied (`TERM_BOOSTS`)  
  examples: higher boosts for terms like `cheat`, `trust`, `breakup`

Vector value rule:

`weight(term) = count(term) * boost(term)`

Why this matters: this lets domain-important relationship terms influence ranking more strongly than generic terms.

### 4) Cosine Similarity Ranking
For query vector `q` and document vector `d`, score is:

`cosine(q, d) = dot(q, d) / (||q|| * ||d||)`

Then:

- results are sorted descending by similarity score
- top ten results are returned (`matches[:10]`)

Why this matters: cosine similarity compares direction rather than raw length, so long posts are not automatically favored only because they contain more words.

### 5) Post-processing / Explainability
Each result includes:

- `similarity_score`
- `matched_terms` (query/doc counts, per-term contribution)
- `key_topics`

Why this matters: these fields make the ranking auditable and interpretable for users and evaluators.

### 6) Upvote-Downvote / Popularity Signal
Current baseline status:

- The assignment asks for upvote/downvote score ranking.
- Our current deployed schema does not yet expose Reddit vote metadata as a direct field.
- Current ranking is primarily text similarity (cosine), with top-10 truncation.

Planned extension (next iteration):

- add `score` (or `upvotes`, `downvotes`) to the ingestion schema
- combine with similarity using weighted fusion, e.g.:  
  `final_score = alpha * cosine_score + (1 - alpha) * normalized_vote_score`

Why this matters: combining relevance and popularity typically improves perceived usefulness and trust in top results.

---

## Five Input-Output Examples (With Screenshots)

> Insert one screenshot per example.  
> Screenshot should show the input text and returned top results on the prototype UI.

### Example 1 (works well)
**Input:** "My boyfriend goes out with friends but avoids going out with me."  
**Output screenshot:** `[INSERT SCREENSHOT 1 HERE]`  
**Brief analysis (1-2 sentences):** The top results contain partner/going-out mismatch themes and include high overlap on normalized partner terms. This aligns with expectations because synonym mapping (`boyfriend -> bf`) and relationship-topic boosts increase relevance.

### Example 2 (works well)
**Input:** "Should I get back with my ex after a breakup?"  
**Output screenshot:** `[INSERT SCREENSHOT 2 HERE]`  
**Brief analysis (1-2 sentences):** The system surfaces breakup and ex-related posts in the top results, which matches user intent. The boosted terms for `ex` and `breakup` improved ranking for directly relevant posts.

### Example 3 (works moderately)
**Input:** "My partner cheated and now I can't trust them."  
**Output screenshot:** `[INSERT SCREENSHOT 3 HERE]`  
**Brief analysis (1-2 sentences):** Results are mostly on infidelity/trust conflict but may include some generic conflict posts. This partially matches expectations and suggests adding vote-based reranking may further improve precision.

### Example 4 (weaker case)
**Input:** "Long-distance communication problems and emotional disconnect."  
**Output screenshot:** `[INSERT SCREENSHOT 4 HERE]`  
**Brief analysis (1-2 sentences):** Some relevant long-distance/communication posts appear, but a few high-level relationship conflict posts may rank above niche long-distance cases. This indicates a need for additional phrase handling or TF-IDF/embedding support.

### Example 5 (weaker / edge case)
**Input:** "How do I handle family pressure about my relationship choices?"  
**Output screenshot:** `[INSERT SCREENSHOT 5 HERE]`  
**Brief analysis (1-2 sentences):** Results may drift toward general relationship tension rather than family-specific pressure. This differs from expectations and motivates adding topic filters or broader forum sources beyond one subreddit.

---

## TA Meta Review Feedback: What We Implemented

The TA feedback emphasized feasibility and differentiation from a plain Reddit search. We implemented this feedback in three ways. First, we clarified input and output format in the prototype: input is a multi-sentence relationship query; output is a ranked list of top similar posts with score and topical signals. Second, we improved the retrieval method beyond naive keyword lookup by using shared normalization and cosine similarity over weighted vectors. Third, we added transparent output components (similarity score, key topics, matched terms) so users can see why a result appears.

The TA also suggested considering additional sources beyond only one subreddit. We have not fully implemented multi-source ingestion yet in the current prototype due milestone scope and integration time. We plan to extend ingestion to other forums in the next iteration and compare retrieval quality against the current Reddit-only baseline.

---

## Submission Packaging Steps (P03 + P02 Combined PDF)

1. Export this completed P03 writeup to `p03.pdf` (after adding screenshots and real links).
2. Locate your previous P02 PDF, e.g. `p02.pdf`.
3. Merge in this order: `p03.pdf` first, then `p02.pdf`.
4. Replace your existing HotCRP submission with the merged PDF (`COMBINED_PDF`).

### Quick merge command (Python)
If needed:

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

