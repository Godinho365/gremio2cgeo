import axios from "axios";

// Central API client. Base URL is proxied to the backend in dev (see vite.config).
export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? "/api",
  headers: { "Content-Type": "application/json" },
});

// Attach JWT if present. TODO(Sprint 1): refresh-token flow + auth store.
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});
