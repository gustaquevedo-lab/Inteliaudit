import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, ArrowRight, Check, Search, Calendar, ShieldCheck, Target, Gavel, FileText, Settings } from 'lucide-react'
import { api } from '../../api/client'
import type { Cliente } from '../../api/types'

const STEPS = [
  { id: 'cliente', label: 'Cliente', icon: Search },
  { id: 'tipo', label: 'Servicio', icon: Settings },
  { id: 'periodo', label: 'Período', icon: Calendar },
  { id: 'materialidad', label: 'Materialidad', icon: Target },
]

const TIPOS_ENCARGO = [
  { id: 'auditoria_anual', label: 'Auditoría Anual (AEI)', icon: Gavel, desc: 'Auditoría impositiva obligatoria según Resolución DNIT.' },
  { id: 'devolucion_iva', label: 'Devolución de IVA', icon: FileText, desc: 'Solicitud de recupero de crédito fiscal para exportadores.' },
  { id: 'fiscalizacion', label: 'Fiscalización DNIT', icon: ShieldCheck, desc: 'Atención y defensa ante órdenes de fiscalización puntual.' },
]

const MATERIALIDADES = [
  { value: 0, label: 'Sin materialidad', desc: 'Se informarán todas las diferencias encontradas.' },
  { value: 5000000, label: 'Gs. 5.000.000', desc: 'Umbral estándar para pequeñas empresas.' },
  { value: 20000000, label: 'Gs. 20.000.000', desc: 'Recomendado para medianos contribuyentes.' },
]

const MESES = Array.from({ length: 12 }, (_, i) => (i + 1).toString().padStart(2, '0'))
const AÑOS = [2022, 2023, 2024, 2025]

