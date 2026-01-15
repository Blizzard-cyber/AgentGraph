// src/services/externalApi.ts
import axios from 'axios';
import { getToken } from '../utils/auth';

// Use relative base so requests go through the dev server proxy (/api/v1 -> 192.168.1.85:8851)
const EXTERNAL_API_BASE_URL = '/api/v1';

const externalApi = axios.create({
  baseURL: EXTERNAL_API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add Authorization header if token exists
externalApi.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
}, (error) => Promise.reject(error));

export default externalApi;

