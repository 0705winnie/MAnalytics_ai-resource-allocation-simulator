import { Navigate, Route, Routes } from 'react-router-dom'
import App from '../App'
import InstructorCourseCreatePage from '../pages/InstructorCourseCreatePage'
import InstructorCourseDetailPage from '../pages/InstructorCourseDetailPage'
import InstructorCoursesPage from '../pages/InstructorCoursesPage'
import InstructorLayout from '../pages/InstructorLayout'
import InstructorLoginPage from '../pages/InstructorLoginPage'
import InstructorRosterImportPage from '../pages/InstructorRosterImportPage'
import InstructorRosterPage from '../pages/InstructorRosterPage'
import StudentActivationPage from '../pages/StudentActivationPage'
import StudentLoginPage from '../pages/StudentLoginPage'
import { useAuth } from './AuthProvider'
import RoleProtectedRoute, {
  AuthLoadingScreen,
  AuthUnavailableScreen,
  roleHomePath,
} from './ProtectedRoute'
import type { ReactNode } from 'react'

function AuthenticatedHomeRedirect() {
  const { user } = useAuth()
  return <Navigate to={user ? roleHomePath(user.role) : '/login'} replace />
}

function RootRedirect() {
  const { status, user } = useAuth()

  if (status === 'loading') {
    return <AuthLoadingScreen />
  }
  if (status === 'error') {
    return <AuthUnavailableScreen />
  }
  return (
    <Navigate
      to={status === 'authenticated' && user ? roleHomePath(user.role) : '/login'}
      replace
    />
  )
}

function PublicAuthRoute({ children }: { children: ReactNode }) {
  const { status } = useAuth()

  if (status === 'loading') {
    return <AuthLoadingScreen />
  }
  if (status === 'error') {
    return <AuthUnavailableScreen />
  }
  if (status === 'authenticated') {
    return <AuthenticatedHomeRedirect />
  }
  return children
}

function ActivationRoute() {
  const { status } = useAuth()

  if (status === 'loading') {
    return <AuthLoadingScreen />
  }
  if (status === 'error') {
    return <AuthUnavailableScreen />
  }
  if (status === 'authenticated') {
    return <AuthenticatedHomeRedirect />
  }
  return <StudentActivationPage />
}

export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<RootRedirect />} />
      <Route
        path="/login"
        element={(
          <PublicAuthRoute>
            <StudentLoginPage />
          </PublicAuthRoute>
        )}
      />
      <Route
        path="/instructor/login"
        element={(
          <PublicAuthRoute>
            <InstructorLoginPage />
          </PublicAuthRoute>
        )}
      />
      <Route path="/activate" element={<ActivationRoute />} />
      <Route
        path="/app/*"
        element={(
          <RoleProtectedRoute
            requiredRole="student"
            unauthenticatedPath="/login"
          >
            <App />
          </RoleProtectedRoute>
        )}
      />
      <Route
        path="/instructor"
        element={(
          <RoleProtectedRoute
            requiredRole="instructor"
            unauthenticatedPath="/instructor/login"
          >
            <InstructorLayout />
          </RoleProtectedRoute>
        )}
      >
        <Route index element={<Navigate to="courses" replace />} />
        <Route path="courses" element={<InstructorCoursesPage />} />
        <Route path="courses/new" element={<InstructorCourseCreatePage />} />
        <Route path="courses/:courseId" element={<InstructorCourseDetailPage />} />
        <Route
          path="courses/:courseId/roster"
          element={<InstructorRosterPage />}
        />
        <Route
          path="courses/:courseId/roster/import"
          element={<InstructorRosterImportPage />}
        />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
