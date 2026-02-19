import { useState, useEffect } from 'react'
import { Plus, FileText, Globe, File, Upload, Trash2, CheckCircle2, Clock, Eye, X } from 'lucide-react'
import { clsx } from 'clsx'
import { api } from '@/lib/api'
import type { Document } from '@/types'

const SOURCE_TYPES = [
  { value: '', label: 'All', icon: FileText },
  { value: 'text', label: 'Text', icon: File },
  { value: 'webpage', label: 'Web', icon: Globe },
  { value: 'markdown', label: 'Markdown', icon: FileText },
  { value: 'pdf', label: 'PDF', icon: File },
]

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<Document[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [showUpload, setShowUpload] = useState(false)
  const [viewDoc, setViewDoc] = useState<Document | null>(null)

  // Create form
  const [docTitle, setDocTitle] = useState('')
  const [docType, setDocType] = useState('text')
  const [docUrl, setDocUrl] = useState('')
  const [docText, setDocText] = useState('')
  const [creating, setCreating] = useState(false)
  const [uploading, setUploading] = useState(false)

  const load = async () => {
    try {
      const docs = await api.listDocuments(filter || undefined)
      setDocuments(docs)
    } catch (err) {
      console.error(err)
    }
    setLoading(false)
  }

  useEffect(() => { load() }, [filter])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setCreating(true)
    try {
      await api.createDocument({
        source_type: docType,
        title: docTitle || undefined,
        source_url: docUrl || undefined,
        raw_text: docText || undefined,
      })
      setShowCreate(false)
      setDocTitle('')
      setDocType('text')
      setDocUrl('')
      setDocText('')
      await load()
    } catch (err) {
      console.error(err)
    }
    setCreating(false)
  }

  const handleUpload = async (files: FileList | null) => {
    if (!files) return
    setUploading(true)
    for (const file of Array.from(files)) {
      try {
        await api.uploadDocument(file)
      } catch (err) {
        console.error(err)
      }
    }
    await load()
    setUploading(false)
    setShowUpload(false)
  }

  const handleDelete = async (id: string) => {
    try {
      await api.deleteDocument(id)
      await load()
    } catch (err) {
      console.error(err)
    }
  }

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'webpage': return Globe
      case 'pdf': return File
      default: return FileText
    }
  }

  return (
    <div className="animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-100">Documents</h1>
          <p className="text-gray-500 mt-1">Ingest and manage text documents for indexing</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setShowUpload(true)} className="btn-secondary flex items-center gap-2 text-sm py-2.5 px-4">
            <Upload className="w-3.5 h-3.5" />
            Upload File
          </button>
          <button onClick={() => setShowCreate(true)} className="btn-primary flex items-center gap-2 text-sm py-2.5 px-4">
            <Plus className="w-3.5 h-3.5" />
            Add Document
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-2 mb-6">
        {SOURCE_TYPES.map(st => (
          <button
            key={st.value}
            onClick={() => setFilter(st.value)}
            className={clsx(
              'px-3 py-1.5 rounded-lg text-sm font-medium transition-all duration-200 flex items-center gap-1.5',
              filter === st.value
                ? 'bg-brand-600/15 text-brand-400 border border-brand-500/30'
                : 'text-gray-500 hover:text-gray-300 border border-transparent hover:border-gray-800/50'
            )}
          >
            <st.icon className="w-3 h-3" />
            {st.label}
          </button>
        ))}
      </div>

      {/* Upload modal */}
      {showUpload && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm animate-fade-in">
          <div className="glass-card p-8 w-full max-w-md animate-slide-up">
            <h2 className="text-xl font-semibold text-gray-100 mb-4">Upload Files</h2>
            <label className={clsx(
              'flex flex-col items-center justify-center py-12 border-2 border-dashed rounded-xl cursor-pointer transition-all',
              uploading ? 'border-brand-500/30 bg-brand-500/5' : 'border-gray-700/50 hover:border-gray-600 hover:bg-gray-800/30'
            )}>
              {uploading ? (
                <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin mb-3" />
              ) : (
                <Upload className="w-8 h-8 text-gray-500 mb-3" />
              )}
              <p className="text-sm text-gray-400">{uploading ? 'Uploading...' : 'Click to select files'}</p>
              <p className="text-xs text-gray-600 mt-1">PDF, Markdown, Text files</p>
              <input type="file" multiple className="hidden" onChange={e => handleUpload(e.target.files)} />
            </label>
            <button onClick={() => setShowUpload(false)} className="btn-ghost w-full mt-4 text-sm">Cancel</button>
          </div>
        </div>
      )}

      {/* Create modal */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm animate-fade-in">
          <form onSubmit={handleCreate} className="glass-card p-8 w-full max-w-lg animate-slide-up">
            <h2 className="text-xl font-semibold text-gray-100 mb-6">Add Document</h2>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-1.5">Title</label>
                  <input value={docTitle} onChange={e => setDocTitle(e.target.value)} className="input-field text-sm" placeholder="Document title" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-1.5">Type</label>
                  <select value={docType} onChange={e => setDocType(e.target.value)} className="input-field text-sm">
                    <option value="text">Text</option>
                    <option value="webpage">Web Page</option>
                    <option value="markdown">Markdown</option>
                    <option value="pdf">PDF</option>
                  </select>
                </div>
              </div>
              {docType === 'webpage' && (
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-1.5">URL</label>
                  <input value={docUrl} onChange={e => setDocUrl(e.target.value)} className="input-field text-sm" placeholder="https://..." />
                </div>
              )}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1.5">Content</label>
                <textarea
                  value={docText}
                  onChange={e => setDocText(e.target.value)}
                  className="input-field text-sm min-h-[160px] resize-none font-mono"
                  placeholder="Paste or type text content..."
                />
              </div>
            </div>
            <div className="flex gap-3 mt-6">
              <button type="button" onClick={() => setShowCreate(false)} className="btn-secondary flex-1">Cancel</button>
              <button type="submit" disabled={creating} className="btn-primary flex-1">{creating ? 'Adding...' : 'Add'}</button>
            </div>
          </form>
        </div>
      )}

      {/* View modal */}
      {viewDoc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm animate-fade-in">
          <div className="glass-card p-8 w-full max-w-2xl max-h-[80vh] overflow-y-auto animate-slide-up">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold text-gray-100">{viewDoc.title || 'Untitled'}</h2>
              <button onClick={() => setViewDoc(null)} className="p-1 text-gray-500 hover:text-gray-300 transition-colors">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="flex gap-2 mb-4">
              <span className="badge-blue">{viewDoc.source_type}</span>
              {viewDoc.indexed ? <span className="badge-green">Indexed</span> : <span className="badge-amber">Pending</span>}
              <span className="badge-purple">{viewDoc.chunk_count} chunks</span>
            </div>
            {viewDoc.raw_text && (
              <pre className="text-sm text-gray-400 whitespace-pre-wrap font-mono bg-gray-800/30 rounded-xl p-4 max-h-96 overflow-y-auto">
                {viewDoc.raw_text}
              </pre>
            )}
          </div>
        </div>
      )}

      {/* Document list */}
      {loading ? (
        <div className="flex justify-center py-20">
          <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : documents.length === 0 ? (
        <div className="glass-card flex flex-col items-center py-20 text-center">
          <FileText className="w-12 h-12 text-gray-600 mb-4" />
          <h3 className="text-lg font-medium text-gray-300 mb-2">No documents yet</h3>
          <p className="text-gray-500 mb-6 max-w-sm">Add text documents, web pages, or PDFs to start building your searchable index.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {documents.map((doc, idx) => {
            const TypeIcon = getTypeIcon(doc.source_type)
            return (
              <div
                key={doc.id}
                className="glass-card-hover px-5 py-4 flex items-center gap-4 animate-slide-up cursor-pointer"
                style={{ animationDelay: `${idx * 30}ms` }}
                onClick={() => setViewDoc(doc)}
              >
                <div className="w-10 h-10 rounded-xl bg-gray-800/50 flex items-center justify-center flex-shrink-0">
                  <TypeIcon className="w-4 h-4 text-gray-400" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <h3 className="font-medium text-gray-200 truncate">{doc.title || 'Untitled'}</h3>
                    <span className="badge-blue text-[10px]">{doc.source_type}</span>
                  </div>
                  <div className="flex items-center gap-3 mt-1 text-xs text-gray-500">
                    <span>{new Date(doc.created_at).toLocaleDateString()}</span>
                    <span>{doc.chunk_count} chunks</span>
                    {doc.source_url && <span className="truncate max-w-xs">{doc.source_url}</span>}
                  </div>
                </div>
                <div className="flex items-center gap-3 flex-shrink-0">
                  {doc.indexed ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                  ) : (
                    <Clock className="w-4 h-4 text-amber-500 animate-pulse" />
                  )}
                  <button
                    onClick={e => { e.stopPropagation(); setViewDoc(doc) }}
                    className="p-1.5 text-gray-500 hover:text-gray-300 transition-colors"
                  >
                    <Eye className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={e => { e.stopPropagation(); handleDelete(doc.id) }}
                    className="p-1.5 text-gray-500 hover:text-red-400 transition-colors"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
