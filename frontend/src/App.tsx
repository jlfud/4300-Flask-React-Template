import { useState, useEffect } from 'react'
import './App.css'
import SearchIcon from './assets/mag.png'
import { Episode } from './types'
import Chat from './Chat'

function App(): JSX.Element {
  const [useLlm, setUseLlm] = useState<boolean | null>(null)
  const [searchTerm, setSearchTerm] = useState<string>('')
  const [episodes, setEpisodes] = useState<Episode[]>([])

  useEffect(() => {
    fetch('/api/config').then(r => r.json()).then(data => setUseLlm(data.use_llm))
  }, [])

  const handleSearch = async (value: string): Promise<void> => {
    setSearchTerm(value)
    if (value.trim() === '') { setEpisodes([]); return }
    const response = await fetch(`/api/episodes?title=${encodeURIComponent(value)}`)
    const data: Episode[] = await response.json()
    setEpisodes(data)
  }

  if (useLlm === null) return <></>

  return (
    <div className={`full-body-container ${useLlm ? 'llm-mode' : ''}`}>
      {/* Search bar (always shown) */}
      <div className="top-text">
        <h1 className="project-title">Hey Girlies...</h1>
        <p className="project-subtitle">
          Relatable relationship advice from real experiences.
        </p>
        <div className="input-box" onClick={() => document.getElementById('search-input')?.focus()}>
          <img src={SearchIcon} alt="search" />
          <input
            id="search-input"
            placeholder="Describe your relationship situation and press Enter"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                void handleSearch(searchTerm)
              }
            }}
          />
        </div>
      </div>

      {/* Search results (always shown) */}
      <div id="answer-box">
        {episodes.length > 0 && (
          <p className="result-count">Top {episodes.length} matches</p>
        )}
        {episodes.map((episode, index) => (
          <div key={index} className="episode-item">
            <h3 className="episode-title">
              {episode.rank !== undefined ? `#${episode.rank} ` : ''}
              {episode.url ? (
                <a href={episode.url} target="_blank" rel="noopener noreferrer" style={{color: 'inherit'}}>
                  {episode.title}
                </a>
              ) : (
                episode.title
              )}
            </h3>
            <p className="episode-desc">{episode.descr}</p>
            {episode.final_score_pct !== undefined && (
              <p className="episode-rating">Final Score: {episode.final_score_pct.toFixed(2)}%</p>
            )}
            <p className="episode-rating">
              Cosine Similarity Score: {(episode.cosine_similarity ?? episode.similarity_score ?? 0).toFixed(4)}
            </p>
            <p className="episode-rating">
              Upvote Score: {(episode.upvote_score ?? episode.imdb_rating).toFixed(1)}
            </p>
            <p className="episode-rating">
              Number of Comments: {episode.num_comments ?? 0}
            </p>
            {episode.top_matching_dimensions && episode.top_matching_dimensions.length > 0 && (
              <div className="matching-dimensions" style={{ marginTop: '10px', fontSize: '0.9em' }}>
                <strong>Top Matching Semantic Dimensions:</strong>
                <ul style={{ margin: '5px 0 0 20px', padding: 0 }}>
                  {episode.top_matching_dimensions.map((dim, dIdx) => (
                    <li key={dIdx}>
                      Dimension {dim.id} (Contribution: {dim.contribution.toFixed(4)})<br/>
                      <em>Top words: {dim.words.join(", ")}</em>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Chat (only when USE_LLM = True in routes.py) */}
      {useLlm && <Chat onSearchTerm={handleSearch} />}
    </div>
  )
}

export default App
