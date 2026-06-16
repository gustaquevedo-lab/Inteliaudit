import { useState, useEffect } from 'react'
import {
  Search, Shield, ShieldCheck, ShieldAlert, MoreVertical, UserX, UserCheck,
  Loader2, Eye, EyeOff, Building2, Key, Edit, ToggleLeft, ToggleRight, CheckSquare
} from 'lucide-react'
import { api } from '../../api/client'
import { useToast } from '../../components/Toaster'
import { useAuth } from '../../context/AuthContext'
import Modal from '../../components/Modal'
import { fecha, initials, labelRol } from '../../utils/formatters'

interface SuperAdminFirma {
  id: string
  nombre: string
  ruc: string | null
  email: string | null
  plan: string
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
  creado_en: string
  ultimo_acceso: string | null
}

const rolIcon = (rol: string) => {
  if (rol === 'super_admin' || rol === 'admin') return <ShieldAlert size={13} className="text-primary" />
  if (rol === 'auditor_senior') return <ShieldCheck size={13} className="text-accent" />
  return <Shield size={13} className="text-gray-400" />
}

const rolBadge = (rol: string) => {
  const base = 'px-2 py-0.5 rounded-full text-[10px] font-bold flex items-center gap-1'
  if (rol === 'super_admin' || rol === 'admin') return `${base} bg-primary/10 text-primary dark:text-primary-light`
  if (rol === 'auditor_senior') return `${base} bg-accent/10 text-accent dark:text-teal-400`
  return `${base} bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400`
}

const planBadge = (plan: string) => {
  const base = 'px-2 py-0.5 rounded-full text-[10px] font-bold tracking-wider uppercase'
  if (plan === 'enterprise') return `${base} bg-blue-100 dark:bg-blue-900/20 text-blue-700 dark:text-blue-400`
  if (plan === 'pro' || plan === 'professional') return `${base} bg-emerald-100 dark:bg-emerald-900/20 text-emerald-700 dark:text-emerald-400`
  if (plan === 'starter') return `${base} bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-400`
  return `${base} bg-amber-100 dark:bg-amber-900/20 text-amber-700 dark:text-amber-400` // trial
}

