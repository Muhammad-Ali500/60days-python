import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
})

export const jobsApi = {
  list:   ()           => api.get('/jobs/'),
  get:    (id)         => api.get(`/jobs/${id}`),
  stats:  ()           => api.get('/jobs/stats'),
  create: (payload)    => api.post('/jobs/', payload),
}
