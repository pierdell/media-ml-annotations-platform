import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

export function useKeyboardShortcuts() {
  const navigate = useNavigate()

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Only trigger with Cmd/Ctrl + key
      if (!(e.metaKey || e.ctrlKey)) return
      // Don't trigger in input/textarea
      const tag = (e.target as HTMLElement).tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return

      switch (e.key) {
        case 'k':
          e.preventDefault()
          navigate('/search')
          // Focus the search input after navigation
          requestAnimationFrame(() => {
            const el = document.getElementById("search-input") as HTMLInputElement
            if (el) el.focus()
          })
          break
        case 'd':
          e.preventDefault()
          navigate('/')
          break
        case 'n':
          e.preventDefault()
          navigate('/documents')
          break
      }
    }

    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [navigate])
}
