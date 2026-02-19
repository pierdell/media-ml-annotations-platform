import { useState, useEffect, useCallback, useRef } from 'react'

interface IndexingEvent {
  type: 'indexing_started' | 'indexing_complete' | 'auto_categorized'
  item_id: string
  item_type?: string
  node_name?: string
  confidence?: number
  chunks?: number
}

export function useIndexingStatus(userId: string | undefined) {
  const [events, setEvents] = useState<IndexingEvent[]>([])
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectRef = useRef<number>(0)

  const connect = useCallback(() => {
    if (!userId) return

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws/indexing/${userId}`)
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
      reconnectRef.current = 0
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as IndexingEvent
        setEvents(prev => [data, ...prev].slice(0, 50)) // keep last 50
      } catch {
        // ignore non-json messages (pong)
      }
    }

    ws.onclose = () => {
      setConnected(false)
      // Reconnect with backoff
      const delay = Math.min(1000 * 2 ** reconnectRef.current, 30000)
      reconnectRef.current++
      setTimeout(connect, delay)
    }

    ws.onerror = () => {
      ws.close()
    }
  }, [userId])

  useEffect(() => {
    connect()
    return () => {
      wsRef.current?.close()
    }
  }, [connect])

  const clearEvents = useCallback(() => setEvents([]), [])

  return { events, connected, clearEvents }
}
