import axios from 'axios'

const envBaseUrl = import.meta.env.VITE_API_BASE?.trim()
const defaultBaseUrl = '/api'

export const apiClient = axios.create({
  baseURL: envBaseUrl || defaultBaseUrl,
})
