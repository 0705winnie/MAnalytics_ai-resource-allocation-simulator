import { Navigate, Route, Routes } from 'react-router-dom'
import App from '../App'
import StudentLoginPage from '../pages/StudentLoginPage'
import { useAuth } from './AuthProvider'
import ProtectedRoute, {
  AuthLoadingScreen,
  AuthUnavailableScreen,
} from './ProtectedRoute'

function RootRedirect() {
  const { status } = useAuth()

  if (status === 'loading') {
    return <AuthLoadingScreen />
  }
  if (status === 'error') {
    return <AuthUnavailableScreen />
  }
  return <Navigate to={status === 'authenticated' ? '/app' : '/login'} replace />
}

function LoginRoute() {
  const { status } = useAuth()

  if (status === 'loading') {
    return <AuthLoadingScreen />
  }
  if (status === 'authenticated') {
    return <Navigate to="/app" replace />
  }
  return <StudentLoginPage />
}

export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<RootRedirect />} />
      <Route path="/login" element={<LoginRoute />} />
      <Route
        path="/app/*"
        element={(
          <ProtectedRoute>
            <App />
          </ProtectedRoute>
        )}
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
