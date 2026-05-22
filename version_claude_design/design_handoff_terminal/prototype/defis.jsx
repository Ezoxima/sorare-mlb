/* eslint-disable */

function DefisView({ filters, openHistory }) {
  const { saison, poste, rarities, stat } = filters;
  const [sortKey, setSortKey] = React.useState('predicted');
  const [sortDir, setSortDir] = React.useState('desc');
  const [selectedSlug, setSelectedSlug] = React.useState(null);

  // Apply filters
  let players = PLAYERS.filter(p => {
    if (saison === 'IS'      && !p.is) return false;
    if (saison === 'Classic' &&  p.is) return false;
    if (poste !== 'TOUS' && p.posAgg !== poste) return false;
    if (rarities.length && !rarities.includes(p.rarity)) return false;
    return true;
  });

  // Sort
  players = [...players].sort((a, b) => {
    let va = a[sortKey], vb = b[sortKey];
    if (typeof va === 'string') { va = va.toLowerCase(); vb = vb.toLowerCase(); }
    if (va < vb) return sortDir === 'asc' ? -1 : 1;
    if (va > vb) return sortDir === 'asc' ?  1 : -1;
    return 0;
  });

  const setSort = (k) => {
    if (sortKey === k) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortKey(k); setSortDir('desc'); }
  };

  const top3 = players.slice(0, 3);
  const headlineAvg = players.length ? players.reduce((s, p) => s + p.predicted, 0) / players.length : 0;
  const headlineMax = players.length ? Math.max(...players.map(p => p.predicted)) : 0;
  const eligibleCount = players.filter(p => p.is).length;
  const ppCount = players.filter(p => p.pp).length;

  return (
    <div className="view-pad">
      {/* Headline strip */}
      <div className="panel mb">
        <div className="lineup-summary">
          <div className="ls-cell">
            <div className="k">Stat sélectionnée</div>
            <div className="headline">
              <span className="big">{stat.label}</span>
              <span className="label">{stat.name}</span>
            </div>
            <div className="sub" style={{ marginTop: 8 }}>
              Fenêtre <span style={{ color: 'var(--fg-0)' }}>10 matchs</span> ·
              Catégorie <span style={{ color: 'var(--fg-0)' }}>{stat.cat}</span>
            </div>
          </div>
          <div className="ls-cell">
            <div className="k">Joueurs ce jour</div>
            <div className="v">{players.length}</div>
            <div className="sub">de {PLAYERS.length} en galerie</div>
          </div>
          <div className="ls-cell">
            <div className="k">Pred. moyenne</div>
            <div className="v pos">{headlineAvg.toFixed(1)}</div>
            <div className="sub">σ ±5.4 pts</div>
          </div>
          <div className="ls-cell">
            <div className="k">Pred. max</div>
            <div className="v">{headlineMax.toFixed(1)}</div>
            <div className="sub">{top3[0]?.name?.split(' ').slice(-1)[0]}</div>
          </div>
          <div className="ls-cell">
            <div className="k">Composition</div>
            <div className="v" style={{ fontSize: 18 }}>
              <span style={{ color: 'var(--pos)' }}>{eligibleCount}</span>
              <span style={{ color: 'var(--fg-3)' }}> / </span>
              <span style={{ color: 'var(--warn)' }}>{ppCount}</span>
            </div>
            <div className="sub">IS éligibles / Probable Pitchers</div>
          </div>
        </div>
      </div>

      {/* Top 3 suggestion */}
      <div className="panel mb">
        <div className="panel__hd">
          <span className="title">Suggestion d'alignement</span>
          <span className="pill accent">TOP 3</span>
          <div className="right">
            <span>tri par <span style={{ color: 'var(--fg-0)' }}>{stat.label}</span></span>
            <span className="dot live" /> <span style={{ color: 'var(--pos)' }}>LIVE</span>
          </div>
        </div>
        <div style={{ padding: 14, display: 'grid',
                      gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
          {top3.map((p, i) => (
            <PlayerCard key={p.slug} player={p} rank={i} statLabel={stat.label}
                        onClick={() => openHistory(p)} />
          ))}
        </div>
      </div>

      {/* Full classement */}
      <div>
        <div className="toolbar">
          <span className="lbl">Classement</span>
          <span style={{ color: 'var(--fg-0)', fontWeight: 600 }}>{players.length} joueurs</span>
          <div className="toolbar__sep" />
          <div className="cmd-bar" style={{ width: 240 }}>
            <span className="prefix">/</span>
            <input placeholder="filtrer par nom, équipe…" />
            <span className="kbd">⌘K</span>
          </div>
          <div className="toolbar__sep" />
          <span className="lbl">tri</span>
          <span style={{ color: 'var(--accent)' }}>{sortKey}</span>
          <span style={{ color: 'var(--fg-3)' }}>{sortDir}</span>
          <div style={{ flex: 1 }} />
          <label className="toggle">
            <input type="checkbox" defaultChecked />
            <span className="track" />
            Sparklines
          </label>
          <label className="toggle">
            <input type="checkbox" />
            <span className="track" />
            Cachés IL
          </label>
        </div>

        <div className="panel" style={{ borderTop: 'none' }}>
          <div className="panel__bd panel__bd--flush" style={{ maxHeight: 480, overflowY: 'auto' }}>
            <table className="dtable">
              <thead>
                <tr>
                  <Th id="rank"   k="#"           onSort={setSort} sortKey={sortKey} sortDir={sortDir} />
                  <Th id="name"   k="Joueur"      onSort={setSort} sortKey={sortKey} sortDir={sortDir} />
                  <Th id="posAgg" k="Poste"       onSort={setSort} sortKey={sortKey} sortDir={sortDir} />
                  <Th id="team"   k="Équipe"      onSort={setSort} sortKey={sortKey} sortDir={sortDir} />
                  <Th id="rarity" k="Rareté"      onSort={setSort} sortKey={sortKey} sortDir={sortDir} />
                  <Th id="is"     k="Saison"      onSort={setSort} sortKey={sortKey} sortDir={sortDir} />
                  <Th id="avg"    k="Avg"         onSort={setSort} sortKey={sortKey} sortDir={sortDir} numeric />
                  <Th id="predicted" k="Pred"     onSort={setSort} sortKey={sortKey} sortDir={sortDir} numeric />
                  <Th id="low"    k="Range"       onSort={setSort} sortKey={sortKey} sortDir={sortDir} numeric />
                  <th>Tendance</th>
                  <Th id="time"   k="Heure"       onSort={setSort} sortKey={sortKey} sortDir={sortDir} />
                  <Th id="target" k="Adversaire"  onSort={setSort} sortKey={sortKey} sortDir={sortDir} />
                </tr>
              </thead>
              <tbody>
                {players.map((p, i) => {
                  const rarity = RARITY[p.rarity];
                  const team = TEAMS[p.team];
                  const rk = i;
                  return (
                    <tr key={p.slug}
                        className={selectedSlug === p.slug ? 'selected' : ''}
                        onClick={() => { setSelectedSlug(p.slug); openHistory(p); }}>
                      <td>
                        <span className={`row-rank ${rk === 0 ? 'r1' : rk === 1 ? 'r2' : rk === 2 ? 'r3' : ''}`}>
                          {String(rk + 1).padStart(2, '0')}
                        </span>
                      </td>
                      <td className="strong">{p.name}</td>
                      <td><span className={`pos-pill ${p.posAgg.toLowerCase()}`}>{p.posAgg}</span></td>
                      <td>
                        <span className="team-chip">
                          <span className="team-dot" style={{ background: team?.primary || 'var(--line-3)' }} />
                          {team?.name || p.team}
                        </span>
                      </td>
                      <td>
                        <span style={{ color: rarity.color, fontSize: 10, letterSpacing: '0.06em' }}>
                          {rarity.label}
                        </span>
                      </td>
                      <td>
                        {p.is
                          ? <span className="tag is">IS</span>
                          : <span className="tag classic">CLASSIC</span>}
                        {p.pp && <span className="tag pp" style={{ marginLeft: 4 }}>PP</span>}
                      </td>
                      <td className="num">{p.avg.toFixed(1)}</td>
                      <td className="num strong" style={{ color: 'var(--pos)' }}>{p.predicted.toFixed(1)}</td>
                      <td className="num" style={{ color: 'var(--fg-2)' }}>
                        {p.low.toFixed(0)}–{p.high.toFixed(0)}
                      </td>
                      <td>
                        <MiniBar data={p.spark} w={70} h={18} refLine={p.avg} />
                      </td>
                      <td style={{ color: 'var(--fg-1)' }}>{p.time}</td>
                      <td>
                        <span style={{ color: 'var(--fg-2)' }}>{p.home ? 'vs' : '@'}</span>{' '}
                        {p.target}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

function Th({ id, k, onSort, sortKey, sortDir, numeric }) {
  const sorted = sortKey === id;
  return (
    <th onClick={() => onSort(id)}
        className={`${sorted ? 'sorted' : ''} ${numeric ? 'num' : ''}`}>
      {k}
      {sorted && <span className="arr">{sortDir === 'asc' ? '▲' : '▼'}</span>}
    </th>
  );
}

Object.assign(window, { DefisView });
