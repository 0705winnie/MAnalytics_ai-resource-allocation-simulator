export type AuthRole = 'student' | 'instructor'

export interface AuthenticatedUser {
  id: string
  username: string
  role: AuthRole
}

export interface AuthenticatedCourse {
  id: string
  course_code: string
}

export interface AuthenticationResponse {
  authenticated: true
  user: AuthenticatedUser
  course?: AuthenticatedCourse | null
  nickname?: string | null
}

export interface StudentLoginRequest {
  course_code: string
  berkeley_username: string
  password: string
}

export interface StudentAuthenticationResponse extends AuthenticationResponse {
  user: AuthenticatedUser & { role: 'student' }
  course: AuthenticatedCourse
  nickname: string
}

export type AuthStatus = 'loading' | 'authenticated' | 'unauthenticated' | 'error'
