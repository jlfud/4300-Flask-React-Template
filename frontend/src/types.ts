export interface Episode {
  title: string;
  descr: string;
  imdb_rating: number;
  similarity_score?: number;
  cosine_similarity?: number;
  upvote_score?: number;
  upvote_score_norm?: number;
  final_score?: number;
  final_score_pct?: number;
  rank?: number;
}
