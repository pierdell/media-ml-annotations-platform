import { Link, useLocation } from 'react-router-dom'
import { Search, Boxes, FileText, LayoutDashboard, LogOut, Zap } from 'lucide-react'
import { clsx } from 'clsx'
import type { User } from '@/types'

interface Props {
  user: User
  onLogout: () => void
  children: React.ReactNode
}

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/search', label: 'Search', icon: Search },
  { to: '/documents', label: 'Documents', icon: FileText },
]

export default function Layout({ user, onLogout, children }: Props) {
  const location = useLocation()

  return (
    <div className="min-h-screen flex">
      {/* Sidebar */}
      <aside className="w-64 fixed inset-y-0 left-0 bg-gray-950 border-r border-gray-800/50 flex flex-col z-30">
        {/* Logo */}
        <div className="h-16 flex items-center gap-3 px-6 border-b border-gray-800/50">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand-500 to-cyan-500 flex items-center justify-center">
            <Zap className="w-4 h-4 text-white" />
          </div>
          <span className="font-semibold text-lg text-gradient">Index Factory</span>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 space-y-1">
          {NAV_ITEMS.map(({ to, label, icon: Icon }) => {
            const active = location.pathname === to || (to !== '/' && location.pathname.startsWith(to))
            return (
              <Link
                key={to}
                to={to}
                className={clsx(
                  'flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200',
                  active
                    ? 'bg-brand-600/15 text-brand-400 shadow-sm shadow-brand-500/5'
                    : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/40'
                )}
              >
                <Icon className="w-4.5 h-4.5" />
                {label}
              </Link>
            )
          })}
        </nav>

        {/* User */}
        <div className="p-4 border-t border-gray-800/50">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-full bg-gradient-to-br from-brand-600 to-purple-600 flex items-center justify-center text-sm font-semibold text-white">
              {user.username.charAt(0).toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-gray-200 truncate">{user.username}</p>
              <p className="text-xs text-gray-500 truncate">{user.email}</p>
            </div>
            <button onClick={onLogout} className="p-2 text-gray-500 hover:text-gray-300 transition-colors" title="Log out">
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 ml-64">
        <div className="max-w-7xl mx-auto px-8 py-8">
          {children}
        </div>
      </main>
    </div>
  )
}
