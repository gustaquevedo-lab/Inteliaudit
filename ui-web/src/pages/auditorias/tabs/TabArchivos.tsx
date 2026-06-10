import { useState, useEffect, useRef } from 'react'
import { Upload, File, CheckCircle, AlertCircle, Loader2, Eye, X, Database } from 'lucide-react'
import { api } from '../../../api/client'
import { pyg } from '../../../utils/formatters'

interface PreviewRow {
  [key: string]: string | number | null
}

interface ImportResult {
  ok: boolean
  preview?: PreviewRow[]
  total_registros?: number
  total_monto?: number
  total_iva?: number
  periodo?: string
  tipo?: string
  archivo?: string
  campos_extraidos?: Record<string, unknown>
  declaracion_id?: string
  registros_importados?: number
  confirmada?: boolean
  requiere_confirmacion?: boolean
}

interface ImportState {
  id: string
  tipo: string
  nombre: string
  status: 'parsing' | 'preview' | 'confirming' | 'done' | 'error'
  periodo: string
  preview?: PreviewRow[]
  total_registros?: number
  total_monto?: number
  total_iva?: number
  campos_extraidos?: Record<string, unknown>
  registros_importados?: number
  confirmada?: boolean
  error_msg?: string
}

interface ImportHistoryItem {
  accion: string
  modulo: string
  timestamp: string
  detalle?: string
  resultado: string
}

const MESES = [
  'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
  'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
]
const CURRENT_YEAR = new Date().getFullYear()

interface Props { auditoriaId: string }

