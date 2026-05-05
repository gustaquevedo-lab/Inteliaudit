import { useState, useEffect } from 'react'
import { Plus, Search, Shield, ShieldCheck, ShieldAlert, MoreVertical, UserX, UserCheck, Loader2, Eye, EyeOff } from 'lucide-react'
import { api } from '../../api/client'
import { useToast } from '../../components/Toaster'
import { useAuth } from '../../context/AuthContext'
import Modal from '../../components/Modal'
import { fecha, initials, labelRol } from '../../utils/formatters'
import type { Usuario } from '../../api/types'

type Rol = 'admin' | 'auditor_senior' | 'auditor'

const ROLES: Rol[] = ['admin', 'auditor_senior', 'auditor']

const rolIcon = (rol: string) => {
  if (rol === 'admin' || rol === 'super_admin') return <ShieldAlert size={13} className="text-primary" />
  if (rol === 'auditor_senior') return <ShieldCheck size={13} className="text-accent" />
  return <Shield size={13} className="text-gray-400" />
}

const rolBadge = (rol: string) => {
  const base = 'px-2 py-0.5 rounded-full text-[10px] font-bold flex items-center gap-1'
  if (rol === 'super_admin' || rol === 'admin') return `${base} bg-primary/10 text-primary dark:text-primary-light`
  if (rol === 'auditor_senior') return `${base} bg-accent/10 text-accent dark:text-teal-400`
  return `${base} bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400`
}

interface NuevoForm {
  nombre: string
  email: string
  rol: Rol
  password: string
}

