import { useState, useEffect } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard, Users, FolderSearch, FileText, Settings,
  Shield, Sun, Moon, Monitor, LogOut, Menu, X,
  Building2, ChevronRight, Search, Bell,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useTheme } from '../context/ThemeContext'
import { initials } from '../utils/formatters'
import Logo from './Logo'

const NAV_GROUPS = [
  {
    title: 'General',
    items: [
      { path: '/dashboard', icon: <LayoutDashboard size={17} />, label: 'Dashboard', roles: ['super_admin', 'admin', 'auditor_senior', 'auditor'] },
      { path: '/clientes', icon: <Building2 size={17} />, label: 'Clientes', roles: ['super_admin', 'admin', 'auditor_senior', 'auditor'] },
    ],
  },
  {
    title: 'Auditorías',
    items: [
      { path: '/auditorias/nueva', icon: <FolderSearch size={17} />, label: 'Nueva auditoría', roles: ['super_admin', 'admin', 'auditor_senior'] },
    ],
  },
  {
    title: 'Informes',
    items: [
      { path: '/informes', icon: <FileText size={17} />, label: 'Informes', roles: ['super_admin', 'admin', 'auditor_senior', 'auditor'] },
    ],
  },
  {
    title: 'Administración',
    items: [
      { path: '/admin/usuarios', icon: <Users size={17} />, label: 'Usuarios', roles: ['super_admin', 'admin'] },
      { path: '/admin/configuracion', icon: <Settings size={17} />, label: 'Configuración', roles: ['super_admin', 'admin'] },
      { path: '/admin/trail', icon: <Shield size={17} />, label: 'Audit Trail', roles: ['super_admin', 'admin'] },
    ],
  },
]

const THEME_OPTS = [
  { value: 'light' as const, icon: <Sun size={14} />, label: 'Claro' },
  { value: 'dark' as const, icon: <Moon size={14} />, label: 'Oscuro' },
  { value: 'auto' as const, icon: <Monitor size={14} />, label: 'Auto' },
]

const ROL_LABEL: Record<string, string> = {
  super_admin: 'Super Admin',
  admin: 'Administrador',
  auditor_senior: 'Auditor Senior',
  auditor: 'Auditor',
}

