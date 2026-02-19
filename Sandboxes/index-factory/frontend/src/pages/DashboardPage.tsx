import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Plus, Boxes, ChevronRight, FileText, Search, Trash2 } from 'lucide-react'
import { api } from '@/lib/api'
import type { IndexObject } from '@/types'

export default function DashboardPage() {
  const [objects, setObjects] = useState<IndexObject[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [newName, setNewName] = useState('')
  const [newDesc, setNewDesc] = useState('')
  const [creating, setCreating] = useState(false)
  const [stats, setStats] = useState({ documents: 0 })

  const load = async () => {
    try {
      const [objs, docs] = await Promise.all([api.listObjects(), api.listDocuments()])
      setObjects(objs)
      setStats({ documents: docs.length })
    } catch (err) {
      console.error(err)
    }
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newName.trim()) return
    setCreating(true)
    try {
      await api.createObject({ name: newName, description: newDesc || undefined })
      setNewName('')
      setNewDesc('')
      setShowCreate(false)
      await load()
    } catch (err) {
      console.error(err)
    }
    setCreating(false)
  }

  const handleDelete = async (id: string) => {
    try {
      await api.deleteObject(id)
      await load()
    } catch (err) {
      console.error(err)
    }
  }

  return (
    <div className="animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-100">Dashboard</h1>
          <p className="text-gray-500 mt-1">Manage your objects and indexation pipelines</p>
        </div>
        <button onClick={() => setShowCreate(true)} className="btn-primary flex items-center gap-2">
          <Plus className="w-4 h-4" />
          New Object
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
        <div className="glass-card p-5">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-9 h-9 rounded-lg bg-brand-500/15 flex items-center justify-center">
              <Boxes className="w-4 h-4 text-brand-400" />
            </div>
            <span className="section-title">Objects</span>
          </div>
          <p className="text-3xl font-bold text-gray-100">{objects.length}</p>
        </div>
        <div className="glass-card p-5">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-9 h-9 rounded-lg bg-emerald-500/15 flex items-center justify-center">
              <FileText className="w-4 h-4 text-emerald-400" />
            </div>
            <span className="section-title">Documents</span>
          </div>
          <p className="text-3xl font-bold text-gray-100">{stats.documents}</p>
        </div>
        <div className="glass-card p-5">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-9 h-9 rounded-lg bg-purple-500/15 flex items-center justify-center">
              <Search className="w-4 h-4 text-purple-400" />
            </div>
            <span className="section-title">Search</span>
          </div>
          <Link to="/search" className="text-sm text-brand-400 hover:text-brand-300 font-medium flex items-center gap-1">
            Open hybrid search <ChevronRight className="w-3 h-3" />
          </Link>
        </div>
      </div>

      {/* Create dialog */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm animate-fade-in">
          <form onSubmit={handleCreate} className="glass-card p-8 w-full max-w-md animate-slide-up">
            <h2 className="text-xl font-semibold text-gray-100 mb-6">Create New Object</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Name</label>
                <input
                  autoFocus
                  value={newName}
                  onChange={e => setNewName(e.target.value)}
                  className="input-field"
                  placeholder="e.g. Trees"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Description</label>
                <textarea
                  value={newDesc}
                  onChange={e => setNewDesc(e.target.value)}
                  className="input-field min-h-[80px] resize-none"
                  placeholder="Optional description..."
                />
              </div>
            </div>
            <div className="flex gap-3 mt-6">
              <button type="button" onClick={() => setShowCreate(false)} className="btn-secondary flex-1">Cancel</button>
              <button type="submit" disabled={creating} className="btn-primary flex-1">
                {creating ? 'Creating...' : 'Create'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Objects grid */}
      {loading ? (
        <div className="flex justify-center py-20">
          <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : objects.length === 0 ? (
        <div className="glass-card flex flex-col items-center justify-center py-20 text-center">
          <Boxes className="w-12 h-12 text-gray-600 mb-4" />
          <h3 className="text-lg font-medium text-gray-300 mb-2">No objects yet</h3>
          <p className="text-gray-500 mb-6 max-w-sm">
            Create your first object to start building an ontology and indexing references.
          </p>
          <button onClick={() => setShowCreate(true)} className="btn-primary flex items-center gap-2">
            <Plus className="w-4 h-4" />
            Create Object
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {objects.map(obj => (
            <Link
              key={obj.id}
              to={`/objects/${obj.id}`}
              className="glass-card-hover p-6 group relative"
            >
              <div className="flex items-start justify-between mb-3">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-brand-600/20 to-cyan-600/20 flex items-center justify-center border border-brand-500/10">
                  <Boxes className="w-5 h-5 text-brand-400" />
                </div>
                <button
                  onClick={e => { e.preventDefault(); e.stopPropagation(); handleDelete(obj.id) }}
                  className="opacity-0 group-hover:opacity-100 p-1.5 text-gray-500 hover:text-red-400 transition-all"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
              <h3 className="text-lg font-semibold text-gray-100 mb-1">{obj.name}</h3>
              {obj.description && (
                <p className="text-sm text-gray-500 line-clamp-2 mb-3">{obj.description}</p>
              )}
              <div className="flex items-center gap-2 text-xs text-gray-500">
                <span>Created {new Date(obj.created_at).toLocaleDateString()}</span>
                <ChevronRight className="w-3 h-3 text-gray-600 group-hover:text-brand-400 transition-colors" />
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