export default function SuperAdminDashboard() {
  const { user: currentUser } = useAuth()
  const { success, error } = useToast()
  
  const [tab, setTab] = useState<'firmas' | 'usuarios'>('firmas')
  const [firmas, setFirmas] = useState<SuperAdminFirma[]>([])
  const [usuarios, setUsuarios] = useState<SuperAdminUsuario[]>([])
  const [loading, setLoading] = useState(true)
  const [busqueda, setBusqueda] = useState('')
  
  // Modales
  const [editingFirma, setEditingFirma] = useState<SuperAdminFirma | null>(null)
  const [editingUsuario, setEditingUsuario] = useState<SuperAdminUsuario | null>(null)
  const [resettingUser, setResettingUser] = useState<SuperAdminUsuario | null>(null)
  
  // Acciones en Menús Desplegables
  const [menuFirmaAbierto, setMenuFirmaAbierto] = useState<string | null>(null)
  const [menuUserAbierto, setMenuUserAbierto] = useState<string | null>(null)
  
  // Formulario edicion Firma
  const [firmaPlan, setFirmaPlan] = useState('trial')
  const [firmaActiva, setFirmaActiva] = useState(true)
  const [firmaTrialHasta, setFirmaTrialHasta] = useState('')
  
  // Formulario edicion Usuario
  const [usuarioNombre, setUsuarioNombre] = useState('')
  const [usuarioRol, setUsuarioRol] = useState('auditor')
  const [usuarioActivo, setUsuarioActivo] = useState(true)
  
  // Formulario Reset Password
  const [newPassword, setNewPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [saving, setSaving] = useState(false)

  const cargarFirmas = () => {
    setLoading(true)
    api.get<SuperAdminFirma[]>('/superadmin/firmas')
      .then(setFirmas)
      .catch(() => error('Error al cargar firmas de la API'))
      .finally(() => setLoading(false))
  }

  const cargarUsuarios = () => {
    setLoading(true)
    api.get<SuperAdminUsuario[]>('/superadmin/usuarios')
      .then(setUsuarios)
      .catch(() => error('Error al cargar usuarios de la API'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    if (tab === 'firmas') {
      cargarFirmas()
    } else {
      cargarUsuarios()
    }
    setBusqueda('')
  }, [tab])

  // Guardar Edición Firma
  const guardarFirmaEdicion = async () => {
    if (!editingFirma) return
    setSaving(true)
    try {
      await api.patch(`/superadmin/firmas/${editingFirma.id}`, {
        plan: firmaPlan,
        activa: firmaActiva,
        trial_hasta: firmaTrialHasta ? new Date(firmaTrialHasta).toISOString() : null
      })
      success('Firma actualizada correctamente')
      setEditingFirma(null)
      cargarFirmas()
    } catch (e: any) {
      error(e.message || 'Error al actualizar la firma')
    } finally {
      setSaving(false)
    }
  }

  // Guardar Edición Usuario
  const guardarUsuarioEdicion = async () => {
    if (!editingUsuario) return
    setSaving(true)
    try {
      await api.patch(`/superadmin/usuarios/${editingUsuario.id}`, {
        nombre: usuarioNombre,
        rol: usuarioRol,
        activo: usuarioActivo
      })
      success('Usuario actualizado correctamente')
      setEditingUsuario(null)
      cargarUsuarios()
    } catch (e: any) {
      error(e.message || 'Error al actualizar el usuario')
    } finally {
      setSaving(false)
    }
  }

  // Guardar Reset Password
  const guardarResetPassword = async () => {
    if (!resettingUser || !newPassword) return
    if (newPassword.length < 8) {
      error('La contraseña debe tener al menos 8 caracteres')
      return
    }
    setSaving(true)
    try {
      await api.patch(`/superadmin/usuarios/${resettingUser.id}/password`, {
        password: newPassword
      })
      success(`Contraseña de ${resettingUser.nombre} restablecida correctamente`)
      setResettingUser(null)
      setNewPassword('')
    } catch (e: any) {
      error(e.message || 'Error al restablecer contraseña')
    } finally {
      setSaving(false)
    }
  }

  const toggleFirmaEstado = async (f: SuperAdminFirma) => {
    try {
      await api.patch(`/superadmin/firmas/${f.id}`, { activa: !f.activa })
      success(`Firma ${f.activa ? 'desactivada' : 'activada'} correctamente`)
      setMenuFirmaAbierto(null)
      cargarFirmas()
    } catch {
      error('Error al cambiar estado de la firma')
    }
  }

  const toggleUsuarioEstado = async (u: SuperAdminUsuario) => {
    try {
      await api.patch(`/superadmin/usuarios/${u.id}`, { activo: !u.activo })
      success(`Usuario ${u.activo ? 'desactivado' : 'activado'} correctamente`)
      setMenuUserAbierto(null)
      cargarUsuarios()
    } catch {
      error('Error al cambiar estado del usuario')
    }
  }

  // Abrir Modal Edición Firma
  const abrirFirmaModal = (f: SuperAdminFirma) => {
    setEditingFirma(f)
    setFirmaPlan(f.plan)
    setFirmaActiva(f.activa)
    setFirmaTrialHasta(f.trial_hasta ? f.trial_hasta.substring(0, 16) : '')
    setMenuFirmaAbierto(null)
  }

  // Abrir Modal Edición Usuario
  const abrirUsuarioModal = (u: SuperAdminUsuario) => {
    setEditingUsuario(u)
    setUsuarioNombre(u.nombre)
    setUsuarioRol(u.rol)
    setUsuarioActivo(u.activo)
    setMenuUserAbierto(null)
  }

  // Abrir Modal Reset Password
  const abrirResetPasswordModal = (u: SuperAdminUsuario) => {
    setResettingUser(u)
    setNewPassword('')
    setShowPassword(false)
    setMenuUserAbierto(null)
  }

  // Búsqueda
  const firmasFiltradas = firmas.filter(f => {
    if (!busqueda) return true
    const q = busqueda.toLowerCase()
    return f.nombre.toLowerCase().includes(q) || (f.ruc && f.ruc.includes(q)) || (f.email && f.email.toLowerCase().includes(q))
  })

  const usuariosFiltrados = usuarios.filter(u => {
    if (!busqueda) return true
    const q = busqueda.toLowerCase()
    return u.nombre.toLowerCase().includes(q) || u.email.toLowerCase().includes(q) || (u.firma_nombre && u.firma_nombre.toLowerCase().includes(q))
  })

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-gray-900 dark:text-white tracking-tight uppercase">Consola de Super Admin</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">Control global de firmas, planes, usuarios y accesos del SaaS</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-gray-100 dark:border-gray-800 gap-6">
        <button
          onClick={() => setTab('firmas')}
          className={`pb-3 text-sm font-bold transition-all relative ${
            tab === 'firmas'
              ? 'text-primary dark:text-primary-light font-black border-b-2 border-primary'
              : 'text-gray-500 dark:text-gray-400 hover:text-gray-700'
          }`}
        >
          <div className="flex items-center gap-2">
            <Building2 size={16} />
            <span>Firmas / Tenants ({firmas.length})</span>
          </div>
        </button>
        <button
          onClick={() => setTab('usuarios')}
          className={`pb-3 text-sm font-bold transition-all relative ${
            tab === 'usuarios'
              ? 'text-primary dark:text-primary-light font-black border-b-2 border-primary'
              : 'text-gray-500 dark:text-gray-400 hover:text-gray-700'
          }`}
        >
          <div className="flex items-center gap-2">
            <Shield size={16} />
            <span>Usuarios Globales ({usuarios.length})</span>
          </div>
        </button>
      </div>

      {/* Buscador */}
      <div className="relative max-w-sm">
        <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
        <input
          className="input-field pl-9 text-sm"
          placeholder={tab === 'firmas' ? 'Buscar firma por nombre, RUC...' : 'Buscar usuario por nombre, email o firma...'}
          value={busqueda}
          onChange={e => setBusqueda(e.target.value)}
        />
      </div>

      {/* Main Content */}
      <div className="card overflow-hidden">
        {loading ? (
          <div className="flex justify-center py-20">
            <Loader2 size={28} className="animate-spin text-gray-400" />
          </div>
        ) : tab === 'firmas' ? (
          /* FIRMAS VIEW */
          firmasFiltradas.length === 0 ? (
            <div className="py-16 text-center text-gray-400 flex flex-col items-center gap-2">
              <Building2 size={32} />
              <p className="text-sm font-bold">No se encontraron firmas</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="table-header">
                  <tr>
                    <th className="table-cell">Firma</th>
                    <th className="table-cell">Plan</th>
                    <th className="table-cell">Clientes</th>
                    <th className="table-cell">Estado</th>
                    <th className="table-cell">Trial Vence</th>
                    <th className="table-cell">Creada el</th>
                    <th className="table-cell"></th>
                  </tr>
                </thead>
                <tbody>
                  {firmasFiltradas.map(f => (
                    <tr key={f.id} className="table-row">
                      <td className="table-td">
                        <div>
                          <p className="text-sm font-bold text-gray-800 dark:text-gray-200">{f.nombre}</p>
                          <p className="text-xs text-gray-500 dark:text-gray-400">
                            {f.ruc ? `RUC: ${f.ruc}` : 'Sin RUC'} · {f.email || 'Sin email'}
                          </p>
                        </div>
                      </td>
                      <td className="table-td">
                        <span className={planBadge(f.plan)}>{f.plan}</span>
                      </td>
                      <td className="table-td text-sm font-bold text-gray-800 dark:text-gray-200">
                        {f.num_clientes}
                      </td>
                      <td className="table-td">
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                          f.activa
                            ? 'bg-green-100 dark:bg-green-900/20 text-green-700 dark:text-green-400'
                            : 'bg-red-100 dark:bg-red-900/20 text-red-700 dark:text-red-400'
                        }`}>
                          {f.activa ? 'Activa' : 'Inactiva'}
                        </span>
                      </td>
                      <td className="table-td text-xs text-gray-500 dark:text-gray-400">
                        {f.trial_hasta ? fecha(f.trial_hasta) : '—'}
                      </td>
                      <td className="table-td text-xs text-gray-500 dark:text-gray-400">
                        {fecha(f.creado_en)}
                      </td>
                      <td className="table-td">
                        <div className="relative">
                          <button
                            onClick={() => setMenuFirmaAbierto(menuFirmaAbierto === f.id ? null : f.id)}
                            className="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
                          >
                            <MoreVertical size={14} className="text-gray-400" />
                          </button>
                          {menuFirmaAbierto === f.id && (
                            <>
                              <div className="fixed inset-0 z-10" onClick={() => setMenuFirmaAbierto(null)} />
                              <div className="absolute right-0 top-8 z-20 w-44 bg-white dark:bg-gray-800 rounded-xl shadow-lg border border-gray-100 dark:border-gray-700 overflow-hidden py-1">
                                <button
                                  onClick={() => abrirFirmaModal(f)}
                                  className="w-full flex items-center gap-2.5 px-3 py-2 text-sm text-left hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors font-medium text-gray-700 dark:text-gray-300"
                                >
                                  <Edit size={14} /> Editar plan / trial
                                </button>
                                <button
                                  onClick={() => toggleFirmaEstado(f)}
                                  className="w-full flex items-center gap-2.5 px-3 py-2 text-sm text-left hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors font-medium"
                                >
                                  {f.activa
                                    ? <><ToggleLeft size={14} className="text-red-500" /><span className="text-red-600 dark:text-red-400">Desactivar</span></>
                                    : <><ToggleRight size={14} className="text-green-500" /><span className="text-green-600 dark:text-green-400">Activar</span></>
                                  }
                                </button>
                              </div>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        ) : (
          /* USUARIOS VIEW */
          usuariosFiltrados.length === 0 ? (
            <div className="py-16 text-center text-gray-400 flex flex-col items-center gap-2">
              <Shield size={32} />
              <p className="text-sm font-bold">No se encontraron usuarios</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="table-header">
                  <tr>
                    <th className="table-cell">Usuario</th>
                    <th className="table-cell">Firma / Tenant</th>
                    <th className="table-cell">Rol</th>
                    <th className="table-cell">Estado</th>
                    <th className="table-cell">Último acceso</th>
                    <th className="table-cell">Desde</th>
                    <th className="table-cell"></th>
                  </tr>
                </thead>
                <tbody>
                  {usuariosFiltrados.map(u => (
                    <tr key={u.id} className="table-row">
                      <td className="table-td">
                        <div className="flex items-center gap-3">
                          <div className="w-9 h-9 rounded-xl bg-primary/10 flex items-center justify-center text-xs font-black text-primary dark:text-primary-light shrink-0">
                            {initials(u.nombre)}
                          </div>
                          <div>
                            <p className="text-sm font-bold text-gray-800 dark:text-gray-200">{u.nombre}</p>
                            <p className="text-xs text-gray-500 dark:text-gray-400">{u.email}</p>
                          </div>
                        </div>
                      </td>
                      <td className="table-td text-sm font-bold text-gray-800 dark:text-gray-200">
                        {u.firma_nombre || '—'}
                      </td>
                      <td className="table-td">
                        <span className={rolBadge(u.rol)}>
                          {rolIcon(u.rol)}
                          {labelRol(u.rol)}
                        </span>
                      </td>
                      <td className="table-td">
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                          u.activo
                            ? 'bg-green-100 dark:bg-green-900/20 text-green-700 dark:text-green-400'
                            : 'bg-gray-100 dark:bg-gray-800 text-gray-500'
                        }`}>
                          {u.activo ? 'Activo' : 'Inactivo'}
                        </span>
                      </td>
                      <td className="table-td text-xs text-gray-500 dark:text-gray-400">
                        {u.ultimo_acceso ? fecha(u.ultimo_acceso) : '—'}
                      </td>
                      <td className="table-td text-xs text-gray-500 dark:text-gray-400">
                        {fecha(u.creado_en)}
                      </td>
                      <td className="table-td">
                        <div className="relative">
                          <button
                            onClick={() => setMenuUserAbierto(menuUserAbierto === u.id ? null : u.id)}
                            className="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
                          >
                            <MoreVertical size={14} className="text-gray-400" />
                          </button>
                          {menuUserAbierto === u.id && (
                            <>
                              <div className="fixed inset-0 z-10" onClick={() => setMenuUserAbierto(null)} />
                              <div className="absolute right-0 top-8 z-20 w-44 bg-white dark:bg-gray-800 rounded-xl shadow-lg border border-gray-100 dark:border-gray-700 overflow-hidden py-1">
                                <button
                                  onClick={() => abrirUsuarioModal(u)}
                                  className="w-full flex items-center gap-2.5 px-3 py-2 text-sm text-left hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors font-medium text-gray-700 dark:text-gray-300"
                                >
                                  <Edit size={14} /> Editar rol / nombre
                                </button>
                                <button
                                  onClick={() => abrirResetPasswordModal(u)}
                                  className="w-full flex items-center gap-2.5 px-3 py-2 text-sm text-left hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors font-medium text-gray-700 dark:text-gray-300"
                                >
                                  <Key size={14} /> Resetear contraseña
                                </button>
                                {u.id !== currentUser?.id && (
                                  <button
                                    onClick={() => toggleUsuarioEstado(u)}
                                    className="w-full flex items-center gap-2.5 px-3 py-2 text-sm text-left hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors font-medium"
                                  >
                                    {u.activo
                                      ? <><UserX size={14} className="text-red-500" /><span className="text-red-600 dark:text-red-400">Desactivar</span></>
                                      : <><UserCheck size={14} className="text-green-500" /><span className="text-green-600 dark:text-green-400">Activar</span></>
                                    }
                                  </button>
                                )}
                              </div>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        )}
      </div>

      {/* MODAL EDITAR FIRMA */}
      <Modal
        open={editingFirma !== null}
        onClose={() => setEditingFirma(null)}
        title="Editar Firma / Tenant"
        size="md"
        footer={
          <>
            <button className="btn-outline" onClick={() => setEditingFirma(null)}>Cancelar</button>
            <button className="btn-primary" onClick={guardarFirmaEdicion} disabled={saving}>
              {saving ? <Loader2 size={16} className="animate-spin" /> : 'Guardar Cambios'}
            </button>
          </>
        }
      >
        {editingFirma && (
          <div className="space-y-4">
            <div>
              <p className="text-xs text-gray-500 dark:text-gray-400">Firma</p>
              <p className="text-base font-bold text-gray-900 dark:text-white">{editingFirma.nombre}</p>
              {editingFirma.ruc && <p className="text-xs text-gray-400">RUC: {editingFirma.ruc}</p>}
            </div>

            <div>
              <label className="input-label">Plan de la Firma</label>
              <select
                className="input-field mt-1 text-sm bg-white dark:bg-gray-800"
                value={firmaPlan}
                onChange={e => setFirmaPlan(e.target.value)}
              >
                <option value="trial">Trial (Degustación Pro)</option>
                <option value="starter">Starter</option>
                <option value="pro">Pro / Professional</option>
                <option value="enterprise">Enterprise</option>
              </select>
            </div>

            <div>
              <label className="input-label">Trial Expiración (Solo si está en plan trial)</label>
              <input
                type="datetime-local"
                className="input-field mt-1 text-sm"
                value={firmaTrialHasta}
                onChange={e => setFirmaTrialHasta(e.target.value)}
              />
            </div>

            <div className="flex items-center gap-2 mt-2">
              <input
                type="checkbox"
                id="firmaActivaCheck"
                checked={firmaActiva}
                onChange={e => setFirmaActiva(e.target.checked)}
                className="rounded text-primary border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 focus:ring-primary"
              />
              <label htmlFor="firmaActivaCheck" className="text-sm font-medium text-gray-700 dark:text-gray-300 select-none cursor-pointer">
                Firma Habilitada (Activa)
              </label>
            </div>
          </div>
        )}
      </Modal>

      {/* MODAL EDITAR USUARIO */}
      <Modal
        open={editingUsuario !== null}
        onClose={() => setEditingUsuario(null)}
        title="Editar Usuario"
        size="md"
        footer={
          <>
            <button className="btn-outline" onClick={() => setEditingUsuario(null)}>Cancelar</button>
            <button className="btn-primary" onClick={guardarUsuarioEdicion} disabled={saving}>
              {saving ? <Loader2 size={16} className="animate-spin" /> : 'Guardar Cambios'}
            </button>
          </>
        }
      >
        {editingUsuario && (
          <div className="space-y-4">
            <div>
              <p className="text-xs text-gray-500 dark:text-gray-400">Email (No modificable)</p>
              <p className="text-sm font-bold text-gray-900 dark:text-white">{editingUsuario.email}</p>
              <p className="text-xs text-gray-400">Pertenece a: {editingUsuario.firma_nombre || 'Sin firma'}</p>
            </div>

            <div>
              <label className="input-label label-required">Nombre Completo</label>
              <input
                className="input-field mt-1"
                placeholder="Nombre del usuario"
                value={usuarioNombre}
                onChange={e => setUsuarioNombre(e.target.value)}
              />
            </div>

            <div>
              <label className="input-label">Rol Global / Nivel de Acceso</label>
              <select
                className="input-field mt-1 text-sm bg-white dark:bg-gray-800"
                value={usuarioRol}
                onChange={e => setUsuarioRol(e.target.value)}
              >
                <option value="super_admin">Super Admin (Global)</option>
                <option value="admin">Administrador de Firma</option>
                <option value="auditor_senior">Auditor Senior</option>
                <option value="auditor">Auditor Junior</option>
              </select>
            </div>

            {editingUsuario.id !== currentUser?.id && (
              <div className="flex items-center gap-2 mt-2">
                <input
                  type="checkbox"
                  id="usuarioActivoCheck"
                  checked={usuarioActivo}
                  onChange={e => setUsuarioActivo(e.target.checked)}
                  className="rounded text-primary border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 focus:ring-primary"
                />
                <label htmlFor="usuarioActivoCheck" className="text-sm font-medium text-gray-700 dark:text-gray-300 select-none cursor-pointer">
                  Usuario Activo (Habilitado para ingresar)
                </label>
              </div>
            )}
          </div>
        )}
      </Modal>

      {/* MODAL RESET PASSWORD */}
      <Modal
        open={resettingUser !== null}
        onClose={() => setResettingUser(null)}
        title="Resetear Contraseña"
        size="md"
        footer={
          <>
            <button className="btn-outline" onClick={() => setResettingUser(null)}>Cancelar</button>
            <button className="btn-primary" onClick={guardarResetPassword} disabled={saving || !newPassword}>
              {saving ? <Loader2 size={16} className="animate-spin" /> : 'Establecer Contraseña'}
            </button>
          </>
        }
      >
        {resettingUser && (
          <div className="space-y-4">
            <div className="p-3 bg-blue-50 dark:bg-blue-900/10 border border-blue-200 dark:border-blue-900 rounded-xl">
              <p className="text-xs text-blue-800 dark:text-blue-300 font-bold">Importante</p>
              <p className="text-xs text-blue-700 dark:text-blue-400 mt-1">
                Estás a punto de reescribir la contraseña de <strong>{resettingUser.nombre}</strong> ({resettingUser.email}).
                El cambio se aplicará de forma inmediata en producción.
              </p>
            </div>

            <div>
              <label className="input-label label-required">Nueva Contraseña (min. 8 caracteres)</label>
              <div className="relative mt-1">
                <input
                  className="input-field pr-10"
                  type={showPassword ? 'text' : 'password'}
                  placeholder="Escribe la nueva contraseña..."
                  value={newPassword}
                  onChange={e => setNewPassword(e.target.value)}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(s => !s)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                >
                  {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
