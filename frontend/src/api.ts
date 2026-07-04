export interface User {
  id: number
  email: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
}

export interface Cycle {
  id: number
  user_id: number
  start_date: string // YYYY-MM-DD
  end_date: string | null // YYYY-MM-DD
  cycle_length: number | null
  created_at: string
  updated_at: string
}

export interface CycleCreate {
  start_date: string
  end_date?: string | null
}

export interface CycleUpdate {
  start_date?: string
  end_date?: string | null
}

export interface PredictionResponse {
  predicted_next_period_start: string | null
  average_cycle_length: number
  current_cycle_day: number | null
  confidence: 'low' | 'medium' | 'high'
  basis: 'default' | 'limited_data' | 'personal_average'
  predicted_range: { earliest: string | null; latest: string | null } | null
  predicted_ovulation_date?: string | null
  fertile_window_start?: string | null
  fertile_window_end?: string | null
}



const TOKEN_KEY = 'auth_token'

export const authService = {
  getToken(): string | null {
    return localStorage.getItem(TOKEN_KEY)
  },

  setToken(token: string): void {
    localStorage.setItem(TOKEN_KEY, token)
  },

  clearToken(): void {
    localStorage.removeItem(TOKEN_KEY)
  },

  isAuthenticated(): boolean {
    return !!this.getToken()
  },

  async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const token = this.getToken()
    const headers = new Headers(options.headers || {})

    if (token) {
      headers.set('Authorization', `Bearer ${token}`)
    }

    const response = await fetch(endpoint, {
      ...options,
      headers,
    })

    if (!response.ok) {
      let errorMsg = 'An error occurred'
      try {
        const errorData = await response.json()
        errorMsg = errorData.detail || errorMsg
      } catch {
        // Fallback if parsing json fails
      }
      throw new Error(errorMsg)
    }

    return response.json() as Promise<T>
  },

  async register(email: string, password: string): Promise<TokenResponse> {
    const data = await this.request<TokenResponse>('/auth/register', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ email, password }),
    })
    this.setToken(data.access_token)
    return data
  },

  async login(email: string, password: string): Promise<TokenResponse> {
    const data = await this.request<TokenResponse>('/auth/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ email, password }),
    })
    this.setToken(data.access_token)
    return data
  },

  async getMe(): Promise<User> {
    return this.request<User>('/auth/me')
  },

  async getCycles(): Promise<Cycle[]> {
    return this.request<Cycle[]>('/cycles')
  },

  async createCycle(cycle: CycleCreate): Promise<Cycle> {
    return this.request<Cycle>('/cycles', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(cycle),
    })
  },

  async updateCycle(id: number, cycle: CycleUpdate): Promise<Cycle> {
    return this.request<Cycle>(`/cycles/${id}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(cycle),
    })
  },

  async getPredictions(today?: string): Promise<PredictionResponse> {
    const url = today ? `/predictions?today=${today}` : '/predictions'
    return this.request<PredictionResponse>(url)
  },

}
