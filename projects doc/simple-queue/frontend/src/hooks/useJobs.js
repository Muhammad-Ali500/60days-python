import { useState, useEffect, useCallback } from 'react'
import { jobsApi } from '../api/jobs'

const POLL_INTERVAL = 3000  // ms — refresh every 3s

export function useJobs() {
  const [jobs, setJobs]     = useState([])
  const [stats, setStats]   = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]   = useState(null)

  const fetchAll = useCallback(async () => {
    try {
      const [jobsRes, statsRes] = await Promise.all([
        jobsApi.list(),
        jobsApi.stats(),
      ])
      setJobs(jobsRes.data)
      setStats(statsRes.data)
      setError(null)
    } catch (err) {
      setError('Failed to fetch jobs. Is the backend running?')
    } finally {
      setLoading(false)
    }
  }, [])

  // Initial load
  useEffect(() => { fetchAll() }, [fetchAll])

  // Poll while any job is pending/running
  useEffect(() => {
    const hasActive = jobs.some(j => j.status === 'pending' || j.status === 'running')
    if (!hasActive) return

    const timer = setInterval(fetchAll, POLL_INTERVAL)
    return () => clearInterval(timer)
  }, [jobs, fetchAll])

  const submitJob = async (name, job_type) => {
    const res = await jobsApi.create({ name, job_type })
    setJobs(prev => [res.data, ...prev])
    fetchAll()   // refresh stats immediately
    return res.data
  }

  return { jobs, stats, loading, error, submitJob, refresh: fetchAll }
}
