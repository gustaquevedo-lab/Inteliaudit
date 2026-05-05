import { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { api } from '../api/client'
import type { AuthUser } from '../api/types'

interface AuthCtx {
  user: AuthUser | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  isAdmin: boolean
  isSuperAdmin: boolean
  planInfo: {
    nombre: string
    planId: string
    enTrial: boolean
    diasRestantes: number
    tieneIA: boolean
    clientesActuales: number
    clientesMaximos: number | null
  } | null
}

const Ctx = createContext<AuthCtx>({
  user: null,
  loading: true,
  login: async () => {},
  logout: () => {},
  isAdmin: false,
  isSuperAdmin: false,
  planInfo: null,
})

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [planInfo, setPlanInfo] = useState<AuthCtx['planInfo']>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('ia_token')
    if (!token) { setLoading(false); return }
    api.get<AuthUser>('/auth/me')
      .then((me) => {
        setUser(me)
        setPlanInfo({
          nombre: me.firma_plan || 'Starter',
          planId: me.firma_plan_id || 'starter',
          enTrial: me.en_trial || false,
          diasRestantes: me.dias_trial_restantes || 0,
          tieneIA: me.plan_tiene_ia || false,
          clientesActuales: me.clientes_actuales || 0,
          clientesMaximos: me.clientes_maximos ?? null,
        })
      })
      .catch(() => localStorage.removeItem('ia_token'))
      .finally(() => setLoading(false))
  }, [])

  const login = async (email: string, password: string) => {
    const res = await api.login(email, password)
    localStorage.setItem('ia_token', res.access_token)
    const me = await api.get<AuthUser>('/auth/me')
    setUser(me)
    setPlanInfo({
      nombre: me.firma_plan || 'Starter',
      planId: me.firma_plan_id || 'starter',
      enTrial: me.en_trial || false,
      diasRestantes: me.dias_trial_restantes || 0,
      tieneIA: me.plan_tiene_ia || false,
      clientesActuales: me.clientes_actuales || 0,
      clientesMaximos: me.clientes_maximos ?? null,
    })
  }

  const logout = () => {
    localStorage.removeItem('ia_token')
    setUser(null)
    setPlanInfo(null)
    window.location.href = '/app/login'
  }

  const isAdmin = user?.rol === 'admin' || user?.rol === 'super_admin'
  const isSuperAdmin = user?.rol === 'super_admin'

  return (
    <Ctx.Provider value={{ user, loading, login, logout, isAdmin, isSuperAdmin, planInfo }}>
      {children}
    </Ctx.Provider>
  )
}

export const useAuth = () => useContext(Ctx)
