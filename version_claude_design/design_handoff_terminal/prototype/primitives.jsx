/* eslint-disable */
// Reusable building blocks: sparkline, monogram, etc.

function Sparkline({ data, w = 180, h = 36, warn = false, dots = false, fill = true }) {
  if (!data || data.length === 0) return null;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const span = Math.max(1e-3, max - min);
  const pad = 2;
  const usableW = w - pad * 2;
  const usableH = h - pad * 2;
  const points = data.map((v, i) => {
    const x = pad + (i / (data.length - 1)) * usableW;
    const y = pad + usableH - ((v - min) / span) * usableH;
    return [x, y];
  });
  const pathLine = points.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`).join(' ');
  const pathFill = `${pathLine} L${points[points.length - 1][0].toFixed(1)},${h} L${points[0][0].toFixed(1)},${h} Z`;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} width={w} height={h} preserveAspectRatio="none">
      {fill && <path d={pathFill} className={`spark-fill ${warn ? 'warn' : ''}`} />}
      <path d={pathLine} className={`spark-line ${warn ? 'warn' : ''}`} />
      {dots && points.map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r="1.6" className={`spark-dot ${warn ? 'warn' : ''}`} />
      ))}
    </svg>
  );
}

function MiniBar({ data, w = 70, h = 18, refLine }) {
  if (!data || data.length === 0) return null;
  const max = Math.max(...data, refLine || 0) * 1.05;
  const bw = w / data.length;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} width={w} height={h} preserveAspectRatio="none" className="mini-spark">
      {data.map((v, i) => {
        const bh = (v / max) * (h - 2);
        return <rect key={i} x={i * bw + 0.5} y={h - bh} width={bw - 1} height={bh}
                     fill="var(--accent)" opacity={0.65} />;
      })}
      {refLine !== undefined && (
        <line x1="0" x2={w} y1={h - (refLine / max) * (h - 2)} y2={h - (refLine / max) * (h - 2)}
              stroke="var(--warn)" strokeWidth="0.6" strokeDasharray="2 2" opacity="0.7" />
      )}
    </svg>
  );
}

function teamGradient(teamCode) {
  const t = TEAMS[teamCode];
  if (!t) return 'linear-gradient(135deg, #1b232e, #11161d)';
  return `linear-gradient(135deg, ${t.primary}, ${t.secondary || '#11161d'})`;
}

function PlayerArt({ player, height = 110, badgeLabel }) {
  const team = TEAMS[player.team];
  const initials = player.name.split(' ').map(s => s[0]).slice(0, 2).join('');
  const lastName = player.name.split(' ').slice(-1)[0].toUpperCase();
  return (
    <div className="pcard__art"
         style={{ '--team-grad': teamGradient(player.team), height: `${height}px` }}>
      <div style={{
        position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
        justifyContent: 'center', alignItems: 'center', zIndex: 1, gap: 4,
      }}>
        <div style={{
          fontFamily: 'var(--mono)', fontWeight: 700, fontSize: 12,
          letterSpacing: '0.16em', color: 'rgba(255,255,255,0.75)',
        }}>{team ? team.name.toUpperCase() : player.team}</div>
        <div className="pcard__monogram" style={{ fontSize: height > 100 ? 36 : 28 }}>
          {lastName}
        </div>
        <div style={{
          fontFamily: 'var(--mono)', fontSize: 9, letterSpacing: '0.12em',
          color: 'rgba(255,255,255,0.55)', textTransform: 'uppercase',
        }}>{player.pos} · #{player.serial}</div>
      </div>
      {badgeLabel && <div className="pcard__art-tag">{badgeLabel}</div>}
      <div className="pcard__art-serial">{player.serial}</div>
    </div>
  );
}

function PlayerCard({ player, rank, statLabel, onClick, showSpark = true }) {
  const rarity = RARITY[player.rarity] || RARITY.limited;
  const rankClass = rank === 0 ? 'rank-1' : rank === 1 ? 'rank-2' : rank === 2 ? 'rank-3' : '';
  const rankNumClass = rank === 0 ? 'r1' : rank === 1 ? 'r2' : rank === 2 ? 'r3' : '';
  const rankLabel = `#${(rank ?? 0) + 1}`;
  const team = TEAMS[player.team];
  return (
    <div className={`pcard ${rankClass}`} onClick={onClick}>
      <div className="pcard__hd">
        <div className={`pcard__rank ${rankNumClass}`}>{rankLabel}</div>
        <div className="pcard__head-info">
          <div className="pcard__name">{player.name}</div>
          <div className="pcard__sub">
            {team?.name || player.team} · {player.pos} · {player.age}y
          </div>
        </div>
        <div className="pcard__rarity-dot" style={{ background: rarity.color }} title={rarity.label} />
      </div>
      <PlayerArt player={player} height={110} badgeLabel={rarity.label} />
      <div className="pcard__row">
        <div className="cell">
          <div className="k">Stat avg</div>
          <div className="v">{player.avg.toFixed(1)}</div>
        </div>
        <div className="cell">
          <div className="k">ML Pred</div>
          <div className="v pos">{player.predicted.toFixed(1)}</div>
        </div>
        <div className="cell">
          <div className="k">Range</div>
          <div className="v dim" style={{ fontSize: 11 }}>{player.low.toFixed(0)}–{player.high.toFixed(0)}</div>
        </div>
      </div>
      {showSpark && (
        <div className="pcard__spark">
          <Sparkline data={player.spark} w={200} h={24} fill={true} />
          <div className="pcard__spark-label">10G</div>
        </div>
      )}
      <div className="pcard__meta">
        <span className={`tag rarity-${player.rarity}`}>{rarity.label}</span>
        {player.is && <span className="tag is">IS</span>}
        {!player.is && <span className="tag classic">CLASSIC</span>}
        {player.pp && <span className="tag pp">PP</span>}
        <span style={{ marginLeft: 'auto', color: 'var(--fg-3)' }}>
          {player.home ? 'vs' : '@'} {player.target} · {player.time}
        </span>
      </div>
    </div>
  );
}

