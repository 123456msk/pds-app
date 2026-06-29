import axios from 'axios';

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '/api').replace(/\/$/, '');

export const http = axios.create({
  baseURL: API_BASE_URL,
  timeout: 0,
});

export function apiUrl(path) {
  return http.getUri({ url: path.startsWith('/') ? path : `/${path}` });
}
