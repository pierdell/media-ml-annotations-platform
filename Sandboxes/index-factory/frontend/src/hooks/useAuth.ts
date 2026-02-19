import { useState, useEffect, useCallback } from 'react'
import { api } from '@/lib/api'
import type { User } from '@/types'

export function useAuth() {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  const checkAuth = useCallback(async () => {
    const token = localStorage.getItem('token')
    if (!token) {
      setLoading(false)
      return
    }
    try {
      const me = await api.me()
      setUser(me as User)
    } catch {
      localStorage.removeItem('token')
    }
    setLoading(false)
  }, [])

  useEffect(() => {
    checkAuth()
  }, [checkAuth])

  const login = async (email: string, password: string) => {
    const { access_token } = await api.login({ email, password })
    localStorage.setItem('token', access_token)
    await checkAuth()
  }

  const register = async (email: string, username: string, password: string) => {
    await api.register({ email, username, password })
    await login(email, password)
  }

  const logout = () => {
    localStorage.removeItem('token')
    setUser(null)
  }

  return { user, loading, login, register, logout }
}
