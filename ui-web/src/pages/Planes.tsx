import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { CheckCircle, Zap, Building2, Users, BrainCircuit, Share2, Headphones, ChevronRight, X, Loader2, Sparkles } from 'lucide-react'
import { api } from '../api/client'
import { useToast } from '../components/Toaster'
import { useAuth } from '../context/AuthContext'
import Modal from '../components/Modal'
import { pyg } from '../utils/formatters'

interface Plan {
  id: string; nombre: string; precio_mensual: number; precio_anual: number
  max_clientes: number | null; max_usuarios: number | null
  tiene_ia: boolean; tiene_portal_cliente: boolean
  features: string[]; soporte: string
}

export default function Planes() {
  const { success, error } = useToast()
  const navigate = useNavigate()
  const { planInfo } = useAuth()
  const [planes, setPlanes] = useState<Plan[]>([])
  const [loading, setLoading] = useState(true)
  const [anual, setAnual] = useState(false)
  const [selectedPlan, setSelectedPlan] = useState<string | null>(null)
  const [solicitando, setSolicitando] = useState(false)
  const [resultado, setResultado] = useState<any>(null)
  const [showModal, setShowModal] = useState(false)
  const [formFactura, setFormFactura] = useState({ ruc: '', razon_social: '' })

  useEffect(() => {
    api.get<Plan[]>('/suscripciones/planes').then(setPlanes).catch(() => {}).finally(() => setLoading(false))
  }, [])

  const solicitar = async (planId: string) => {
    setSelectedPlan(planId)
    setShowModal(true)
  }

  const confirmarSolicitud = async () => {
    if (!selectedPlan) return
    setSolicitando(true)
    try {
      const res = await api.post('/suscripciones/solicitar', {
        plan_id: selectedPlan, periodo: anual ? 'anual' : 'mensual',
        ruc_facturacion: formFactura.ruc || null,
        razon_social_facturacion: formFactura.razon_social || null,
      })
      setResultado(res)
      success('Solicitud enviada')
    } catch (e: unknown) { error(e instanceof Error ? e.message : 'Error') }
    setSolicitando(false)
  }

  if (loading) return <div className="flex items-center justify-center py-24"><Loader2 size={28} className="animate-spin text-primary" /></div>

  const planActual = planInfo?.planId || 'starter'

  return (
    <div className="space-y-8 animate-fade-in max-w-5xl mx-auto pb-16">
      <div className="text-center">
        <h1 className="text-3xl font-black text-gray-900 dark:text-white uppercase tracking-tighter">Planes</h1>
        <p className="text-sm text-gray-500 mt-2">Elegi el plan que mejor se adapte a tu firma</p>
      </div>

      {/* Toggle mensual/anual */}
      <div className="flex items-center justify-center gap-4">
        <span className={`text-sm font-bold ${!anual ? 'text-gray-900 dark:text-white' : 'text-gray-400'}`}>Mensual</span>
        <button onClick={() => setAnual(!anual)}
          className={`w-14 h-7 rounded-full transition-colors relative ${anual ? 'bg-primary' : 'bg-gray-300 dark:bg-gray-600'}`}>
          <div className={`absolute top-1 w-5 h-5 bg-white rounded-full shadow transition-transform ${anual ? 'translate-x-8' : 'translate-x-1'}`} />
        </button>
        <span className={`text-sm font-bold ${anual ? 'text-gray-900 dark:text-white' : 'text-gray-400'}`}>
          Anual <span className="text-green-500 text-xs">-15%</span>
        </span>
      </div>

      {/* Planes cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {planes.map((plan, i) => {
          const precio = anual ? plan.precio_anual : plan.precio_mensual
          const esActual = planActual === plan.id
          const esPopular = i === 1
          return (
            <div key={plan.id} className={`card p-6 flex flex-col relative ${esPopular ? 'border-primary ring-2 ring-primary/20' : ''} ${esActual ? 'border-green-500' : ''}`}>
              {esPopular && <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 bg-primary text-white text-[10px] font-black rounded-full uppercase">Mas popular</div>}
              {esActual && <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 bg-green-500 text-white text-[10px] font-black rounded-full uppercase">Plan actual</div>}

              <div className="mb-1">
                <p className="text-lg font-black text-gray-900 dark:text-white">{plan.nombre}</p>
              </div>

              <div className="mb-4">
                <span className="text-3xl font-black text-gray-900 dark:text-white">Gs. {(precio / (anual ? 12 : 1)).toLocaleString('es-PY')}</span>
                <span className="text-sm text-gray-400 ml-1">/mes</span>
                {anual && <p className="text-xs text-green-600 mt-1">Facturado anualmente: Gs. {precio.toLocaleString('es-PY')}/año</p>}
              </div>

              <div className="text-xs text-gray-500 space-y-1 mb-4">
                <p>Clientes: {plan.max_clientes ? `Hasta ${plan.max_clientes}` : 'Ilimitados'}</p>
                <p>Usuarios: {plan.max_usuarios ? `Hasta ${plan.max_usuarios}` : 'Ilimitados'}</p>
                {plan.tiene_ia && <p className="text-purple-600 font-bold">IA incluida</p>}
                {plan.tiene_portal_cliente && <p className="text-blue-600 font-bold">Portal del cliente</p>}
              </div>

              <div className="flex-1 space-y-2 mb-6">
                {plan.features.map((f, fi) => (
                  <div key={fi} className="flex items-start gap-2 text-xs">
                    <CheckCircle size={12} className="text-green-500 shrink-0 mt-0.5" />
                    <span className="text-gray-600 dark:text-gray-400">{f}</span>
                  </div>
                ))}
              </div>

              <button onClick={() => solicitar(plan.id)} disabled={esActual}
                className={`w-full py-3 rounded-xl text-sm font-bold transition-all ${
                  esPopular ? 'btn-primary' : esActual ? 'bg-gray-100 dark:bg-gray-800 text-gray-400 cursor-not-allowed' : 'btn-outline'
                }`}>
                {esActual ? 'Plan actual' : 'Solicitar plan'}
              </button>
            </div>
          )
        })}
      </div>

      {/* Modal de solicitud */}
      <Modal open={showModal} onClose={() => { setShowModal(false); setResultado(null) }} title="Solicitar plan" size="md">
        {resultado ? (
          <div className="space-y-4">
            <div className="p-4 rounded-xl bg-green-50 dark:bg-green-900/10 border border-green-200 dark:border-green-800/30">
              <p className="text-sm font-bold text-green-700 dark:text-green-400 mb-2">Solicitud recibida</p>
              <p className="text-xs text-green-600 dark:text-green-300">{resultado.mensaje}</p>
            </div>
            {resultado.datos_transferencia && (
              <div className="p-4 rounded-xl bg-gray-50 dark:bg-gray-800/50 space-y-2 text-sm">
                <p className="font-bold text-gray-700 dark:text-gray-300">Datos para la transferencia:</p>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <span className="text-gray-500">Banco:</span><span className="font-bold">{resultado.datos_transferencia.banco}</span>
                  <span className="text-gray-500">Titular:</span><span className="font-bold">{resultado.datos_transferencia.titular}</span>
                  <span className="text-gray-500">RUC:</span><span className="font-bold">{resultado.datos_transferencia.ruc}</span>
                  <span className="text-gray-500">Cuenta:</span><span className="font-bold font-mono">{resultado.datos_transferencia.cuenta}</span>
                  <span className="text-gray-500">Monto:</span><span className="font-bold">{pyg(resultado.datos_transferencia.monto)}</span>
                  <span className="text-gray-500 col-span-2">Concepto: <span className="font-mono text-[10px]">{resultado.datos_transferencia.concepto}</span></span>
                </div>
              </div>
            )}
            <button onClick={() => { setShowModal(false); setResultado(null) }} className="btn-primary w-full">Cerrar</button>
          </div>
        ) : (
          <div className="space-y-4">
            <p className="text-xs text-gray-500">Completa los datos de facturacion para solicitar el plan.</p>
            <div>
              <label className="input-label">RUC de facturacion</label>
              <input className="input-field" placeholder="80012345-6" value={formFactura.ruc} onChange={e => setFormFactura(f => ({ ...f, ruc: e.target.value }))} />
            </div>
            <div>
              <label className="input-label">Razon social</label>
              <input className="input-field" placeholder="Mi Firma SRL" value={formFactura.razon_social} onChange={e => setFormFactura(f => ({ ...f, razon_social: e.target.value }))} />
            </div>
            <div className="p-3 rounded-xl bg-amber-50 dark:bg-amber-900/10 text-xs text-amber-700 dark:text-amber-400">
              Al solicitar, te enviaremos los datos de transferencia por email. Una vez recibido el pago, activaremos tu plan.
            </div>
            <button onClick={confirmarSolicitud} disabled={solicitando} className="btn-primary w-full py-3">
              {solicitando ? <Loader2 size={15} className="animate-spin" /> : null}
              {solicitando ? 'Enviando...' : 'Solicitar plan'}
            </button>
          </div>
        )}
      </Modal>
    </div>
  )
}
