import { useState } from 'react'
import { useJobs } from './hooks/useJobs'
import './styles.css'

const JOB_TYPES = ['report', 'email', 'export', 'sync']

const STATUS_CONFIG = {
  pending: { color: '#f59e0b', label: 'Pending',  icon: '⏳' },
  running: { color: '#3b82f6', label: 'Running',  icon: '⚙️' },
  success: { color: '#10b981', label: 'Success',  icon: '✅' },
  failed:  { color: '#ef4444', label: 'Failed',   icon: '❌' },
}

export default function App() {
  const { jobs, stats, loading, error, submitJob } = useJobs()
  const [form, setForm] = useState({ name: '', job_type: 'report' })
  const [submitting, setSubmitting] = useState(false)
  const [toast, setToast] = useState(null)
  const [selected, setSelected] = useState(null)

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 3000)
  }

  const handleSubmit = async () => {
    if (!form.name.trim()) return showToast('Enter a job name', 'error')
    setSubmitting(true)
    try {
      await submitJob(form.name.trim(), form.job_type)
      setForm(f => ({ ...f, name: '' }))
      showToast(`Job "${form.name}" queued!`)
    } catch {
      showToast('Failed to submit job', 'error')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="app">
      {/* ── Header ── */}
      <header className="header">
        <div className="header-inner">
          <div className="logo">
            <span className="logo-icon">⚡</span>
            <span className="logo-text">JobFlow</span>
            <span className="logo-tag">Dashboard</span>
          </div>
          <div className="header-meta">Background job processing · Celery + Redis</div>
        </div>
      </header>

      <main className="main">
        {/* ── Stats Bar ── */}
        {stats && (
          <section className="stats-bar">
            {[
              { key: 'total',   label: 'Total',   val: stats.total   },
              { key: 'pending', label: 'Pending',  val: stats.pending },
              { key: 'running', label: 'Running',  val: stats.running },
              { key: 'success', label: 'Success',  val: stats.success },
              { key: 'failed',  label: 'Failed',   val: stats.failed  },
            ].map(s => (
              <div key={s.key} className={`stat-card stat-${s.key}`}>
                <div className="stat-val">{s.val}</div>
                <div className="stat-label">{s.label}</div>
              </div>
            ))}
          </section>
        )}

        {/* ── Submit Form ── */}
        <section className="submit-panel">
          <h2 className="panel-title">Submit New Job</h2>
          <div className="form-row">
            <input
              className="input"
              placeholder="Job name  e.g.  Monthly Sales Report"
              value={form.name}
              onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
              onKeyDown={e => e.key === 'Enter' && handleSubmit()}
            />
            <select
              className="select"
              value={form.job_type}
              onChange={e => setForm(f => ({ ...f, job_type: e.target.value }))}
            >
              {JOB_TYPES.map(t => (
                <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>
              ))}
            </select>
            <button className="btn-submit" onClick={handleSubmit} disabled={submitting}>
              {submitting ? 'Queuing…' : '+ Queue Job'}
            </button>
          </div>
        </section>

        {/* ── Job List ── */}
        <section className="jobs-panel">
          <h2 className="panel-title">Jobs <span className="count">{jobs.length}</span></h2>

          {loading && <div className="empty-state">Loading…</div>}
          {error   && <div className="empty-state error">{error}</div>}

          {!loading && jobs.length === 0 && (
            <div className="empty-state">No jobs yet. Submit one above ↑</div>
          )}

          <div className="job-list">
            {jobs.map(job => (
              <div
                key={job.id}
                className={`job-card ${selected === job.id ? 'expanded' : ''}`}
                onClick={() => setSelected(selected === job.id ? null : job.id)}
              >
                <div className="job-main">
                  <div className="job-left">
                    <span className="job-icon">{STATUS_CONFIG[job.status]?.icon}</span>
                    <div>
                      <div className="job-name">{job.name}</div>
                      <div className="job-meta">
                        <span className="tag">{job.job_type}</span>
                        <span className="job-time">{formatAge(job.created_at)}</span>
                      </div>
                    </div>
                  </div>
                  <div className="job-right">
                    <span
                      className="status-badge"
                      style={{ '--status-color': STATUS_CONFIG[job.status]?.color }}
                    >
                      {STATUS_CONFIG[job.status]?.label}
                    </span>
                  </div>
                </div>

                {/* Progress bar for running jobs */}
                {job.status === 'running' && (
                  <div className="progress-track">
                    <div className="progress-fill" style={{ width: `${job.progress}%` }} />
                    <span className="progress-label">{job.progress.toFixed(0)}%</span>
                  </div>
                )}

                {/* Expanded detail view */}
                {selected === job.id && (
                  <div className="job-detail">
                    <div className="detail-grid">
                      <div className="detail-row">
                        <span className="detail-key">Job ID</span>
                        <span className="detail-val mono">{job.id}</span>
                      </div>
                      <div className="detail-row">
                        <span className="detail-key">Celery Task</span>
                        <span className="detail-val mono">{job.celery_task_id || '—'}</span>
                      </div>
                      {job.result && Object.entries(job.result).map(([k, v]) => (
                        <div className="detail-row" key={k}>
                          <span className="detail-key">{k}</span>
                          <span className="detail-val">{String(v)}</span>
                        </div>
                      ))}
                      {job.error && (
                        <div className="detail-row error-row">
                          <span className="detail-key">Error</span>
                          <span className="detail-val error-text">{job.error}</span>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      </main>

      {/* ── Architecture Info ── */}
      <footer className="arch-footer">
        <div className="arch-inner">
          <div className="arch-title">How this app works</div>
          <div className="arch-flow">
            <div className="arch-node frontend">React Frontend</div>
            <div className="arch-arrow">→ POST /api/jobs →</div>
            <div className="arch-node backend">FastAPI Backend</div>
            <div className="arch-arrow">→ .delay() →</div>
            <div className="arch-node redis">Redis Broker</div>
            <div className="arch-arrow">→ picks up →</div>
            <div className="arch-node celery">Celery Worker</div>
            <div className="arch-arrow">→ writes result →</div>
            <div className="arch-node db">PostgreSQL</div>
          </div>
          <div className="arch-note">Stats are cached in Redis · Flower UI at :5555</div>
        </div>
      </footer>

      {/* ── Toast ── */}
      {toast && (
        <div className={`toast toast-${toast.type}`}>{toast.msg}</div>
      )}
    </div>
  )
}

function formatAge(iso) {
  const diff = Date.now() - new Date(iso).getTime()
  const s = Math.floor(diff / 1000)
  if (s < 60) return `${s}s ago`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m ago`
  return `${Math.floor(m / 60)}h ago`
}
