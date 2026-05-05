import { useEffect, useState } from 'react'
import { Settings, Building2, Save, CheckCircle, AlertCircle, Loader2, Crown, Calendar } from 'lucide-react'
import { api } from '../../api/client'
import { useToast } from '../../components/Toaster'
import { fecha } from '../../utils/formatters'
import { useAuth } from '../../context/AuthContext'

interface FirmaConfig {
  id: string
  nombre: string
  ruc: string | null
  email: string | null
  eslogan: string | null
  plan: string
  activa: boolean
  trial_hasta: string | null
  logo_path: string | null
  creado_en: string | null
}

const PLAN_LABELS: Record<string, { label: string; color: string }> = {
  trial:        { label: 'Trial (30 días)', color: 'text-amber-600 bg-amber-50 dark:bg-amber-900/20' },
  starter:      { label: 'Starter', color: 'text-blue-600 bg-blue-50 dark:bg-blue-900/20' },
  professional: { label: 'Professional', color: 'text-primary bg-primary/10' },
  enterprise:   { label: 'Enterprise', color: 'text-secondary bg-secondary/10' },
}

export default function Configuracion() {
  const { user } = useAuth()
  const { success, error } = useToast()
  const [config, setConfig] = useState<FirmaConfig | null>(null)
  const [form, setForm] = useState({ nombre: '', ruc: '', email: '', eslogan: '' })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    api.get<FirmaConfig>('/firmas/configuracion')
      .then(c => {
        setConfig(c)
        setForm({
          nombre:  c.nombre ?? '',
          ruc:     c.ruc ?? '',
          email:   c.email ?? '',
          eslogan: c.eslogan ?? '',
        })
      })
      .catch(() => error('No se pudo cargar la configuración'))
      .finally(() => setLoading(false))
  }, [])

  const handleSave = async () => {
    setSaving(true)
    try {
      const body: Record<string, string> = {}
      if (form.nombre)  body.nombre  = form.nombre
      if (form.ruc)     body.ruc     = form.ruc
      if (form.email)   body.email   = form.email
      if (form.eslogan) body.eslogan = form.eslogan

      await api.patch('/firmas/configuracion', body)
      success('Configuración guardada')
      setConfig(c => c ? { ...c, ...body } : c)
    } catch (e: unknown) {
      error(e instanceof Error ? e.message : 'Error al guardar')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return (
    <div className="flex items-center justify-center py-24">
      <Loader2 size={28} className="animate-spin text-primary" />
    </div>
  )

  const planInfo = PLAN_LABELS[config?.plan ?? 'trial'] ?? PLAN_LABELS.trial

  return (
    <div className="space-y-6 animate-fade-in max-w-3xl">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-2.5 bg-primary/10 rounded-xl">
          <Settings className="text-primary" size={20} />
        </div>
        <div>
          <h1 className="text-xl font-black text-gray-900 dark:text-white leading-none">Configuración</h1>
          <p className="text-[10px] text-gray-500 mt-0.5 uppercase font-bold tracking-wider">Datos de la firma auditora</p>
        </div>
      </div>

      {/* Plan actual */}
      <div className="card p-5 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-secondary/10 rounded-xl">
            <Crown className="text-secondary" size={18} />
          </div>
          <div>
            <p className="text-[10px] text-gray-400 uppercase font-bold tracking-wider mb-0.5">Plan Actual</p>
            <span className={`px-2.5 py-1 rounded-full text-xs font-black uppercase tracking-wider ${planInfo.color}`}>
              {planInfo.label}
            </span>
          </div>
        </div>
        {config?.trial_hasta && (
          <div className="flex items-center gap-1.5 text-xs text-amber-600 dark:text-amber-400 font-bold">
            <Calendar size={13} />
            Vence: {fecha(config.trial_hasta)}
          </div>
        )}
      </div>

      {/* Formulario de datos */}
      <div className="card p-6 space-y-5">
        <div className="flex items-center gap-2 mb-2">
          <Building2 size={16} className="text-primary" />
          <h2 className="text-sm font-black text-gray-900 dark:text-white uppercase tracking-tight">Datos de la Firma</h2>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="sm:col-span-2">
            <label className="input-label">Nombre de la Firma *</label>
            <input
              type="text"
              value={form.nombre}
              onChange={e => setForm(f => ({ ...f, nombre: e.target.value }))}
              className="input-field"
              placeholder="Ej: Estudio Contable González & Asociados"
            />
          </div>

          <div>
            <label className="input-label">RUC de la Firma</label>
            <input
              type="text"
              value={form.ruc}
              onChange={e => setForm(f => ({ ...f, ruc: e.target.value }))}
              className="input-field"
              placeholder="Ej: 80012345-6"
            />
          </div>

          <div>
            <label className="input-label">Email de contacto</label>
            <input
              type="email"
              value={form.email}
              onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
              className="input-field"
              placeholder="contacto@firma.com.py"
            />
          </div>

          <div className="sm:col-span-2">
            <label className="input-label">Eslogan / Descripción corta</label>
            <input
              type="text"
              value={form.eslogan}
              onChange={e => setForm(f => ({ ...f, eslogan: e.target.value }))}
              className="input-field"
              placeholder="Ej: Especialistas en auditoría impositiva paraguaya"
            />
            <p className="text-[10px] text-gray-400 mt-1">Aparece en el encabezado de los informes generados.</p>
          </div>
        </div>

        <div className="flex justify-end pt-2">
          <button
            onClick={handleSave}
            disabled={saving}
            className="btn-primary py-2 px-6 flex items-center gap-2"
          >
            {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
            {saving ? 'Guardando...' : 'Guardar cambios'}
          </button>
        </div>
      </div>

      {/* Info de la cuenta */}
      <div className="card p-6">
        <h2 className="text-sm font-black text-gray-900 dark:text-white uppercase tracking-tight mb-4">Información de la Cuenta</h2>
        <div className="space-y-3">
          {[
            { label: 'ID de Firma', val: config?.id?.slice(0, 8) + '...' },
            { label: 'Cuenta creada', val: config?.creado_en ? fecha(config.creado_en) : '—' },
            { label: 'Usuario actual', val: user?.nombre },
            { label: 'Rol', val: user?.rol },
            { label: 'Estado', val: config?.activa ? 'Activa' : 'Inactiva' },
          ].map(row => (
            <div key={row.label} className="flex justify-between items-center py-2 border-b border-gray-50 dark:border-gray-800 last:border-0">
              <span className="text-xs text-gray-500 font-medium">{row.label}</span>
              <span className="text-xs font-bold text-gray-900 dark:text-white">{row.val}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Nota sobre logo */}
      <div className="rounded-2xl border border-dashed border-gray-200 dark:border-gray-700 p-5 flex items-start gap-3 text-sm text-gray-500 dark:text-gray-400">
        <AlertCircle size={16} className="text-amber-500 shrink-0 mt-0.5" />
        <p>
          Para subir el <strong>logo de la firma</strong> que aparece en los informes,
          usá la sección <strong>Archivos</strong> dentro de cada auditoría
          con el tipo <em>"Logo cliente"</em>. El logo se incluirá automáticamente
          en los informes Word y PDF generados.
        </p>
      </div>
    </div>
  )
}
