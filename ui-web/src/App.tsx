import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ThemeProvider } from './context/ThemeContext'
import { AuthProvider, useAuth } from './context/AuthContext'
import { ToasterProvider } from './components/Toaster'
import Layout from './components/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import EvidenceExplorer from './pages/EvidenceExplorer'
import ClientesList from './pages/clientes/ClientesList'
import ClienteDetail from './pages/clientes/ClienteDetail'
import NuevaAuditoria from './pages/auditorias/NuevaAuditoria'
import AuditoriaDetail from './pages/auditorias/AuditoriaDetail'
import Usuarios from './pages/admin/Usuarios'
import InformesList from './pages/informes/InformesList'
import Configuracion from './pages/admin/Configuracion'
import AuditTrail from './pages/admin/AuditTrail'
import PortalCliente from './pages/PortalCliente'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-body-light dark:bg-body-dark">
        <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }
  if (!user) return <Navigate to="/login" replace />
  return <>{children}</>
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="clientes" element={<ClientesList />} />
        <Route path="clientes/:ruc" element={<ClienteDetail />} />
        <Route path="auditorias/nueva" element={<NuevaAuditoria />} />
        <Route path="auditorias/:id/*" element={<AuditoriaDetail />} />
        <Route path="auditorias/:id/evidencia" element={<EvidenceExplorer />} />
        <Route path="admin/usuarios" element={<Usuarios />} />
        <Route path="informes" element={<InformesList />} />
        <Route path="admin/configuracion" element={<Configuracion />} />
        <Route path="admin/trail" element={<AuditTrail />} />
      </Route>
      {/* Portal público — sin auth */}
      <Route path="/portal/:token" element={<PortalCliente />} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <ToasterProvider>
          <BrowserRouter basename="/app">
            <AppRoutes />
          </BrowserRouter>
        </ToasterProvider>
      </AuthProvider>
    </ThemeProvider>
  )
}