export default function Layout() {
  const { user, logout } = useAuth()
  const { theme, setTheme } = useTheme()
  const location = useLocation()
  const navigate = useNavigate()
  const [sidebarOpen, setSidebarOpen] = useState(false)

  // Cerrar sidebar en cambio de ruta (mobile)
  useEffect(() => { setSidebarOpen(false) }, [location.pathname])
  useEffect(() => {
    const handler = () => { if (window.innerWidth >= 1024) setSidebarOpen(false) }
    window.addEventListener('resize', handler)
    return () => window.removeEventListener('resize', handler)
  }, [])

  const visibleGroups = NAV_GROUPS.map(g => ({
    ...g,
    items: g.items.filter(i => i.roles.includes(user?.rol ?? 'auditor')),
  })).filter(g => g.items.length)

  // Título de página actual
  const allItems = NAV_GROUPS.flatMap(g => g.items)
  const currentLabel = allItems.find(i => location.pathname.startsWith(i.path))?.label ?? 'Inteliaudit'

  return (
    <div className="flex h-screen overflow-hidden bg-body-light dark:bg-body-dark">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/60 z-[140] lg:hidden backdrop-blur-sm"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* ─── Sidebar ───────────────────────────────────────────── */}
      <aside className={`
        fixed lg:static inset-y-0 left-0 z-[150]
        w-64 sidebar-gradient text-white flex flex-col shadow-2xl
        transform transition-transform duration-300 ease-in-out
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
      `}>
        {/* Logo */}
        <div className="py-5 px-4 border-b border-white/10 flex items-center justify-between">
          <Logo size="md" dark />
          <button onClick={() => setSidebarOpen(false)} className="lg:hidden p-1 text-white/50 hover:text-white rounded-md">
            <X size={20} />
          </button>
        </div>

        {/* Nav */}
        <nav className="flex-1 p-3 overflow-y-auto space-y-5 py-4">
          {visibleGroups.map((group, gi) => (
            <div key={gi}>
              <h3 className="px-4 text-[9px] font-black text-blue-200/40 uppercase tracking-[0.25em] mb-3">
                {group.title}
              </h3>
              <div className="space-y-1">
                {group.items.map(item => (
                  <NavLink
                    key={item.path}
                    to={item.path}
                    className={({ isActive }) =>
                      `flex items-center gap-3 px-4 py-2.5 rounded-xl transition-all duration-200 text-[13px] font-bold ${
                        isActive
                          ? 'bg-white text-primary shadow-lg shadow-black/20 scale-[1.01]'
                          : 'text-blue-100/60 hover:bg-white/8 hover:text-white'
                      }`
                    }
                  >
                    <span className="shrink-0">{item.icon}</span>
                    <span className="truncate">{item.label}</span>
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </nav>

        {/* User section */}
        <div className="p-4 border-t border-white/8 space-y-3">
          <div className="flex items-center gap-3 px-2">
            <div className="w-9 h-9 rounded-xl bg-white/15 border border-white/10 flex items-center justify-center text-white font-black text-xs shrink-0">
              {initials(user?.nombre ?? '?')}
            </div>
            <div className="flex-1 min-w-0">
              <p className="font-black text-white text-sm leading-tight truncate">{user?.nombre}</p>
              <p className="text-[10px] font-bold text-blue-200/50 truncate uppercase tracking-wider mt-0.5">
                {ROL_LABEL[user?.rol ?? ''] ?? user?.rol}
              </p>
            </div>
          </div>
          <button
            onClick={logout}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-xl text-[11px] font-black uppercase tracking-wider text-blue-200/50 hover:text-white hover:bg-white/10 transition-all border border-white/5"
          >
            <LogOut size={13} />
            Cerrar sesión
          </button>
        </div>
      </aside>

      {/* ─── Main ──────────────────────────────────────────────── */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <header className="bg-white/80 dark:bg-slate-900/80 backdrop-blur-xl border-b border-gray-100 dark:border-gray-800 px-4 sm:px-6 py-3 shrink-0 z-30">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-3 min-w-0">
              <button
                onClick={() => setSidebarOpen(true)}
                className="lg:hidden p-2 bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 rounded-xl"
              >
                <Menu size={18} />
              </button>
              {/* Breadcrumb */}
              <div className="flex items-center gap-1.5 text-xs text-gray-400 dark:text-gray-500 min-w-0">
                <span className="font-bold text-gray-500 dark:text-gray-400">{user?.firma_nombre}</span>
                <ChevronRight size={12} />
                <h1 className="font-black text-gray-900 dark:text-white uppercase tracking-tight text-sm truncate">{currentLabel}</h1>
              </div>
            </div>

            <div className="flex items-center gap-2">
              {/* Theme switcher */}
              <div className="flex items-center bg-gray-100 dark:bg-gray-800 rounded-lg p-0.5 gap-0.5">
                {THEME_OPTS.map(opt => (
                  <button
                    key={opt.value}
                    onClick={() => setTheme(opt.value)}
                    title={opt.label}
                    className={`p-1.5 rounded-md transition-all duration-200 flex items-center gap-1 text-xs font-medium ${
                      theme === opt.value
                        ? 'bg-white dark:bg-gray-700 text-primary shadow-sm'
                        : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
                    }`}
                  >
                    {opt.icon}
                    <span className="hidden md:inline text-[11px]">{opt.label}</span>
                  </button>
                ))}
              </div>

              {/* Nueva auditoría shortcut */}
              <button
                onClick={() => navigate('/auditorias/nueva')}
                className="btn-primary py-2 px-4 text-xs hidden sm:flex"
              >
                + Nueva auditoría
              </button>
            </div>
          </div>
        </header>

        {/* Content */}
        <div className="flex-1 overflow-y-auto">
          <div className="p-4 sm:p-6 lg:p-8 max-w-[1600px] mx-auto">
            <Outlet />
          </div>
        </div>
      </main>
    </div>
  )
}
