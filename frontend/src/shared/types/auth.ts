export interface AuthTokens {
  accessToken: string;
  refreshToken: string;
  tokenType: string;
  expiresIn: number;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface RegisterRequest {
  username: string;
  email: string;
  password: string;
}

export interface UserProfile {
  id: string;
  username: string;
  email: string;
  role: string;
  avatar?: string | null;
  isActive: boolean;
  createdAt?: string;
  lastLoginAt?: string | null;
  documentCount?: number;
  queryCount?: number;
  storageUsed?: number;
}
