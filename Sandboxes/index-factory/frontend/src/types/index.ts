export interface User {
  id: string
  email: string
  username: string
  created_at: string
}

export interface IndexObject {
  id: string
  user_id: string
  name: string
  description: string | null
  created_at: string
  updated_at: string
}

export interface OntologyNode {
  id: string
  object_id: string
  parent_id: string | null
  name: string
  description: string | null
  color: string | null
  sort_order: number
  created_at: string
  children: OntologyNode[]
}

export interface ReferenceMedia {
  id: string
  object_id: string
  file_name: string
  mime_type: string | null
  file_size: number | null
  indexed: boolean
  created_at: string
}

export interface Document {
  id: string
  user_id: string
  source_type: string
  source_url: string | null
  title: string | null
  raw_text: string | null
  indexed: boolean
  created_at: string
  chunk_count: number
}

export interface SearchResult {
  id: string
  score: number
  content_type: string
  title: string | null
  snippet: string | null
  source_id: string | null
  metadata: Record<string, unknown>
}

export interface SearchResponse {
  results: SearchResult[]
  total: number
  query: string
  mode: string
}

export interface CategoryAssignment {
  id: string
  reference_media_id: string | null
  document_id: string | null
  ontology_node_id: string
  confidence: number | null
  is_confirmed: boolean
  assigned_by: string
}
