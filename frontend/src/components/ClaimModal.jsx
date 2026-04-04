/**
 * ShieldPay – Claim Result Modal
 * Shows full claim breakdown including:
 *   - Status + payout
 *   - Fraud analysis with signals
 *   - Behavioral breakdown
 *   - Income prediction
 *   - Trust update (before → after)
 *   - Full XAI explainability sections
 */

export default function ClaimModal({ result, onClose }) {
  if (!result) return null

  const {
    status, payout_breakdown, fraud_analysis, behavioral_analysis,
    income_prediction, trust_update, explainability, environment,
    error_reason,
  } = result

  const isApproved = status === 'approved'
  const isBlocked = status === 'blocked'
  const isExcluded = status === 'excluded'

  const statusColors = {
    approved: { bg: 'rgba(16,185,129,0.12)', border: 'rgba(16,185,129,0.3)', text: '#10b981' },
    blocked:  { bg: 'rgba(239,68,68,0.12)',  border: 'rgba(239,68,68,0.3)',  text: '#ef4444' },
    excluded: { bg: 'rgba(245,158,11,0.12)', border: 'rgba(245,158,11,0.3)', text: '#f59e0b' },
  }
  const sc = statusColors[status] || statusColors.excluded

  return (
    <div className="modal-backdrop" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal">
        {/* Header */}
        <div className="modal-header">
          <div>
            <h3 style={{ fontSize: '1.1rem' }}>
              Claim #{result.claim_id > 0 ? result.claim_id : 'N/A'}
            </h3>
            <p className="text-xs text-muted" style={{ marginTop: '2px' }}>
              {result.timestamp ? new Date(result.timestamp).toLocaleString() : '—'}
            </p>
          </div>
          <div className="flex gap-8 align-center">
            <div style={{
              background: sc.bg, border: `1px solid ${sc.border}`,
              borderRadius: '6px', padding: '5px 14px',
              color: sc.text, fontSize: '0.8rem', fontWeight: 700,
              textTransform: 'uppercase', letterSpacing: '1px',
            }}>
              {status === 'approved' ? '✓' : status === 'blocked' ? '✗' : '⚠'} {status}
            </div>
            <button className="modal-close" onClick={onClose}>✕</button>
          </div>
        </div>

        <div className="modal-body flex-col gap-20">

          {/* Excluded / Error reason */}
          {(isExcluded || error_reason) && (
            <AlertBox color="amber" icon="⚠">
              {error_reason || 'Claim could not be processed'}
            </AlertBox>
          )}

          {/* ── PAYOUT BREAKDOWN ── */}
          {payout_breakdown && (
            <Section title="Payout Breakdown">
              <div className="grid-3" style={{ gap: '10px', marginBottom: '12px' }}>
                <AmountCard label="Base Payout" amount={payout_breakdown.base_payout} color="blue" />
                <AmountCard label="Adjusted Payout" amount={payout_breakdown.adjusted_payout}
                  color={isApproved ? 'green' : 'red'} highlight />
                <div style={{ background: 'var(--bg-elevated)', borderRadius: 'var(--radius-sm)', padding: '12px' }}>
                  <div className="text-xs text-muted">Formula</div>
                  <div style={{ fontSize: '0.65rem', color: 'var(--text-secondary)', marginTop: '4px', lineHeight: 1.6 }}>
                    Base × Trust × (1−Fraud) × Env
                  </div>
                </div>
              </div>
              <div className="grid-3" style={{ gap: '8px' }}>
                <FactorPill label="Trust Factor" value={`${(payout_breakdown.trust_factor * 100).toFixed(1)}%`} />
                <FactorPill label="Fraud Multiplier" value={`${(payout_breakdown.fraud_multiplier * 100).toFixed(1)}%`}
                  warning={payout_breakdown.fraud_multiplier < 0.7} />
                <FactorPill label="Env Factor" value={`${(payout_breakdown.env_factor * 100).toFixed(1)}%`} />
              </div>
              {payout_breakdown.block_reason && (
                <AlertBox color="red" icon="✗" style={{ marginTop: '10px' }}>
                  {payout_breakdown.block_reason}
                </AlertBox>
              )}
            </Section>
          )}

          {/* ── FRAUD ANALYSIS ── */}
          {fraud_analysis && (
            <Section title="Fraud Analysis">
              <div className="grid-2" style={{ gap: '12px', marginBottom: '12px' }}>
                <FraudGauge score={fraud_analysis.fraud_score} />
                <div className="flex-col gap-8">
                  <InfoRow label="Model" value={fraud_analysis.model_type?.replace(/_/g, ' ')} />
                  <InfoRow label="Probability" value={`${(fraud_analysis.probability * 100).toFixed(2)}%`} />
                  <InfoRow label="Confidence" value={`${((fraud_analysis.confidence || 0.7) * 100).toFixed(0)}%`} />
                  <InfoRow label="Formula" value="P(fraud|X) = sigmoid(wᵀX+b)" mono />
                </div>
              </div>

              {/* Signals */}
              <div>
                <p className="text-xs text-muted" style={{ marginBottom: '6px' }}>DETECTED SIGNALS</p>
                {(fraud_analysis.signals || []).length === 0 ? (
                  <span className="badge badge-green">No anomalies detected</span>
                ) : (
                  <div className="flex" style={{ flexWrap: 'wrap', gap: '6px' }}>
                    {fraud_analysis.signals.map(s => (
                      <span key={s} className="badge badge-red" style={{ fontSize: '0.65rem' }}>
                        ⚠ {s.replace(/_/g, ' ')}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {/* Feature importances */}
              {fraud_analysis.feature_importances && (
                <div style={{ marginTop: '12px' }}>
                  <p className="text-xs text-muted" style={{ marginBottom: '8px' }}>FEATURE IMPORTANCES</p>
                  {Object.entries(fraud_analysis.feature_importances).map(([k, v]) => (
                    <div key={k} style={{ marginBottom: '5px' }}>
                      <div className="flex-between" style={{ fontSize: '0.72rem', marginBottom: '2px' }}>
                        <span className="text-muted">{k.replace(/_/g, ' ')}</span>
                        <span>{(v * 100).toFixed(1)}%</span>
                      </div>
                      <div className="progress-bar">
                        <div className="progress-fill" style={{
                          width: `${v * 100}%`,
                          background: v > 0.25 ? 'var(--accent-red)' : 'var(--accent-amber)',
                        }} />
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Features used */}
              {fraud_analysis.features_used && (
                <div style={{ marginTop: '12px', background: 'var(--bg-elevated)', borderRadius: '6px', padding: '10px' }}>
                  <p className="text-xs text-muted" style={{ marginBottom: '6px' }}>FEATURES USED</p>
                  {Object.entries(fraud_analysis.features_used).map(([k, v]) => (
                    <div key={k} className="flex-between" style={{ fontSize: '0.7rem', padding: '2px 0' }}>
                      <span className="text-muted">{k.replace(/_/g, ' ')}</span>
                      <span className="font-mono">{typeof v === 'number' ? v.toFixed(4) : v}</span>
                    </div>
                  ))}
                </div>
              )}
            </Section>
          )}

          {/* ── BEHAVIORAL ANALYSIS ── */}
          {behavioral_analysis && (
            <Section title="Behavioral Analysis">
              <div className="grid-2" style={{ gap: '8px', marginBottom: '12px' }}>
                <div style={{ background: 'var(--bg-elevated)', borderRadius: '8px', padding: '14px' }}>
                  <div className="text-xs text-muted">Behavior Score</div>
                  <div style={{
                    fontFamily: 'Syne, sans-serif', fontSize: '1.8rem', fontWeight: 800,
                    color: getScoreColor(behavioral_analysis.behavior_score), marginTop: '4px'
                  }}>
                    {behavioral_analysis.behavior_score?.toFixed(1)}
                  </div>
                  <div className="text-xs text-muted" style={{ marginTop: '2px' }}>/ 100</div>
                </div>
                <div style={{ background: 'var(--bg-elevated)', borderRadius: '8px', padding: '14px' }}>
                  <div className="text-xs text-muted">Risk Level</div>
                  <div style={{ marginTop: '8px' }}>
                    <span className={`badge badge-${getRiskBadge(behavioral_analysis.risk_level)}`}
                      style={{ fontSize: '0.75rem' }}>
                      {behavioral_analysis.risk_level?.toUpperCase()}
                    </span>
                  </div>
                  <div className="text-xs text-muted" style={{ marginTop: '8px' }}>
                    {(behavioral_analysis.all_anomaly_signals || []).length} signal(s)
                  </div>
                </div>
              </div>

              {/* Dimension scores */}
              {behavioral_analysis.dimensions && (
                <div>
                  <p className="text-xs text-muted" style={{ marginBottom: '8px' }}>DIMENSION SCORES</p>
                  {Object.entries(behavioral_analysis.dimensions).map(([dim, d]) => (
                    <div key={dim} style={{ marginBottom: '8px' }}>
                      <div className="flex-between" style={{ fontSize: '0.72rem', marginBottom: '3px' }}>
                        <span>{dim.replace(/_/g, ' ')}</span>
                        <div className="flex gap-8 align-center">
                          {(d.anomaly_signals || []).map(s => (
                            <span key={s} className="badge badge-amber" style={{ fontSize: '0.6rem' }}>
                              {s.replace(/_/g, ' ')}
                            </span>
                          ))}
                          <span style={{ fontWeight: 700, color: getScoreColor(d.score) }}>
                            {d.score?.toFixed(0)}
                          </span>
                        </div>
                      </div>
                      <div className="progress-bar">
                        <div className="progress-fill" style={{
                          width: `${d.score}%`,
                          background: d.score >= 70 ? 'var(--accent-green)' :
                                      d.score >= 45 ? 'var(--accent-amber)' : 'var(--accent-red)',
                        }} />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Section>
          )}

          {/* ── INCOME PREDICTION ── */}
          {income_prediction && (
            <Section title="AI Income Prediction">
              <div className="grid-3" style={{ gap: '10px', marginBottom: '12px' }}>
                <AmountCard label="Predicted Income" amount={income_prediction.predicted_income} color="blue" />
                <AmountCard label="Lower Bound" amount={income_prediction.confidence_lower} color="amber" />
                <AmountCard label="Upper Bound" amount={income_prediction.confidence_upper} color="green" />
              </div>
              <div className="grid-2" style={{ gap: '8px', marginBottom: '12px' }}>
                <InfoRow label="Model" value={income_prediction.model_type?.replace(/_/g, ' ')} />
                <InfoRow label="Env Impact" value={`−${income_prediction.env_impact_pct?.toFixed(1)}%`} />
                <InfoRow label="Confidence Band" value={`±${income_prediction.confidence_band_pct?.toFixed(1)}%`} />
                <InfoRow label="R² Score" value={income_prediction.r2_score?.toFixed(4) || '–'} />
                <InfoRow label="Trend" value={income_prediction.trend_direction === 'up' ? '↑ Upward' : '↓ Downward'} />
                <InfoRow  label="Decision Confidence" value={`${(result.decision_confidence * 100).toFixed(1)}%`}highlight={result.decision_confidence > 0.75}/>
              </div>

              {income_prediction.feature_importances && (
                <div>
                  <p className="text-xs text-muted" style={{ marginBottom: '8px' }}>FEATURE IMPORTANCE</p>
                  {Object.entries(income_prediction.feature_importances).map(([k, v]) => (
                    <div key={k} style={{ marginBottom: '5px' }}>
                      <div className="flex-between" style={{ fontSize: '0.72rem', marginBottom: '2px' }}>
                        <span className="text-muted">{k}</span>
                        <span>{(v * 100).toFixed(1)}%</span>
                      </div>
                      <div className="progress-bar">
                        <div className="progress-fill" style={{
                          width: `${v * 100}%`, background: 'var(--accent-blue)',
                        }} />
                      </div>
                    </div>
                  ))}
                </div>
              )}

              <div style={{ background: 'var(--bg-elevated)', borderRadius: '6px', padding: '10px', marginTop: '10px' }}>
                <p className="text-xs text-muted" style={{ marginBottom: '4px' }}>FORMULA</p>
                <p className="font-mono text-xs" style={{ color: 'var(--text-secondary)' }}>
                  ŷ = recent_avg × trend_adj × (1 − env_impact)<br />
                  L = Σ(y − ŷ)² (MSE loss)
                </p>
              </div>
            </Section>
          )}

          {/* ── TRUST UPDATE ── */}
          {trust_update && (
            <Section title="Trust Score Update">
              <div className="flex-center" style={{ gap: '20px', padding: '8px 0' }}>
                <div style={{ textAlign: 'center' }}>
                  <div className="text-xs text-muted" style={{ marginBottom: '4px' }}>Before</div>
                  <div style={{ fontFamily: 'Syne, sans-serif', fontSize: '2rem', fontWeight: 800,
                    color: getScoreColor(trust_update.trust_before) }}>
                    {trust_update.trust_before?.toFixed(1)}
                  </div>
                </div>
                <div style={{ fontSize: '1.5rem', color: trust_update.delta >= 0 ? 'var(--accent-green)' : 'var(--accent-red)' }}>
                  {trust_update.delta >= 0 ? '↑' : '↓'}
                </div>
                <div style={{ textAlign: 'center' }}>
                  <div className="text-xs text-muted" style={{ marginBottom: '4px' }}>After</div>
                  <div style={{ fontFamily: 'Syne, sans-serif', fontSize: '2rem', fontWeight: 800,
                    color: getScoreColor(trust_update.trust_after) }}>
                    {trust_update.trust_after?.toFixed(1)}
                  </div>
                </div>
                <div style={{ textAlign: 'center' }}>
                  <div className="text-xs text-muted" style={{ marginBottom: '4px' }}>Change</div>
                  <div style={{ fontFamily: 'Syne, sans-serif', fontSize: '1.4rem', fontWeight: 800,
                    color: trust_update.delta >= 0 ? 'var(--accent-green)' : 'var(--accent-red)' }}>
                    {trust_update.delta >= 0 ? '+' : ''}{trust_update.delta?.toFixed(2)}
                  </div>
                </div>
              </div>
              <p className="text-xs text-muted" style={{ textAlign: 'center', marginTop: '8px' }}>
                {trust_update.interpretation}
              </p>
              <div style={{ background: 'var(--bg-elevated)', borderRadius: '6px', padding: '10px', marginTop: '10px' }}>
                <p className="text-xs text-muted" style={{ marginBottom: '4px' }}>UPDATE FORMULA</p>
                <p className="font-mono text-xs" style={{ color: 'var(--text-secondary)' }}>
                  Δ = α × (behavior_score/100) × direction − β × fraud_penalty<br />
                  α={trust_update.factors?.alpha} (learn rate), β={trust_update.factors?.beta} (fraud weight)
                </p>
              </div>
            </Section>
          )}

          {/* ── EXPLAINABILITY ── */}
          {explainability && (
            <Section title="AI Decision Explanation">
              <AlertBox color="blue" icon="🤖" style={{ marginBottom: '12px' }}>
                {explainability.decision_summary}
              </AlertBox>

              <p className="text-xs text-muted" style={{ marginBottom: '8px' }}>DECISION FACTORS</p>
              {(explainability.decision_factors || []).map((f, i) => (
                <div key={i} style={{
                  display: 'flex', gap: '10px', alignItems: 'flex-start',
                  padding: '10px', background: 'var(--bg-elevated)',
                  borderRadius: '6px', marginBottom: '6px',
                  borderLeft: `3px solid ${f.type === 'positive' ? 'var(--accent-green)' :
                    f.type === 'negative' ? 'var(--accent-red)' : 'var(--accent-blue)'}`,
                }}>
                  <div style={{ flex: 1 }}>
                    <div className="flex-between">
                      <span style={{ fontSize: '0.8rem', fontWeight: 700 }}>{f.name}</span>
                      <span className={`badge badge-${f.type === 'positive' ? 'green' : f.type === 'negative' ? 'red' : 'blue'}`}
                        style={{ fontSize: '0.62rem' }}>Weight: {f.weight}</span>
                    </div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--accent-amber)', marginTop: '2px' }}>{f.impact}</div>
                    <div className="text-xs text-muted" style={{ marginTop: '2px' }}>{f.detail}</div>
                  </div>
                </div>
              ))}

              <div style={{ background: 'rgba(59,130,246,0.05)', border: '1px solid rgba(59,130,246,0.15)',
                borderRadius: '6px', padding: '10px', marginTop: '10px' }}>
                <p className="text-xs text-muted" style={{ marginBottom: '4px' }}>FAIRNESS NOTE</p>
                <p style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                  {explainability.fairness_note}
                </p>
              </div>

              {explainability.appeal_eligible && (
                <AlertBox color="green" icon="✔" style={{ marginTop: '10px' }}>
                  This claim is eligible for appeal review
                </AlertBox>
              )}
            </Section>
          )}

          {/* Close button */}
          <button className="btn btn-secondary btn-full" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  )
}

// ── Helper sub-components ──

function Section({ title, children }) {
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px' }}>
        <span style={{ fontSize: '0.65rem', textTransform: 'uppercase', letterSpacing: '1.5px',
          color: 'var(--text-muted)', fontWeight: 600 }}>{title}</span>
        <div style={{ flex: 1, height: '1px', background: 'var(--border)' }} />
      </div>
      {children}
    </div>
  )
}

function AlertBox({ color, icon, children, style }) {
  const colors = {
    red:   ['rgba(239,68,68,0.08)',   'rgba(239,68,68,0.25)',   '#ef4444'],
    amber: ['rgba(245,158,11,0.08)',  'rgba(245,158,11,0.25)',  '#f59e0b'],
    green: ['rgba(16,185,129,0.08)',  'rgba(16,185,129,0.25)',  '#10b981'],
    blue:  ['rgba(59,130,246,0.08)',  'rgba(59,130,246,0.25)',  '#3b82f6'],
  }
  const [bg, border, text] = colors[color] || colors.blue
  return (
    <div style={{ background: bg, border: `1px solid ${border}`, borderRadius: '6px',
      padding: '10px 14px', color: text, fontSize: '0.8rem', lineHeight: 1.5, ...style }}>
      {icon && <span style={{ marginRight: '8px' }}>{icon}</span>}
      {children}
    </div>
  )
}

function AmountCard({ label, amount, color, highlight }) {
  const colors = { green: 'var(--accent-green)', blue: 'var(--accent-blue)',
                   amber: 'var(--accent-amber)', red: 'var(--accent-red)' }
  return (
    <div style={{
      background: highlight ? `rgba(16,185,129,0.08)` : 'var(--bg-elevated)',
      border: highlight ? '1px solid rgba(16,185,129,0.25)' : 'none',
      borderRadius: '8px', padding: '12px',
    }}>
      <div className="text-xs text-muted" style={{ marginBottom: '4px' }}>{label}</div>
      <div style={{ fontFamily: 'Syne, sans-serif', fontSize: '1.3rem', fontWeight: 800,
        color: colors[color] || 'var(--text-primary)' }}>
        ₹{(amount || 0).toFixed(2)}
      </div>
    </div>
  )
}

function InfoRow({ label, value, mono }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      padding: '5px 0', borderBottom: '1px solid var(--border)', fontSize: '0.76rem' }}>
      <span className="text-muted">{label}</span>
      <span className={`${mono ? 'font-mono' : ''}`} style={{ color: 'var(--text-primary)', fontSize: mono ? '0.68rem' : '0.76rem' }}>
        {value}
      </span>
    </div>
  )
}

function FactorPill({ label, value, warning }) {
  return (
    <div style={{
      background: warning ? 'rgba(239,68,68,0.08)' : 'var(--bg-elevated)',
      border: warning ? '1px solid rgba(239,68,68,0.2)' : 'none',
      borderRadius: '6px', padding: '8px 10px',
    }}>
      <div className="text-xs text-muted">{label}</div>
      <div style={{ fontWeight: 700, color: warning ? 'var(--accent-red)' : 'var(--text-primary)',
        fontFamily: 'Syne, sans-serif', fontSize: '1rem', marginTop: '2px' }}>{value}</div>
    </div>
  )
}

function FraudGauge({ score }) {
  const color = score < 30 ? 'var(--accent-green)' : score < 60 ? 'var(--accent-amber)' : 'var(--accent-red)'
  const circumference = 2 * Math.PI * 36
  const strokeDasharray = `${(score / 100) * circumference} ${circumference}`

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
      <svg width="80" height="80" viewBox="0 0 80 80">
        <circle cx="40" cy="40" r="36" fill="none" stroke="var(--bg-elevated)" strokeWidth="7" />
        <circle cx="40" cy="40" r="36" fill="none" stroke={color} strokeWidth="7"
          strokeDasharray={strokeDasharray} strokeLinecap="round"
          transform="rotate(-90 40 40)" style={{ transition: 'stroke-dasharray 0.6s ease' }} />
        <text x="40" y="44" textAnchor="middle" fill={color}
          style={{ fontFamily: 'Syne, sans-serif', fontSize: '14px', fontWeight: 800 }}>
          {score?.toFixed(0)}
        </text>
      </svg>
      <div>
        <div className="text-xs text-muted">Fraud Score</div>
        <div style={{ color, fontWeight: 700, fontSize: '0.82rem', marginTop: '2px' }}>
          {score < 30 ? 'Low Risk' : score < 60 ? 'Moderate' : 'High Risk'}
        </div>
      </div>
    </div>
  )
}

function getScoreColor(score) {
  if (score >= 70) return 'var(--accent-green)'
  if (score >= 45) return 'var(--accent-amber)'
  return 'var(--accent-red)'
}

function getRiskBadge(level) {
  return { low: 'green', moderate: 'amber', high: 'red', critical: 'red' }[level] || 'blue'
}
