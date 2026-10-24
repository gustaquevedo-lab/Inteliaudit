import { useState, useRef, useEffect } from 'react'
import { Bot, X, Send, Sparkles, Trash2, ArrowDown, ShieldCheck, CornerDownLeft, Wrench, FileCheck, Layers, ExternalLink } from 'lucide-react'
import { api } from '../api/client'
import { useToast } from './Toaster'

interface ToolCallInfo {
  name: string
  args: any
}

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  tools?: ToolCallInfo[]
  timestamp: string
}

interface ConversacionItem {
  id: string
  titulo: string
}

interface Props {
  auditoriaId: string
  clienteNombre?: string
}

const CHIPS_SUGERENCIAS = [
  '¿Cuáles son las mayores contingencias detectadas?',
  '¿Qué comprobantes tienen riesgo de crédito fiscal?',
  'Explicame las multas aplicables según Ley 125/1991',
  'Consultá en el grafo si hay proveedores con RUC inactivo',
]

export default function CopilotDrawer({ auditoriaId, clienteNombre }: Props) {
  const toast = useToast()
  const [isOpen, setIsOpen] = useState(false)
  const [conversaciones, setConversaciones] = useState<ConversacionItem[]>([])
  const [currentConvId, setCurrentConvId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content: `Hola, soy tu **Agente Auditor Forense** con memoria persistente y RAG legal.\n\nTengo acceso al grafo de operaciones de esta auditoría${clienteNombre ? ` de **${clienteNombre}**` : ''}, sus facturas RG90, y el compendio legal de la **Ley 6380/2019**, **RG 90/2021** y **Ley 125/1991**.\n\n¿Qué indagación o cruce forense querés que realice?`,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [activeTool, setActiveTool] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  const cargarConversaciones = async () => {
    try {
      const data = await api.get<ConversacionItem[]>(`/auditorias/${auditoriaId}/agente/conversaciones`)
      setConversaciones(data)
    } catch {
      // Silencioso si aún no hay
    }
  }

  useEffect(() => {
    if (isOpen) {
      cargarConversaciones()
      scrollToBottom()
      setTimeout(() => inputRef.current?.focus(), 150)
    }
  }, [isOpen, messages, isStreaming, activeTool])

  const handleSend = async (textToSend?: string) => {
    const prompt = (textToSend || input).trim()
    if (!prompt || isStreaming) return

    const userMsg: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: prompt,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }

    const assistantMsgId = `assistant-${Date.now()}`
    const placeholderMsg: Message = {
      id: assistantMsgId,
      role: 'assistant',
      content: '',
      tools: [],
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }

    setMessages(prev => [...prev, userMsg, placeholderMsg])
    setInput('')
    setIsStreaming(true)
    setActiveTool(null)

    const token = localStorage.getItem('ia_token')
    const BASE = import.meta.env.VITE_API_URL || '/api'

    try {
      const response = await fetch(`${BASE}/auditorias/${auditoriaId}/agente/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          pregunta: prompt,
          conversacion_id: currentConvId
        }),
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      if (!response.body) {
        throw new Error('ReadableStream no disponible')
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder('utf-8')
      let accumulated = ''
      let buffer = ''
      const toolsAccumulated: ToolCallInfo[] = []

      while (true) {
        const { value, done } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed.startsWith('data:')) continue
          const dataStr = trimmed.replace(/^data:\s*/, '')

          try {
            const ev = JSON.parse(dataStr)

            if (ev.type === 'init' && ev.conversacion_id) {
              setCurrentConvId(ev.conversacion_id)
            } else if (ev.type === 'tool_call') {
              setActiveTool(ev.name)
              toolsAccumulated.push({ name: ev.name, args: ev.args })
              setMessages(prev =>
                prev.map(m =>
                  m.id === assistantMsgId ? { ...m, tools: [...toolsAccumulated] } : m
                )
              )
            } else if (ev.type === 'tool_result') {
              setActiveTool(null)
            } else if (ev.type === 'content' && ev.delta) {
              accumulated += ev.delta
              setMessages(prev =>
                prev.map(m =>
                  m.id === assistantMsgId ? { ...m, content: accumulated } : m
                )
              )
            } else if (ev.type === 'error') {
              accumulated += `\n\n*(Error: ${ev.detail})*`
              setMessages(prev =>
                prev.map(m =>
                  m.id === assistantMsgId ? { ...m, content: accumulated } : m
                )
              )
            }
          } catch {
            // Chunk parcial
          }
        }
      }
    } catch (err: unknown) {
      setMessages(prev =>
        prev.map(m =>
          m.id === assistantMsgId
            ? {
                ...m,
                content: `⚠️ Error de comunicación con el agente en Ollama: ${
                  err instanceof Error ? err.message : 'Error desconocido'
                }. Verificá que el modelo esté activo en tu dev-server.`,
              }
            : m
        )
      )
    } finally {
      setIsStreaming(false)
      setActiveTool(null)
      cargarConversaciones()
    }
  }

  const handleCrearCedulaDesdeRespuesta = async (content: string) => {
    try {
      await api.post(`/auditorias/${auditoriaId}/generar-cedulas`)
      toast.success('Cédula de auditoría NIA 230 creada y guardada con éxito')
    } catch (err: any) {
      toast.error(err?.message || 'Error al generar cédula')
    }
  }

  const handleClear = () => {
    setCurrentConvId(null)
    setMessages([
      {
        id: 'welcome',
        role: 'assistant',
        content: 'Nueva sesión iniciada. ¿En qué otro tema puedo asistirte?',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      },
    ])
  }

  const formatToolName = (name: string) => {
    switch (name) {
      case 'consultar_normativa_legal':
        return '⚖️ Consultó RAG Legal (Ley 6380 / DNIT)'
      case 'buscar_comprobantes_cliente':
        return '📋 Consultó Comprobantes RG90'
      case 'consultar_relaciones_proveedor':
        return '🕸️ Inspeccionó Grafo de Proveedor'
      case 'recalcular_contingencia_fiscal':
        return '🧮 Recalculó Contingencia Ley 125'
      case 'crear_borrador_cedula_trabajo':
        return '📑 Creó Cédula de Trabajo NIA 230'
      default:
        return `🔧 Herramienta: ${name}`
    }
  }

  return (
    <>
      {/* Botón flotante siempre visible */}
      <button
        onClick={() => setIsOpen(true)}
        className={`fixed bottom-6 right-6 z-40 flex items-center gap-2.5 px-4 py-3 rounded-2xl shadow-xl transition-all duration-300 font-bold text-sm ${
          isOpen
            ? 'opacity-0 pointer-events-none scale-90'
            : 'opacity-100 scale-100 bg-linear-to-r from-blue-600 via-indigo-600 to-emerald-600 text-white hover:shadow-2xl hover:scale-105 active:scale-95'
        }`}
      >
        <div className="relative">
          <Bot size={20} className="animate-pulse" />
          <span className="absolute -top-1 -right-1 w-2 h-2 rounded-full bg-emerald-400 border border-white" />
        </div>
        <span>Agente Forense (14B)</span>
        <Sparkles size={14} className="text-amber-300" />
      </button>

      {/* Drawer lateral */}
      {isOpen && (
        <div className="fixed inset-0 z-50 overflow-hidden pointer-events-none">
          {/* Backdrop tenue */}
          <div
            onClick={() => setIsOpen(false)}
            className="absolute inset-0 bg-black/25 backdrop-blur-xs transition-opacity pointer-events-auto"
          />

          <div className="absolute inset-y-0 right-0 max-w-full flex pl-10 pointer-events-auto">
            <div className="w-screen max-w-md sm:max-w-lg bg-white dark:bg-[#0c1929] shadow-2xl flex flex-col border-l border-gray-200 dark:border-gray-800">
              {/* Header */}
              <div className="px-5 py-4 border-b border-gray-100 dark:border-gray-800 bg-gray-50/70 dark:bg-gray-900/50 flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="w-9 h-9 rounded-xl bg-linear-to-br from-blue-600 to-emerald-500 flex items-center justify-center text-white shadow-sm">
                    <Bot size={20} />
                  </div>
                  <div>
                    <h3 className="text-sm font-black text-gray-900 dark:text-white flex items-center gap-2">
                      Agente Forense
                      <span className="px-1.5 py-0.5 text-[9px] font-black rounded-md bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 border border-emerald-300/30">
                        Qwen 14B RAG
                      </span>
                    </h3>
                    <p className="text-[11px] text-gray-500 dark:text-gray-400 flex items-center gap-1">
                      <ShieldCheck size={12} className="text-emerald-500" />
                      Aislamiento Estricto • Dev-Server
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-1">
                  <button
                    onClick={handleClear}
                    title="Nueva conversación"
                    className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                  >
                    <Trash2 size={16} />
                  </button>
                  <button
                    onClick={() => setIsOpen(false)}
                    className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                  >
                    <X size={18} />
                  </button>
                </div>
              </div>

              {/* Sugerencias Rápidas */}
              <div className="px-4 py-2 bg-blue-50/40 dark:bg-blue-950/20 border-b border-blue-100/50 dark:border-blue-900/30 overflow-x-auto no-scrollbar flex gap-1.5 shrink-0">
                {CHIPS_SUGERENCIAS.map((chip, i) => (
                  <button
                    key={i}
                    onClick={() => handleSend(chip)}
                    disabled={isStreaming}
                    className="whitespace-nowrap px-2.5 py-1 text-[11px] font-medium rounded-full bg-white dark:bg-gray-800 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800/60 hover:bg-blue-100 dark:hover:bg-blue-900/40 transition-colors shrink-0 disabled:opacity-50"
                  >
                    {chip}
                  </button>
                ))}
              </div>

              {/* Mensajes */}
              <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {messages.map(msg => (
                  <div
                    key={msg.id}
                    className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}
                  >
                    {/* Chips de herramientas usadas */}
                    {msg.tools && msg.tools.length > 0 && (
                      <div className="mb-1 flex flex-wrap gap-1 max-w-[88%]">
                        {msg.tools.map((t, idx) => (
                          <span
                            key={idx}
                            className="inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-md bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20"
                          >
                            <Wrench size={10} />
                            {formatToolName(t.name)}
                          </span>
                        ))}
                      </div>
                    )}

                    <div
                      className={`max-w-[88%] rounded-2xl p-3.5 text-xs leading-relaxed whitespace-pre-wrap shadow-xs ${
                        msg.role === 'user'
                          ? 'bg-blue-600 text-white rounded-br-xs'
                          : 'bg-gray-100 dark:bg-gray-800 text-gray-800 dark:text-gray-100 border border-gray-200/60 dark:border-gray-700/60 rounded-bl-xs'
                      }`}
                    >
                      {msg.content ? (
                        <div>
                          <div>{msg.content}</div>
                          {msg.role === 'assistant' && msg.content.length > 80 && (
                            <div className="mt-2.5 pt-2 border-t border-gray-200/50 dark:border-gray-700/50 flex justify-end">
                              <button
                                onClick={() => handleCrearCedulaDesdeRespuesta(msg.content)}
                                className="inline-flex items-center gap-1 px-2 py-1 text-[10px] font-semibold text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 hover:bg-emerald-500/20 rounded transition-colors"
                              >
                                <FileCheck size={12} />
                                Convertir en Cédula NIA 230
                              </button>
                            </div>
                          )}
                        </div>
                      ) : (
                        <div className="flex items-center gap-1.5 py-1 text-gray-400 italic">
                          <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-ping" />
                          <span>
                            {activeTool
                              ? `Ejecutando: ${formatToolName(activeTool)}...`
                              : 'Analizando grafo y leyes paraguayas...'}
                          </span>
                        </div>
                      )}
                    </div>
                    <span className="text-[10px] text-gray-400 mt-1 px-1">{msg.timestamp}</span>
                  </div>
                ))}
                {isStreaming && (
                  <div className="flex items-center gap-1.5 text-[11px] text-gray-400 italic">
                    <span className="inline-block w-1.5 h-3.5 bg-blue-500 animate-pulse" />
                    <span>{activeTool ? `Consultando: ${formatToolName(activeTool)}` : 'Sintetizando dictamen forense...'}</span>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>

              {/* Input bar */}
              <div className="p-3 border-t border-gray-100 dark:border-gray-800 bg-white dark:bg-[#0c1929]">
                <form
                  onSubmit={e => {
                    e.preventDefault()
                    handleSend()
                  }}
                  className="flex items-center gap-2 bg-gray-50 dark:bg-gray-800/70 border border-gray-200 dark:border-gray-700 rounded-xl px-3 py-1.5 focus-within:border-blue-500 transition-colors"
                >
                  <input
                    ref={inputRef}
                    type="text"
                    value={input}
                    onChange={e => setInput(e.target.value)}
                    placeholder="Consultá al auditor forense sobre esta auditoría..."
                    disabled={isStreaming}
                    className="flex-1 bg-transparent text-xs text-gray-800 dark:text-gray-100 placeholder-gray-400 focus:outline-hidden py-1.5"
                  />
                  <button
                    type="submit"
                    disabled={!input.trim() || isStreaming}
                    className="p-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-30 disabled:hover:bg-blue-600 transition-all cursor-pointer disabled:cursor-not-allowed"
                  >
                    <CornerDownLeft size={14} />
                  </button>
                </form>
                <p className="text-[10px] text-gray-400 text-center mt-2">
                  Qwen 14B Local • Tool Calling Activo • Memoria Persistente por Auditoría
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
