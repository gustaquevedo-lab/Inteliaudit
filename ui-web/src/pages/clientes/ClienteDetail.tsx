import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Plus, FolderSearch, Key, Lock, Eye, EyeOff, CheckCircle2 } from 'lucide-react'
import { api } from '../../api/client'
import { useToast } from '../../components/Toaster'
import Modal from '../../components/Modal'
import EmptyState from '../../components/EmptyState'
import { BadgeEstadoAuditoria } from '../../components/Badge'
import { rangoPeríodos, fecha } from '../../utils/formatters'
import type { Cliente, Auditoria } from '../../api/types'

type Tab = 'auditorias' | 'credenciales'

export default function ClienteDetail() {
  const { ruc } = useParams<{ ruc: string }>()
  const navigate = useNavigate()
  const { success, error: toastError } = useToast()
  const [cliente, setCliente] = useState<Cliente | null>(null)
  const [auditorias, setAuditorias] = useState<Auditoria[]>([])
  const [tab, setTab] = useState<Tab>('auditorias')
  const [loading, setLoading] = useState(true)
  const [credStatus, setCredStatus] = useState<{ tiene_credencial: boolean; alias?: string; actualizado_en?: string } | null>(null)
  const [showCredModal, setShowCredModal] = useState(false)
  const [cred, setCred] = useState({ usuario_set: '', clave_set: '', alias: '' })
  const [showClave, setShowClave] = useState(false)
  const [savingCred, setSavingCred] = useState(false)

  useEffect(() => {
    if (!ruc) return
    Promise.all([
      api.get<Cliente>(`/clientes/${ruc}`),
      api.get<Auditoria[]>(`/auditorias?cliente_ruc=${ruc}`),
      api.get<{ tiene_credencial: boolean; alias?: string; actualizado_en?: string }>(`/auth/credenciales/${ruc}`),
    ]).then(([c, auds, cred]) => {
      setCliente(c)
      setAuditorias(auds)
      setCredStatus(cred)
    }).catch(() => navigate('/clientes'))
      .finally(() => setLoading(false))
  }, [ruc])

  const guardarCred = async () => {
    if (!cred.usuario_set || !cred.clave_set) return
    setSavingCred(true)
    try {
      await api.post('/auth/credenciales', { cliente_ruc: ruc, ...cred })
      success('Credenciales guardadas correctamente')
      setShowCredModal(false)
      setCredStatus({ tiene_credencial: true, alias: cred.alias })
      setCred({ usuario_set: '', clave_set: '', alias: '' })
    } catch (e: unknown) {
      toastError(e instanceof Error ? e.message : 'Error al guardar')
    } finally {
      setSavingCred(false)
    }
  }

  if (loading) return (
    <div className="flex justify-center py-24">
      <div className="w-7 h-7 border-4 border-primary border-t-transparent rounded-full animate-spin" />
    </div>
  )

  if (!cliente) return null

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-start gap-4">
        <button onClick={() => navigate('/clientes')} className="btn-ghost mt-1 p-2">
          <ArrowLeft size={18} />
        </button>
        <div className="flex-1">
          <h1 className="text-2xl font-black text-gray-900 dark:text-white uppercase tracking-tight leading-tight">
            {cliente.razon_social}
          </h1>
          <div className="flex flex-wrap items-center gap-3 mt-1">
            <span className="font-mono text-sm font-bold text-gray-500 dark:text-gray-400">RUC: {cliente.ruc}</span>
            <span className="badge-info">{cliente.regimen}</span>
            {credStatus?.tiene_credencial && (
              <span className="badge-bajo"><Key size={10} />Marangatú vinculado</span>
            )}
          </div>
        </div>
        <button onClick={() => navigate('/auditorias/nueva', { state: { cliente_ruc: ruc } })} className="btn-primary shrink-0">
          <Plus size={16} /> Nueva auditoría
        </button>
      </div>

      {/* Info cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: 'Actividad', value: cliente.actividad_principal ?? '—' },
          { label: 'Dirección', value: cliente.direccion ?? '—' },
          { label: 'Email DNIT', value: cliente.email_dnit ?? '—' },
          { label: 'Inscripción DNIT', value: fecha(cliente.fecha_inscripcion) },
        ].map((item, i) => (
          <div key={i} className="card p-4">
            <p className="input-label">{item.label}</p>
            <p className="text-sm font-bold text-gray-800 dark:text-gray-200 truncate" title={item.value}>{item.value}</p>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="card overflow-hidden">
        <div className="border-b border-gray-100 dark:border-gray-700 flex">
          {([
            { key: 'auditorias', label: `Auditorías (${auditorias.length})` },
            { key: 'credenciales', label: 'Credenciales Marangatú' },
          ] as { key: Tab; label: string }[]).map(t => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`px-6 py-3.5 text-sm font-bold border-b-2 transition-all ${
                tab === t.key
                  ? 'border-primary text-primary dark:text-primary-light'
                  : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Tab: Auditorías */}
        {tab === 'auditorias' && (
          auditorias.length === 0 ? (
            <EmptyState
              icon={<FolderSearch size={32} />}
              title="Sin auditorías"
              description="Este cliente no tiene auditorías registradas todavía"
              action={
                <button onClick={() => navigate('/auditorias/nueva', { state: { cliente_ruc: ruc } })} className="btn-primary text-sm py-2">
                  <Plus size={14} /> Crear primera auditoría
                </button>
              }
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="table-header">
                  <tr>
                    <th className="table-cell">Período</th>
                    <th className="table-cell">Impuestos</th>
                    <th className="table-cell">Auditor</th>
                    <th className="table-cell">Estado</th>
                    <th className="table-cell">Inicio</th>
                    <th className="table-cell"></th>
                  </tr>
                </thead>
                <tbody>
                  {auditorias.map(a => (
                    <tr key={a.id} className="table-row" onClick={() => navigate(`/auditorias/${a.id}`)}>
                      <td className="table-td font-bold text-gray-900 dark:text-white text-xs">
                        {rangoPeríodos(a.periodo_desde, a.periodo_hasta)}
                      </td>
                      <td className="table-td">
                        <div className="flex flex-wrap gap-1">
                          {a.impuestos.map(imp => (
                            <span key={imp} className="badge-gray text-[10px]">{imp.replace('_', ' ')}</span>
                          ))}
                        </div>
                      </td>
                      <td className="table-td text-gray-500 dark:text-gray-400 text-xs">{a.auditor ?? '—'}</td>
                      <td className="table-td"><BadgeEstadoAuditoria estado={a.estado} /></td>
                      <td className="table-td text-gray-500 text-xs">{fecha(a.fecha_inicio)}</td>
                      <td className="table-td text-gray-400"><ArrowLeft size={14} className="rotate-180" /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        )}

        {/* Tab: Credenciales */}
        {tab === 'credenciales' && (
          <div className="p-6">
            {credStatus?.tiene_credencial ? (
              <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4 p-5 bg-green-50 dark:bg-green-900/10 border border-green-200 dark:border-green-800/30 rounded-2xl">
                <div className="p-3 bg-green-100 dark:bg-green-900/30 rounded-xl">
                  <CheckCircle2 size={24} className="text-green-600 dark:text-green-400" />
                </div>
                <div className="flex-1">
                  <p className="font-black text-green-800 dark:text-green-300 uppercase tracking-tight">Credenciales configuradas</p>
                  {credStatus.alias && <p className="text-sm text-green-700 dark:text-green-400 mt-0.5">{credStatus.alias}</p>}
                  {credStatus.actualizado_en && <p className="text-xs text-green-600/70 dark:text-green-500/70 mt-1">Actualizado: {fecha(credStatus.actualizado_en)}</p>}
                </div>
                <button onClick={() => setShowCredModal(true)} className="btn-outline text-sm py-2">
                  Actualizar
                </button>
              </div>
            ) : (
              <div className="flex flex-col items-center py-8 gap-4 text-center">
                <div className="p-4 bg-gray-100 dark:bg-gray-800 rounded-2xl">
                  <Lock size={28} className="text-gray-400" />
                </div>
                <div>
                  <p className="font-black text-gray-700 dark:text-gray-300 uppercase tracking-tight">Sin credenciales configuradas</p>
                  <p className="text-sm text-gray-500 dark:text-gray-400 mt-1 max-w-sm">
                    Guardá las credenciales de Marangatú del cliente para habilitar la descarga automática de datos.
                    Se almacenan cifradas con AES-256.
                  </p>
                </div>
                <button onClick={() => setShowCredModal(true)} className="btn-primary">
                  <Key size={16} /> Configurar credenciales
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Modal credenciales */}
      <Modal
        open={showCredModal}
        onClose={() => setShowCredModal(false)}
        title="Credenciales Marangatú"
        size="md"
        footer={
          <>
            <button className="btn-outline" onClick={() => setShowCredModal(false)}>Cancelar</button>
            <button className="btn-primary" onClick={guardarCred} disabled={savingCred || !cred.usuario_set || !cred.clave_set}>
              {savingCred ? <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" /> : 'Guardar cifradas'}
            </button>
          </>
        }
      >
        <div className="space-y-4">
          <div className="p-3.5 bg-amber-50 dark:bg-amber-900/10 border border-amber-200 dark:border-amber-800/30 rounded-xl text-xs text-amber-700 dark:text-amber-400 font-medium">
            Las credenciales se cifran con AES-256 antes de guardarse. Inteliaudit nunca las almacena en texto plano.
          </div>
          <div>
            <label className="input-label label-required">Usuario DNIT (RUC o email)</label>
            <input className="input-field" placeholder="80012345-6" value={cred.usuario_set} onChange={e => setCred(c => ({ ...c, usuario_set: e.target.value }))} />
          </div>
          <div>
            <label className="input-label label-required">Clave de acceso Marangatú</label>
            <div className="relative">
              <input
                type={showClave ? 'text' : 'password'}
                className="input-field pr-10"
                placeholder="••••••••"
                value={cred.clave_set}
                onChange={e => setCred(c => ({ ...c, clave_set: e.target.value }))}
              />
              <button type="button" onClick={() => setShowClave(v => !v)} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400">
                {showClave ? <EyeOff size={15} /> : <Eye size={15} />}
              </button>
            </div>
          </div>
          <div>
            <label className="input-label">Alias (opcional)</label>
            <input className="input-field" placeholder="Ej: Clave principal 2024" value={cred.alias} onChange={e => setCred(c => ({ ...c, alias: e.target.value }))} />
          </div>
        </div>
      </Modal>
    </div>
  )
}
