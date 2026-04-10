import { useState, useEffect } from 'react'
import './App.css'
import SearchIcon from './assets/mag.png'
import { Episode, FilterOptionsPayload } from './types'
import Chat from './Chat'
import { Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer, Tooltip } from 'recharts'

type HeartBurst = {
  id: string
  x: number
  size: number
  durationMs: number
  delayMs: number
  opacity: number
  hue: 'pink' | 'berry'
}

const THEME_STORAGE_KEY = 'hey-girlie-theme'

type ThemeMode = 'light' | 'dark'

function readStoredTheme(): ThemeMode {
  try {
    const s = localStorage.getItem(THEME_STORAGE_KEY)
    if (s === 'dark' || s === 'light') return s
    /* migrate old three-mode values */
    if (s === 'intense') return 'dark'
    if (s === 'soft' || s === 'cozy') return 'light'
  } catch {
    /* ignore */
  }
  return 'light'
}

function clamp(n: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, n))
}

function formatPct(pct: number | undefined): string {
  if (pct === undefined || Number.isNaN(pct)) return '—'
  return `${pct.toFixed(2)}%`
}

function formatNum(n: number | undefined, digits = 2): string {
  if (n === undefined || Number.isNaN(n)) return '—'
  return n.toFixed(digits)
}

function buildEpisodesUrl(title: string, f: {
  safeMode: boolean
  blockwords: string
}): string {
  const p = new URLSearchParams()
  p.set('title', title)
  if (f.safeMode) p.set('safe_mode', '1')
  if (f.blockwords.trim()) p.set('blockwords', f.blockwords.trim())
  return `/api/episodes?${p.toString()}`
}

