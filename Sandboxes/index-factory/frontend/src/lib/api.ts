const API_BASE = '/api'

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem('token')
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string> || {}),
  }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json'
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers })

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new ApiError(res.status, body.detail || res.statusText)
  }

  if (res.status === 204) return undefined as T
  return res.json()
}

export const api = {
  // Auth
  register: (data: { email: string; username: string; password: string }) =>
    request<{ id: string }>('/auth/register', { method: 'POST', body: JSON.stringify(data) }),

  login: (data: { email: string; password: string }) =>
    request<{ access_token: string }>('/auth/login', { method: 'POST', body: JSON.stringify(data) }),

  me: () => request<{ id: string; email: string; username: string; created_at: string }>('/auth/me'),

  // Objects
  listObjects: () => request<any[]>('/objects/'),
  createObject: (data: { name: string; description?: string }) =>
    request<any>('/objects/', { method: 'POST', body: JSON.stringify(data) }),
  getObject: (id: string) => request<any>(`/objects/${id}`),
  updateObject: (id: string, data: { name?: string; description?: string }) =>
    request<any>(`/objects/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  deleteObject: (id: string) =>
    request<void>(`/objects/${id}`, { method: 'DELETE' }),

  // Ontology
  listOntology: (objectId: string) => request<any[]>(`/objects/${objectId}/ontology`),
  createOntologyNode: (objectId: string, data: any) =>
    request<any>(`/objects/${objectId}/ontology`, { method: 'POST', body: JSON.stringify(data) }),
  updateOntologyNode: (objectId: string, nodeId: string, data: any) =>
    request<any>(`/objects/${objectId}/ontology/${nodeId}`, { method: 'PATCH', body: JSON.stringify(data) }),
  deleteOntologyNode: (objectId: string, nodeId: string) =>
    request<void>(`/objects/${objectId}/ontology/${nodeId}`, { method: 'DELETE' }),

  // Media
  listMedia: (objectId: string) => request<any[]>(`/media/${objectId}`),
  uploadMedia: (objectId: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<any>(`/media/${objectId}/upload`, { method: 'POST', body: form })
  },
  deleteMedia: (objectId: string, mediaId: string) =>
    request<void>(`/media/${objectId}/${mediaId}`, { method: 'DELETE' }),

  // Documents
  listDocuments: (sourceType?: string) =>
    request<any[]>(`/documents/${sourceType ? `?source_type=${sourceType}` : ''}`),
  createDocument: (data: any) =>
    request<any>('/documents/', { method: 'POST', body: JSON.stringify(data) }),
  uploadDocument: (file: File, title?: string) => {
    const form = new FormData()
    form.append('file', file)
    if (title) form.append('title', title)
    return request<any>('/documents/upload', { method: 'POST', body: form })
  },
  getDocument: (id: string) => request<any>(`/documents/${id}`),
  deleteDocument: (id: string) => request<void>(`/documents/${id}`, { method: 'DELETE' }),

  // Search
  search: (data: { query: string; mode?: string; limit?: number; object_id?: string }) =>
    request<any>('/search/', { method: 'POST', body: JSON.stringify(data) }),

  // Categories
  listAssignments: (ontologyNodeId?: string) =>
    request<any[]>(`/categories/${ontologyNodeId ? `?ontology_node_id=${ontologyNodeId}` : ''}`),
  createAssignment: (data: any) =>
    request<any>('/categories/', { method: 'POST', body: JSON.stringify(data) }),
  confirmAssignment: (id: string) =>
    request<any>(`/categories/${id}/confirm`, { method: 'PATCH' }),
  deleteAssignment: (id: string) =>
    request<void>(`/categories/${id}`, { method: 'DELETE' }),
}
