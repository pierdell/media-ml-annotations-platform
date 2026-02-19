import { useState } from 'react'
import { Search, Zap, FileText, Image, Layers, SlidersHorizontal } from 'lucide-react'
import { clsx } from 'clsx'
import { api } from '@/lib/api'
import type { SearchResult } from '@/types'

const MODES = [
  { value: 'hybrid', label: 'Hybrid', icon: Layers, desc: 'Text + Image vectors' },
  { value: 'text', label: 'Text', icon: FileText, desc: 'Sentence embeddings' },
  { value: 'image', label: 'Image', icon: Image, desc: 'CLIP embeddings' },
] as const

export default function SearchPage() {
  const [query, setQuery] = useState('')
  const [mode, setMode] = useState<string>('hybrid')
  const [results, setResults] = useState<SearchResult[]>([])
  const [total, setTotal] = useState(0)
  const [searching, setSearching] = useState(false)
  const [hasSearched, setHasSearched] = useState(false)
  const [showFilters, setShowFilters] = useState(false)

  const handleSearch = async (e?: React.FormEvent) => {
    e?.preventDefault()
    if (!query.trim()) return
    setSearching(true)
    setHasSearched(true)
    try {
      const res = await api.search({ query, mode, limit: 30 })
      setResults(res.results)
      setTotal(res.total)
    } catch (err) {
      console.error(err)
      setResults([])
    }
    setSearching(false)
  }

  const getScoreColor = (score: number) => {
    if (score >= 0.8) return 'text-emerald-400'
    if (score >= 0.6) return 'text-brand-400'
    if (score >= 0.4) return 'text-amber-400'
    return 'text-gray-500'
  }

  const getScoreBar = (score: number) => {
    if (score >= 0.8) return 'bg-emerald-500'
    if (score >= 0.6) return 'bg-brand-500'
    if (score >= 0.4) return 'bg-amber-500'
    return 'bg-gray-600'
  }

  return (
    <div className="animate-fade-in">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-100">Hybrid Search</h1>
        <p className="text-gray-500 mt-1">Search across documents and images using semantic embeddings</p>
      </div>

      {/* Search bar */}
      <form onSubmit={handleSearch} className="mb-6">
        <div className="relative">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-500" />
          <input
            id="search-input"
            value={query}
            onChange={e => setQuery(e.target.value)}
            className="w-full pl-12 pr-32 py-4 bg-gray-900/60 backdrop-blur-xl border border-gray-800/50 rounded-2xl text-gray-100 text-lg placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:border-brand-500/60 transition-all duration-200"
            placeholder="Search documents, images, references..."
          />
          <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-2">
            <button
              type="button"
              onClick={() => setShowFilters(!showFilters)}
              className={clsx(
                'p-2 rounded-lg transition-all',
                showFilters ? 'bg-brand-600/20 text-brand-400' : 'text-gray-500 hover:text-gray-300'
              )}
            >
              <SlidersHorizontal className="w-4 h-4" />
            </button>
            <button type="submit" disabled={searching || !query.trim()} className="btn-primary py-2 px-5 text-sm flex items-center gap-1.5">
              {searching ? (
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <><Zap className="w-3.5 h-3.5" /> Search</>
              )}
            </button>
          </div>
        </div>
      </form>

      {/* Mode selector */}
      {showFilters && (
        <div className="glass-card p-4 mb-6 animate-slide-up">
          <p className="section-title mb-3">Search Mode</p>
          <div className="flex gap-3">
            {MODES.map(m => (
              <button
                key={m.value}
                onClick={() => setMode(m.value)}
                className={clsx(
                  'flex-1 p-4 rounded-xl border transition-all duration-200',
                  mode === m.value
                    ? 'bg-brand-600/10 border-brand-500/40 text-brand-400'
                    : 'bg-gray-800/30 border-gray-800/50 text-gray-400 hover:border-gray-700/60'
                )}
              >
                <m.icon className="w-5 h-5 mb-2" />
                <p className="font-medium text-sm">{m.label}</p>
                <p className="text-xs opacity-60 mt-0.5">{m.desc}</p>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Results */}
      {hasSearched && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <p className="text-sm text-gray-500">
              {total} result{total !== 1 ? 's' : ''} for <span className="text-gray-300">"{query}"</span>
            </p>
            <p className="text-xs text-gray-600">
              Mode: <span className="text-gray-400 capitalize">{mode}</span>
            </p>
          </div>

          {results.length === 0 ? (
            <div className="glass-card flex flex-col items-center py-16 text-center">
              <Search className="w-10 h-10 text-gray-600 mb-3" />
              <p className="text-gray-400">No results found</p>
              <p className="text-sm text-gray-600 mt-1">Try a different query or search mode</p>
            </div>
          ) : (
            <div className="space-y-3">
              {results.map((result, idx) => (
                <div key={result.id} className="glass-card-hover p-5 animate-slide-up" style={{ animationDelay: `${idx * 40}ms` }}>
                  <div className="flex items-start gap-4">
                    {/* Type icon */}
                    <div className={clsx(
                      'w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0',
                      result.content_type === 'reference_media'
                        ? 'bg-purple-500/15'
                        : 'bg-brand-500/15'
                    )}>
                      {result.content_type === 'reference_media' ? (
                        <Image className="w-4 h-4 text-purple-400" />
                      ) : (
                        <FileText className="w-4 h-4 text-brand-400" />
                      )}
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <h3 className="font-medium text-gray-200 truncate">
                          {result.title || 'Untitled'}
                        </h3>
                        <span className={clsx(
                          'text-[10px] uppercase font-semibold px-1.5 py-0.5 rounded',
                          result.content_type === 'reference_media'
                            ? 'bg-purple-500/15 text-purple-400'
                            : 'bg-brand-500/15 text-brand-400'
                        )}>
                          {result.content_type === 'reference_media' ? 'Image' : 'Document'}
                        </span>
                      </div>
                      {result.snippet && (
                        <p className="text-sm text-gray-500 line-clamp-2">{result.snippet}</p>
                      )}
                    </div>

                    {/* Score */}
                    <div className="flex flex-col items-end gap-1 flex-shrink-0">
                      <span className={clsx('text-sm font-mono font-semibold', getScoreColor(result.score))}>
                        {(result.score * 100).toFixed(1)}%
                      </span>
                      <div className="w-16 h-1.5 bg-gray-800 rounded-full overflow-hidden">
                        <div
                          className={clsx('h-full rounded-full transition-all duration-500', getScoreBar(result.score))}
                          style={{ width: `${result.score * 100}%` }}
                        />
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Empty state before search */}
      {!hasSearched && (
        <div className="flex flex-col items-center py-20 text-center">
          <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-brand-600/10 to-cyan-600/10 flex items-center justify-center mb-6 border border-brand-500/10">
            <Search className="w-8 h-8 text-brand-500/50" />
          </div>
          <h3 className="text-lg font-medium text-gray-300 mb-2">Search your index</h3>
          <p className="text-gray-500 max-w-md">
            Enter a query to search across all indexed documents and images using hybrid semantic search.
          </p>
          <div className="flex gap-2 mt-6">
            {['oak tree leaves', 'photosynthesis process', 'bark texture'].map(example => (
              <button
                key={example}
                onClick={() => { setQuery(example); }}
                className="px-3 py-1.5 text-xs bg-gray-800/50 border border-gray-700/30 rounded-lg text-gray-400 hover:text-gray-200 hover:border-gray-600/50 transition-all"
              >
                {example}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
