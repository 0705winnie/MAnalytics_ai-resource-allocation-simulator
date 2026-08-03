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

export interface InstructorLoginRequest {
  username: string
  password: string
}

export type ActivationPasswordMode = 'create' | 'confirm'

export interface ActivationVerifyRequest {
  course_code: string
  berkeley_username: string
  activation_code: string
}

export interface ActivationVerificationResponse {
  verified: true
  expires_in_seconds: number
  password_mode: ActivationPasswordMode
}

export interface ActivationCompleteRequest {
  password: string
  password_confirmation: string
  nickname: string
}

export interface StudentAuthenticationResponse extends AuthenticationResponse {
  user: AuthenticatedUser & { role: 'student' }
  course: AuthenticatedCourse
  nickname: string
}

export interface InstructorAuthenticationResponse extends AuthenticationResponse {
  user: AuthenticatedUser & { role: 'instructor' }
  course?: null
  nickname?: null
}

export type AuthStatus = 'loading' | 'authenticated' | 'unauthenticated' | 'error'