function ResultCard({ episode }: { episode: Episode }): JSX.Element {
  const scorePctRaw =
    episode.final_score_pct ??
    (episode.final_score !== undefined ? episode.final_score * 100 : undefined)
  const scorePct = scorePctRaw !== undefined ? clamp(scorePctRaw, 0, 100) : undefined

  const cosine = episode.cosine_similarity ?? episode.similarity_score
  const upvotes = episode.upvote_score ?? episode.imdb_rating
  const comments = episode.num_comments

  return (
    <div className="result-card">
      <div className="result-card__top">
        <h3 className="result-card__title">
          {episode.rank !== undefined ? <span className="result-card__rank">#{episode.rank}</span> : null}
          {episode.url ? (
            <a className="result-card__link" href={episode.url} target="_blank" rel="noopener noreferrer">
              {episode.title}
            </a>
          ) : (
            <span>{episode.title}</span>
          )}
        </h3>
      </div>

      <div className="result-card__body">
        <div className="score-gauge" style={{ ['--pct' as any]: scorePct ?? 0 }}>
          <div className="score-gauge__ring" aria-hidden="true" />
          <div className="score-gauge__center">
            <div className="score-gauge__label">Final score</div>
            <div className="score-gauge__value">{formatPct(scorePct)}</div>
          </div>
        </div>

        <div className="result-card__content">
          <p className="result-card__summaryLabel">Summary (whole post, extractive)</p>
          <p className="result-card__desc">{episode.descr}</p>
          {episode.summary_source === 'title_only' || episode.summary_source === 'unavailable' ? (
            <p className="result-card__fullHint">Post text was removed on Reddit — the link may still show some comments.</p>
          ) : null}
          {episode.summary_source === 'comments' ? (
            <p className="result-card__fullHint">Summary uses comment text stored in our dataset (not live-fetched).</p>
          ) : null}
          {episode.summary_source === 'body' &&
          episode.body_full_length !== undefined &&
          episode.body_full_length > (episode.descr?.length ?? 0) + 20 ? (
            <p className="result-card__fullHint">Full post is longer — open the link for the whole thread.</p>
          ) : null}

          <div className="metric-row" aria-label="Match metrics">
            <div className="metric-pill">
              <div className="metric-pill__k">Cosine</div>
              <div className="metric-pill__v">{formatNum(cosine, 4)}</div>
            </div>
            <div className="metric-pill">
              <div className="metric-pill__k">Upvotes</div>
              <div className="metric-pill__v">{upvotes !== undefined ? upvotes.toFixed(1) : '—'}</div>
            </div>
            <div className="metric-pill">
              <div className="metric-pill__k">Comments</div>
              <div className="metric-pill__v">{comments ?? '—'}</div>
            </div>
          </div>

          {episode.top_matching_dimensions && episode.top_matching_dimensions.length > 0 ? (
            <details className="dims">
              <summary className="dims__summary">Top matching semantic dimensions</summary>
              <div className="dims__list">
                {episode.top_matching_dimensions.map((dim) => (
                  <div key={dim.id} className="dim-row">
                    <div className="dim-row__meta">
                      <div className="dim-row__title">
                        <span className="dim-badge">Dim {dim.id}</span>
                        <span className="dim-contrib">{dim.contribution.toFixed(4)}</span>
                      </div>
                      <div className="dim-words">
                        {dim.words.slice(0, 10).map((w) => (
                          <span key={`${dim.id}-${w}`} className="word-chip word-chip--muted">{w}</span>
                        ))}
                      </div>
                    </div>
                    <div className="dim-row__bar" aria-hidden="true">
                      <div
                        className="dim-row__barFill"
                        style={{ width: `${clamp(dim.contribution * 100, 0, 100)}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </details>
          ) : null}

          {episode.radar_strengths && episode.radar_strengths.length > 0 ? (
            <div className="result-card__radar">
              <h4 className="result-card__radarTitle">SVD component strengths</h4>
              <div className="result-card__radarChart">
                <ResponsiveContainer width="100%" height="100%">
                  <RadarChart cx="50%" cy="50%" outerRadius="70%" data={episode.radar_strengths}>
                    <PolarGrid />
                    <PolarAngleAxis dataKey="name" tick={{ fontSize: 9, fill: '#7a4a62' }} />
                    <PolarRadiusAxis angle={30} domain={[0, 1]} tick={{ fontSize: 9 }} />
                    <Radar
                      name="Strength"
                      dataKey="value"
                      stroke="#ff5aa8"
                      fill="#ff5aa8"
                      fillOpacity={0.28}
                      strokeWidth={2}
                    />
                    <Tooltip
                      formatter={(value) =>
                        typeof value === 'number' ? value.toFixed(3) : String(value ?? '')
                      }
                      contentStyle={{ borderRadius: '10px', fontSize: '12px' }}
                    />
                  </RadarChart>
                </ResponsiveContainer>
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}

function HeartEyesCatIcon(): JSX.Element {
  return (
    <svg
      className="cat-icon"
      width="44"
      height="44"
      viewBox="0 0 48 48"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M14 14.5 8.8 10.2c-1-.8-2.5 0-2.3 1.3l1.2 8.3M34 14.5l5.2-4.3c1-.8 2.5 0 2.3 1.3l-1.2 8.3"
        stroke="currentColor"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M13.5 21.2c-2.2 2.2-3.5 5.2-3.5 8.6 0 8 6.3 13.7 14 13.7s14-5.7 14-13.7c0-3.4-1.3-6.4-3.5-8.6-2.8-2.8-6.6-4.3-10.5-4.3s-7.7 1.5-10.5 4.3Z"
        stroke="currentColor"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M20.2 30.4c-1.1-1.1-3.1-1.5-4.3 0-1.2 1.5.2 3.4 2.2 4.6 2-1.2 3.4-3.1 2.1-4.6Zm11.6 0c-1.1-1.1-3.1-1.5-4.3 0-1.2 1.5.2 3.4 2.2 4.6 2-1.2 3.4-3.1 2.1-4.6Z"
        fill="currentColor"
        opacity="0.85"
      />
      <path
        d="M24 32.5c-1.1 0-2 .9-2 2 0 1.5 2 3.3 2 3.3s2-1.8 2-3.3c0-1.1-.9-2-2-2Z"
        fill="currentColor"
      />
      <path
        d="M13.2 33.8h5.4M29.4 33.8h5.4"
        stroke="currentColor"
        strokeWidth="2.2"
        strokeLinecap="round"
      />
    </svg>
  )
}

function App(): JSX.Element {
  const [useLlm, setUseLlm] = useState<boolean | null>(null)
  const [searchTerm, setSearchTerm] = useState<string>('')
  const [episodes, setEpisodes] = useState<Episode[]>([])
  const [isLoading, setIsLoading] = useState<boolean>(false)
  const [lastQuery, setLastQuery] = useState<string>('')
  const [heartBursts, setHeartBursts] = useState<HeartBurst[]>([])
  const [theme, setTheme] = useState<ThemeMode>(readStoredTheme)
  const [filterOptions, setFilterOptions] = useState<FilterOptionsPayload | null>(null)
  const [filtersOpen, setFiltersOpen] = useState(false)
  const [safeMode, setSafeMode] = useState(false)
  const [blockwords, setBlockwords] = useState('')

  useEffect(() => {
    fetch('/api/config').then(r => r.json()).then(data => setUseLlm(data.use_llm))
  }, [])

  useEffect(() => {
    fetch('/api/filter-options')
      .then((r) => r.json())
      .then((data: FilterOptionsPayload) => setFilterOptions(data))
      .catch(() => setFilterOptions(null))
  }, [])

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try {
      localStorage.setItem(THEME_STORAGE_KEY, theme)
    } catch {
      /* ignore */
    }
  }, [theme])

  const spawnHearts = (count = 7): void => {
    const now = Date.now()
    const newHearts: HeartBurst[] = Array.from({ length: count }).map((_, i) => {
      const id = `hb_${now}_${i}_${Math.random().toString(16).slice(2)}`
      return {
        id,
        x: (Math.random() * 56) - 28,
        size: 10 + Math.random() * 10,
        durationMs: 900 + Math.random() * 900,
        delayMs: Math.random() * 120,
        opacity: 0.55 + Math.random() * 0.35,
        hue: Math.random() < 0.72 ? 'pink' : 'berry',
      }
    })

    const maxLifetime = Math.max(...newHearts.map(h => h.durationMs + h.delayMs))
    setHeartBursts(prev => [...prev, ...newHearts])
    window.setTimeout(() => {
      setHeartBursts(prev => prev.filter(h => !newHearts.some(nh => nh.id === h.id)))
    }, maxLifetime + 60)
  }

  const handleSearch = async (value: string): Promise<void> => {
    setSearchTerm(value)
    const q = value.trim()
    setLastQuery(q)
    if (q === '') { setEpisodes([]); return }
    setIsLoading(true)
    try {
      const url = buildEpisodesUrl(q, {
        safeMode,
        blockwords,
      })
      const response = await fetch(url)
      const data: Episode[] = await response.json()
      setEpisodes(data)
    } finally {
      setIsLoading(false)
    }
  }

  if (useLlm === null) return <></>

  return (
    <div className={`full-body-container ${useLlm ? 'llm-mode' : ''}`}>
      <div className="theme-switcher" role="group" aria-label="Color mode">
        {(['light', 'dark'] as const).map((t) => (
          <button
            key={t}
            type="button"
            className={`theme-switcher__btn ${theme === t ? 'theme-switcher__btn--active' : ''}`}
            onClick={() => setTheme(t)}
            aria-pressed={theme === t}
          >
            {t === 'light' ? 'Light' : 'Dark'}
          </button>
        ))}
      </div>

      {/* Search bar (always shown) */}
      <div className="top-text">
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '24px' }}>
          <div
            className="girlie-logo girlie-logo--home"
            role="link"
            tabIndex={0}
            aria-label="Back to home"
            title="Back to home"
            onClick={() => {
              window.location.assign('/')
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                window.location.assign('/')
              }
            }}
          >
            <button
              type="button"
              className="girlie-logo__cat"
              aria-label="Cat mascot (click for hearts)"
              onClick={(ev) => {
                ev.stopPropagation()
                spawnHearts(9)
              }}
            >
              <HeartEyesCatIcon />
              {heartBursts.map((h) => (
                <span
                  key={h.id}
                  className={`cat-burst-heart cat-burst-heart--${h.hue}`}
                  style={{
                    ['--x' as any]: `${h.x}px`,
                    ['--size' as any]: `${h.size}px`,
                    ['--dur' as any]: `${h.durationMs}ms`,
                    ['--delay' as any]: `${h.delayMs}ms`,
                    ['--op' as any]: h.opacity,
                  }}
                  aria-hidden="true"
                >
                  ♥
                </span>
              ))}
            </button>
            <span className="girlie-logo__text">Hey Girlie</span>
            <span className="girlie-logo__dots" aria-hidden="true">…</span>
          </div>
        </div>
        <p className="project-subtitle">
          Relatable relationship advice from real Reddit posts!
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

        <div className="search-filters">
          <button
            type="button"
            className="search-filters__toggle"
            aria-expanded={filtersOpen}
            onClick={() => setFiltersOpen((o) => !o)}
          >
            Filters — block words and safe mode
            <span className="search-filters__chevron" aria-hidden="true">{filtersOpen ? '▴' : '▾'}</span>
          </button>
          {filtersOpen && !filterOptions ? (
            <p className="search-filters__loading">Loading filters…</p>
          ) : null}
          {filtersOpen && filterOptions ? (
            <div className="search-filters__panel">
              <p className="search-filters__hint">
                {filterOptions.blockwords_help}{' '}
                {filterOptions.safe_mode_help}
              </p>

              <div className="search-filters__row">
                <span className="search-filters__label">Block words</span>
                <input
                  type="text"
                  className="search-filters__text"
                  placeholder="e.g. gambling, drugs, slur phrase here"
                  value={blockwords}
                  onChange={(e) => setBlockwords(e.target.value)}
                  aria-label="Words or phrases to exclude from results"
                />
              </div>

              <label className="search-filters__check">
                <input
                  type="checkbox"
                  checked={safeMode}
                  onChange={(e) => setSafeMode(e.target.checked)}
                />
                <span>Safe mode — also hide posts that match a built-in adult / explicit term list</span>
              </label>

              <button
                type="button"
                className="search-filters__apply"
                onClick={() => { if (searchTerm.trim()) void handleSearch(searchTerm) }}
              >
                Apply filters to search
              </button>
            </div>
          ) : null}
        </div>
      </div>

      {/* Search results (always shown) */}
      <div id="answer-box">
        {isLoading ? (
          <>
            <div className="loading-card">
              <div className="loading-mascot" aria-hidden="true">
                <div className="loading-mascot__shadow" />
                <div className="loading-mascot__body loading-mascot__body--spin">
                  <div className="loading-mascot__spark loading-mascot__spark--a" />
                  <div className="loading-mascot__spark loading-mascot__spark--b" />
                  <div className="loading-mascot__spark loading-mascot__spark--c" />
                </div>
              </div>
              <div className="loading-copy">
                <div className="loading-title">Hey girlie… I’m finding your matches</div>
                <div className="loading-subtitle">
                  {lastQuery ? <>Searching posts like “{lastQuery}”</> : <>Preparing results…</>}
                </div>
                <div className="skeleton-row">
                  <div className="skeleton skeleton--pill" />
                  <div className="skeleton skeleton--pill" />
                  <div className="skeleton skeleton--pill" />
                </div>
                <div className="skeleton skeleton--line" />
                <div className="skeleton skeleton--line skeleton--line2" />
              </div>
            </div>

            <div className="skeleton-cards">
              {[0, 1].map((i) => (
                <div key={i} className="result-card result-card--skeleton">
                  <div className="skeleton skeleton--title" />
                  <div className="result-card__body">
                    <div className="skeleton skeleton--gauge" />
                    <div>
                      <div className="skeleton skeleton--line" />
                      <div className="skeleton skeleton--line skeleton--line2" />
                      <div className="skeleton-row">
                        <div className="skeleton skeleton--pill" />
                        <div className="skeleton skeleton--pill" />
                        <div className="skeleton skeleton--pill" />
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </>
        ) : (
          <>
            {episodes.length > 0 && (
              <p className="result-count">Top {episodes.length} matches</p>
            )}
            {episodes.length === 0 && lastQuery && !isLoading ? (
              <p className="result-count result-count--empty">
                No posts matched. Clear block words if you listed very common terms (e.g. “reddit”), turn off safe mode if it is hiding everything, or try a different search.
              </p>
            ) : null}
            {episodes.map((episode, index) => (
              <ResultCard key={`${episode.rank ?? index}-${episode.title}`} episode={episode} />
            ))}
          </>
        )}
      </div>

      {/* Chat (only when USE_LLM = True in routes.py) */}
      {useLlm && <Chat onSearchTerm={handleSearch} />}
    </div>
  )
}

export default App
