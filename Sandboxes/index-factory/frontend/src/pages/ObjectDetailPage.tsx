import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  ArrowLeft, Plus, Upload, ChevronRight, ChevronDown,
  Image, Trash2, FolderTree, Tag, Circle
} from 'lucide-react'
import { clsx } from 'clsx'
import { api } from '@/lib/api'
import type { IndexObject, OntologyNode, ReferenceMedia } from '@/types'

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#f97316']

export default function ObjectDetailPage() {
  const { objectId } = useParams<{ objectId: string }>()
  const [object, setObject] = useState<IndexObject | null>(null)
  const [ontology, setOntology] = useState<OntologyNode[]>([])
  const [media, setMedia] = useState<ReferenceMedia[]>([])
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'ontology' | 'media'>('ontology')

  // Ontology form
  const [showAddNode, setShowAddNode] = useState(false)
  const [nodeName, setNodeName] = useState('')
  const [nodeDesc, setNodeDesc] = useState('')
  const [nodeColor, setNodeColor] = useState(COLORS[0])
  const [nodeParent, setNodeParent] = useState<string | null>(null)

  // Media upload
  const [uploading, setUploading] = useState(false)

  const load = async () => {
    if (!objectId) return
    try {
      const [obj, ont, med] = await Promise.all([
        api.getObject(objectId),
        api.listOntology(objectId),
        api.listMedia(objectId),
      ])
      setObject(obj)
      setOntology(ont)
      setMedia(med)
    } catch (err) {
      console.error(err)
    }
    setLoading(false)
  }

  useEffect(() => { load() }, [objectId])

  const handleAddNode = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!objectId || !nodeName.trim()) return
    try {
      await api.createOntologyNode(objectId, {
        name: nodeName,
        description: nodeDesc || undefined,
        color: nodeColor,
        parent_id: nodeParent,
      })
      setNodeName('')
      setNodeDesc('')
      setShowAddNode(false)
      setNodeParent(null)
      await load()
    } catch (err) {
      console.error(err)
    }
  }

  const handleDeleteNode = async (nodeId: string) => {
    if (!objectId) return
    try {
      await api.deleteOntologyNode(objectId, nodeId)
      await load()
    } catch (err) {
      console.error(err)
    }
  }

  const handleUpload = async (files: FileList | null) => {
    if (!objectId || !files) return
    setUploading(true)
    for (const file of Array.from(files)) {
      try {
        await api.uploadMedia(objectId, file)
      } catch (err) {
        console.error(err)
      }
    }
    await load()
    setUploading(false)
  }

  const handleDeleteMedia = async (mediaId: string) => {
    if (!objectId) return
    try {
      await api.deleteMedia(objectId, mediaId)
      await load()
    } catch (err) {
      console.error(err)
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (!object) {
    return <div className="text-center py-20 text-gray-500">Object not found</div>
  }

  return (
    <div className="animate-fade-in">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-gray-500 mb-6">
        <Link to="/" className="hover:text-gray-300 transition-colors">Dashboard</Link>
        <ChevronRight className="w-3 h-3" />
        <span className="text-gray-300">{object.name}</span>
      </div>

      {/* Header */}
      <div className="flex items-center gap-4 mb-8">
        <Link to="/" className="p-2 rounded-lg hover:bg-gray-800/50 text-gray-400 hover:text-gray-200 transition-all">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-gray-100">{object.name}</h1>
          {object.description && <p className="text-gray-500 mt-0.5">{object.description}</p>}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 bg-gray-900/40 p-1 rounded-xl w-fit">
        {(['ontology', 'media'] as const).map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={clsx(
              'px-5 py-2 rounded-lg text-sm font-medium transition-all duration-200 capitalize',
              activeTab === tab
                ? 'bg-gray-800 text-gray-100 shadow-sm'
                : 'text-gray-500 hover:text-gray-300'
            )}
          >
            {tab === 'ontology' ? (
              <span className="flex items-center gap-2"><FolderTree className="w-3.5 h-3.5" /> Ontology</span>
            ) : (
              <span className="flex items-center gap-2"><Image className="w-3.5 h-3.5" /> Media ({media.length})</span>
            )}
          </button>
        ))}
      </div>

      {/* Ontology tab */}
      {activeTab === 'ontology' && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <p className="section-title">Property Hierarchy</p>
            <button onClick={() => { setShowAddNode(true); setNodeParent(null) }} className="btn-primary text-sm flex items-center gap-1.5 py-2 px-4">
              <Plus className="w-3.5 h-3.5" />
              Add Node
            </button>
          </div>

          {showAddNode && (
            <form onSubmit={handleAddNode} className="glass-card p-5 mb-4 animate-slide-up">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-1.5">Name</label>
                  <input autoFocus value={nodeName} onChange={e => setNodeName(e.target.value)} className="input-field text-sm py-2.5" placeholder="e.g. Species" required />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-1.5">Description</label>
                  <input value={nodeDesc} onChange={e => setNodeDesc(e.target.value)} className="input-field text-sm py-2.5" placeholder="Optional" />
                </div>
              </div>
              <div className="mt-4">
                <label className="block text-sm font-medium text-gray-300 mb-2">Color</label>
                <div className="flex gap-2">
                  {COLORS.map(c => (
                    <button
                      key={c}
                      type="button"
                      onClick={() => setNodeColor(c)}
                      className={clsx(
                        'w-7 h-7 rounded-full transition-all',
                        nodeColor === c ? 'ring-2 ring-offset-2 ring-offset-gray-900 ring-white/50 scale-110' : 'hover:scale-105'
                      )}
                      style={{ backgroundColor: c }}
                    />
                  ))}
                </div>
              </div>
              <div className="flex gap-2 mt-5">
                <button type="button" onClick={() => setShowAddNode(false)} className="btn-ghost text-sm">Cancel</button>
                <button type="submit" className="btn-primary text-sm py-2 px-5">Add</button>
              </div>
            </form>
          )}

          {ontology.length === 0 ? (
            <div className="glass-card flex flex-col items-center py-16 text-center">
              <FolderTree className="w-10 h-10 text-gray-600 mb-3" />
              <p className="text-gray-400 mb-1">No ontology nodes yet</p>
              <p className="text-sm text-gray-600">Define the property hierarchy for this object</p>
            </div>
          ) : (
            <div className="space-y-2">
              {ontology.map(node => (
                <OntologyTreeNode
                  key={node.id}
                  node={node}
                  depth={0}
                  onDelete={handleDeleteNode}
                  onAddChild={(parentId) => {
                    setNodeParent(parentId)
                    setShowAddNode(true)
                  }}
                />
              ))}
            </div>
          )}
        </div>
      )}

      {/* Media tab */}
      {activeTab === 'media' && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <p className="section-title">Reference Media</p>
            <label className={clsx('btn-primary text-sm flex items-center gap-1.5 py-2 px-4 cursor-pointer', uploading && 'opacity-50 pointer-events-none')}>
              <Upload className="w-3.5 h-3.5" />
              {uploading ? 'Uploading...' : 'Upload'}
              <input type="file" multiple accept="image/*,video/*" className="hidden" onChange={e => handleUpload(e.target.files)} />
            </label>
          </div>

          {media.length === 0 ? (
            <div className="glass-card flex flex-col items-center py-16 text-center">
              <Image className="w-10 h-10 text-gray-600 mb-3" />
              <p className="text-gray-400 mb-1">No reference media yet</p>
              <p className="text-sm text-gray-600">Upload images or videos to build the reference index</p>
            </div>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
              {media.map(m => (
                <div key={m.id} className="glass-card-hover group relative aspect-square overflow-hidden">
                  <div className="absolute inset-0 flex items-center justify-center bg-gray-800/50">
                    <Image className="w-8 h-8 text-gray-600" />
                  </div>
                  <div className="absolute bottom-0 inset-x-0 bg-gradient-to-t from-black/80 to-transparent p-3">
                    <p className="text-xs text-gray-300 truncate">{m.file_name}</p>
                    <div className="flex items-center gap-2 mt-1">
                      {m.indexed ? (
                        <span className="badge-green text-[10px]">Indexed</span>
                      ) : (
                        <span className="badge-amber text-[10px]">Pending</span>
                      )}
                    </div>
                  </div>
                  <button
                    onClick={() => handleDeleteMedia(m.id)}
                    className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 p-1.5 bg-black/60 rounded-lg text-gray-400 hover:text-red-400 transition-all"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// Recursive tree node component
function OntologyTreeNode({
  node,
  depth,
  onDelete,
  onAddChild,
}: {
  node: OntologyNode
  depth: number
  onDelete: (id: string) => void
  onAddChild: (parentId: string) => void
}) {
  const [expanded, setExpanded] = useState(true)
  const hasChildren = node.children && node.children.length > 0

  return (
    <div style={{ marginLeft: depth * 20 }}>
      <div className="glass-card-hover px-4 py-3 flex items-center gap-3 group">
        {hasChildren ? (
          <button onClick={() => setExpanded(!expanded)} className="p-0.5 text-gray-500 hover:text-gray-300">
            {expanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
          </button>
        ) : (
          <Circle className="w-2 h-2 ml-1 mr-0.5" style={{ color: node.color || '#6b7280' }} fill={node.color || '#6b7280'} />
        )}
        <div
          className="w-3 h-3 rounded-full flex-shrink-0"
          style={{ backgroundColor: node.color || '#6b7280' }}
        />
        <span className="text-sm font-medium text-gray-200 flex-1">{node.name}</span>
        {node.description && (
          <span className="text-xs text-gray-500 hidden sm:block">{node.description}</span>
        )}
        <div className="opacity-0 group-hover:opacity-100 flex items-center gap-1 transition-opacity">
          <button onClick={() => onAddChild(node.id)} className="p-1 text-gray-500 hover:text-brand-400 transition-colors" title="Add child">
            <Plus className="w-3 h-3" />
          </button>
          <button onClick={() => onDelete(node.id)} className="p-1 text-gray-500 hover:text-red-400 transition-colors" title="Delete">
            <Trash2 className="w-3 h-3" />
          </button>
        </div>
      </div>
      {hasChildren && expanded && (
        <div className="mt-1 space-y-1">
          {node.children.map(child => (
            <OntologyTreeNode key={child.id} node={child} depth={depth + 1} onDelete={onDelete} onAddChild={onAddChild} />
          ))}
        </div>
      )}
    </div>
  )
}
