import { useState, useEffect } from 'react'
import {
  Search, Shield, ShieldCheck, ShieldAlert, UserX, UserCheck,
  Loader2, Eye, EyeOff, Building2, Key, Edit, RefreshCw, Copy, Check,
  AlertTriangle, Bug, Activity, Users, Database, Cpu, Cloud, CheckCircle2,
  ExternalLink, Plus, Sparkles, FileText, Terminal, X, ArrowUpRight
} from 'lucide-react'
import { api } from '../../api/client'
import { useToast } from '../../components/Toaster'
import { useAuth } from '../../context/AuthContext'
import Modal from '../../components/Modal'
import { fecha, initials } from '../../utils/formatters'

interface SuperAdminFirma {
  id: string
  nombre: string
  ruc: string | null
  email: string | null
  plan: string
  features_override_json: string | null
  activa: boolean
  trial_hasta: string | null
  creado_en: string
  num_clientes: number
}

interface SuperAdminUsuario {
  id: string
  firma_id: string
  firma_nombre: string | null
  email: string
  nombre: string
  rol: string
  activo: boolean
  debe_cambiar_password: boolean
  creado_en: string
  ultimo_acceso: string | null
}

interface ErrorPlataformaItem {
  id: string
  fingerprint: string
  tipo_error: string
  mensaje: string
  path: string
  metodo: string
  status_code: number
  stacktrace: string
  contexto_json: string | null
  firma_id: string | null
  usuario_email: string | null
  ocurrencias: number
  primera_vez: string
  ultima_vez: string
  resuelto: boolean
  resuelto_en: string | null
  notas_resolucion: string | null
}

interface VitalsData {
  status: 'ok' | 'degraded' | 'error'
  timestamp: string
  database: {
    status: string
    latency_ms: number
    engine: string
  }
  ollama_ai: {
    status: string
    latency_ms?: number
    modelos?: string[]
    error?: string
  }
  sifen_cache: {
    status: string
    total_comprobantes_cacheados?: number
    error?: string
  }
  storage: {
    status: string
    bucket: string
  }
}

interface StatsData {
  total_firmas: number
  firmas_activas: number
  total_usuarios: number
  total_clientes: number
  distribucion_planes: Record<string, number>
  total_errores_pendientes: number
}

const rolBadge = (rol: string) => {
  const base = 'px-2 py-0.5 rounded-full text-[10px] font-bold flex items-center gap-1'
  if (rol === 'super_admin' || rol === 'admin') return `${base} bg-primary/10 text-primary dark:text-primary-light`
  if (rol === 'auditor_senior') return `${base} bg-accent/10 text-accent dark:text-teal-400`
  return `${base} bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400`
}

const planBadge = (plan: string) => {
  const base = 'px-2 py-0.5 rounded-full text-[10px] font-bold tracking-wider uppercase'
  if (plan === 'enterprise') return `${base} bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 border border-purple-200 dark:border-purple-800`
  if (plan === 'pro' || plan === 'professional') return `${base} bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800`
  if (plan === 'starter') return `${base} bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800`
  return `${base} bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-800`
}