const INIT_PERIODO = () => {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth()).padStart(2, '0')}`
}

function getPeriodoLabel(periodo: string): string {
  const [y, m] = periodo.split('-')
  return `${MESES[parseInt(m) - 1]} ${y}`
}

export default function TabArchivos({ auditoriaId }: Props) {
  const [imports, setImports] = useState<ImportState[]>([])
  const [history, setHistory] = useState<ImportHistoryItem[]>([])
  const [rg90Periodo, setRg90Periodo] = useState(INIT_PERIODO)
  const [rg90Tipo, setRg90Tipo] = useState<'compras' | 'ventas'>('compras')
  const [hechaukaPeriodo, setHechaukaPeriodo] = useState(INIT_PERIODO)
  const [djPeriodo, setDjPeriodo] = useState(INIT_PERIODO)
  const [djFormulario, setDjFormulario] = useState('120')
  const [loadingHistory, setLoadingHistory] = useState(false)

  useEffect(() => {
    loadHistory()
  }, [auditoriaId])

  const loadHistory = async () => {
    setLoadingHistory(true)
    try {
      const data = await api.get<ImportHistoryItem[]>(`/audit-trail?auditoria_id=${auditoriaId}&modulo=importacion&limit=20`)
      setHistory(data ?? [])
    } catch { /* ignore */ }
    setLoadingHistory(false)
  }

  const addImport = (id: string, tipo: string, nombre: string, periodo: string) => {
    const state: ImportState = { id, tipo, nombre, status: 'parsing', periodo }
    setImports(prev => [...prev, state])
    return state
  }

  const updateImport = (id: string, update: Partial<ImportState>) => {
    setImports(prev => prev.map(s => s.id === id ? { ...s, ...update } : s))
  }

  const handleRg90 = async (file: File) => {
    const id = `rg90-${Date.now()}`
    addImport(id, 'RG90', file.name, rg90Periodo)
    const form = new FormData()
    form.append('tipo', rg90Tipo)
    form.append('periodo', rg90Periodo)
    form.append('archivo', file)

    try {
      const res = await api.upload<ImportResult>(`/auditorias/${auditoriaId}/importar/rg90`, form)
      if (res.preview && res.total_registros) {
        updateImport(id, { status: 'preview', preview: res.preview, total_registros: res.total_registros, total_monto: res.total_monto, total_iva: res.total_iva, nombre: res.archivo ?? file.name })
      } else {
        updateImport(id, { status: 'done', registros_importados: res.registros_importados, total_registros: res.total_registros })
      }
    } catch (e: unknown) {
      updateImport(id, { status: 'error', error_msg: e instanceof Error ? e.message : 'Error al importar' })
    }
  }

  const confirmRg90 = async (st: ImportState) => {
    updateImport(st.id, { status: 'confirming' })
    const form = new FormData()
    form.append('tipo', rg90Tipo)
    form.append('periodo', rg90Periodo)
    form.append('archivo_nombre', st.nombre)
    try {
      const res = await api.upload<ImportResult>(`/auditorias/${auditoriaId}/importar/rg90/confirmar`, form)
      updateImport(st.id, { status: 'done', registros_importados: res.registros_importados })
      loadHistory()
    } catch (e: unknown) {
      updateImport(st.id, { status: 'error', error_msg: e instanceof Error ? e.message : 'Error al confirmar' })
    }
  }

  const handleHechauka = async (file: File) => {
    const id = `hechauka-${Date.now()}`
    addImport(id, 'HECHAUKA', file.name, hechaukaPeriodo)
    const form = new FormData()
    form.append('periodo', hechaukaPeriodo)
    form.append('archivo', file)

    try {
      const res = await api.upload<ImportResult>(`/auditorias/${auditoriaId}/importar/hechauka`, form)
      if (res.preview && res.total_registros) {
        updateImport(id, { status: 'preview', preview: res.preview, total_registros: res.total_registros, total_monto: res.total_monto, total_iva: res.total_iva, nombre: res.archivo ?? file.name })
      } else {
        updateImport(id, { status: 'done', registros_importados: res.registros_importados })
      }
    } catch (e: unknown) {
      updateImport(id, { status: 'error', error_msg: e instanceof Error ? e.message : 'Error al importar' })
    }
  }

  const confirmHechauka = async (st: ImportState) => {
    updateImport(st.id, { status: 'confirming' })
    const form = new FormData()
    form.append('periodo', hechaukaPeriodo)
    form.append('archivo_nombre', st.nombre)
    try {
      const res = await api.upload<ImportResult>(`/auditorias/${auditoriaId}/importar/hechauka/confirmar`, form)
      updateImport(st.id, { status: 'done', registros_importados: res.registros_importados })
      loadHistory()
    } catch (e: unknown) {
      updateImport(st.id, { status: 'error', error_msg: e instanceof Error ? e.message : 'Error al confirmar' })
    }
  }

  const handleDj = async (file: File) => {
    const id = `dj-${Date.now()}`
    addImport(id, 'DJ', file.name, djPeriodo)
    const form = new FormData()
    form.append('formulario', djFormulario)
    form.append('periodo', djPeriodo)
    form.append('archivo', file)

    try {
      const res = await api.upload<ImportResult>(`/auditorias/${auditoriaId}/importar/dj`, form)
      updateImport(id, { status: 'done', registros_importados: 1, campos_extraidos: res.campos_extraidos, confirmada: res.confirmada })
      loadHistory()
    } catch (e: unknown) {
      updateImport(id, { status: 'error', error_msg: e instanceof Error ? e.message : 'Error al importar' })
    }
  }

  const discardImport = (id: string) => {
    setImports(prev => prev.filter(s => s.id !== id))
  }

  const ImportsEnProgreso = imports.filter(s => s.status === 'parsing' || s.status === 'confirming')
  const ImportsPreview = imports.filter(s => s.status === 'preview')
  const ImportsDone = imports.filter(s => s.status === 'done')

  return (
    <div className="space-y-5">
      {/* Import progress bar */}
      {ImportsEnProgreso.length > 0 && (
        <div className="card p-4 space-y-3">
          <div className="flex items-center gap-3">
            <Loader2 size={18} className="animate-spin text-primary" />
            <span className="font-bold text-sm">Procesando {ImportsEnProgreso.length} archivo(s)...</span>
          </div>
          <div className="w-full h-2 bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden">
            <div className="h-full bg-primary rounded-full animate-pulse" style={{ width: '60%' }} />
          </div>
          {ImportsEnProgreso.map(s => (
            <p key={s.id} className="text-xs text-gray-500">{s.nombre} - {s.status === 'confirming' ? 'Guardando en base de datos...' : 'Parseando archivo...'}</p>
          ))}
        </div>
      )}

      {/* Preview section - waiting for confirmation */}
      {ImportsPreview.length > 0 && (
        <div className="card overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100 dark:border-gray-700 flex items-center justify-between">
            <p className="section-label mb-0 flex items-center gap-2">
              <Eye size={16} /> Vista previa de importacion
            </p>
          </div>
          {ImportsPreview.map(s => (
            <div key={s.id} className="p-5 space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-bold text-sm">{s.tipo} - {getPeriodoLabel(s.periodo)}</p>
                  <p className="text-xs text-gray-500">{s.nombre}</p>
                </div>
                <div className="text-right">
                  <p className="font-bold text-primary text-lg">{s.total_registros?.toLocaleString()}</p>
                  <p className="text-xs text-gray-500">registros</p>
                </div>
              </div>
              {s.total_monto !== undefined && (
                <div className="grid grid-cols-2 gap-4 px-4 py-3 bg-gray-50 dark:bg-gray-800/50 rounded-xl">
                  <div>
                    <p className="text-xs text-gray-500">Total comprobantes</p>
                    <p className="font-bold text-sm">Gs. {pyg(s.total_monto)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">Total IVA</p>
                    <p className="font-bold text-sm">Gs. {pyg(s.total_iva ?? 0)}</p>
                  </div>
                </div>
              )}
              {s.preview && s.preview.length > 0 && (
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-gray-100 dark:border-gray-700">
                        {Object.keys(s.preview[0]).slice(0, 6).map(col => (
                          <th key={col} className="text-left py-2 px-2 font-semibold text-gray-500 uppercase tracking-wide">{col.replace(/_/g, ' ')}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {s.preview.slice(0, 10).map((row, i) => (
                        <tr key={i} className="border-b border-gray-50 dark:border-gray-800">
                          {Object.values(row).slice(0, 6).map((val, j) => (
                            <td key={j} className="py-2 px-2 text-gray-700 dark:text-gray-300 truncate max-w-[120px]">{String(val ?? '')}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <p className="text-xs text-gray-400 mt-2">Mostrando las primeras {Math.min(10, s.preview.length)} filas</p>
                </div>
              )}
              <div className="flex items-center gap-3 pt-2">
                <button className="btn-primary text-sm flex items-center gap-2" onClick={() => confirmRg90(s)} disabled={s.status === 'confirming'}>
                  {s.status === 'confirming' ? <Loader2 size={14} className="animate-spin" /> : <Database size={14} />}
                  Confirmar importacion
                </button>
                <button className="btn-ghost text-sm flex items-center gap-2 text-gray-500" onClick={() => discardImport(s.id)}>
                  <X size={14} /> Descartar
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Upload zones grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* RG90 */}
        <div className="card p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-bold text-sm uppercase tracking-wide">RG90</p>
              <p className="text-xs text-gray-500">Detalle de comprobantes IVA</p>
            </div>
            <div className="flex items-center gap-2">
              <button className={`px-3 py-1 text-xs rounded-lg font-bold transition-colors ${rg90Tipo === 'compras' ? 'bg-primary text-white' : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400'}`} onClick={() => setRg90Tipo('compras')}>Compras</button>
              <button className={`px-3 py-1 text-xs rounded-lg font-bold transition-colors ${rg90Tipo === 'ventas' ? 'bg-primary text-white' : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400'}`} onClick={() => setRg90Tipo('ventas')}>Ventas</button>
            </div>
          </div>
          <div>
            <label className="input-label">Periodo</label>
            <input type="month" className="input-field" value={rg90Periodo} onChange={e => setRg90Periodo(e.target.value)} />
          </div>
          <Rg90UploadZone
            key={`rg90-${rg90Tipo}-${rg90Periodo}`}
            onFile={handleRg90}
            disabled={ImportsEnProgreso.some(s => s.tipo === 'RG90')}
          />
          {ImportsDone.filter(s => s.tipo === 'RG90').slice(-3).map(s => (
            <div key={s.id} className="flex items-center gap-2 px-3 py-2 rounded-lg bg-green-50 dark:bg-green-900/10 text-green-700 dark:text-green-400 text-xs font-medium">
              <CheckCircle size={12} />
              {s.registros_importados ? `${s.registros_importados} registros importados` : `${s.total_registros} registros`}
            </div>
          ))}
        </div>

        {/* HECHAUKA */}
        <div className="card p-5 space-y-4">
          <div>
            <p className="font-bold text-sm uppercase tracking-wide">HECHAUKA</p>
            <p className="text-xs text-gray-500">Informacion de terceros (retenciones)</p>
          </div>
          <div>
            <label className="input-label">Periodo</label>
            <input type="month" className="input-field" value={hechaukaPeriodo} onChange={e => setHechaukaPeriodo(e.target.value)} />
          </div>
          <HechaukaUploadZone
            key={`hechauka-${hechaukaPeriodo}`}
            onFile={handleHechauka}
            disabled={ImportsEnProgreso.some(s => s.tipo === 'HECHAUKA')}
          />
          {ImportsDone.filter(s => s.tipo === 'HECHAUKA').slice(-3).map(s => (
            <div key={s.id} className="flex items-center gap-2 px-3 py-2 rounded-lg bg-green-50 dark:bg-green-900/10 text-green-700 dark:text-green-400 text-xs font-medium">
              <CheckCircle size={12} />
              {s.registros_importados ? `${s.registros_importados} registros importados` : `${s.total_registros} registros`}
            </div>
          ))}
        </div>
      </div>

      {/* DJ - full width */}
      <div className="card p-5 space-y-4">
        <div>
          <p className="font-bold text-sm uppercase tracking-wide">Declaracion Jurada</p>
          <p className="text-xs text-gray-500">PDF descargado de Marangatu</p>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="input-label">Periodo</label>
            <input type="month" className="input-field" value={djPeriodo} onChange={e => setDjPeriodo(e.target.value)} />
          </div>
          <div>
            <label className="input-label">Formulario</label>
            <select className="input-field" value={djFormulario} onChange={e => setDjFormulario(e.target.value)}>
              <option value="120">120 - IVA</option>
              <option value="500">500 - IRE</option>
              <option value="800">800 - Retenciones IVA</option>
              <option value="810">810 - Retenciones IVA (simplif.)</option>
              <option value="820">820 - Retenciones IRE</option>
              <option value="830">830 - Ret. IVA + IRE (peq. cont.)</option>
            </select>
          </div>
        </div>
        <DjUploadZone
          key={`dj-${djPeriodo}-${djFormulario}`}
          onFile={handleDj}
          disabled={ImportsEnProgreso.some(s => s.tipo === 'DJ')}
        />
        {ImportsDone.filter(s => s.tipo === 'DJ').slice(-3).map(s => (
          <div key={s.id} className="space-y-2">
            <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-green-50 dark:bg-green-900/10 text-green-700 dark:text-green-400 text-xs font-medium">
              <CheckCircle size={12} />
              DJ importada - Form. {s.campos_extraidos ? Object.keys(s.campos_extraidos).join(', ') : 'OK'}
            </div>
          </div>
        ))}
      </div>

      {/* Import history */}
      {history.length > 0 && (
        <div className="card overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100 dark:border-gray-700 flex items-center justify-between">
            <p className="section-label mb-0">Historial de importaciones</p>
            {loadingHistory && <Loader2 size={14} className="animate-spin text-gray-400" />}
          </div>
          <div className="divide-y divide-gray-100 dark:divide-gray-700/50">
            {history.map((h, i) => (
              <div key={i} className="px-5 py-3 flex items-center gap-3">
                <div className="w-2 h-2 rounded-full bg-green-500 shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-bold text-gray-700 dark:text-gray-300">{h.accion}</p>
                  <p className="text-[11px] text-gray-400">{new Date(h.timestamp).toLocaleString('es-PY')}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Error states */}
      {imports.filter(s => s.status === 'error').map(s => (
        <div key={s.id} className="flex items-center gap-2 px-4 py-3 rounded-xl bg-red-50 dark:bg-red-900/10 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400 text-sm">
          <AlertCircle size={16} className="shrink-0" />
          <div>
            <p className="font-bold">{s.tipo} - {s.nombre}</p>
            <p className="text-xs">{s.error_msg}</p>
          </div>
          <button className="ml-auto text-xs font-bold text-red-500 hover:text-red-700" onClick={() => discardImport(s.id)}>
            <X size={14} />
          </button>
        </div>
      ))}
    </div>
  )
}

/* Upload zone sub-components */

function Rg90UploadZone({ onFile, disabled }: { onFile: (f: File) => void; disabled: boolean }) {
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const handle = (file: File | undefined) => {
    if (file && !disabled && file.name.endsWith('.xlsx')) {
      onFile(file)
    }
  }

  return (
    <div
      className={`border-2 border-dashed rounded-2xl p-6 flex flex-col items-center gap-2 transition-all cursor-pointer ${
        dragging ? 'border-primary bg-primary/5' : 'border-gray-200 dark:border-gray-700 hover:border-primary/40 hover:bg-gray-50 dark:hover:bg-gray-800/40'
      } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
      onClick={() => !disabled && inputRef.current?.click()}
      onDragOver={e => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={e => { e.preventDefault(); setDragging(false); handle(e.dataTransfer.files[0]) }}
    >
      <div className={`p-3 rounded-xl ${dragging ? 'bg-primary/10' : 'bg-gray-100 dark:bg-gray-800'}`}>
        <Upload size={20} className={dragging ? 'text-primary' : 'text-gray-400'} />
      </div>
      <p className="text-xs font-bold text-gray-600 dark:text-gray-400">Arrastra el XLSX o hace clic</p>
      <p className="text-[10px] text-gray-400">XLSX de Marangatu (RG 90/2021)</p>
      <input ref={inputRef} type="file" accept=".xlsx,.xls" className="hidden" onChange={e => handle(e.target.files?.[0])} disabled={disabled} />
    </div>
  )
}

function HechaukaUploadZone({ onFile, disabled }: { onFile: (f: File) => void; disabled: boolean }) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)

  const handle = (file: File | undefined) => {
    if (file && !disabled && file.name.endsWith('.xlsx')) {
      onFile(file)
    }
  }

  return (
    <div
      className={`border-2 border-dashed rounded-2xl p-6 flex flex-col items-center gap-2 transition-all cursor-pointer ${
        dragging ? 'border-primary bg-primary/5' : 'border-gray-200 dark:border-gray-700 hover:border-primary/40 hover:bg-gray-50 dark:hover:bg-gray-800/40'
      } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
      onClick={() => !disabled && inputRef.current?.click()}
      onDragOver={e => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={e => { e.preventDefault(); setDragging(false); handle(e.dataTransfer.files[0]) }}
    >
      <div className={`p-3 rounded-xl ${dragging ? 'bg-primary/10' : 'bg-gray-100 dark:bg-gray-800'}`}>
        <Upload size={20} className={dragging ? 'text-primary' : 'text-gray-400'} />
      </div>
      <p className="text-xs font-bold text-gray-600 dark:text-gray-400">Arrastra el XLSX o hace clic</p>
      <p className="text-[10px] text-gray-400">XLSX de HECHAUKA (informacion recibida)</p>
      <input ref={inputRef} type="file" accept=".xlsx,.xls" className="hidden" onChange={e => handle(e.target.files?.[0])} disabled={disabled} />
    </div>
  )
}

function DjUploadZone({ onFile, disabled }: { onFile: (f: File) => void; disabled: boolean }) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)

  const handle = (file: File | undefined) => {
    if (file && !disabled && file.name.endsWith('.pdf')) {
      onFile(file)
    }
  }

  return (
    <div
      className={`border-2 border-dashed rounded-2xl p-6 flex flex-col items-center gap-2 transition-all cursor-pointer ${
        dragging ? 'border-primary bg-primary/5' : 'border-gray-200 dark:border-gray-700 hover:border-primary/40 hover:bg-gray-50 dark:hover:bg-gray-800/40'
      } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
      onClick={() => !disabled && inputRef.current?.click()}
      onDragOver={e => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={e => { e.preventDefault(); setDragging(false); handle(e.dataTransfer.files[0]) }}
    >
      <div className={`p-3 rounded-xl ${dragging ? 'bg-primary/10' : 'bg-gray-100 dark:bg-gray-800'}`}>
        <File size={20} className={dragging ? 'text-primary' : 'text-gray-400'} />
      </div>
      <p className="text-xs font-bold text-gray-600 dark:text-gray-400">Arrastra el PDF o hace clic</p>
      <p className="text-[10px] text-gray-400">PDF de declaracion jurada (descargado de Marangatu)</p>
      <input ref={inputRef} type="file" accept=".pdf" className="hidden" onChange={e => handle(e.target.files?.[0])} disabled={disabled} />
    </div>
  )
}