export default function Usuarios() {
  const { user } = useAuth()
  const { success, error } = useToast()
  const [usuarios, setUsuarios] = useState<Usuario[]>([])
  const [loading, setLoading] = useState(true)
  const [busqueda, setBusqueda] = useState('')
  const [showNuevo, setShowNuevo] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [saving, setSaving] = useState(false)
  const [menuAbierto, setMenuAbierto] = useState<string | null>(null)
  const [form, setForm] = useState<NuevoForm>({ nombre: '', email: '', rol: 'auditor', password: '' })

  const cargar = () =>
    api.get<Usuario[]>('/auth/usuarios').then(setUsuarios).catch(() => error('No se pudieron cargar los usuarios')).finally(() => setLoading(false))

  useEffect(() => { cargar() }, [])

  const set = <K extends keyof NuevoForm>(k: K, v: NuevoForm[K]) => setForm(f => ({ ...f, [k]: v }))

  const crear = async () => {
    if (!form.nombre || !form.email || !form.password) return
    setSaving(true)
    try {
      await api.post('/auth/usuarios', form)
      success(`Usuario ${form.nombre} creado correctamente`)
      setShowNuevo(false)
      setForm({ nombre: '', email: '', rol: 'auditor', password: '' })
      cargar()
    } catch (e: unknown) {
      error(e instanceof Error ? e.message : 'Error al crear usuario')
    } finally {
      setSaving(false)
    }
  }

  const toggleActivo = async (u: Usuario) => {
    try {
      await api.patch(`/auth/usuarios/${u.id}`, { activo: !u.activo })
      success(`Usuario ${u.activo ? 'desactivado' : 'activado'} correctamente`)
      setMenuAbierto(null)
      cargar()
    } catch {
      error('Error al actualizar usuario')
    }
  }

  const filtrados = usuarios.filter(u => {
    if (!busqueda) return true
    const q = busqueda.toLowerCase()
    return u.nombre.toLowerCase().includes(q) || u.email.toLowerCase().includes(q)
  })

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-gray-900 dark:text-white tracking-tight">Usuarios</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">Gestioná los auditores de tu firma</p>
        </div>
        <button onClick={() => setShowNuevo(true)} className="btn-primary self-start sm:self-auto">
          <Plus size={15} /> Nuevo usuario
        </button>
      </div>

      {/* Buscador */}
      <div className="relative max-w-sm">
        <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
        <input
          className="input-field pl-9 text-sm"
          placeholder="Buscar por nombre o email..."
          value={busqueda}
          onChange={e => setBusqueda(e.target.value)}
        />
      </div>

      {/* Tabla */}
      <div className="card overflow-hidden">
        {loading ? (
          <div className="flex justify-center py-16">
            <Loader2 size={24} className="animate-spin text-gray-400" />
          </div>
        ) : filtrados.length === 0 ? (
          <div className="py-16 flex flex-col items-center gap-2 text-gray-400">
            <Shield size={28} />
            <p className="text-sm font-bold">Sin usuarios</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="table-header">
                <tr>
                  <th className="table-cell">Usuario</th>
                  <th className="table-cell">Rol</th>
                  <th className="table-cell">Estado</th>
                  <th className="table-cell">Último acceso</th>
                  <th className="table-cell">Desde</th>
                  <th className="table-cell"></th>
                </tr>
              </thead>
              <tbody>
                {filtrados.map(u => (
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
                      {u.id !== user?.id && (
                        <div className="relative">
                          <button
                            onClick={() => setMenuAbierto(menuAbierto === u.id ? null : u.id)}
                            className="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
                          >
                            <MoreVertical size={14} className="text-gray-400" />
                          </button>
                          {menuAbierto === u.id && (
                            <>
                              <div className="fixed inset-0 z-10" onClick={() => setMenuAbierto(null)} />
                              <div className="absolute right-0 top-8 z-20 w-44 bg-white dark:bg-gray-800 rounded-xl shadow-lg border border-gray-100 dark:border-gray-700 overflow-hidden py-1">
                                <button
                                  onClick={() => toggleActivo(u)}
                                  className="w-full flex items-center gap-2.5 px-3 py-2 text-sm text-left hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                                >
                                  {u.activo
                                    ? <><UserX size={14} className="text-red-500" /><span className="text-red-600 dark:text-red-400 font-medium">Desactivar</span></>
                                    : <><UserCheck size={14} className="text-green-500" /><span className="text-green-600 dark:text-green-400 font-medium">Activar</span></>
                                  }
                                </button>
                              </div>
                            </>
                          )}
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Resumen de roles */}
      <div className="grid grid-cols-3 gap-4">
        {ROLES.map(rol => {
          const count = usuarios.filter(u => u.rol === rol && u.activo).length
          return (
            <div key={rol} className="card p-4 flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-gray-50 dark:bg-gray-800 flex items-center justify-center shrink-0">
                {rolIcon(rol)}
              </div>
              <div>
                <p className="text-xs text-gray-500 dark:text-gray-400">{labelRol(rol)}</p>
                <p className="text-xl font-black text-gray-900 dark:text-white">{count}</p>
              </div>
            </div>
          )
        })}
      </div>

      {/* Modal nuevo usuario */}
      <Modal
        open={showNuevo}
        onClose={() => setShowNuevo(false)}
        title="Nuevo usuario"
        size="md"
        footer={
          <>
            <button className="btn-outline" onClick={() => setShowNuevo(false)}>Cancelar</button>
            <button className="btn-primary" onClick={crear} disabled={saving || !form.nombre || !form.email || !form.password}>
              {saving ? <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" /> : 'Crear usuario'}
            </button>
          </>
        }
      >
        <div className="space-y-4">
          <div>
            <label className="input-label label-required">Nombre completo</label>
            <input className="input-field" placeholder="María García" value={form.nombre} onChange={e => set('nombre', e.target.value)} />
          </div>
          <div>
            <label className="input-label label-required">Email</label>
            <input className="input-field" type="email" placeholder="maria@firma.com.py" value={form.email} onChange={e => set('email', e.target.value)} />
          </div>
          <div>
            <label className="input-label">Rol</label>
            <div className="grid grid-cols-3 gap-2 mt-1">
              {ROLES.map(r => (
                <button
                  key={r}
                  type="button"
                  onClick={() => set('rol', r)}
                  className={`py-2.5 px-3 rounded-xl border-2 text-xs font-bold transition-all flex flex-col items-center gap-1 ${
                    form.rol === r
                      ? 'border-primary bg-primary/5 dark:bg-primary/10 text-primary dark:text-primary-light'
                      : 'border-gray-200 dark:border-gray-700 text-gray-500 hover:border-gray-300'
                  }`}
                >
                  {rolIcon(r)}
                  {labelRol(r)}
                </button>
              ))}
            </div>
            <p className="text-[10px] text-gray-400 mt-2">
              {form.rol === 'admin' && 'Acceso total: puede gestionar usuarios y configuración.'}
              {form.rol === 'auditor_senior' && 'Puede crear, editar y cerrar auditorías.'}
              {form.rol === 'auditor' && 'Puede trabajar en auditorías asignadas.'}
            </p>
          </div>
          <div>
            <label className="input-label label-required">Contraseña inicial</label>
            <div className="relative">
              <input
                className="input-field pr-10"
                type={showPassword ? 'text' : 'password'}
                placeholder="Mínimo 8 caracteres"
                value={form.password}
                onChange={e => set('password', e.target.value)}
              />
              <button
                type="button"
                onClick={() => setShowPassword(s => !s)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
              >
                {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
              </button>
            </div>
            <p className="text-[10px] text-gray-400 mt-1">El usuario deberá cambiarla en su primer acceso.</p>
          </div>
        </div>
      </Modal>
    </div>
  )
}
