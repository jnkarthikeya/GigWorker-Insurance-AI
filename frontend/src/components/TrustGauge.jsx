/**
 * ShieldPay – TrustGauge Component
 * Animated SVG ring gauge showing trust score
 */
export function TrustGauge({ score = 75 }) {
  const radius = 52
  const circumference = 2 * Math.PI * radius
  const progress = Math.min(1, Math.max(0, score / 100))
  const strokeDash = `${progress * circumference} ${circumference}`
  const color = score >= 70 ? '#10b981' : score >= 45 ? '#f59e0b' : '#ef4444'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '8px 0' }}>
      <svg width="130" height="130" viewBox="0 0 130 130">
        {/* Background ring */}
        <circle cx="65" cy="65" r={radius} fill="none"
          stroke="var(--bg-elevated)" strokeWidth="10" />
        {/* Progress ring */}
        <circle cx="65" cy="65" r={radius} fill="none"
          stroke={color} strokeWidth="10"
          strokeDasharray={strokeDash}
          strokeLinecap="round"
          transform="rotate(-90 65 65)"
          style={{ transition: 'stroke-dasharray 0.8s ease, stroke 0.4s ease' }}
        />
        {/* Glow */}
        <circle cx="65" cy="65" r={radius} fill="none"
          stroke={color} strokeWidth="2" opacity="0.2"
          strokeDasharray={strokeDash}
          transform="rotate(-90 65 65)"
        />
        {/* Score text */}
        <text x="65" y="60" textAnchor="middle"
          style={{ fontFamily: 'Syne, sans-serif', fontSize: '22px', fontWeight: 800, fill: color }}>
          {score.toFixed(1)}
        </text>
        <text x="65" y="78" textAnchor="middle"
          style={{ fontFamily: 'IBM Plex Mono, monospace', fontSize: '9px', fill: '#475569' }}>
          / 100
        </text>
      </svg>
      <div style={{ textAlign: 'center' }}>
        <span className={`badge badge-${score >= 70 ? 'green' : score >= 45 ? 'amber' : 'red'}`}
          style={{ fontSize: '0.7rem' }}>
          {score >= 80 ? 'Excellent' : score >= 70 ? 'Good' :
           score >= 50 ? 'Moderate Risk' : score >= 30 ? 'High Risk' : 'Critical'}
        </span>
      </div>
    </div>
  )
}

export default TrustGauge


/**
 * ShieldPay – Environment Panel
 * Shows live weather, demand, AQI, traffic data
 */
export function EnvPanel({ environment }) {
  if (!environment) return (
    <div className="card">
      <p className="card-title">Live Environment</p>
      <p className="text-xs text-muted">Loading...</p>
    </div>
  )

  const { weather, demand, aqi, traffic, city, composite_env_score } = environment

  const getEnvColor = (impact) => {
    if (impact >= 40) return '#ef4444'
    if (impact >= 20) return '#f59e0b'
    if (impact >= 5) return '#3b82f6'
    return '#10b981'
  }

  return (
    <div className="card">
      <div className="flex-between" style={{ marginBottom: '12px' }}>
        <p className="card-title" style={{ marginBottom: 0 }}>Live Environment</p>
        <div className="flex gap-8 align-center">
          <span className="status-dot green" />
          <span className="text-xs text-muted">{city}</span>
        </div>
      </div>

      {/* Composite score bar */}
      <div style={{ marginBottom: '14px' }}>
        <div className="flex-between" style={{ fontSize: '0.72rem', marginBottom: '4px' }}>
          <span className="text-muted">Env Score</span>
          <span style={{ color: composite_env_score >= 70 ? '#10b981' : '#f59e0b', fontWeight: 700 }}>
            {composite_env_score?.toFixed(1)}/100
          </span>
        </div>
        <div className="progress-bar">
          <div className="progress-fill" style={{
            width: `${composite_env_score || 0}%`,
            background: composite_env_score >= 70 ? 'var(--accent-green)' : 'var(--accent-amber)',
          }} />
        </div>
      </div>

      <div className="env-grid">
        <EnvCard
          label="Rain" icon="🌧"
          value={`${weather?.rain_mm?.toFixed(1)} mm`}
          severity={weather?.severity}
          impact={weather?.income_impact_pct}
          color={getEnvColor(weather?.income_impact_pct || 0)}
        />
        <EnvCard
          label="Demand" icon="📊"
          value={`${demand?.index?.toFixed(0)}%`}
          severity={demand?.category}
          impact={demand?.income_impact_pct}
          color={getEnvColor(demand?.income_impact_pct || 0)}
        />
        <EnvCard
          label="AQI" icon="💨"
          value={aqi?.aqi?.toFixed(0)}
          severity={aqi?.category?.replace('_', ' ')}
          impact={aqi?.income_impact_pct}
          color={getEnvColor(aqi?.income_impact_pct || 0)}
        />
        <EnvCard
          label="Traffic" icon="🚦"
          value={`${(traffic?.congestion_index * 100)?.toFixed(0)}%`}
          severity={traffic?.category?.replace('_', ' ')}
          impact={traffic?.income_impact_pct}
          color={getEnvColor(traffic?.income_impact_pct || 0)}
        />
      </div>

      <div style={{ marginTop: '10px', fontSize: '0.68rem', color: 'var(--text-muted)', textAlign: 'center' }}>
        {new Date().toLocaleTimeString()} · Simulated data
      </div>
    </div>
  )
}

