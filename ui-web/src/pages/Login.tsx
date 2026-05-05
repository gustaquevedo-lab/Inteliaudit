import { useState, FormEvent } from 'react'
import { Navigate } from 'react-router-dom'
import { Eye, EyeOff, Lock, Mail, AlertCircle } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import Logo from '../components/Logo'

export default function Login() {
  const { user, login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPwd, setShowPwd] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  if (user) return <Navigate to="/dashboard" replace />

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(email, password)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Credenciales incorrectas')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex">
      {/* Left panel — brand */}
      <div className="hidden lg:flex w-1/2 sidebar-gradient flex-col items-center justify-center p-12 relative overflow-hidden">
        {/* Decorative circles */}
        <div className="absolute top-[-80px] right-[-80px] w-80 h-80 rounded-full bg-white/5" />
        <div className="absolute bottom-[-60px] left-[-60px] w-60 h-60 rounded-full bg-white/5" />
        <div className="absolute top-1/3 right-8 w-40 h-40 rounded-full bg-secondary/10" />

        <div className="relative z-10 flex flex-col items-center text-center max-w-md">
          <Logo size="lg" showSlogan dark />
          <div className="mt-12 space-y-6">
            {[
              { n: '5', label: 'Cruces de auditoría\nautomatizados por período' },
              { n: '100%', label: 'Compliance con Ley 6380/2019\ny Resoluciones DNIT vigentes' },
              { n: '∞', label: 'Clientes y auditorías\nsin límite por firma' },
            ].map((stat, i) => (
              <div key={i} className="flex items-center gap-4 text-left glass rounded-2xl px-5 py-4">
                <span className="text-3xl font-black text-secondary-light">{stat.n}</span>
                <p className="text-sm text-blue-100/70 font-medium whitespace-pre-line">{stat.label}</p>
              </div>
            ))}
          </div>
          <p className="mt-12 text-xs text-blue-200/40 font-medium uppercase tracking-widest">
            Auditoría impositiva inteligente para Paraguay
          </p>
        </div>
      </div>

      {/* Right panel — form */}
      <div className="flex-1 flex items-center justify-center p-6 bg-body-light dark:bg-body-dark">
        <div className="w-full max-w-md">
          {/* Mobile logo */}
          <div className="lg:hidden flex justify-center mb-8">
            <Logo size="lg" showSlogan />
          </div>

          <div className="card p-8 shadow-xl">
            <div className="mb-8">
              <h1 className="text-2xl font-black text-gray-900 dark:text-white uppercase tracking-tight">
                Iniciar sesión
              </h1>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                Ingresá con tu cuenta de auditor
              </p>
            </div>

            {error && (
              <div className="mb-5 flex items-center gap-3 p-3.5 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800/30 rounded-xl">
                <AlertCircle size={16} className="text-red-500 shrink-0" />
                <p className="text-sm text-red-700 dark:text-red-400 font-medium">{error}</p>
              </div>
            )}

            <form onSubmit={submit} className="space-y-5">
              <div>
                <label className="input-label label-required">Email</label>
                <div className="relative">
                  <Mail size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400" />
                  <input
                    type="email"
                    className="input-field pl-10"
                    placeholder="auditor@firma.com.py"
                    value={email}
                    onChange={e => setEmail(e.target.value)}
                    required
                    autoFocus
                  />
                </div>
              </div>

              <div>
                <label className="input-label label-required">Contraseña</label>
                <div className="relative">
                  <Lock size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400" />
                  <input
                    type={showPwd ? 'text' : 'password'}
                    className="input-field pl-10 pr-10"
                    placeholder="••••••••"
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowPwd(v => !v)}
                    className="absolute right-3.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                  >
                    {showPwd ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>

              <button type="submit" className="btn-primary w-full py-3 mt-2" disabled={loading}>
                {loading
                  ? <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  : 'Ingresar al sistema'
                }
              </button>
            </form>

            <p className="text-center text-xs text-gray-400 dark:text-gray-500 mt-6">
              Portal Marangatú (DNIT): Declaraciones juradas presentadas, RG 90, HECHAUKA, estado de cuenta.
            </p>
          </div>

          <p className="text-center text-[10px] text-gray-400 dark:text-gray-600 mt-6 uppercase tracking-widest">
            © {new Date().getFullYear()} Inteliaudit · Intelihouse
          </p>
        </div>
      </div>
    </div>
  )
}
