export interface Episode {
  title: string;
  descr: string;
  url?: string;
  imdb_rating: number;
  similarity_score?: number;
  cosine_similarity?: number;
  upvote_score?: number;
  upvote_score_norm?: number;
  final_score?: number;
  final_score_pct?: number;
  rank?: number;
  num_comments?: number;
  top_matching_dimensions?: {
    id: number;
    contribution: number;
    words: string[];
  }[];
}
