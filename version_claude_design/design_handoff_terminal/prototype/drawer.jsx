/* eslint-disable */

function HistoryDrawer({ player, onClose, stat }) {
  React.useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  if (!player) return null;
  const history = React.useMemo(() => genHistory(player.slug), [player.slug]);
  const team = TEAMS[player.team];
  const rarity = RARITY[player.rarity];

  const playedScores = history.filter(h => h.played).map(h => h.score);
  const mean = playedScores.reduce((s, v) => s + v, 0) / Math.max(1, playedScores.length);
  const std = Math.sqrt(playedScores.reduce((s, v) => s + (v - mean) ** 2, 0) / Math.max(1, playedScores.length));
  const last5 = playedScores.slice(-5);
  const last5Mean = last5.reduce((s, v) => s + v, 0) / Math.max(1, last5.length);
  const trend = last5Mean - mean;

  return (
    <React.Fragment>
      <div className="drawer-overlay" onClick={onClose} />
      <div className="drawer">
        <div className="drawer__hd">
          <div className="manager-avatar" style={{
            width: 36, height: 36, background: teamGradient(player.team), fontSize: 12,
          }}>
            {player.name.split(' ').map(s => s[0]).slice(0, 2).join('')}
          </div>
          <div>
            <div className="drawer__title">{player.name}</div>
            <div className="drawer__sub">
              {team?.name || player.team} · {player.pos} · {player.age}y ·{' '}
              <span style={{ color: rarity.color }}>{rarity.label}</span> · #{player.serial}
            </div>
          </div>
          <button className="drawer__close" onClick={onClose}>✕</button>
        </div>

        <div className="drawer__bd">
          {/* Headline */}
          <div className="panel mb">
            <div className="panel__hd">
              <span className="title">Performance — 20 derniers matchs</span>
              <span className="pill">{playedScores.length} GP</span>
            </div>
            <div className="panel__bd">
              <div className="headline" style={{ marginBottom: 12 }}>
                <div>
                  <div className="label">Moyenne</div>
                  <div className="big">{mean.toFixed(1)}</div>
                </div>
                <div>
                  <div className="label">σ</div>
                  <div style={{ fontSize: 18, color: 'var(--fg-1)', fontVariantNumeric: 'tabular-nums' }}>
                    ±{std.toFixed(1)}
                  </div>
                </div>
                <div>
                  <div className="label">L5</div>
                  <div style={{ fontSize: 18, color: 'var(--fg-0)', fontVariantNumeric: 'tabular-nums' }}>
                    {last5Mean.toFixed(1)}
                  </div>
                </div>
                <div>
                  <div className="label">Tendance</div>
                  <div className={`delta ${trend >= 0 ? 'pos' : 'neg'}`}
                       style={{ fontSize: 18, fontVariantNumeric: 'tabular-nums' }}>
                    {trend >= 0 ? '▲' : '▼'} {Math.abs(trend).toFixed(1)}
                  </div>
                </div>
                <div style={{ marginLeft: 'auto' }}>
                  <div className="label">Pred GW23</div>
                  <div className="big pos" style={{ color: 'var(--pos)' }}>{player.predicted.toFixed(1)}</div>
                </div>
              </div>

              {/* big chart */}
              <ScoreChart history={history} target={player.predicted} mean={mean} />
            </div>
          </div>

          {/* History table */}
          <div className="panel mb">
            <div className="panel__hd">
              <span className="title">Détail</span>
            </div>
            <div className="panel__bd panel__bd--flush">
              <table className="dtable">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>GW</th>
                    <th>Status</th>
                    <th className="num">Score</th>
                    <th className="num">{stat?.label || 'STAT'}</th>
                  </tr>
                </thead>
                <tbody>
                  {[...history].reverse().map((h, i) => (
                    <tr key={i}>
                      <td>{h.date}</td>
                      <td style={{ color: 'var(--fg-2)' }}>GW{h.gw}</td>
                      <td>
                        {h.played
                          ? <span className="tag is">PLAYED</span>
                          : <span className="tag" style={{ color: 'var(--neg)', borderColor: 'rgba(255,93,93,0.35)' }}>DNP</span>}
                      </td>
                      <td className="num strong" style={{ color: h.played ? 'var(--fg-0)' : 'var(--fg-3)' }}>
                        {h.played ? h.score.toFixed(1) : '—'}
                      </td>
                      <td className="num" style={{ color: h.played ? 'var(--fg-1)' : 'var(--fg-3)' }}>
                        {h.played ? h.stat.toFixed(1) : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Context */}
          <div className="panel">
            <div className="panel__hd">
              <span className="title">Prochain match</span>
              <span className="pill">{player.home ? 'HOME' : 'AWAY'}</span>
            </div>
            <div className="panel__bd">
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: 12 }}>
                <div>
                  <div className="label" style={{ fontSize: 9, color: 'var(--fg-3)',
                                                  textTransform: 'uppercase', letterSpacing: '0.14em', marginBottom: 4 }}>
                    Adversaire
                  </div>
                  <div style={{ fontSize: 14, color: 'var(--fg-0)' }}>
                    {player.home ? 'vs' : '@'} {TEAMS[player.target]?.name || player.target}
                  </div>
                </div>
                <div>
                  <div className="label" style={{ fontSize: 9, color: 'var(--fg-3)',
                                                  textTransform: 'uppercase', letterSpacing: '0.14em', marginBottom: 4 }}>
                    Heure
                  </div>
                  <div style={{ fontSize: 14, color: 'var(--fg-0)' }}>{player.time} UTC</div>
                </div>
                <div>
                  <div className="label" style={{ fontSize: 9, color: 'var(--fg-3)',
                                                  textTransform: 'uppercase', letterSpacing: '0.14em', marginBottom: 4 }}>
                    Intervalle
                  </div>
                  <div style={{ fontSize: 14, color: 'var(--fg-0)' }}>
                    {player.low.toFixed(1)} – {player.high.toFixed(1)}
                  </div>
                </div>
                <div>
                  <div className="label" style={{ fontSize: 9, color: 'var(--fg-3)',
                                                  textTransform: 'uppercase', letterSpacing: '0.14em', marginBottom: 4 }}>
                    Probable
                  </div>
                  <div style={{ fontSize: 14, color: player.pp ? 'var(--warn)' : 'var(--fg-2)' }}>
                    {player.pp ? 'PROBABLE PITCHER' : 'Non confirmé'}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </React.Fragment>
  );
}

function ScoreChart({ history, target, mean }) {
  const w = 500, h = 180;
  const pad = { t: 16, r: 16, b: 24, l: 30 };
  const innerW = w - pad.l - pad.r;
  const innerH = h - pad.t - pad.b;
  const playedVals = history.filter(h => h.played).map(h => h.score);
  const maxY = Math.max(...playedVals, target || 0) * 1.15;
  const bx = (i) => pad.l + (i / Math.max(1, history.length - 1)) * innerW;
  const by = (v) => pad.t + innerH - (v / maxY) * innerH;

  // line through played points only
  const lineData = history.map((h, i) => h.played ? [bx(i), by(h.score)] : null);
  const segs = [];
  let cur = [];
  lineData.forEach(p => {
    if (p) cur.push(p);
    else if (cur.length) { segs.push(cur); cur = []; }
  });
  if (cur.length) segs.push(cur);

  return (
    <svg viewBox={`0 0 ${w} ${h}`} width="100%" height={h} style={{ display: 'block' }}>
      {/* grid */}
      {[0.25, 0.5, 0.75, 1].map((f, i) => (
        <line key={i} x1={pad.l} x2={pad.l + innerW}
              y1={pad.t + innerH * (1 - f)} y2={pad.t + innerH * (1 - f)}
              stroke="var(--line)" strokeDasharray="2 4" strokeWidth="0.6" />
      ))}
      {/* y-labels */}
      {[0.25, 0.5, 0.75, 1].map((f, i) => (
        <text key={i} x={pad.l - 6} y={pad.t + innerH * (1 - f) + 3}
              fontFamily="var(--mono)" fontSize="9" fill="var(--fg-3)" textAnchor="end">
          {(maxY * f).toFixed(0)}
        </text>
      ))}
      {/* mean line */}
      <line x1={pad.l} x2={pad.l + innerW} y1={by(mean)} y2={by(mean)}
            stroke="var(--fg-3)" strokeDasharray="2 3" strokeWidth="0.8" />
      <text x={pad.l + innerW} y={by(mean) - 4} fontFamily="var(--mono)" fontSize="9"
            fill="var(--fg-3)" textAnchor="end">moy {mean.toFixed(1)}</text>
      {/* target / predicted */}
      {target && (
        <React.Fragment>
          <line x1={pad.l} x2={pad.l + innerW} y1={by(target)} y2={by(target)}
                stroke="var(--accent)" strokeDasharray="3 3" strokeWidth="1" opacity="0.7" />
          <text x={pad.l} y={by(target) - 4} fontFamily="var(--mono)" fontSize="9"
                fill="var(--accent)">pred {target.toFixed(1)}</text>
        </React.Fragment>
      )}
      {/* line segments */}
      {segs.map((seg, i) => (
        <polyline key={i}
          points={seg.map(([x, y]) => `${x},${y}`).join(' ')}
          fill="none" stroke="var(--accent)" strokeWidth="1.5" />
      ))}
      {/* bars for DNP */}
      {history.map((h, i) => !h.played && (
        <rect key={`dnp${i}`} x={bx(i) - 2} y={pad.t} width={4} height={innerH}
              fill="var(--neg)" opacity="0.08" />
      ))}
      {/* points */}
      {history.map((h, i) => h.played && (
        <circle key={`pt${i}`} cx={bx(i)} cy={by(h.score)} r="2.5"
                fill={h.score >= mean ? 'var(--pos)' : 'var(--warn)'}
                stroke="var(--bg-1)" strokeWidth="1" />
      ))}
      {/* DNP markers */}
      {history.map((h, i) => !h.played && (
        <text key={`dnpt${i}`} x={bx(i)} y={pad.t + innerH - 4}
              fontFamily="var(--mono)" fontSize="8" fill="var(--neg)"
              textAnchor="middle" opacity="0.7">×</text>
      ))}
      {/* x-axis dates */}
      {history.map((h, i) => i % 4 === 0 && (
        <text key={`xl${i}`} x={bx(i)} y={h - 6}
              fontFamily="var(--mono)" fontSize="8" fill="var(--fg-3)" textAnchor="middle">
          {h.date.slice(5)}
        </text>
      ))}
    </svg>
  );
}

Object.assign(window, { HistoryDrawer });
