import { useState, useEffect } from 'react'
import { BookOpen, Upload, Search, CheckCircle, FileText, ChevronRight, Layers, Sparkles, AlertCircle, RefreshCw } from 'lucide-react'
import { api } from '../../api/client'
import { useToast } from '../../components/Toaster'
import Modal from '../../components/Modal'

interface Normativa {
  id: string
  tipo: string
  numero: string
  titulo: string
  organismo: string
  estado: string
  fecha_vigencia: string | null
  es_global: boolean
  total_chunks: number
  creado_en: string
}

interface Chunk {
  id: string
  jerarquia: string
  articulo: string | null
  texto: string
}

export default function NormativasAdmin() {
  const toast = useToast()
  const [normativas, setNormativas] = useState<Normativa[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [activeTab, setActiveTab] = useState<'catalogo' | 'importar'>('catalogo')

  // Modal para ver chunks
  const [selectedNormativa, setSelectedNormativa] = useState<Normativa | null>(null)
  const [chunks, setChunks] = useState<Chunk[]>([])
  const [loadingChunks, setLoadingChunks] = useState(false)

  // Formulario de importación
  const [tipo, setTipo] = useState('resolucion_general')
  const [numero, setNumero] = useState('')
  const [titulo, setTitulo] = useState('')
  const [organismo, setOrganismo] = useState('DNIT')
  const [esGlobal, setEsGlobal] = useState(true)
  const [textoCompleto, setTextoCompleto] = useState('')
  const [importing, setImporting] = useState(false)

  const cargarNormativas = async () => {
    try {
      setLoading(true)
      const data = await api.get<Normativa[]>('/normativas')
      setNormativas(data)
    } catch (err: any) {
      toast.error(err?.message || 'Error al cargar normativas')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    cargarNormativas()
  }, [])

  const handleVerChunks = async (norm: Normativa) => {
    setSelectedNormativa(norm)
    try {
      setLoadingChunks(true)
      const data = await api.get<Chunk[]>(`/normativas/${norm.id}/chunks`)
      setChunks(data)
    } catch (err: any) {
      toast.error('Error al cargar fragmentos de la normativa')
    } finally {
      setLoadingChunks(false)
    }
  }

  const handleImportar = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!numero.trim() || !titulo.trim() || !textoCompleto.trim()) {
      toast.error('Por favor completá el número, título y contenido de la normativa')
      return
    }

    try {
      setImporting(true)
      const data = await api.post<{ status: string; numero: string; chunks_indexados: number }>('/normativas/texto', {
        tipo,
        numero: numero.trim(),
        titulo: titulo.trim(),
        organismo,
        es_global: esGlobal,
        texto_completo: textoCompleto
      })
      toast.success(`Normativa ${data.numero} indexada con éxito (${data.chunks_indexados} artículos)`)
      setNumero('')
      setTitulo('')
      setTextoCompleto('')
      setActiveTab('catalogo')
      cargarNormativas()
    } catch (err: any) {
      toast.error(err?.message || 'Error al importar normativa')
    } finally {
      setImporting(false)
    }
  }

  const filtered = normativas.filter(n =>
    n.numero.toLowerCase().includes(search.toLowerCase()) ||
    n.titulo.toLowerCase().includes(search.toLowerCase()) ||
    n.tipo.toLowerCase().includes(search.toLowerCase())
  )

  const totalChunks = normativas.reduce((acc, curr) => acc + (curr.total_chunks || 0), 0)

  return (
    <div className="space-y-6">
      {/* Encabezado */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight">Base Legal & Normativas RAG</h1>
            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <Sparkles size={12} />
              Cerebro Ollama 14B
            </span>
          </div>
          <p className="text-sm text-muted mt-1">
            Compendio de leyes tributarias de Paraguay, resoluciones DNIT y NIAs indexadas para el Agente Forense.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setActiveTab('catalogo')}
            className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors ${
              activeTab === 'catalogo'
                ? 'bg-primary text-white shadow'
                : 'bg-card border border-border text-foreground hover:bg-card-hover'
            }`}
          >
            Catálogo ({normativas.length})
          </button>
          <button
            onClick={() => setActiveTab('importar')}
            className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors flex items-center gap-1.5 ${
              activeTab === 'importar'
                ? 'bg-primary text-white shadow'
                : 'bg-card border border-border text-foreground hover:bg-card-hover'
            }`}
          >
            <Upload size={14} />
            Ingestar Normativa
          </button>
        </div>
      </div>

      {/* Tarjetas KPI */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-card border border-border rounded-xl p-4 flex items-center justify-between">
          <div>
            <p className="text-xs text-muted font-medium">Normativas Indexadas</p>
            <p className="text-2xl font-bold mt-1">{normativas.length}</p>
          </div>
          <div className="w-10 h-10 rounded-lg bg-blue-500/10 text-blue-400 flex items-center justify-center">
            <BookOpen size={20} />
          </div>
        </div>

        <div className="bg-card border border-border rounded-xl p-4 flex items-center justify-between">
          <div>
            <p className="text-xs text-muted font-medium">Artículos y Chunks RAG</p>
            <p className="text-2xl font-bold mt-1 text-emerald-400">{totalChunks}</p>
          </div>
          <div className="w-10 h-10 rounded-lg bg-emerald-500/10 text-emerald-400 flex items-center justify-center">
            <Layers size={20} />
          </div>
        </div>

        <div className="bg-card border border-border rounded-xl p-4 flex items-center justify-between">
          <div>
            <p className="text-xs text-muted font-medium">Motor de Vectores</p>
            <p className="text-sm font-semibold mt-1">nomic-embed-text</p>
            <p className="text-[11px] text-muted">768 dimensiones • Local en Dev-Server</p>
          </div>
          <div className="w-10 h-10 rounded-lg bg-purple-500/10 text-purple-400 flex items-center justify-center">
            <Sparkles size={20} />
          </div>
        </div>
      </div>

      {/* Contenido por Pestaña */}
      {activeTab === 'catalogo' ? (
        <div className="bg-card border border-border rounded-xl overflow-hidden shadow-sm">
          <div className="p-4 border-b border-border flex flex-col sm:flex-row items-center justify-between gap-3">
            <div className="relative w-full sm:w-80">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" size={16} />
              <input
                type="text"
                placeholder="Buscar por número o palabra clave..."
                value={search}
                onChange={e => setSearch(e.target.value)}
                className="w-full pl-9 pr-3 py-1.5 text-xs rounded-lg border border-border bg-body-light dark:bg-body-dark focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>
            <button
              onClick={cargarNormativas}
              className="p-1.5 rounded-lg border border-border text-muted hover:text-foreground transition-colors"
              title="Recargar catálogo"
            >
              <RefreshCw size={15} />
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead className="bg-body-light dark:bg-body-dark/50 text-muted uppercase tracking-wider text-[10px]">
                <tr>
                  <th className="px-4 py-3">Tipo / Número</th>
                  <th className="px-4 py-3">Título de la Norma</th>
                  <th className="px-4 py-3">Organismo</th>
                  <th className="px-4 py-3 text-center">Artículos Indexados</th>
                  <th className="px-4 py-3">Ámbito</th>
                  <th className="px-4 py-3 text-right">Acción</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {loading ? (
                  <tr>
                    <td colSpan={6} className="text-center py-8 text-muted">
                      Cargando catálogo de normativas...
                    </td>
                  </tr>
                ) : filtered.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="text-center py-8 text-muted">
                      No se encontraron normativas que coincidan con la búsqueda.
                    </td>
                  </tr>
                ) : (
                  filtered.map(norm => (
                    <tr key={norm.id} className="hover:bg-card-hover/40 transition-colors">
                      <td className="px-4 py-3 font-semibold text-primary whitespace-nowrap">
                        <span className="uppercase text-[10px] px-1.5 py-0.5 rounded bg-primary/10 text-primary mr-1.5">
                          {norm.tipo.replace('_', ' ')}
                        </span>
                        {norm.numero}
                      </td>
                      <td className="px-4 py-3 font-medium max-w-md truncate" title={norm.titulo}>
                        {norm.titulo}
                      </td>
                      <td className="px-4 py-3 text-muted">{norm.organismo}</td>
                      <td className="px-4 py-3 text-center">
                        <span className="inline-flex items-center gap-1 font-mono font-semibold px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400">
                          <Layers size={11} />
                          {norm.total_chunks}
                        </span>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        {norm.es_global ? (
                          <span className="px-2 py-0.5 text-[10px] font-medium rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20">
                            Global
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 text-[10px] font-medium rounded-full bg-purple-500/10 text-purple-400 border border-purple-500/20">
                            Firma Privada
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => handleVerChunks(norm)}
                          className="px-2.5 py-1 text-xs font-medium rounded border border-border hover:bg-body-light dark:hover:bg-body-dark transition-colors inline-flex items-center gap-1"
                        >
                          Ver Artículos
                          <ChevronRight size={13} />
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        /* Formulario de Ingesta */
        <div className="bg-card border border-border rounded-xl p-6 shadow-sm max-w-4xl">
          <div className="flex items-start gap-3 mb-6 p-4 rounded-xl bg-primary/5 border border-primary/15">
            <Sparkles className="text-primary mt-0.5 shrink-0" size={18} />
            <div className="text-xs space-y-1">
              <p className="font-semibold text-foreground">Ingesta Semántica Inteligente</p>
              <p className="text-muted leading-relaxed">
                El sistema detectará automáticamente los artículos, incisos y capítulos preservando la jerarquía para citaciones legales exactas en las auditorías.
              </p>
            </div>
          </div>

          <form onSubmit={handleImportar} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-semibold text-muted uppercase tracking-wider mb-1">
                  Tipo de Norma
                </label>
                <select
                  value={tipo}
                  onChange={e => setTipo(e.target.value)}
                  className="w-full px-3 py-2 text-xs rounded-lg border border-border bg-body-light dark:bg-body-dark focus:outline-none focus:ring-1 focus:ring-primary"
                >
                  <option value="ley">Ley de la Nación</option>
                  <option value="decreto">Decreto del Poder Ejecutivo</option>
                  <option value="resolucion_general">Resolución General DNIT</option>
                  <option value="nia">Norma Internacional de Auditoría (NIA)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-muted uppercase tracking-wider mb-1">
                  Número / Identificador
                </label>
                <input
                  type="text"
                  placeholder="Ej: 90/2021 o 6380/2019"
                  value={numero}
                  onChange={e => setNumero(e.target.value)}
                  className="w-full px-3 py-2 text-xs rounded-lg border border-border bg-body-light dark:bg-body-dark focus:outline-none focus:ring-1 focus:ring-primary"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-muted uppercase tracking-wider mb-1">
                  Organismo Emisor
                </label>
                <input
                  type="text"
                  placeholder="Ej: DNIT / SET / Congreso"
                  value={organismo}
                  onChange={e => setOrganismo(e.target.value)}
                  className="w-full px-3 py-2 text-xs rounded-lg border border-border bg-body-light dark:bg-body-dark focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-muted uppercase tracking-wider mb-1">
                Título o Epígrafe Completo
              </label>
              <input
                type="text"
                placeholder="Ej: Por la cual se implementa el Registro Electrónico de Comprobantes..."
                value={titulo}
                onChange={e => setTitulo(e.target.value)}
                className="w-full px-3 py-2 text-xs rounded-lg border border-border bg-body-light dark:bg-body-dark focus:outline-none focus:ring-1 focus:ring-primary"
                required
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-muted uppercase tracking-wider mb-1">
                Contenido del Texto Legal
              </label>
              <textarea
                rows={12}
                placeholder="Pegá aquí el texto de la ley o resolución (debe contener 'Artículo 1°.-', 'Artículo 2°.-', etc.)..."
                value={textoCompleto}
                onChange={e => setTextoCompleto(e.target.value)}
                className="w-full p-3 font-mono text-xs rounded-lg border border-border bg-body-light dark:bg-body-dark focus:outline-none focus:ring-1 focus:ring-primary leading-relaxed"
                required
              />
            </div>

            <div className="flex items-center justify-between pt-2">
              <label className="flex items-center gap-2 cursor-pointer text-xs text-muted">
                <input
                  type="checkbox"
                  checked={esGlobal}
                  onChange={e => setEsGlobal(e.target.checked)}
                  className="rounded text-primary focus:ring-primary"
                />
                Compartir como normativa global del sistema
              </label>

              <button
                type="submit"
                disabled={importing}
                className="px-5 py-2 text-xs font-semibold text-white bg-primary rounded-lg shadow hover:bg-primary-hover disabled:opacity-50 transition-colors flex items-center gap-2"
              >
                {importing ? (
                  <>
                    <RefreshCw className="animate-spin" size={14} />
                    Segmentando y Vectorizando...
                  </>
                ) : (
                  <>
                    <Upload size={14} />
                    Indexar en Cerebro RAG
                  </>
                )}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Modal de Artículos / Chunks */}
      <Modal
        open={Boolean(selectedNormativa)}
        onClose={() => setSelectedNormativa(null)}
        title={`Fragmentos Indexados: ${selectedNormativa?.numero ?? ''}`}
      >
        <div className="space-y-4 max-h-[70vh] overflow-y-auto pr-2">
          {loadingChunks ? (
            <div className="text-center py-8 text-xs text-muted">
              Cargando fragmentos vectorizados...
            </div>
          ) : chunks.length === 0 ? (
            <div className="text-center py-8 text-xs text-muted">
              Esta normativa no tiene fragmentos procesados aún.
            </div>
          ) : (
            chunks.map(ch => (
              <div key={ch.id} className="p-3.5 rounded-lg border border-border bg-body-light/50 dark:bg-body-dark/50 space-y-1.5">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold text-xs text-primary">{ch.articulo || 'Disposición General'}</span>
                  <span className="text-[10px] text-muted font-mono">{ch.jerarquia}</span>
                </div>
                <p className="text-xs text-foreground/90 whitespace-pre-wrap leading-relaxed">
                  {ch.texto}
                </p>
              </div>
            ))
          )}
        </div>
      </Modal>
    </div>
  )
}
