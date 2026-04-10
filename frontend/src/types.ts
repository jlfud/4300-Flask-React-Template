export interface Episode {
  title: string;
  descr: string;
  /** body | comments | title_only | unavailable — how `descr` was built */
  summary_source?: string;
  /** Character length of full post body (API may show extractive summary in descr). */
  body_full_length?: number;
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
  radar_strengths?: {
    name: string;
    value: number;
  }[];
}

export interface FilterOptionsPayload {
  safe_mode_help: string;
  blockwords_help: string;
}
