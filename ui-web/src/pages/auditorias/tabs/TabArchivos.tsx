import { useState, useEffect } from 'react'
import { Upload, File, CheckCircle, AlertCircle, Loader2 } from 'lucide-react'
import { api } from '../../../api/client'
import { useToast } from '../../../components/Toaster'
import FileUploadZone from '../../../components/FileUploadZone'
import { fileSize } from '../../../utils/formatters'
import type { ArchivoSubido } from '../../../api/types'

interface TipoConfig {
  id: string
  label: string
  desc: string
  accept: string
  necesitaPeriodo: boolean
  color: string
}

const TIPOS: TipoConfig[] = [
  { id: 'rg90', label: 'RG 90', desc: 'XLSX con detalle de comprobantes IVA descargado de Marangatú', accept: '.xlsx,.xls', necesitaPeriodo: true, color: 'purple' },
  { id: 'hechauka', label: 'HECHAUKA', desc: 'XLSX con información de terceros (retenciones recibidas)', accept: '.xlsx,.xls', necesitaPeriodo: true, color: 'blue' },
  { id: 'estado_cuenta', label: 'Estado de cuenta DNIT', desc: 'PDF descargado de Marangatú con situación fiscal', accept: '.pdf', necesitaPeriodo: false, color: 'orange' },
  { id: 'estados_contables', label: 'Estados contables', desc: 'Balance / cuadro de resultados del ejercicio', accept: '.xlsx,.xls,.csv', necesitaPeriodo: false, color: 'green' },
  { id: 'banco', label: 'Extracto bancario', desc: 'Movimientos bancarios del período', accept: '.xlsx,.xls,.csv,.pdf', necesitaPeriodo: false, color: 'cyan' },
  { id: 'comprobante', label: 'Comprobantes sueltos', desc: 'PDF o XML de comprobantes individuales', accept: '.pdf,.xml,.jpg,.jpeg,.png', necesitaPeriodo: false, color: 'indigo' },
  { id: 'otro', label: 'Otro documento', desc: 'Cualquier evidencia adicional', accept: '.pdf,.xlsx,.xls,.docx,.png,.jpg', necesitaPeriodo: false, color: 'gray' },
]

const MESES = Array.from({length:12},(_,i)=>String(i+1).padStart(2,'0'))
const ANOS = Array.from({length:6},(_,i)=>String(new Date().getFullYear()-i))

interface UploadState { tipo: string; status: 'uploading' | 'done' | 'error'; message: string }

interface Props { auditoriaId: string }