function EnvCard({ label, icon, value, severity, impact, color }) {
  return (
    <div className="env-item">
      <div className="flex-between">
        <div className="env-label">{label}</div>
        <span style={{ fontSize: '1rem' }}>{icon}</span>
      </div>
      <div className="env-value" style={{ color }}>{value}</div>
      <div className="env-severity">{severity}</div>
      {impact > 0 && (
        <div style={{ fontSize: '0.62rem', color: '#ef4444', marginTop: '2px' }}>
          −{impact}% income
        </div>
      )}
    </div>
  )
}


/**
 * ShieldPay – Behavioral Panel
 * Shows all 5 behavioral dimension scores
 */
export function BehavioralPanel({ behavioral }) {
  if (!behavioral) return null

  const { dimensions, behavior_score, risk_level, all_anomaly_signals } = behavioral

  const dimLabels = {
    login_frequency: 'Login Frequency',
    claim_timing: 'Claim Timing',
    session_consistency: 'Session Consistency',
    income_consistency: 'Income Consistency',
    claim_velocity: 'Claim Velocity',
  }

  const getColor = (score) => {
    if (score >= 70) return 'var(--accent-green)'
    if (score >= 45) return 'var(--accent-amber)'
    return 'var(--accent-red)'
  }

  const riskBadge = { low: 'green', moderate: 'amber', high: 'red', critical: 'red' }

  return (
    <div className="card">
      <div className="flex-between" style={{ marginBottom: '16px' }}>
        <p className="card-title" style={{ marginBottom: 0 }}>Behavioral Risk Breakdown</p>
        <div className="flex gap-8 align-center">
          <span className={`badge badge-${riskBadge[risk_level] || 'blue'}`}>
            {risk_level?.toUpperCase()} RISK
          </span>
          <span style={{
            fontFamily: 'Syne, sans-serif', fontWeight: 800, fontSize: '1.2rem',
            color: getColor(behavior_score),
          }}>
            {behavior_score?.toFixed(1)}
          </span>
        </div>
      </div>

      {/* Dimension bars */}
      {dimensions && Object.entries(dimensions).map(([key, dim]) => (
        <div key={key} style={{ marginBottom: '12px' }}>
          <div className="flex-between" style={{ fontSize: '0.76rem', marginBottom: '4px' }}>
            <span style={{ color: 'var(--text-secondary)' }}>{dimLabels[key] || key}</span>
            <div className="flex gap-8 align-center">
              {(dim.anomaly_signals || []).length > 0 && (
                <span className="badge badge-amber" style={{ fontSize: '0.6rem' }}>
                  ⚠ {dim.anomaly_signals.length}
                </span>
              )}
              <span style={{ fontWeight: 700, color: getColor(dim.score) }}>
                {dim.score?.toFixed(0)}/100
              </span>
            </div>
          </div>
          <div className="progress-bar">
            <div className="progress-fill" style={{
              width: `${dim.score || 0}%`,
              background: getColor(dim.score),
              transition: 'width 0.6s ease',
            }} />
          </div>
          {(dim.anomaly_signals || []).length > 0 && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginTop: '4px' }}>
              {dim.anomaly_signals.map(s => (
                <span key={s} style={{ fontSize: '0.62rem', color: 'var(--text-muted)',
                  background: 'var(--bg-elevated)', padding: '1px 6px', borderRadius: '3px' }}>
                  {s.replace(/_/g, ' ')}
                </span>
              ))}
            </div>
          )}
        </div>
      ))}

      {/* All signals summary */}
      {(all_anomaly_signals || []).length > 0 && (
        <div style={{ marginTop: '8px', padding: '10px', background: 'var(--bg-elevated)', borderRadius: '6px' }}>
          <p className="text-xs text-muted" style={{ marginBottom: '6px' }}>ALL ANOMALY SIGNALS</p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
            {all_anomaly_signals.map(s => (
              <span key={s} className="badge badge-amber" style={{ fontSize: '0.62rem' }}>
                {s.replace(/_/g, ' ')}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
