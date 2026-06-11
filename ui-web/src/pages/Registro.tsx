import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Building2, User, Mail, Lock, Eye, EyeOff, CheckCircle, ChevronRight, ChevronLeft, ArrowRight } from 'lucide-react'
import { api } from '../api/client'

function validarRUC(ruc: string): boolean {
  const limpio = ruc.replace(/\s/g, '')
  const match = limpio.match(/^(\d{1,8})-(\d)$/)
  if (!match) return false
  const base = match[1]
  const dv = parseInt(match[2])
  let suma = 0
  for (let i = 0; i < base.length; i++) {
    suma += parseInt(base[i]) * (base.length + 1 - i)
  }
  const resto = suma % 11
  const calc = resto === 0 ? 0 : 11 - resto
  return calc === dv
}

export default function Registro() {
  const navigate = useNavigate()
  const [paso, setPaso] = useState(1)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)
  const [bienvenida, setBienvenida] = useState(false)

  const [form, setForm] = useState({
    nombre: '',
    ruc: '',
    email: '',
    admin_nombre: '',
    admin_email: '',
    admin_password: '',
    admin_password_confirm: '',
  })

  const update = (field: string, value: string) => setForm(f => ({ ...f, [field]: value }))

  const validoPaso1 = form.nombre.trim().length > 0
  const rucValido = form.ruc === '' || validarRUC(form.ruc)
  const validoPaso2 = form.admin_nombre.trim().length > 0 &&
    form.admin_email.includes('@') &&
    form.admin_password.length >= 8 &&
    form.admin_password === form.admin_password_confirm

  const handleSubmit = async () => {
    if (!validoPaso1 || !validoPaso2) return
    setLoading(true)
    setError('')
    try {
      const res = await api.post<{ access_token: string; firma_id: string; admin_id: string }>('/auth/firmas', {
        nombre: form.nombre,
        ruc: form.ruc || null,
        email: form.email || null,
        admin_email: form.admin_email,
        admin_nombre: form.admin_nombre,
        admin_password: form.admin_password,
      })
      localStorage.setItem('ia_token', res.access_token)
      setBienvenida(true)
      setTimeout(() => navigate('/dashboard'), 2000)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Error al crear la cuenta')
    }
    setLoading(false)
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4" style={{ background: '#091624' }}>
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center font-bold text-white"
              style={{ background: 'linear-gradient(135deg, #2E84F0, #1558B0)' }}>
              iA
            </div>
            <span className="text-2xl font-bold">
              <span style={{ color: '#2E84F0' }}>Inteli</span>
              <span style={{ color: '#22C47E', fontWeight: 300 }}>audit</span>
            </span>
          </div>
          <p className="text-sm mt-2" style={{ color: '#A8B4C8' }}>Auditoria impositiva inteligente para Paraguay</p>
        </div>

        <AnimatePresence mode="wait">
          {bienvenida ? (
            <motion.div
              key="bienvenida"
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              className="text-center p-8 rounded-2xl" style={{ background: '#0c1a2e', border: '1px solid #1a3352' }}
            >
              <div className="w-16 h-16 rounded-full bg-green-500/20 flex items-center justify-center mx-auto mb-4">
                <CheckCircle size={32} style={{ color: '#22C47E' }} />
              </div>
              <h2 className="text-xl font-bold text-white mb-2">Cuenta creada con exito</h2>
              <p className="text-sm mb-6" style={{ color: '#A8B4C8' }}>Bienvenido a Inteliaudit. Te estamos redirigiendo...</p>

              <div className="space-y-3 text-left">
                {[
                  { num: '1', text: 'Crea un cliente desde el panel' },
                  { num: '2', text: 'Subi archivos RG90 y HECHAUKA' },
                  { num: '3', text: 'Ejecuta el analisis automatico' },
                ].map((s, i) => (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.3 + i * 0.2 }}
                    className="flex items-center gap-3 p-3 rounded-xl" style={{ background: '#091624', border: '1px solid #1a3352' }}
                  >
                    <div className="w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold"
                      style={{ background: 'rgba(46,132,240,0.15)', color: '#2E84F0' }}>{s.num}</div>
                    <span className="text-sm" style={{ color: '#E2E8F0' }}>{s.text}</span>
                    <ArrowRight size={14} style={{ color: '#22C47E', marginLeft: 'auto' }} />
                  </motion.div>
                ))}
              </div>
            </motion.div>
          ) : paso === 1 ? (
            <motion.div
              key="paso1"
              initial={{ opacity: 0, x: -30 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 30 }}
              className="p-8 rounded-2xl space-y-5" style={{ background: '#0c1a2e', border: '1px solid #1a3352' }}
            >
              <div className="flex items-center gap-2 mb-1">
                <Building2 size={18} style={{ color: '#2E84F0' }} />
                <h2 className="text-lg font-bold text-white">Datos de la firma</h2>
              </div>
              <p className="text-xs" style={{ color: '#A8B4C8' }}>Paso 1 de 2</p>

              <div className="space-y-4">
                <div>
                  <label className="text-xs font-semibold mb-1 block" style={{ color: '#A8B4C8' }}>Nombre de la firma *</label>
                  <input
                    className="w-full px-4 py-3 rounded-xl text-sm outline-none transition-all"
                    style={{ background: '#091624', border: '1px solid #1a3352', color: '#E2E8F0' }}
                    placeholder="Ej: Auditores Asociados SRL"
                    value={form.nombre}
                    onChange={e => update('nombre', e.target.value)}
                    onFocus={e => e.target.style.borderColor = '#2E84F0'}
                    onBlur={e => e.target.style.borderColor = '#1a3352'}
                  />
                </div>

                <div>
                  <label className="text-xs font-semibold mb-1 block" style={{ color: '#A8B4C8' }}>RUC de la firma (opcional)</label>
                  <input
                    className="w-full px-4 py-3 rounded-xl text-sm outline-none transition-all"
                    style={{ background: '#091624', border: `1px solid ${form.ruc && !rucValido ? '#E53E3E' : '#1a3352'}`, color: '#E2E8F0' }}
                    placeholder="80012345-6"
                    value={form.ruc}
                    onChange={e => update('ruc', e.target.value)}
                  />
                  {form.ruc && !rucValido && <p className="text-xs mt-1" style={{ color: '#E53E3E' }}>RUC invalido. Formato: XXXXXXXX-D</p>}
                </div>

                <div>
                  <label className="text-xs font-semibold mb-1 block" style={{ color: '#A8B4C8' }}>Email de contacto</label>
                  <input
                    type="email"
                    className="w-full px-4 py-3 rounded-xl text-sm outline-none transition-all"
                    style={{ background: '#091624', border: '1px solid #1a3352', color: '#E2E8F0' }}
                    placeholder="contacto@firma.com"
                    value={form.email}
                    onChange={e => update('email', e.target.value)}
                  />
                </div>
              </div>

              <button
                onClick={() => setPaso(2)}
                disabled={!validoPaso1}
                className="w-full py-3 rounded-xl text-sm font-bold flex items-center justify-center gap-2 transition-all disabled:opacity-50"
                style={{ background: validoPaso1 ? 'linear-gradient(135deg, #2E84F0, #1558B0)' : '#1a3352', color: '#fff' }}
              >
                Siguiente <ChevronRight size={16} />
              </button>

              <p className="text-center text-xs" style={{ color: '#6B7A90' }}>
                Ya tenes cuenta?{' '}
                <a href="/login" style={{ color: '#2E84F0' }}>Inicia sesion</a>
              </p>
            </motion.div>
          ) : (
            <motion.div
              key="paso2"
              initial={{ opacity: 0, x: 30 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -30 }}
              className="p-8 rounded-2xl space-y-5" style={{ background: '#0c1a2e', border: '1px solid #1a3352' }}
            >
              <div className="flex items-center gap-2 mb-1">
                <User size={18} style={{ color: '#2E84F0' }} />
                <h2 className="text-lg font-bold text-white">Cuenta del administrador</h2>
              </div>
              <p className="text-xs" style={{ color: '#A8B4C8' }}>Paso 2 de 2</p>

              {error && (
                <div className="p-3 rounded-xl text-xs font-bold" style={{ background: 'rgba(229,62,62,0.1)', border: '1px solid rgba(229,62,62,0.3)', color: '#E53E3E' }}>
                  {error}
                </div>
              )}

              <div className="space-y-4">
                <div>
                  <label className="text-xs font-semibold mb-1 block" style={{ color: '#A8B4C8' }}>Nombre completo *</label>
                  <input
                    className="w-full px-4 py-3 rounded-xl text-sm outline-none transition-all"
                    style={{ background: '#091624', border: '1px solid #1a3352', color: '#E2E8F0' }}
                    placeholder="Juan Perez"
                    value={form.admin_nombre}
                    onChange={e => update('admin_nombre', e.target.value)}
                  />
                </div>

                <div>
                  <label className="text-xs font-semibold mb-1 block" style={{ color: '#A8B4C8' }}>Email (sera tu usuario) *</label>
                  <div className="relative">
                    <Mail size={16} className="absolute left-4 top-1/2 -translate-y-1/2" style={{ color: '#6B7A90' }} />
                    <input
                      type="email"
                      className="w-full pl-11 pr-4 py-3 rounded-xl text-sm outline-none transition-all"
                      style={{ background: '#091624', border: '1px solid #1a3352', color: '#E2E8F0' }}
                      placeholder="admin@firma.com"
                      value={form.admin_email}
                      onChange={e => update('admin_email', e.target.value)}
                    />
                  </div>
                </div>

                <div>
                  <label className="text-xs font-semibold mb-1 block" style={{ color: '#A8B4C8' }}>Password * (min. 8 caracteres)</label>
                  <div className="relative">
                    <Lock size={16} className="absolute left-4 top-1/2 -translate-y-1/2" style={{ color: '#6B7A90' }} />
                    <input
                      type={showPassword ? 'text' : 'password'}
                      className="w-full pl-11 pr-11 py-3 rounded-xl text-sm outline-none transition-all"
                      style={{ background: '#091624', border: '1px solid #1a3352', color: '#E2E8F0' }}
                      placeholder="••••••••"
                      value={form.admin_password}
                      onChange={e => update('admin_password', e.target.value)}
                    />
                    <button className="absolute right-4 top-1/2 -translate-y-1/2" onClick={() => setShowPassword(!showPassword)}>
                      {showPassword ? <EyeOff size={16} style={{ color: '#6B7A90' }} /> : <Eye size={16} style={{ color: '#6B7A90' }} />}
                    </button>
                  </div>
                </div>

                <div>
                  <label className="text-xs font-semibold mb-1 block" style={{ color: '#A8B4C8' }}>Confirmar password *</label>
                  <div className="relative">
                    <Lock size={16} className="absolute left-4 top-1/2 -translate-y-1/2" style={{ color: '#6B7A90' }} />
                    <input
                      type={showConfirm ? 'text' : 'password'}
                      className="w-full pl-11 pr-11 py-3 rounded-xl text-sm outline-none transition-all"
                      style={{
                        background: '#091624',
                        border: `1px solid ${form.admin_password_confirm && form.admin_password !== form.admin_password_confirm ? '#E53E3E' : '#1a3352'}`,
                        color: '#E2E8F0',
                      }}
                      placeholder="••••••••"
                      value={form.admin_password_confirm}
                      onChange={e => update('admin_password_confirm', e.target.value)}
                    />
                    <button className="absolute right-4 top-1/2 -translate-y-1/2" onClick={() => setShowConfirm(!showConfirm)}>
                      {showConfirm ? <EyeOff size={16} style={{ color: '#6B7A90' }} /> : <Eye size={16} style={{ color: '#6B7A90' }} />}
                    </button>
                  </div>
                  {form.admin_password_confirm && form.admin_password !== form.admin_password_confirm && (
                    <p className="text-xs mt-1" style={{ color: '#E53E3E' }}>Las passwords no coinciden</p>
                  )}
                </div>
              </div>

              <div className="flex gap-3">
                <button
                  onClick={() => setPaso(1)}
                  className="py-3 px-4 rounded-xl text-sm font-bold flex items-center gap-2"
                  style={{ background: '#091624', border: '1px solid #1a3352', color: '#A8B4C8' }}
                >
                  <ChevronLeft size={16} /> Atras
                </button>
                <button
                  onClick={handleSubmit}
                  disabled={!validoPaso2 || loading}
                  className="flex-1 py-3 rounded-xl text-sm font-bold flex items-center justify-center gap-2 transition-all disabled:opacity-50"
                  style={{ background: 'linear-gradient(135deg, #2E84F0, #1558B0)', color: '#fff' }}
                >
                  {loading ? 'Creando cuenta...' : 'Crear cuenta — 7 dias gratis'}
                </button>
              </div>

              <p className="text-center text-xs" style={{ color: '#6B7A90' }}>
                Al registrarte aceptas nuestros{' '}
                <a href="/politica-de-privacidad" target="_blank" style={{ color: '#22C47E' }}>Terminos</a> y{' '}
                <a href="/privacidad" target="_blank" style={{ color: '#22C47E' }}>Politica de Privacidad</a>
              </p>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}