export default function TabArchivos({ auditoriaId }: Props) {
  const { success, error } = useToast()
  const [archivos, setArchivos] = useState<ArchivoSubido[]>([])
  const [uploads, setUploads] = useState<UploadState[]>([])
  const [periodos, setPeriodos] = useState<Record<string, { mes: string; anio: string }>>({})

  const loadArchivos = () => api.get<ArchivoSubido[]>(`/auditorias/${auditoriaId}/archivos`).then(setArchivos)
  useEffect(() => { loadArchivos() }, [auditoriaId])

  const getPeriodo = (tipo: string) => {
    const p = periodos[tipo] ?? { mes: MESES[0], anio: ANOS[0] }
    return `${p.anio}-${p.mes}`
  }

  const handleFile = async (tipo: TipoConfig, file: File) => {
    const state: UploadState = { tipo: tipo.id, status: 'uploading', message: `Subiendo ${file.name}...` }
    setUploads(u => [...u, state])

    const form = new FormData()
    form.append('tipo', tipo.id)
    form.append('archivo', file)
    if (tipo.necesitaPeriodo) form.append('periodo', getPeriodo(tipo.id))

    try {
      const res = await api.upload<{ registros_importados?: number; procesado: boolean }>(`/auditorias/${auditoriaId}/archivos`, form)
      setUploads(u => u.map(x => x.tipo === tipo.id
        ? { ...x, status: 'done', message: res.registros_importados ? `${res.registros_importados} registros importados` : 'Archivo guardado' }
        : x
      ))
      success(`${tipo.label} cargado correctamente`)
      loadArchivos()
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Error al subir'
      setUploads(u => u.map(x => x.tipo === tipo.id ? { ...x, status: 'error', message: msg } : x))
      error(msg)
    }
  }

  const getUpload = (tipo: string) => uploads.filter(u => u.tipo === tipo).at(-1)
  const archivosPorTipo = (tipo: string) => archivos.filter(a => a.tipo === tipo)

  return (
    <div className="space-y-5">
      {/* Archivos existentes */}
      {archivos.length > 0 && (
        <div className="card overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100 dark:border-gray-700">
            <p className="section-label mb-0">Archivos subidos ({archivos.length})</p>
          </div>
          <div className="divide-y divide-gray-100 dark:divide-gray-700/50">
            {archivos.map((a, i) => (
              <div key={i} className="px-5 py-3 flex items-center gap-3">
                <File size={16} className="text-gray-400 shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-bold text-gray-800 dark:text-gray-200 truncate">{a.nombre}</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">{a.tipo.replace('_',' ')} · {fileSize(a.tamaño_kb)}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Upload zones */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {TIPOS.map(tipo => {
          const upload = getUpload(tipo.id)
          const yaSubidos = archivosPorTipo(tipo.id)
          return (
            <div key={tipo.id} className="card p-5 space-y-3">
              <div className="flex items-start justify-between">
                <div>
                  <p className="font-black text-gray-800 dark:text-gray-200 text-sm uppercase tracking-tight">{tipo.label}</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{tipo.desc}</p>
                </div>
                {yaSubidos.length > 0 && (
                  <span className="badge-bajo text-[10px] shrink-0"><CheckCircle size={10} />{yaSubidos.length} archivo{yaSubidos.length > 1 ? 's' : ''}</span>
                )}
              </div>

              {/* Selector de período */}
              {tipo.necesitaPeriodo && (
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="input-label">Mes</label>
                    <select className="input-field text-xs py-1.5"
                      value={periodos[tipo.id]?.mes ?? MESES[0]}
                      onChange={e => setPeriodos(p => ({ ...p, [tipo.id]: { ...p[tipo.id], mes: e.target.value } }))}>
                      {MESES.map(m => <option key={m} value={m}>{new Date(2024,Number(m)-1).toLocaleString('es-PY',{month:'long'})}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="input-label">Año</label>
                    <select className="input-field text-xs py-1.5"
                      value={periodos[tipo.id]?.anio ?? ANOS[0]}
                      onChange={e => setPeriodos(p => ({ ...p, [tipo.id]: { ...p[tipo.id], anio: e.target.value } }))}>
                      {ANOS.map(a => <option key={a}>{a}</option>)}
                    </select>
                  </div>
                </div>
              )}

              {/* Estado del upload */}
              {upload && (
                <div className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium ${
                  upload.status === 'uploading' ? 'bg-blue-50 dark:bg-blue-900/10 text-blue-700 dark:text-blue-400'
                  : upload.status === 'done' ? 'bg-green-50 dark:bg-green-900/10 text-green-700 dark:text-green-400'
                  : 'bg-red-50 dark:bg-red-900/10 text-red-700 dark:text-red-400'
                }`}>
                  {upload.status === 'uploading' ? <Loader2 size={12} className="animate-spin" />
                    : upload.status === 'done' ? <CheckCircle size={12} />
                    : <AlertCircle size={12} />}
                  {upload.message}
                </div>
              )}

              <FileUploadZone
                accept={tipo.accept}
                onFile={file => handleFile(tipo, file)}
                label={`Subir ${tipo.label}`}
                hint={tipo.accept.toUpperCase().replace(/\./g, '').replace(/,/g, ' / ')}
                disabled={upload?.status === 'uploading'}
              />
            </div>
          )
        })}
      </div>
    </div>
  )
}