export default function NuevaAuditoria() {
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [clientes, setClientes] = useState<Cliente[]>([])
  const [filtro, setFiltro] = useState('')
  const [creating, setCreating] = useState(false)
  const [form, setForm] = useState({
    cliente_id: '',
    tipo_encargo: 'auditoria_anual',
    mes_desde: '01',
    anio_desde: '2023',
    mes_hasta: '12',
    anio_hasta: '2023',
    impuestos: ['IVA', 'IRE'],
    materialidad: 0,
    auditor: ''
  })

  useEffect(() => {
    api.get<Cliente[]>('/clientes').then(setClientes)
  }, [])

  const filtered = clientes.filter(c => 
    c.razon_social.toLowerCase().includes(filtro.toLowerCase()) || 
    c.ruc.includes(filtro)
  )

  const set = (key: string, val: any) => setForm(f => ({ ...f, [key]: val }))
  
  const crear = async () => {
    setCreating(true)
    try {
      const payload = {
        cliente_id: form.cliente_id,
        tipo_encargo: form.tipo_encargo,
        periodo_desde: `${form.anio_desde}-${form.mes_desde}`,
        periodo_hasta: `${form.anio_hasta}-${form.mes_hasta}`,
        impuestos: form.impuestos,
        materialidad: form.materialidad,
        auditor: form.auditor
      }
      const res = await api.post<any>('/auditorias', payload)
      navigate(`/auditorias/${res.id}`)
    } catch (err) {
      console.error(err)
    } finally {
      setCreating(false)
    }
  }

  const clienteSeleccionado = clientes.find(c => c.id === form.cliente_id)
  const canNext = (step === 0 && form.cliente_id) || (step === 1) || (step === 2) || (step === 3)
  const periodoDes = `${form.anio_desde}-${form.mes_desde}`
  const periodoHas = `${form.anio_hasta}-${form.mes_hasta}`
  const pyg = (n: number) => new Intl.NumberFormat('es-PY').format(n)

  return (
    <div className="max-w-2xl mx-auto animate-fade-in">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-black text-gray-900 dark:text-white uppercase tracking-tighter">
          Nuevo Encargo Fiscal
        </h1>
        <p className="text-gray-500 dark:text-gray-400 text-sm mt-1">Configuración del servicio de auditoría o intervención.</p>
      </div>

      {/* Steps Indicator */}
      <div className="flex items-center gap-2 mb-8 bg-white dark:bg-gray-800 p-2 rounded-2xl shadow-sm border border-gray-100 dark:border-gray-700">
        {STEPS.map((s, i) => {
          const Icon = s.icon
          const active = step === i
          const done = step > i
          return (
            <div key={s.id} className="flex-1 flex items-center gap-2 px-3 py-2 rounded-xl transition-all">
              <div className={`w-8 h-8 rounded-lg flex items-center justify-center transition-all ${
                active ? 'bg-primary text-white shadow-lg shadow-primary/30 scale-110' : 
                done ? 'bg-green-500 text-white' : 'bg-gray-100 dark:bg-gray-700 text-gray-400'
              }`}>
                {done ? <Check size={16} /> : <Icon size={16} />}
              </div>
              <div className="hidden sm:block">
                <p className={`text-[10px] font-black uppercase tracking-widest ${active ? 'text-gray-900 dark:text-white' : 'text-gray-400'}`}>
                  {s.label}
                </p>
              </div>
              {i < STEPS.length - 1 && <div className="flex-1 h-px bg-gray-100 dark:bg-gray-700 mx-2" />}
            </div>
          )
        })}
      </div>

      <div className="card p-6 shadow-xl">
        {/* Step 0: Cliente */}
        {step === 0 && (
          <div className="space-y-4">
            <div className="relative">
              <Search className="absolute left-3 top-3 text-gray-400" size={18} />
              <input 
                className="input-field pl-10" 
                placeholder="Buscar cliente por RUC o Razón Social..."
                value={filtro}
                onChange={e => setFiltro(e.target.value)}
              />
            </div>
            <div className="max-h-60 overflow-y-auto space-y-2 pr-2">
              {filtered.map(c => (
                <button 
                  key={c.id}
                  onClick={() => set('cliente_id', c.id)}
                  className={`w-full text-left p-4 rounded-xl border-2 transition-all ${
                    form.cliente_id === c.id 
                      ? 'border-primary bg-primary/5 dark:bg-primary/10' 
                      : 'border-gray-50 dark:border-gray-800 hover:border-primary/30'
                  }`}
                >
                  <p className="font-bold text-gray-900 dark:text-white text-sm">{c.razon_social}</p>
                  <p className="text-xs text-gray-500 mt-1">{c.ruc} • {c.regimen}</p>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Step 1: Tipo de Encargo */}
        {step === 1 && (
          <div className="space-y-4">
            <h2 className="text-base font-black text-gray-800 dark:text-white uppercase tracking-tight mb-2">Tipo de Servicio</h2>
            <div className="grid gap-3">
              {TIPOS_ENCARGO.map(t => {
                const Icon = t.icon
                return (
                  <button
                    key={t.id}
                    onClick={() => set('tipo_encargo', t.id)}
                    className={`flex items-start gap-4 p-4 rounded-xl border-2 text-left transition-all ${
                      form.tipo_encargo === t.id 
                        ? 'border-primary bg-primary/5 dark:bg-primary/10' 
                        : 'border-gray-100 dark:border-gray-700 hover:border-primary/30'
                    }`}
                  >
                    <div className={`p-2 rounded-lg ${form.tipo_encargo === t.id ? 'bg-primary text-white' : 'bg-gray-100 dark:bg-gray-700 text-gray-400'}`}>
                      <Icon size={20} />
                    </div>
                    <div>
                      <p className="font-bold text-gray-900 dark:text-white text-sm">{t.label}</p>
                      <p className="text-[11px] text-gray-500 dark:text-gray-400 mt-0.5 leading-relaxed">{t.desc}</p>
                    </div>
                  </button>
                )
              })}
            </div>
          </div>
        )}

        {/* Step 2: Período */}
        {step === 2 && (
          <div className="space-y-6">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="input-label">Desde (Mes/Año)</label>
                <div className="grid grid-cols-2 gap-2">
                  <select className="input-field" value={form.mes_desde} onChange={e => set('mes_desde', e.target.value)}>
                    {MESES.map(m => <option key={m} value={m}>{new Date(2024, Number(m)-1).toLocaleString('es-PY', { month: 'long' })}</option>)}
                  </select>
                  <select className="input-field" value={form.anio_desde} onChange={e => set('anio_desde', e.target.value)}>
                    {AÑOS.map(a => <option key={a}>{a}</option>)}
                  </select>
                </div>
              </div>
              <div className="space-y-2">
                <label className="input-label">Hasta (Mes/Año)</label>
                <div className="grid grid-cols-2 gap-2">
                  <select className="input-field" value={form.mes_hasta} onChange={e => set('mes_hasta', e.target.value)}>
                    {MESES.map(m => <option key={m} value={m}>{new Date(2024, Number(m)-1).toLocaleString('es-PY', { month: 'long' })}</option>)}
                  </select>
                  <select className="input-field" value={form.anio_hasta} onChange={e => set('anio_hasta', e.target.value)}>
                    {AÑOS.map(a => <option key={a}>{a}</option>)}
                  </select>
                </div>
              </div>
            </div>
            <div>
              <label className="input-label">Auditor responsable</label>
              <input className="input-field" value={form.auditor} onChange={e => set('auditor', e.target.value)} placeholder="Nombre del auditor" />
            </div>
          </div>
        )}

        {/* Step 3: Materialidad */}
        {step === 3 && (
          <div className="space-y-4">
            <h2 className="text-base font-black text-gray-800 dark:text-white uppercase tracking-tight mb-2">Umbral de materialidad</h2>
            <div className="space-y-2">
              {MATERIALIDADES.map(m => (
                <button
                  key={m.value}
                  onClick={() => set('materialidad', m.value)}
                  className={`w-full text-left p-4 rounded-xl border-2 transition-all ${
                    form.materialidad === m.value
                      ? 'border-primary bg-primary/5 dark:bg-primary/10'
                      : 'border-gray-200 dark:border-gray-700 hover:border-primary/30'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-black text-gray-900 dark:text-white text-sm">{m.label}</p>
                      <p className="text-[11px] text-gray-500 dark:text-gray-400 mt-0.5">{m.desc}</p>
                    </div>
                    {form.materialidad === m.value && <Check size={16} className="text-primary shrink-0" />}
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Navigation */}
        <div className="flex justify-between mt-8 pt-5 border-t border-gray-100 dark:border-gray-700">
          <button
            onClick={() => step > 0 ? setStep(s => s - 1) : navigate(-1)}
            className="btn-outline"
          >
            <ArrowLeft size={16} /> {step === 0 ? 'Cancelar' : 'Anterior'}
          </button>
          
          {step < STEPS.length - 1 ? (
            <button onClick={() => setStep(s => s + 1)} className="btn-primary" disabled={!canNext}>
              Siguiente <ArrowRight size={16} />
            </button>
          ) : (
            <button onClick={crear} className="btn-secondary" disabled={creating}>
              {creating ? 'Creando...' : 'Crear auditoría'}
            </button>
          )}
        </div>
      </div>

      {/* Summary Footer */}
      {step > 0 && (
        <div className="card p-4 mt-4 bg-gray-50/50 dark:bg-gray-800/50 border-dashed">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-[10px]">
            <div>
              <p className="text-gray-400 font-bold uppercase tracking-widest mb-1">Cliente</p>
              <p className="font-bold text-gray-900 dark:text-white truncate">{clienteSeleccionado?.razon_social || '---'}</p>
            </div>
            <div>
              <p className="text-gray-400 font-bold uppercase tracking-widest mb-1">Servicio</p>
              <p className="font-bold text-gray-900 dark:text-white capitalize">{form.tipo_encargo.replace('_', ' ')}</p>
            </div>
            <div>
              <p className="text-gray-400 font-bold uppercase tracking-widest mb-1">Período</p>
              <p className="font-bold text-gray-900 dark:text-white">{periodoDes} - {periodoHas}</p>
            </div>
            <div>
              <p className="text-gray-400 font-bold uppercase tracking-widest mb-1">Materialidad</p>
              <p className="font-bold text-gray-900 dark:text-white">{form.materialidad === 0 ? 'Sin umbral' : pyg(form.materialidad)}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