export default function SuperAdminDashboard() {
  const { user: currentUser } = useAuth()
  const { success, error } = useToast()

  const [tab, setTab] = useState<'firmas' | 'usuarios' | 'errores' | 'vitals'>('firmas')
  const [stats, setStats] = useState<StatsData | null>(null)
  const [firmas, setFirmas] = useState<SuperAdminFirma[]>([])
  const [usuarios, setUsuarios] = useState<SuperAdminUsuario[]>([])
  const [errores, setErrores] = useState<ErrorPlataformaItem[]>([])
  const [vitals, setVitals] = useState<VitalsData | null>(null)

  const [loading, setLoading] = useState(true)
  const [refreshingVitals, setRefreshingVitals] = useState(false)
  const [busqueda, setBusqueda] = useState('')
  const [filtroErrorResuelto, setFiltroErrorResuelto] = useState<boolean | null>(false)

  // Modales
  const [showNuevaFirmaModal, setShowNuevaFirmaModal] = useState(false)
  const [showNuevoUsuarioModal, setShowNuevoUsuarioModal] = useState(false)
  const [editingFirma, setEditingFirma] = useState<SuperAdminFirma | null>(null)
  const [resettingUser, setResettingUser] = useState<SuperAdminUsuario | null>(null)
  const [selectedError, setSelectedError] = useState<ErrorPlataformaItem | null>(null)
  const [resolviendoError, setResolviendoError] = useState(false)
  const [notasResolucion, setNotasResolucion] = useState('')

  // Modal Credenciales Temporales Reveladas
  const [credsReveladas, setCredsReveladas] = useState<{
    email: string
    password_temporal: string
    nombre_entidad: string
    tipo: 'firma' | 'usuario'
  } | null>(null)
  const [showPassRevelada, setShowPassRevelada] = useState(false)
  const [copiadoPass, setCopiadoPass] = useState(false)

  // Formulario Nueva Firma
  const [nuevaFirma, setNuevaFirma] = useState({
    nombre: '',
    ruc: '',
    email: '',
    plan: 'starter',
    admin_nombre: '',
    admin_email: '',
    admin_password: '',
    tiene_ia: false,
    max_clientes: '5',
    max_usuarios: '3',
  })

  // Formulario Nuevo Usuario
  const [nuevoUsuario, setNuevoUsuario] = useState({
    firma_id: '',
    nombre: '',
    email: '',
    rol: 'auditor',
    password: '',
  })

  // Formulario Edición Firma
  const [firmaPlan, setFirmaPlan] = useState('starter')
  const [firmaActiva, setFirmaActiva] = useState(true)
  const [firmaTrialHasta, setFirmaTrialHasta] = useState('')
  const [firmaTieneIa, setFirmaTieneIa] = useState(false)
  const [firmaMaxClientes, setFirmaMaxClientes] = useState('')
  const [firmaMaxUsuarios, setFirmaMaxUsuarios] = useState('')

  // Formulario Reset Password
  const [newPassword, setNewPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [saving, setSaving] = useState(false)

  // Carga de datos
  const cargarStats = () => {
    api.get<StatsData>('/superadmin/stats').then(setStats).catch(() => {})
  }

  const cargarFirmas = () => {
    setLoading(true)
    api.get<SuperAdminFirma[]>('/superadmin/firmas')
      .then(setFirmas)
      .catch(() => error('Error al cargar firmas'))
      .finally(() => setLoading(false))
  }

  const cargarUsuarios = () => {
    setLoading(true)
    api.get<SuperAdminUsuario[]>('/superadmin/usuarios')
      .then(setUsuarios)
      .catch(() => error('Error al cargar usuarios'))
      .finally(() => setLoading(false))
  }

  const cargarErrores = () => {
    setLoading(true)
    const query = filtroErrorResuelto !== null ? `?resuelto=${filtroErrorResuelto}` : ''
    api.get<ErrorPlataformaItem[]>(`/superadmin/errores${query}`)
      .then(setErrores)
      .catch(() => error('Error al cargar registro de errores Sentry-Lite'))
      .finally(() => setLoading(false))
  }

  const cargarVitals = () => {
    setRefreshingVitals(true)
    api.get<VitalsData>('/superadmin/vitals')
      .then((data) => {
        setVitals(data)
      })
      .catch(() => error('Error al consultar vitals'))
      .finally(() => setRefreshingVitals(false))
  }

  useEffect(() => {
    cargarStats()
    if (tab === 'firmas') cargarFirmas()
    if (tab === 'usuarios') cargarUsuarios()
    if (tab === 'errores') cargarErrores()
    if (tab === 'vitals') cargarVitals()
  }, [tab, filtroErrorResuelto])

  // Crear Firma Atómica
  const handleCrearFirma = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)

    const overrides: Record<string, any> = {
      tiene_ia: nuevaFirma.tiene_ia,
    }
    if (nuevaFirma.max_clientes) overrides.max_clientes = parseInt(nuevaFirma.max_clientes, 10)
    if (nuevaFirma.max_usuarios) overrides.max_usuarios = parseInt(nuevaFirma.max_usuarios, 10)

    try {
      const res = await api.post<{
        firma: SuperAdminFirma
        admin_usuario: SuperAdminUsuario
        password_temporal: string
      }>('/superadmin/firmas', {
        nombre: nuevaFirma.nombre,
        ruc: nuevaFirma.ruc || undefined,
        email: nuevaFirma.email || undefined,
        plan: nuevaFirma.plan,
        admin_nombre: nuevaFirma.admin_nombre,
        admin_email: nuevaFirma.admin_email,
        admin_password: nuevaFirma.admin_password || undefined,
        features_override_json: JSON.stringify(overrides),
      })

      success(`Firma "${res.firma.nombre}" creada con éxito`)
      setShowNuevaFirmaModal(false)
      cargarFirmas()
      cargarStats()

      // Revelar credenciales
      setCredsReveladas({
        email: res.admin_usuario.email,
        password_temporal: res.password_temporal,
        nombre_entidad: res.firma.nombre,
        tipo: 'firma',
      })
    } catch (err: any) {
      error(err.message || 'Error al crear la firma')
    } finally {
      setSaving(false)
    }
  }

  // Crear Usuario en Tenant
  const handleCrearUsuario = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    try {
      const res = await api.post<{
        usuario: SuperAdminUsuario
        password_temporal: string
      }>('/superadmin/usuarios', {
        firma_id: nuevoUsuario.firma_id,
        nombre: nuevoUsuario.nombre,
        email: nuevoUsuario.email,
        rol: nuevoUsuario.rol,
        password: nuevoUsuario.password || undefined,
      })

      success(`Usuario "${res.usuario.nombre}" creado exitosamente`)
      setShowNuevoUsuarioModal(false)
      cargarUsuarios()
      cargarStats()

      setCredsReveladas({
        email: res.usuario.email,
        password_temporal: res.password_temporal,
        nombre_entidad: res.usuario.nombre,
        tipo: 'usuario',
      })
    } catch (err: any) {
      error(err.message || 'Error al crear usuario')
    } finally {
      setSaving(false)
    }
  }

  // Impersonar Tenant
  const handleImpersonar = async (firma: SuperAdminFirma) => {
    if (!confirm(`¿Iniciar sesión como administrador de la firma "${firma.nombre}"?`)) return
    try {
      const res = await api.post<{
        ok: boolean
        token: string
        user: { email: string; nombre: string; rol: string }
        firma: { nombre: string }
      }>(`/superadmin/firmas/${firma.id}/impersonate`)

      if (res.token) {
        localStorage.setItem('ia_token', res.token)
        success(`Modo Impersonación Activado: ${res.user.nombre} (${res.firma.nombre})`)
        window.location.href = '/dashboard'
      }
    } catch (err: any) {
      error(err.message || 'No se pudo impersonar al tenant')
    }
  }

  // Guardar Edición de Firma
  const handleGuardarFirma = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!editingFirma) return
    setSaving(true)

    const overrides: Record<string, any> = {
      tiene_ia: firmaTieneIa,
    }
    if (firmaMaxClientes) overrides.max_clientes = parseInt(firmaMaxClientes, 10)
    if (firmaMaxUsuarios) overrides.max_usuarios = parseInt(firmaMaxUsuarios, 10)

    try {
      await api.patch(`/superadmin/firmas/${editingFirma.id}`, {
        plan: firmaPlan,
        activa: firmaActiva,
        trial_hasta: firmaTrialHasta ? new Date(firmaTrialHasta).toISOString() : null,
        features_override_json: JSON.stringify(overrides),
      })
      success('Firma y overrides actualizados')
      setEditingFirma(null)
      cargarFirmas()
      cargarStats()
    } catch (err: any) {
      error(err.message || 'Error al actualizar firma')
    } finally {
      setSaving(false)
    }
  }

  // Resetear Contraseña
  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!resettingUser) return
    setSaving(true)
    try {
      await api.patch(`/superadmin/usuarios/${resettingUser.id}/password`, {
        password: newPassword,
        debe_cambiar_password: true,
      })
      success(`Contraseña restablecida para ${resettingUser.email}`)
      setCredsReveladas({
        email: resettingUser.email,
        password_temporal: newPassword,
        nombre_entidad: resettingUser.nombre,
        tipo: 'usuario',
      })
      setResettingUser(null)
      setNewPassword('')
    } catch (err: any) {
      error(err.message || 'Error al restablecer contraseña')
    } finally {
      setSaving(false)
    }
  }

  // Toggle Activar/Desactivar Usuario
  const toggleUsuarioActivo = async (u: SuperAdminUsuario) => {
    try {
      await api.patch(`/superadmin/usuarios/${u.id}`, { activo: !u.activo })
      success(`Usuario ${!u.activo ? 'activado' : 'desactivado'}`)
      cargarUsuarios()
      cargarStats()
    } catch (err: any) {
      error(err.message || 'Error al cambiar estado')
    }
  }

  // Resolver Error Sentry-Lite
  const handleResolverError = async () => {
    if (!selectedError) return
    setResolviendoError(true)
    try {
      await api.post(`/superadmin/errores/${selectedError.id}/resolver`, {
        notas_resolucion: notasResolucion || 'Marcado como resuelto por SuperAdmin',
      })
      success('Incidente marcado como resuelto')
      setSelectedError(null)
      setNotasResolucion('')
      cargarErrores()
      cargarStats()
    } catch (err: any) {
      error(err.message || 'Error al resolver incidente')
    } finally {
      setResolviendoError(false)
    }
  }

  // Copiar Reporte para Agente AI
  const handleCopiarReporteAI = (errItem: ErrorPlataformaItem) => {
    const markdownReport = `### 🚨 Reporte de Incidente Sentry-Lite (Inteliaudit SaaS)
- **ID:** \`${errItem.id}\`
- **Fingerprint:** \`${errItem.fingerprint}\`
- **Tipo de Error:** \`${errItem.tipo_error}\`
- **Mensaje:** ${errItem.mensaje}
- **Ruta:** \`${errItem.metodo} ${errItem.path}\`
- **HTTP Status:** ${errItem.status_code}
- **Ocurrencias:** ${errItem.ocurrencias}
- **Firma / Tenant:** \`${errItem.firma_id || 'N/A'}\`
- **Usuario:** \`${errItem.usuario_email || 'N/A'}\`
- **Primera vez:** ${errItem.primera_vez}
- **Última vez:** ${errItem.ultima_vez}

#### Stacktrace
\`\`\`python
${errItem.stacktrace}
\`\`\`

#### Contexto HTTP Sanitizado
\`\`\`json
${errItem.contexto_json || '{}'}
\`\`\`
`
    navigator.clipboard.writeText(markdownReport)
    success('📋 Reporte copiado en Markdown. Listo para pegar al Agente AI!')
  }

  // Abrir Modal de Edición de Firma
  const openEditFirma = (f: SuperAdminFirma) => {
    setEditingFirma(f)
    setFirmaPlan(f.plan)
    setFirmaActiva(f.activa)
    setFirmaTrialHasta(f.trial_hasta ? f.trial_hasta.substring(0, 10) : '')
    if (f.features_override_json) {
      try {
        const parsed = JSON.parse(f.features_override_json)
        setFirmaTieneIa(Boolean(parsed.tiene_ia))
        setFirmaMaxClientes(parsed.max_clientes !== undefined ? String(parsed.max_clientes) : '')
        setFirmaMaxUsuarios(parsed.max_usuarios !== undefined ? String(parsed.max_usuarios) : '')
      } catch {
        setFirmaTieneIa(false)
        setFirmaMaxClientes('')
        setFirmaMaxUsuarios('')
      }
    } else {
      setFirmaTieneIa(f.plan === 'pro' || f.plan === 'enterprise')
      setFirmaMaxClientes('')
      setFirmaMaxUsuarios('')
    }
  }

  // Filtrado de búsquedas
  const firmasFiltradas = firmas.filter(
    (f) =>
      f.nombre.toLowerCase().includes(busqueda.toLowerCase()) ||
      (f.ruc && f.ruc.includes(busqueda)) ||
      (f.email && f.email.toLowerCase().includes(busqueda.toLowerCase()))
  )

  const usuariosFiltrados = usuarios.filter(
    (u) =>
      u.nombre.toLowerCase().includes(busqueda.toLowerCase()) ||
      u.email.toLowerCase().includes(busqueda.toLowerCase()) ||
      (u.firma_nombre && u.firma_nombre.toLowerCase().includes(busqueda.toLowerCase()))
  )

  const erroresFiltrados = errores.filter(
    (e) =>
      e.tipo_error.toLowerCase().includes(busqueda.toLowerCase()) ||
      e.mensaje.toLowerCase().includes(busqueda.toLowerCase()) ||
      e.path.toLowerCase().includes(busqueda.toLowerCase())
  )

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-16">
      {/* Header y KPIs */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-border/40 pb-5">
        <div>
          <div className="flex items-center gap-2">
            <span className="p-2 rounded-xl bg-primary/10 text-primary">
              <ShieldAlert size={22} />
            </span>
            <h1 className="text-2xl font-bold tracking-tight text-foreground">
              Consola de Plataforma SuperAdmin
            </h1>
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            Control integral del SaaS multitenant: tenants, cuotas, incidentes Sentry-Lite y vitals de infraestructura.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {tab === 'firmas' && (
            <button
              onClick={() => {
                setNuevaFirma({
                  nombre: '',
                  ruc: '',
                  email: '',
                  plan: 'starter',
                  admin_nombre: '',
                  admin_email: '',
                  admin_password: '',
                  tiene_ia: false,
                  max_clientes: '5',
                  max_usuarios: '3',
                })
                setShowNuevaFirmaModal(true)
              }}
              className="px-3.5 py-2 rounded-lg bg-primary text-primary-foreground text-xs font-semibold hover:bg-primary/90 flex items-center gap-1.5 shadow-sm transition"
            >
              <Plus size={15} />
              + Nueva Firma
            </button>
          )}

          {tab === 'usuarios' && (
            <button
              onClick={() => {
                setNuevoUsuario({
                  firma_id: firmas[0]?.id || '',
                  nombre: '',
                  email: '',
                  rol: 'auditor',
                  password: '',
                })
                setShowNuevoUsuarioModal(true)
              }}
              className="px-3.5 py-2 rounded-lg bg-primary text-primary-foreground text-xs font-semibold hover:bg-primary/90 flex items-center gap-1.5 shadow-sm transition"
            >
              <Plus size={15} />
              + Nuevo Usuario
            </button>
          )}

          {tab === 'vitals' && (
            <button
              onClick={cargarVitals}
              disabled={refreshingVitals}
              className="px-3.5 py-2 rounded-lg bg-card border border-border text-xs font-semibold hover:bg-muted flex items-center gap-1.5 transition disabled:opacity-50"
            >
              <RefreshCw size={14} className={refreshingVitals ? 'animate-spin' : ''} />
              Refrescar Vitals
            </button>
          )}
        </div>
      </div>

      {/* KPI Cards Bar */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="p-4 rounded-xl border border-border/60 bg-card/60 backdrop-blur-sm shadow-sm flex items-center justify-between">
            <div>
              <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">Total Firmas</p>
              <p className="text-2xl font-black tracking-tight text-foreground mt-0.5">{stats.total_firmas}</p>
              <p className="text-[10px] text-emerald-600 dark:text-emerald-400 font-medium mt-0.5">
                {stats.firmas_activas} activas
              </p>
            </div>
            <div className="p-3 rounded-xl bg-blue-500/10 text-blue-600 dark:text-blue-400">
              <Building2 size={22} />
            </div>
          </div>

          <div className="p-4 rounded-xl border border-border/60 bg-card/60 backdrop-blur-sm shadow-sm flex items-center justify-between">
            <div>
              <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">Usuarios Activos</p>
              <p className="text-2xl font-black tracking-tight text-foreground mt-0.5">{stats.total_usuarios}</p>
              <p className="text-[10px] text-muted-foreground mt-0.5">En todos los tenants</p>
            </div>
            <div className="p-3 rounded-xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
              <Users size={22} />
            </div>
          </div>

          <div className="p-4 rounded-xl border border-border/60 bg-card/60 backdrop-blur-sm shadow-sm flex items-center justify-between">
            <div>
              <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">Contribuyentes DNIT</p>
              <p className="text-2xl font-black tracking-tight text-foreground mt-0.5">{stats.total_clientes}</p>
              <p className="text-[10px] text-muted-foreground mt-0.5">Clientes auditados</p>
            </div>
            <div className="p-3 rounded-xl bg-purple-500/10 text-purple-600 dark:text-purple-400">
              <FileText size={22} />
            </div>
          </div>

          <div className="p-4 rounded-xl border border-border/60 bg-card/60 backdrop-blur-sm shadow-sm flex items-center justify-between">
            <div>
              <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">Errores 5xx Pendientes</p>
              <p className="text-2xl font-black tracking-tight text-foreground mt-0.5">
                {stats.total_errores_pendientes}
              </p>
              <p className="text-[10px] text-amber-600 dark:text-amber-400 font-medium mt-0.5">
                {stats.total_errores_pendientes > 0 ? 'Requieren intervención' : 'Plataforma estable'}
              </p>
            </div>
            <div className={`p-3 rounded-xl ${stats.total_errores_pendientes > 0 ? 'bg-red-500/10 text-red-600 dark:text-red-400' : 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'}`}>
              <Bug size={22} />
            </div>
          </div>
        </div>
      )}

      {/* Tabs Navigation */}
      <div className="flex border-b border-border">
        <button
          onClick={() => { setTab('firmas'); setBusqueda('') }}
          className={`px-4 py-2.5 text-xs font-semibold border-b-2 flex items-center gap-2 transition ${
            tab === 'firmas'
              ? 'border-primary text-primary dark:text-primary-light'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
        >
          <Building2 size={15} />
          Tenants (Firmas)
          {firmas.length > 0 && <span className="ml-1 px-1.5 py-0.2 rounded-full bg-muted text-[10px]">{firmas.length}</span>}
        </button>

        <button
          onClick={() => { setTab('usuarios'); setBusqueda('') }}
          className={`px-4 py-2.5 text-xs font-semibold border-b-2 flex items-center gap-2 transition ${
            tab === 'usuarios'
              ? 'border-primary text-primary dark:text-primary-light'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
        >
          <Users size={15} />
          Directorio Global de Usuarios
          {usuarios.length > 0 && <span className="ml-1 px-1.5 py-0.2 rounded-full bg-muted text-[10px]">{usuarios.length}</span>}
        </button>

        <button
          onClick={() => { setTab('errores'); setBusqueda('') }}
          className={`px-4 py-2.5 text-xs font-semibold border-b-2 flex items-center gap-2 transition ${
            tab === 'errores'
              ? 'border-primary text-primary dark:text-primary-light'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
        >
          <Bug size={15} />
          Sentry-Lite (Errores 5xx)
          {stats?.total_errores_pendientes ? (
            <span className="ml-1 px-1.5 py-0.2 rounded-full bg-red-500 text-white font-bold text-[10px]">
              {stats.total_errores_pendientes}
            </span>
          ) : null}
        </button>

        <button
          onClick={() => { setTab('vitals'); setBusqueda('') }}
          className={`px-4 py-2.5 text-xs font-semibold border-b-2 flex items-center gap-2 transition ${
            tab === 'vitals'
              ? 'border-primary text-primary dark:text-primary-light'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
        >
          <Activity size={15} />
          Vitals de Infraestructura
          {vitals && (
            <span className={`w-2 h-2 rounded-full ${vitals.status === 'ok' ? 'bg-emerald-500 animate-pulse' : 'bg-red-500'}`} />
          )}
        </button>
      </div>

      {/* Barra de Búsqueda y Filtros */}
      {tab !== 'vitals' && (
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="relative w-full sm:w-80">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <input
              type="text"
              placeholder={`Buscar en ${tab}...`}
              value={busqueda}
              onChange={(e) => setBusqueda(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 text-xs rounded-lg border border-border bg-card text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>

          {tab === 'errores' && (
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">Estado:</span>
              <select
                value={filtroErrorResuelto === null ? 'todos' : filtroErrorResuelto ? 'resueltos' : 'pendientes'}
                onChange={(e) => {
                  if (e.target.value === 'todos') setFiltroErrorResuelto(null)
                  else if (e.target.value === 'resueltos') setFiltroErrorResuelto(true)
                  else setFiltroErrorResuelto(false)
                }}
                className="text-xs rounded-lg border border-border bg-card px-2.5 py-1.5 text-foreground"
              >
                <option value="pendientes">Pendientes</option>
                <option value="resueltos">Resueltos</option>
                <option value="todos">Todos los incidentes</option>
              </select>
            </div>
          )}
        </div>
      )}

      {/* ============================================================ */}
      {/* TAB 1: TENANTS (FIRMAS) */}
      {/* ============================================================ */}
      {tab === 'firmas' && (
        <div className="bg-card rounded-xl border border-border overflow-hidden shadow-sm">
          {loading ? (
            <div className="p-12 flex justify-center text-muted-foreground">
              <Loader2 className="animate-spin" size={24} />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-muted/50 border-b border-border text-muted-foreground font-semibold uppercase tracking-wider">
                  <tr>
                    <th className="py-3 px-4">Firma</th>
                    <th className="py-3 px-4">Plan & Límites</th>
                    <th className="py-3 px-4 text-center">Clientes</th>
                    <th className="py-3 px-4 text-center">Estado</th>
                    <th className="py-3 px-4">Creado</th>
                    <th className="py-3 px-4 text-right">Acciones</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/60">
                  {firmasFiltradas.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="py-8 text-center text-muted-foreground">
                        No se encontraron firmas.
                      </td>
                    </tr>
                  ) : (
                    firmasFiltradas.map((f) => {
                      let overridesObj: any = null
                      if (f.features_override_json) {
                        try {
                          overridesObj = JSON.parse(f.features_override_json)
                        } catch {}
                      }

                      return (
                        <tr key={f.id} className="hover:bg-muted/30 transition">
                          <td className="py-3 px-4">
                            <div className="font-semibold text-foreground flex items-center gap-2">
                              {f.nombre}
                              {overridesObj?.tiene_ia && (
                                <span title="IA Habilitada por Override" className="text-amber-500">
                                  <Sparkles size={13} />
                                </span>
                              )}
                            </div>
                            <div className="text-[11px] text-muted-foreground">
                              {f.ruc ? `RUC: ${f.ruc}` : 'Sin RUC'} • {f.email || 'Sin email'}
                            </div>
                          </td>

                          <td className="py-3 px-4">
                            <div className="flex items-center gap-1.5 flex-wrap">
                              <span className={planBadge(f.plan)}>{f.plan}</span>
                              {overridesObj && (
                                <span className="px-1.5 py-0.2 rounded bg-amber-500/10 text-amber-600 dark:text-amber-400 font-mono text-[9px] font-bold">
                                  Custom Limits
                                </span>
                              )}
                            </div>
                            {overridesObj && (
                              <div className="text-[10px] text-muted-foreground mt-0.5">
                                {overridesObj.max_clientes && `Max: ${overridesObj.max_clientes} cli`}
                                {overridesObj.max_usuarios && ` • Max: ${overridesObj.max_usuarios} usr`}
                              </div>
                            )}
                          </td>

                          <td className="py-3 px-4 text-center font-bold text-foreground">
                            {f.num_clientes}
                          </td>

                          <td className="py-3 px-4 text-center">
                            <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                              f.activa ? 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300' : 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300'
                            }`}>
                              {f.activa ? 'Activa' : 'Inactiva'}
                            </span>
                          </td>

                          <td className="py-3 px-4 text-muted-foreground text-[11px]">
                            {fecha(f.creado_en)}
                          </td>

                          <td className="py-3 px-4 text-right">
                            <div className="flex items-center justify-end gap-1.5">
                              <button
                                onClick={() => handleImpersonar(f)}
                                title="Ingresar como este tenant"
                                className="px-2.5 py-1 rounded-lg bg-primary/10 text-primary hover:bg-primary/20 text-[11px] font-semibold flex items-center gap-1 transition"
                              >
                                <ArrowUpRight size={13} />
                                Impersonar
                              </button>

                              <button
                                onClick={() => openEditFirma(f)}
                                title="Editar plan y cuotas"
                                className="p-1.5 rounded-lg border border-border hover:bg-muted text-muted-foreground hover:text-foreground transition"
                              >
                                <Edit size={14} />
                              </button>
                            </div>
                          </td>
                        </tr>
                      )
                    })
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ============================================================ */}
      {/* TAB 2: USUARIOS GLOBALES */}
      {/* ============================================================ */}
      {tab === 'usuarios' && (
        <div className="bg-card rounded-xl border border-border overflow-hidden shadow-sm">
          {loading ? (
            <div className="p-12 flex justify-center text-muted-foreground">
              <Loader2 className="animate-spin" size={24} />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-muted/50 border-b border-border text-muted-foreground font-semibold uppercase tracking-wider">
                  <tr>
                    <th className="py-3 px-4">Usuario</th>
                    <th className="py-3 px-4">Firma (Tenant)</th>
                    <th className="py-3 px-4">Rol</th>
                    <th className="py-3 px-4 text-center">Estado</th>
                    <th className="py-3 px-4">Password Status</th>
                    <th className="py-3 px-4 text-right">Acciones</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/60">
                  {usuariosFiltrados.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="py-8 text-center text-muted-foreground">
                        No se encontraron usuarios.
                      </td>
                    </tr>
                  ) : (
                    usuariosFiltrados.map((u) => (
                      <tr key={u.id} className="hover:bg-muted/30 transition">
                        <td className="py-3 px-4">
                          <div className="flex items-center gap-2.5">
                            <div className="w-7 h-7 rounded-full bg-primary/10 text-primary font-bold flex items-center justify-center text-[11px]">
                              {initials(u.nombre)}
                            </div>
                            <div>
                              <div className="font-semibold text-foreground">{u.nombre}</div>
                              <div className="text-[11px] text-muted-foreground font-mono">{u.email}</div>
                            </div>
                          </div>
                        </td>

                        <td className="py-3 px-4 font-medium text-foreground">
                          {u.firma_nombre || 'Sin firma asignada'}
                        </td>

                        <td className="py-3 px-4">
                          <span className={rolBadge(u.rol)}>{u.rol}</span>
                        </td>

                        <td className="py-3 px-4 text-center">
                          <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                            u.activo ? 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300' : 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300'
                          }`}>
                            {u.activo ? 'Activo' : 'Desactivado'}
                          </span>
                        </td>

                        <td className="py-3 px-4">
                          {u.debe_cambiar_password ? (
                            <span className="px-2 py-0.5 rounded bg-amber-500/10 text-amber-600 dark:text-amber-400 font-semibold text-[10px] flex items-center gap-1 w-fit">
                              <Key size={11} />
                              Debe cambiar (temporal)
                            </span>
                          ) : (
                            <span className="text-[11px] text-muted-foreground">
                              Definitiva
                            </span>
                          )}
                        </td>

                        <td className="py-3 px-4 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            <button
                              onClick={() => {
                                setResettingUser(u)
                                setNewPassword('')
                              }}
                              title="Restablecer contraseña"
                              className="p-1.5 rounded-lg border border-border hover:bg-muted text-muted-foreground hover:text-foreground transition"
                            >
                              <Key size={14} />
                            </button>

                            <button
                              onClick={() => toggleUsuarioActivo(u)}
                              title={u.activo ? 'Desactivar usuario' : 'Activar usuario'}
                              className={`p-1.5 rounded-lg border border-border transition ${
                                u.activo ? 'hover:bg-red-500/10 text-muted-foreground hover:text-red-600' : 'hover:bg-emerald-500/10 text-muted-foreground hover:text-emerald-600'
                              }`}
                            >
                              {u.activo ? <UserX size={14} /> : <UserCheck size={14} />}
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ============================================================ */}
      {/* TAB 3: SENTRY-LITE (ERRORES 5xx) */}
      {/* ============================================================ */}
      {tab === 'errores' && (
        <div className="bg-card rounded-xl border border-border overflow-hidden shadow-sm">
          {loading ? (
            <div className="p-12 flex justify-center text-muted-foreground">
              <Loader2 className="animate-spin" size={24} />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-muted/50 border-b border-border text-muted-foreground font-semibold uppercase tracking-wider">
                  <tr>
                    <th className="py-3 px-4">Incidente / Tipo</th>
                    <th className="py-3 px-4">Ruta & Método</th>
                    <th className="py-3 px-4 text-center">Ocurrencias</th>
                    <th className="py-3 px-4">Última Vez</th>
                    <th className="py-3 px-4 text-center">Estado</th>
                    <th className="py-3 px-4 text-right">Acción</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/60">
                  {erroresFiltrados.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="py-12 text-center text-muted-foreground">
                        <CheckCircle2 size={32} className="mx-auto text-emerald-500 mb-2 opacity-80" />
                        <p className="font-semibold text-foreground text-sm">Cero incidentes en esta vista</p>
                        <p className="text-xs">No se han registrado errores 5xx no controlados con este filtro.</p>
                      </td>
                    </tr>
                  ) : (
                    erroresFiltrados.map((errItem) => (
                      <tr
                        key={errItem.id}
                        className="hover:bg-muted/30 cursor-pointer transition"
                        onClick={() => setSelectedError(errItem)}
                      >
                        <td className="py-3 px-4">
                          <div className="font-bold text-red-600 dark:text-red-400 font-mono text-[11px] flex items-center gap-1.5">
                            <Bug size={13} />
                            {errItem.tipo_error}
                          </div>
                          <div className="text-foreground truncate max-w-sm mt-0.5" title={errItem.mensaje}>
                            {errItem.mensaje}
                          </div>
                          <div className="text-[10px] text-muted-foreground font-mono mt-0.5">
                            FP: {errItem.fingerprint.substring(0, 16)}...
                          </div>
                        </td>

                        <td className="py-3 px-4">
                          <div className="flex items-center gap-1.5 font-mono text-[11px]">
                            <span className="px-1.5 py-0.2 rounded bg-muted text-muted-foreground font-bold">
                              {errItem.metodo}
                            </span>
                            <span className="text-foreground truncate max-w-xs">{errItem.path}</span>
                          </div>
                          {errItem.usuario_email && (
                            <div className="text-[10px] text-muted-foreground mt-0.5">
                              Por: {errItem.usuario_email}
                            </div>
                          )}
                        </td>

                        <td className="py-3 px-4 text-center">
                          <span className="px-2 py-0.5 rounded-full bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 font-bold font-mono">
                            {errItem.ocurrencias}x
                          </span>
                        </td>

                        <td className="py-3 px-4 text-muted-foreground text-[11px]">
                          {fecha(errItem.ultima_vez)}
                        </td>

                        <td className="py-3 px-4 text-center">
                          <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                            errItem.resuelto ? 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300' : 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300'
                          }`}>
                            {errItem.resuelto ? 'Resuelto' : 'Pendiente'}
                          </span>
                        </td>

                        <td className="py-3 px-4 text-right" onClick={(e) => e.stopPropagation()}>
                          <div className="flex items-center justify-end gap-1.5">
                            <button
                              onClick={() => handleCopiarReporteAI(errItem)}
                              title="Copiar reporte formateado para agente AI"
                              className="px-2.5 py-1 rounded-lg bg-card border border-border hover:bg-muted text-foreground text-[11px] font-medium flex items-center gap-1 transition shadow-sm"
                            >
                              <Copy size={12} />
                              Copiar AI
                            </button>
                            <button
                              onClick={() => setSelectedError(errItem)}
                              className="px-2.5 py-1 rounded-lg bg-primary text-primary-foreground text-[11px] font-medium hover:bg-primary/90 transition"
                            >
                              Ver Trace
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ============================================================ */}
      {/* TAB 4: SYSTEM VITALS */}
      {/* ============================================================ */}
      {tab === 'vitals' && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Database */}
            <div className="p-5 rounded-xl border border-border bg-card shadow-sm space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="p-2.5 rounded-lg bg-blue-500/10 text-blue-600 dark:text-blue-400">
                    <Database size={20} />
                  </div>
                  <div>
                    <h3 className="font-bold text-foreground text-sm">Base de Datos Principal</h3>
                    <p className="text-xs text-muted-foreground">{vitals?.database.engine || 'PostgreSQL'}</p>
                  </div>
                </div>
                <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                  vitals?.database.status === 'ok' ? 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300' : 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300'
                }`}>
                  {vitals?.database.status === 'ok' ? 'En Línea' : 'Error'}
                </span>
              </div>
              <div className="pt-2 border-t border-border flex justify-between text-xs text-muted-foreground">
                <span>Latencia de consulta:</span>
                <span className="font-mono font-bold text-foreground">{vitals?.database.latency_ms ?? 0} ms</span>
              </div>
            </div>

            {/* Ollama Local AI */}
            <div className="p-5 rounded-xl border border-border bg-card shadow-sm space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="p-2.5 rounded-lg bg-purple-500/10 text-purple-600 dark:text-purple-400">
                    <Cpu size={20} />
                  </div>
                  <div>
                    <h3 className="font-bold text-foreground text-sm">Motor IA Local (Ollama Qwen 14B)</h3>
                    <p className="text-xs text-muted-foreground">localhost:11434</p>
                  </div>
                </div>
                <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                  vitals?.ollama_ai.status === 'ok' ? 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300' : 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300'
                }`}>
                  {vitals?.ollama_ai.status === 'ok' ? 'Activo' : 'Offline / Remoto'}
                </span>
              </div>
              <div className="pt-2 border-t border-border space-y-1 text-xs">
                <div className="flex justify-between text-muted-foreground">
                  <span>Latencia ping:</span>
                  <span className="font-mono font-bold text-foreground">{vitals?.ollama_ai.latency_ms ?? 0} ms</span>
                </div>
                {vitals?.ollama_ai.modelos && vitals.ollama_ai.modelos.length > 0 && (
                  <div className="text-[11px] text-muted-foreground">
                    Modelos detectados: <span className="font-mono text-foreground font-semibold">{vitals.ollama_ai.modelos.join(', ')}</span>
                  </div>
                )}
              </div>
            </div>

            {/* SIFEN Cache */}
            <div className="p-5 rounded-xl border border-border bg-card shadow-sm space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="p-2.5 rounded-lg bg-teal-500/10 text-teal-600 dark:text-teal-400">
                    <Activity size={20} />
                  </div>
                  <div>
                    <h3 className="font-bold text-foreground text-sm">Caché Comprobantes DNIT SIFEN</h3>
                    <p className="text-xs text-muted-foreground">Tabla e-Kuatia sifen_cache</p>
                  </div>
                </div>
                <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300">
                  Operativo
                </span>
              </div>
              <div className="pt-2 border-t border-border flex justify-between text-xs text-muted-foreground">
                <span>Comprobantes cacheados:</span>
                <span className="font-mono font-bold text-foreground">
                  {vitals?.sifen_cache.total_comprobantes_cacheados ?? 0}
                </span>
              </div>
            </div>

            {/* Storage R2 */}
            <div className="p-5 rounded-xl border border-border bg-card shadow-sm space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="p-2.5 rounded-lg bg-orange-500/10 text-orange-600 dark:text-orange-400">
                    <Cloud size={20} />
                  </div>
                  <div>
                    <h3 className="font-bold text-foreground text-sm">Almacenamiento de Evidencias</h3>
                    <p className="text-xs text-muted-foreground">Cloudflare R2 / Local</p>
                  </div>
                </div>
                <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300">
                  {vitals?.storage.status === 'ok' ? 'Cloudflare R2' : 'Local Fallback'}
                </span>
              </div>
              <div className="pt-2 border-t border-border flex justify-between text-xs text-muted-foreground">
                <span>Bucket / Raíz:</span>
                <span className="font-mono font-bold text-foreground">{vitals?.storage.bucket || 'inteliaudit-evidencias'}</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ============================================================ */}
      {/* MODAL DETALLES ERROR SENTRY-LITE */}
      {/* ============================================================ */}
      {selectedError && (
        <Modal
          open={true}
          onClose={() => setSelectedError(null)}
          title={`Incidente: ${selectedError.tipo_error}`}
          size="xl"
        >
          <div className="space-y-4 text-xs">
            {/* Cabecera del error */}
            <div className="p-3.5 rounded-xl bg-red-500/10 border border-red-500/20 text-foreground space-y-1">
              <div className="flex items-center justify-between">
                <span className="font-mono font-bold text-red-600 dark:text-red-400 text-sm">
                  {selectedError.tipo_error} ({selectedError.status_code})
                </span>
                <span className="px-2 py-0.5 rounded-full bg-red-500/20 text-red-600 dark:text-red-300 font-bold font-mono">
                  {selectedError.ocurrencias} ocurrencias
                </span>
              </div>
              <p className="text-xs font-medium text-foreground">{selectedError.mensaje}</p>
              <div className="text-[11px] text-muted-foreground font-mono pt-1">
                Fingerprint: <span className="text-foreground">{selectedError.fingerprint}</span>
              </div>
            </div>

            {/* Metadatos */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-[11px] p-3 rounded-lg bg-muted/40 border border-border">
              <div>
                <span className="text-muted-foreground">Endpoint:</span>
                <p className="font-mono font-semibold text-foreground">{selectedError.metodo} {selectedError.path}</p>
              </div>
              <div>
                <span className="text-muted-foreground">Usuario:</span>
                <p className="font-medium text-foreground">{selectedError.usuario_email || 'Anónimo'}</p>
              </div>
              <div>
                <span className="text-muted-foreground">Primera vez:</span>
                <p className="text-foreground">{fecha(selectedError.primera_vez)}</p>
              </div>
              <div>
                <span className="text-muted-foreground">Última vez:</span>
                <p className="text-foreground">{fecha(selectedError.ultima_vez)}</p>
              </div>
            </div>

            {/* Botón destacado Copiar para Agente AI */}
            <div className="flex justify-end">
              <button
                onClick={() => handleCopiarReporteAI(selectedError)}
                className="px-3.5 py-2 rounded-lg bg-primary text-primary-foreground font-semibold flex items-center gap-2 hover:bg-primary/90 shadow-sm transition"
              >
                <Copy size={14} />
                📋 Copiar Reporte Completo para Agente AI
              </button>
            </div>

            {/* Stacktrace */}
            <div>
              <p className="font-bold text-foreground mb-1 flex items-center gap-1.5">
                <Terminal size={14} />
                Stacktrace de Python
              </p>
              <pre className="p-3.5 rounded-xl bg-slate-950 text-slate-100 font-mono text-[11px] overflow-x-auto max-h-72 border border-slate-800 leading-relaxed">
                {selectedError.stacktrace}
              </pre>
            </div>

            {/* Contexto HTTP */}
            {selectedError.contexto_json && (
              <div>
                <p className="font-bold text-foreground mb-1">Contexto HTTP</p>
                <pre className="p-3 rounded-xl bg-muted/60 font-mono text-[11px] overflow-x-auto max-h-40 border border-border">
                  {selectedError.contexto_json}
                </pre>
              </div>
            )}

            {/* Resolver Incidente */}
            <div className="p-3.5 rounded-xl border border-border bg-card space-y-2">
              <p className="font-bold text-foreground">Gestión de Resolución</p>
              <textarea
                placeholder="Notas de resolución (ej: Se corrigió bug en parser de RG90)..."
                value={notasResolucion || selectedError.notas_resolucion || ''}
                onChange={(e) => setNotasResolucion(e.target.value)}
                className="w-full p-2.5 rounded-lg border border-border bg-background text-foreground text-xs"
                rows={2}
              />
              <div className="flex justify-end">
                <button
                  onClick={handleResolverError}
                  disabled={resolviendoError}
                  className="px-4 py-1.5 rounded-lg bg-emerald-600 text-white font-semibold hover:bg-emerald-700 transition disabled:opacity-50 flex items-center gap-1.5"
                >
                  {resolviendoError ? <Loader2 size={13} className="animate-spin" /> : <CheckCircle2 size={13} />}
                  Marcar como Resuelto
                </button>
              </div>
            </div>
          </div>
        </Modal>
      )}

      {/* ============================================================ */}
      {/* MODAL NUEVA FIRMA ATÓMICA */}
      {/* ============================================================ */}
      {showNuevaFirmaModal && (
        <Modal
          open={true}
          onClose={() => setShowNuevaFirmaModal(false)}
          title="Alta Atómica de Nueva Firma (Tenant)"
          size="lg"
        >
          <form onSubmit={handleCrearFirma} className="space-y-4 text-xs">
            <div className="p-3 rounded-lg bg-primary/5 border border-primary/20 text-foreground">
              <p className="font-semibold text-primary">Creación Atómica</p>
              <p className="text-[11px] text-muted-foreground">
                Crea la Firma, provisiona el Administrador inicial con contraseña temporal y configura cuotas de la landing.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block font-semibold mb-1">Nombre de la Firma *</label>
                <input
                  type="text"
                  required
                  placeholder="Ej: Estudio Contable Benítez SRL"
                  value={nuevaFirma.nombre}
                  onChange={(e) => setNuevaFirma({ ...nuevaFirma, nombre: e.target.value })}
                  className="w-full p-2 rounded-lg border border-border bg-background text-foreground"
                />
              </div>

              <div>
                <label className="block font-semibold mb-1">RUC de la Firma</label>
                <input
                  type="text"
                  placeholder="Ej: 80012345-6"
                  value={nuevaFirma.ruc}
                  onChange={(e) => setNuevaFirma({ ...nuevaFirma, ruc: e.target.value })}
                  className="w-full p-2 rounded-lg border border-border bg-background text-foreground"
                />
              </div>

              <div>
                <label className="block font-semibold mb-1">Plan Inicial *</label>
                <select
                  value={nuevaFirma.plan}
                  onChange={(e) => setNuevaFirma({ ...nuevaFirma, plan: e.target.value })}
                  className="w-full p-2 rounded-lg border border-border bg-background text-foreground"
                >
                  <option value="starter">Starter (5 clientes, 3 usuarios, sin IA)</option>
                  <option value="pro">Pro (15 clientes, 8 usuarios, con IA Qwen)</option>
                  <option value="enterprise">Enterprise (Ilimitado, con IA, White-label)</option>
                  <option value="trial">Trial (14 días de degustación Pro)</option>
                </select>
              </div>

              <div>
                <label className="block font-semibold mb-1">Email Institucional</label>
                <input
                  type="email"
                  placeholder="contacto@estudio.com.py"
                  value={nuevaFirma.email}
                  onChange={(e) => setNuevaFirma({ ...nuevaFirma, email: e.target.value })}
                  className="w-full p-2 rounded-lg border border-border bg-background text-foreground"
                />
              </div>
            </div>

            <div className="border-t border-border pt-3">
              <h4 className="font-bold text-foreground mb-2">Administrador Inicial del Tenant</h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold mb-1">Nombre y Apellido *</label>
                  <input
                    type="text"
                    required
                    placeholder="Lic. Juan Pérez"
                    value={nuevaFirma.admin_nombre}
                    onChange={(e) => setNuevaFirma({ ...nuevaFirma, admin_nombre: e.target.value })}
                    className="w-full p-2 rounded-lg border border-border bg-background text-foreground"
                  />
                </div>

                <div>
                  <label className="block font-semibold mb-1">Email del Administrador *</label>
                  <input
                    type="email"
                    required
                    placeholder="juan.perez@estudio.com.py"
                    value={nuevaFirma.admin_email}
                    onChange={(e) => setNuevaFirma({ ...nuevaFirma, admin_email: e.target.value })}
                    className="w-full p-2 rounded-lg border border-border bg-background text-foreground"
                  />
                </div>
              </div>
            </div>

            <div className="border-t border-border pt-3">
              <h4 className="font-bold text-foreground mb-2">Overrides de Límites (Opcional)</h4>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="block font-semibold mb-1">Límite Clientes</label>
                  <input
                    type="number"
                    placeholder="Default plan"
                    value={nuevaFirma.max_clientes}
                    onChange={(e) => setNuevaFirma({ ...nuevaFirma, max_clientes: e.target.value })}
                    className="w-full p-2 rounded-lg border border-border bg-background text-foreground"
                  />
                </div>

                <div>
                  <label className="block font-semibold mb-1">Límite Usuarios</label>
                  <input
                    type="number"
                    placeholder="Default plan"
                    value={nuevaFirma.max_usuarios}
                    onChange={(e) => setNuevaFirma({ ...nuevaFirma, max_usuarios: e.target.value })}
                    className="w-full p-2 rounded-lg border border-border bg-background text-foreground"
                  />
                </div>

                <div className="flex items-center pt-5">
                  <label className="flex items-center gap-2 cursor-pointer font-semibold">
                    <input
                      type="checkbox"
                      checked={nuevaFirma.tiene_ia}
                      onChange={(e) => setNuevaFirma({ ...nuevaFirma, tiene_ia: e.target.checked })}
                      className="rounded border-border text-primary"
                    />
                    Habilitar IA Qwen 14B
                  </label>
                </div>
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t border-border">
              <button
                type="button"
                onClick={() => setShowNuevaFirmaModal(false)}
                className="px-4 py-2 rounded-lg border border-border hover:bg-muted font-medium transition"
              >
                Cancelar
              </button>
              <button
                type="submit"
                disabled={saving}
                className="px-4 py-2 rounded-lg bg-primary text-primary-foreground font-semibold hover:bg-primary/90 transition disabled:opacity-50 flex items-center gap-1.5"
              >
                {saving ? <Loader2 size={14} className="animate-spin" /> : <Building2 size={14} />}
                Crear Firma y Provisionar
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* ============================================================ */}
      {/* MODAL NUEVO USUARIO DIRECTO */}
      {/* ============================================================ */}
      {showNuevoUsuarioModal && (
        <Modal
          open={true}
          onClose={() => setShowNuevoUsuarioModal(false)}
          title="Crear Nuevo Usuario"
          size="md"
        >
          <form onSubmit={handleCrearUsuario} className="space-y-4 text-xs">
            <div>
              <label className="block font-semibold mb-1">Firma / Tenant de Destino *</label>
              <select
                required
                value={nuevoUsuario.firma_id}
                onChange={(e) => setNuevoUsuario({ ...nuevoUsuario, firma_id: e.target.value })}
                className="w-full p-2 rounded-lg border border-border bg-background text-foreground"
              >
                {firmas.map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.nombre} ({f.plan})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block font-semibold mb-1">Nombre Completo *</label>
              <input
                type="text"
                required
                placeholder="Lic. María González"
                value={nuevoUsuario.nombre}
                onChange={(e) => setNuevoUsuario({ ...nuevoUsuario, nombre: e.target.value })}
                className="w-full p-2 rounded-lg border border-border bg-background text-foreground"
              />
            </div>

            <div>
              <label className="block font-semibold mb-1">Correo Electrónico *</label>
              <input
                type="email"
                required
                placeholder="maria@estudio.com.py"
                value={nuevoUsuario.email}
                onChange={(e) => setNuevoUsuario({ ...nuevoUsuario, email: e.target.value })}
                className="w-full p-2 rounded-lg border border-border bg-background text-foreground"
              />
            </div>

            <div>
              <label className="block font-semibold mb-1">Rol *</label>
              <select
                value={nuevoUsuario.rol}
                onChange={(e) => setNuevoUsuario({ ...nuevoUsuario, rol: e.target.value })}
                className="w-full p-2 rounded-lg border border-border bg-background text-foreground"
              >
                <option value="auditor">Auditor Junior</option>
                <option value="auditor_senior">Auditor Senior</option>
                <option value="admin">Administrador de Firma</option>
              </select>
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t border-border">
              <button
                type="button"
                onClick={() => setShowNuevoUsuarioModal(false)}
                className="px-4 py-2 rounded-lg border border-border hover:bg-muted font-medium transition"
              >
                Cancelar
              </button>
              <button
                type="submit"
                disabled={saving}
                className="px-4 py-2 rounded-lg bg-primary text-primary-foreground font-semibold hover:bg-primary/90 transition disabled:opacity-50 flex items-center gap-1.5"
              >
                {saving ? <Loader2 size={14} className="animate-spin" /> : <Users size={14} />}
                Crear Usuario
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* ============================================================ */}
      {/* MODAL EDITAR PLAN Y OVERRIDES DE FIRMA */}
      {/* ============================================================ */}
      {editingFirma && (
        <Modal
          open={true}
          onClose={() => setEditingFirma(null)}
          title={`Gestionar Firma: ${editingFirma.nombre}`}
          size="md"
        >
          <form onSubmit={handleGuardarFirma} className="space-y-4 text-xs">
            <div>
              <label className="block font-semibold mb-1">Plan de Suscripción</label>
              <select
                value={firmaPlan}
                onChange={(e) => setFirmaPlan(e.target.value)}
                className="w-full p-2 rounded-lg border border-border bg-background text-foreground"
              >
                <option value="starter">Starter</option>
                <option value="pro">Pro</option>
                <option value="enterprise">Enterprise</option>
                <option value="trial">Trial</option>
              </select>
            </div>

            <div className="flex items-center gap-3">
              <label className="flex items-center gap-2 cursor-pointer font-semibold">
                <input
                  type="checkbox"
                  checked={firmaActiva}
                  onChange={(e) => setFirmaActiva(e.target.checked)}
                  className="rounded border-border text-primary"
                />
                Firma Activa en Plataforma
              </label>
            </div>

            <div className="border-t border-border pt-3 space-y-3">
              <h4 className="font-bold text-foreground">Overrides Específicos para este Tenant</h4>

              <div>
                <label className="block font-semibold mb-1">Límite Custom de Clientes (Vacío = Default del plan)</label>
                <input
                  type="number"
                  placeholder="Sin override"
                  value={firmaMaxClientes}
                  onChange={(e) => setFirmaMaxClientes(e.target.value)}
                  className="w-full p-2 rounded-lg border border-border bg-background text-foreground"
                />
              </div>

              <div>
                <label className="block font-semibold mb-1">Límite Custom de Usuarios (Vacío = Default del plan)</label>
                <input
                  type="number"
                  placeholder="Sin override"
                  value={firmaMaxUsuarios}
                  onChange={(e) => setFirmaMaxUsuarios(e.target.value)}
                  className="w-full p-2 rounded-lg border border-border bg-background text-foreground"
                />
              </div>

              <div>
                <label className="flex items-center gap-2 cursor-pointer font-semibold">
                  <input
                    type="checkbox"
                    checked={firmaTieneIa}
                    onChange={(e) => setFirmaTieneIa(e.target.checked)}
                    className="rounded border-border text-primary"
                  />
                  Habilitar IA Forense Qwen 14B
                </label>
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t border-border">
              <button
                type="button"
                onClick={() => setEditingFirma(null)}
                className="px-4 py-2 rounded-lg border border-border hover:bg-muted font-medium transition"
              >
                Cancelar
              </button>
              <button
                type="submit"
                disabled={saving}
                className="px-4 py-2 rounded-lg bg-primary text-primary-foreground font-semibold hover:bg-primary/90 transition disabled:opacity-50"
              >
                {saving ? 'Guardando...' : 'Guardar Cambios'}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* ============================================================ */}
      {/* MODAL RESET PASSWORD */}
      {/* ============================================================ */}
      {resettingUser && (
        <Modal
          open={true}
          onClose={() => setResettingUser(null)}
          title={`Restablecer Contraseña: ${resettingUser.nombre}`}
          size="sm"
        >
          <form onSubmit={handleResetPassword} className="space-y-4 text-xs">
            <p className="text-muted-foreground">
              Se asignará una contraseña temporal y se marcará{' '}
              <strong className="text-foreground">debe_cambiar_password = true</strong> para exigir cambio en primer login.
            </p>

            <div className="relative">
              <label className="block font-semibold mb-1">Nueva Contraseña Temporal *</label>
              <input
                type={showPassword ? 'text' : 'password'}
                required
                minLength={8}
                placeholder="Mínimo 8 caracteres"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className="w-full p-2 pr-8 rounded-lg border border-border bg-background text-foreground font-mono"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-2.5 top-7 text-muted-foreground hover:text-foreground"
              >
                {showPassword ? <EyeOff size={14} /> : <Eye size={14} />}
              </button>
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-border">
              <button
                type="button"
                onClick={() => setResettingUser(null)}
                className="px-4 py-2 rounded-lg border border-border hover:bg-muted font-medium transition"
              >
                Cancelar
              </button>
              <button
                type="submit"
                disabled={saving || newPassword.length < 8}
                className="px-4 py-2 rounded-lg bg-primary text-primary-foreground font-semibold hover:bg-primary/90 transition disabled:opacity-50 flex items-center gap-1.5"
              >
                {saving ? 'Guardando...' : 'Restablecer'}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* ============================================================ */}
      {/* MODAL TARJETA DE CREDENCIALES TEMPORALES REVELADAS */}
      {/* ============================================================ */}
      {credsReveladas && (
        <Modal
          open={true}
          onClose={() => setCredsReveladas(null)}
          title="Credenciales Temporales Generadas"
          size="md"
        >
          <div className="space-y-4 text-xs">
            <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 space-y-2">
              <p className="font-bold text-amber-700 dark:text-amber-300 text-sm flex items-center gap-1.5">
                <Key size={16} />
                Credenciales de Acceso para {credsReveladas.nombre_entidad}
              </p>
              <p className="text-muted-foreground text-xs leading-relaxed">
                Entregá estas credenciales al cliente o usuario. En su primer inicio de sesión se le exigirá cambiar la contraseña por una personal.
              </p>
            </div>

            <div className="p-4 rounded-xl border border-border bg-muted/40 space-y-3 font-mono">
              <div>
                <span className="text-muted-foreground text-[10px] uppercase block">Email de Acceso:</span>
                <span className="font-bold text-foreground text-sm select-all">{credsReveladas.email}</span>
              </div>

              <div>
                <span className="text-muted-foreground text-[10px] uppercase block">Contraseña Temporal:</span>
                <div className="flex items-center gap-2 mt-1">
                  <input
                    type={showPassRevelada ? 'text' : 'password'}
                    readOnly
                    value={credsReveladas.password_temporal}
                    className="p-2 rounded-lg border border-border bg-background text-foreground font-bold tracking-wider text-sm select-all w-full"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassRevelada(!showPassRevelada)}
                    className="p-2 rounded-lg border border-border hover:bg-muted text-muted-foreground hover:text-foreground"
                    title={showPassRevelada ? 'Ocultar' : 'Ver'}
                  >
                    {showPassRevelada ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>
            </div>

            <div className="flex justify-between items-center pt-2 border-t border-border">
              <button
                type="button"
                onClick={() => {
                  const texto = `Hola ${credsReveladas.nombre_entidad}, tus credenciales de acceso a Inteliaudit son:\nUsuario: ${credsReveladas.email}\nContraseña Temporal: ${credsReveladas.password_temporal}\nAcceso: https://inteliaudit.intellihouse.lat/login`
                  navigator.clipboard.writeText(texto)
                  setCopiadoPass(true)
                  setTimeout(() => setCopiadoPass(false), 2500)
                }}
                className="px-4 py-2 rounded-lg bg-card border border-border hover:bg-muted font-semibold flex items-center gap-2 transition"
              >
                {copiadoPass ? <Check size={14} className="text-emerald-500" /> : <Copy size={14} />}
                {copiadoPass ? '¡Copiado al portapapeles!' : 'Copiar Credenciales'}
              </button>

              <button
                type="button"
                onClick={() => setCredsReveladas(null)}
                className="px-4 py-2 rounded-lg bg-primary text-primary-foreground font-semibold hover:bg-primary/90 transition"
              >
                Entendido y Cerrar
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}