// Compact slot card for lineup
function SlotCard({ slot, player, onClick, idx }) {
  const rarity = RARITY[player.rarity] || RARITY.limited;
  const team = TEAMS[player.team];
  const diff = player.real !== undefined && player.real !== null
    ? (player.real - player.predicted)
    : null;
  const real = player.real;
  const slotLower = slot.toLowerCase();
  return (
    <div className="slot" onClick={onClick} style={{ cursor: 'pointer' }}>
      <div className="slot__label">
        <span>{slot}</span>
        <span className="num">{String(idx + 1).padStart(2, '0')}</span>
      </div>
      <PlayerArt player={player} height={140} badgeLabel={rarity.label} />
      <div style={{ padding: '8px 10px', borderTop: '1px solid var(--line)' }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--fg-0)',
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {player.name}
        </div>
        <div className="flex gap-tight" style={{ marginTop: 4, fontSize: 10, color: 'var(--fg-2)' }}>
          <span className={`pos-pill ${slotLower}`}>{slot}</span>
          <span className="team-chip">
            <span className="team-dot" style={{ background: team?.primary || 'var(--line-3)' }} />
            {team?.name || player.team}
          </span>
        </div>
      </div>
      <div className="pred-strip">
        <div className="cell">
          <div className="k">Prédit</div>
          <div className="v">{player.predicted.toFixed(1)}</div>
        </div>
        <div className="cell">
          <div className="k">Réel</div>
          <div className="v dim">{real !== undefined && real !== null ? real.toFixed(1) : '—'}</div>
        </div>
        <div className="cell">
          <div className="k">Diff</div>
          <div className={`v ${diff === null ? 'dim' : diff >= 0 ? 'pos' : 'neg'}`}>
            {diff === null ? '—' : `${diff >= 0 ? '+' : ''}${diff.toFixed(1)}`}
          </div>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { Sparkline, MiniBar, PlayerArt, PlayerCard, SlotCard, teamGradient });
