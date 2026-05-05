import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, Search, Building2, ChevronRight, CheckCircle, XCircle, AlertTriangle } from 'lucide-react'
import { api } from '../../api/client'
import { useToast } from '../../components/Toaster'
import { useAuth } from '../../context/AuthContext'
import Modal from '../../components/Modal'
import EmptyState from '../../components/EmptyState'
import type { Cliente } from '../../api/types'

const REGIMENES = ['General', 'Pequeño contribuyente', 'Autoliquidación', 'Otro']

export default function ClientesList() {
  const navigate = useNavigate()
  const { success, error } = useToast()
  const { planInfo } = useAuth()
  const [clientes, setClientes] = useState<Cliente[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({
    ruc: '', razon_social: '', regimen: 'General',
    nombre_fantasia: '', actividad_principal: '', direccion: '', email_dnit: '',
  })

  const load = () =>
    api.get<Cliente[]>('/clientes').then(setClientes).finally(() => setLoading(false))

  useEffect(() => { load() }, [])

  const filtered = clientes.filter(c =>
    c.razon_social.toLowerCase().includes(search.toLowerCase()) ||
    c.ruc.includes(search)
  )

  const set = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }))

  const crear = async () => {
    if (!form.ruc || !form.razon_social) return
    setSaving(true)
    try {
      await api.post('/clientes', form)
      success('Cliente registrado correctamente')
      setShowModal(false)
      setForm({ ruc: '', razon_social: '', regimen: 'General', nombre_fantasia: '', actividad_principal: '', direccion: '', email_dnit: '' })
      load()
    } catch (e: unknown) {
      error(e instanceof Error ? e.message : 'Error al guardar')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-gray-900 dark:text-white uppercase tracking-tight">Clientes</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">{clientes.length} cliente{clientes.length !== 1 ? 's' : ''} registrado{clientes.length !== 1 ? 's' : ''}</p>
        </div>
        <button onClick={() => setShowModal(true)} className="btn-primary self-start">
          <Plus size={16} /> Nuevo cliente
        </button>
      </div>

      {/* Banner límite de clientes */}
      {planInfo?.clientesMaximos != null && (() => {
        const actual = clientes.length
        const maximo = planInfo.clientesMaximos!
        const restantes = maximo - actual
        if (restantes <= 1) {
          return (
            <div className={`flex items-start gap-3 p-4 rounded-2xl border text-sm ${
              restantes <= 0
                ? 'bg-red-50 dark:bg-red-900/10 border-red-200 dark:border-red-800/40 text-red-700 dark:text-red-300'
                : 'bg-amber-50 dark:bg-amber-900/10 border-amber-200 dark:border-amber-800/40 text-amber-700 dark:text-amber-300'
            }`}>
              <AlertTriangle size={16} className="shrink-0 mt-0.5" />
              <div>
                <p className="font-black">
                  {restantes <= 0
                    ? `Límite de clientes alcanzado — ${actual}/${maximo} en tu plan ${planInfo.nombre}`
                    : `Te queda 1 cliente disponible en tu plan ${planInfo.nombre} (${actual}/${maximo})`}
                </p>
                <a
                  href="https://inteliaudit.com/#precios"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-bold underline underline-offset-2 mt-0.5 inline-block opacity-80 hover:opacity-100 transition-opacity"
                >
                  Actualizá tu plan para agregar más
                </a>
              </div>
            </div>
          )
        }
        return null
      })()}

      {/* Search */}
      <div className="card p-4">
        <div className="relative">
          <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            className="input-field pl-10"
            placeholder="Buscar por razón social o RUC..."
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
      </div>

      {/* Table */}
      <div className="card overflow-hidden">
        {loading ? (
          <div className="flex justify-center py-16">
            <div className="w-7 h-7 border-4 border-primary border-t-transparent rounded-full animate-spin" />
          </div>
        ) : filtered.length === 0 ? (
          <EmptyState
            icon={<Building2 size={32} />}
            title={search ? 'Sin resultados' : 'Sin clientes aún'}
            description={search ? 'Probá con otro término de búsqueda' : 'Registrá el primer cliente para empezar'}
            action={!search ? <button onClick={() => setShowModal(true)} className="btn-primary text-sm py-2">Registrar cliente</button> : undefined}
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="table-header">
                <tr>
                  <th className="table-cell">RUC</th>
                  <th className="table-cell">Razón social</th>
                  <th className="table-cell hidden md:table-cell">Régimen</th>
                  <th className="table-cell hidden lg:table-cell">Actividad</th>
                  <th className="table-cell">Estado DNIT</th>
                  <th className="table-cell"></th>
                </tr>
              </thead>
              <tbody>
                {filtered.map(c => (
                  <tr key={c.ruc} className="table-row" onClick={() => navigate(`/clientes/${c.ruc}`)}>
                    <td className="table-td font-mono font-bold text-gray-900 dark:text-white">{c.ruc}</td>
                    <td className="table-td">
                      <div>
                        <p className="font-bold text-gray-900 dark:text-white">{c.razon_social}</p>
                        {c.nombre_fantasia && <p className="text-xs text-gray-500 dark:text-gray-400">{c.nombre_fantasia}</p>}
                      </div>
                    </td>
                    <td className="table-td hidden md:table-cell text-gray-600 dark:text-gray-300">{c.regimen}</td>
                    <td className="table-td hidden lg:table-cell text-gray-500 dark:text-gray-400 text-xs max-w-[200px] truncate">{c.actividad_principal ?? '—'}</td>
                    <td className="table-td">
                      {c.estado_dnit === 'activo'
                        ? <span className="badge-bajo"><CheckCircle size={11} />Activo</span>
                        : <span className="badge-alto"><XCircle size={11} />Inactivo</span>
                      }
                    </td>
                    <td className="table-td"><ChevronRight size={14} className="text-gray-400" /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Modal nuevo cliente */}
      <Modal
        open={showModal}
        onClose={() => setShowModal(false)}
        title="Registrar cliente"
        size="lg"
        footer={
          <>
            <button className="btn-outline" onClick={() => setShowModal(false)}>Cancelar</button>
            <button className="btn-primary" onClick={crear} disabled={saving || !form.ruc || !form.razon_social}>
              {saving ? <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" /> : 'Registrar cliente'}
            </button>
          </>
        }
      >
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="input-label label-required">RUC</label>
            <input className="input-field font-mono" placeholder="80012345-6" value={form.ruc} onChange={e => set('ruc', e.target.value)} />
          </div>
          <div>
            <label className="input-label label-required">Régimen</label>
            <select className="input-field" value={form.regimen} onChange={e => set('regimen', e.target.value)}>
              {REGIMENES.map(r => <option key={r}>{r}</option>)}
            </select>
          </div>
          <div className="sm:col-span-2">
            <label className="input-label label-required">Razón social</label>
            <input className="input-field" placeholder="EMPRESA SA" value={form.razon_social} onChange={e => set('razon_social', e.target.value)} />
          </div>
          <div className="sm:col-span-2">
            <label className="input-label">Nombre de fantasía</label>
            <input className="input-field" placeholder="Nombre comercial" value={form.nombre_fantasia} onChange={e => set('nombre_fantasia', e.target.value)} />
          </div>
          <div className="sm:col-span-2">
            <label className="input-label">Actividad principal</label>
            <input className="input-field" placeholder="Comercio al por mayor de..." value={form.actividad_principal} onChange={e => set('actividad_principal', e.target.value)} />
          </div>
          <div>
            <label className="input-label">Dirección</label>
            <input className="input-field" placeholder="Av. España 123, Asunción" value={form.direccion} onChange={e => set('direccion', e.target.value)} />
          </div>
          <div>
            <label className="input-label">Email DNIT</label>
            <input className="input-field" type="email" placeholder="contacto@empresa.com.py" value={form.email_dnit} onChange={e => set('email_dnit', e.target.value)} />
          </div>
        </div>
        <p className="text-xs text-gray-400 dark:text-gray-500 mt-4">
          Las credenciales de Marangatú se configuran desde el perfil del cliente una vez registrado.
        </p>
      </Modal>
    </div>
  )
}
