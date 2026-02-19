import { useState, useEffect, useCallback, createContext, useContext } from 'react'
import { CheckCircle2, AlertCircle, X, Info } from 'lucide-react'
import { clsx } from 'clsx'

interface ToastMessage {
  id: number
  type: 'success' | 'error' | 'info'
  message: string
}

interface ToastContextType {
  toast: (type: ToastMessage['type'], message: string) => void
}

const ToastContext = createContext<ToastContextType>({ toast: () => {} })

export function useToast() {
  return useContext(ToastContext)
}

let nextId = 0

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastMessage[]>([])

  const toast = useCallback((type: ToastMessage['type'], message: string) => {
    const id = nextId++
    setToasts(prev => [...prev, { id, type, message }])
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id))
    }, 4000)
  }, [])

  const dismiss = (id: number) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div className="fixed bottom-6 right-6 z-[100] flex flex-col gap-2">
        {toasts.map(t => {
          const Icon = t.type === 'success' ? CheckCircle2 : t.type === 'error' ? AlertCircle : Info
          return (
            <div
              key={t.id}
              className={clsx(
                'flex items-center gap-3 px-5 py-3 rounded-xl shadow-2xl backdrop-blur-xl border animate-slide-up min-w-[280px]',
                t.type === 'success' && 'bg-emerald-950/80 border-emerald-800/50 text-emerald-300',
                t.type === 'error' && 'bg-red-950/80 border-red-800/50 text-red-300',
                t.type === 'info' && 'bg-brand-950/80 border-brand-800/50 text-brand-300',
              )}
            >
              <Icon className="w-4 h-4 flex-shrink-0" />
              <span className="text-sm flex-1">{t.message}</span>
              <button onClick={() => dismiss(t.id)} className="p-0.5 hover:opacity-70 transition-opacity">
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}
