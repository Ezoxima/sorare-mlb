/* eslint-disable */

function EquipeView({ filters, openHistory }) {
  const [showLocked, setShowLocked] = React.useState(true);

  // resolve lineup
  const lineup = LINEUP_SLOTS.map((s, i) => ({
    slot: s.slot,
    idx: i,
    player: PLAYERS.find(p => p.slug === s.fill),
  })).filter(s => s.player);

  // Mock — game weekly: predicted only since GW not started
  const lineupWithReal = lineup.map(s => ({
    ...s, player: { ...s.player, real: null }
  }));

  const totalPred = lineupWithReal.reduce((sum, s) => sum + s.player.predicted, 0);
  const effectivePred = totalPred * 1.0; // power multiplier could be applied
  const isCount = lineupWithReal.filter(s => s.player.is).length;
  const clubs = {};
  lineupWithReal.forEach(s => { clubs[s.player.team] = (clubs[s.player.team] || 0) + 1; });
  const maxClub = Math.max(...Object.values(clubs));
  const maxClubName = Object.entries(clubs).sort((a, b) => b[1] - a[1])[0][0];

  // Roster non-lineup
  const inLineup = new Set(LINEUP_SLOTS.map(s => s.fill));
  const bench = PLAYERS.filter(p => !inLineup.has(p.slug)).slice(0, 12);

  return (
    <div className="view-pad">
      {/* Summary KPIs */}
      <div className="panel mb">
        <div className="panel__hd">
          <span className="title">Lineup actuelle</span>
          <span className="pill">GW 23</span>
          <span className="pill">CLASSIC</span>
          <span className="pill accent">LIMITED CHAMPION</span>
          <div className="right">
            <span style={{ color: 'var(--fg-2)' }}>Verrouillage</span>
            <span style={{ color: 'var(--warn)' }}>2j 21h</span>
            <span className="dot warn" />
          </div>
        </div>
        <div className="lineup-summary">
          <div className="ls-cell">
            <div className="k">Score prédit total</div>
            <div className="headline">
              <span className="big">{totalPred.toFixed(1)}</span>
              <span className="label">pts</span>
            </div>
            <div className="sub" style={{ marginTop: 8 }}>
              Eff. ×power · <span style={{ color: 'var(--pos)' }}>{effectivePred.toFixed(1)} pts</span>
            </div>
            <div className="checks">
              <span className="check ok"><span className="ico">✓</span>IS 7/7 (min 6)</span>
              <span className="check ok"><span className="ico">✓</span>Club max {maxClub}/6</span>
              <span className="check ok"><span className="ico">✓</span>7/7 slots</span>
            </div>
          </div>
          <div className="ls-cell">
            <div className="k">Slots remplis</div>
            <div className="v">7<span style={{ color: 'var(--fg-3)' }}>/7</span></div>
            <div className="sub">SP · RP · CI · MI · OF · FLEX · LIBRE</div>
          </div>
          <div className="ls-cell">
            <div className="k">IS éligibles</div>
            <div className="v pos">{isCount}<span style={{ color: 'var(--fg-3)' }}>/7</span></div>
            <div className="sub">min. requis 6/7</div>
          </div>
          <div className="ls-cell">
            <div className="k">Club max</div>
            <div className="v">{maxClub}<span style={{ color: 'var(--fg-3)' }}>/6</span></div>
            <div className="sub">{TEAMS[maxClubName]?.name}</div>
          </div>
          <div className="ls-cell">
            <div className="k">Reward attendue</div>
            <div className="v warn" style={{ color: 'var(--warn)' }}>$8.40</div>
            <div className="sub">Palier 51-100 · 193.8 pts</div>
          </div>
        </div>
      </div>

      {/* Lineup grid */}
      <div className="mb">
        <div className="toolbar">
          <span className="lbl">Composition</span>
          <span style={{ color: 'var(--fg-0)', fontWeight: 600 }}>Mon équipe</span>
          <div className="toolbar__sep" />
          <button className="chip active">Cartes</button>
          <button className="chip">Liste</button>
          <button className="chip">Diamant</button>
          <div style={{ flex: 1 }} />
          <label className="toggle">
            <input type="checkbox" checked={showLocked} onChange={e => setShowLocked(e.target.checked)} />
            <span className="track" />
            Afficher verrouillage
          </label>
          <div className="toolbar__sep" />
          <button className="chip">⤓ Export PNG</button>
          <button className="chip">★ Sauvegarder</button>
        </div>

        <div style={{ padding: '14px',
                      background: 'var(--bg-1)', border: '1px solid var(--line)',
                      borderTop: 'none' }}>
          <div className="lineup-grid">
            {lineupWithReal.map((s, i) => (
              <SlotCard key={s.slot} slot={s.slot} idx={i} player={s.player}
                        onClick={() => openHistory(s.player)} />
            ))}
          </div>
        </div>
      </div>

      {/* Distribution & Bench */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
        {/* Risk / distribution panel */}
        <div className="panel">
          <div className="panel__hd">
            <span className="title">Distribution des prédictions</span>
            <span className="pill">σ ML</span>
          </div>
          <div className="panel__bd">
            {lineupWithReal.map((s, i) => {
              const p = s.player;
              const total = 50;
              const center = p.predicted;
              const span = p.high - p.low;
              const startPct = Math.max(0, (p.low / total) * 100);
              const widthPct = Math.min(100 - startPct, (span / total) * 100);
              const meanPct = Math.min(99, (center / total) * 100);
              return (
                <div key={p.slug} style={{ marginBottom: 10 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 11 }}>
                    <span style={{ width: 40, color: 'var(--fg-2)', fontSize: 10, letterSpacing: '0.1em' }}>
                      {s.slot}
                    </span>
                    <span style={{ flex: 1, color: 'var(--fg-0)', overflow: 'hidden',
                                   textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {p.name}
                    </span>
                    <span style={{ color: 'var(--fg-2)', fontSize: 10, fontVariantNumeric: 'tabular-nums' }}>
                      {p.low.toFixed(0)}–{p.high.toFixed(0)}
                    </span>
                    <span style={{ color: 'var(--pos)', fontWeight: 600, fontVariantNumeric: 'tabular-nums', width: 38, textAlign: 'right' }}>
                      {p.predicted.toFixed(1)}
                    </span>
                  </div>
                  <div style={{ position: 'relative', height: 8, marginTop: 4,
                                background: 'var(--bg-2)', border: '1px solid var(--line)' }}>
                    <div style={{
                      position: 'absolute',
                      left: `${startPct}%`,
                      width: `${widthPct}%`,
                      top: 0, bottom: 0,
                      background: 'linear-gradient(90deg, rgba(95,179,255,0.2), rgba(74,222,128,0.35), rgba(95,179,255,0.2))',
                    }} />
                    <div style={{
                      position: 'absolute',
                      left: `${meanPct}%`,
                      top: -2, bottom: -2, width: 2,
                      background: 'var(--accent)',
                      boxShadow: '0 0 4px var(--accent)',
                    }} />
                  </div>
                </div>
              );
            })}
            <div style={{ marginTop: 10, fontSize: 10, color: 'var(--fg-3)',
                          display: 'flex', alignItems: 'center', gap: 12 }}>
              <span><span style={{ display: 'inline-block', width: 14, height: 4,
                                   background: 'linear-gradient(90deg, rgba(95,179,255,0.5), rgba(74,222,128,0.6))',
                                   verticalAlign: 'middle', marginRight: 4 }} />intervalle ML</span>
              <span><span style={{ display: 'inline-block', width: 2, height: 8,
                                   background: 'var(--accent)', verticalAlign: 'middle', marginRight: 6,
                                   marginLeft: 4 }} />médiane prédite</span>
              <span style={{ marginLeft: 'auto' }}>Total {totalPred.toFixed(1)} pts</span>
            </div>
          </div>
        </div>

        {/* Bench / candidats */}
        <div className="panel">
          <div className="panel__hd">
            <span className="title">Banc & candidats</span>
            <span className="pill">{bench.length}</span>
            <div className="right">
              <span style={{ color: 'var(--accent)' }}>+ swap</span>
            </div>
          </div>
          <div className="panel__bd panel__bd--flush">
            <table className="dtable">
              <thead>
                <tr>
                  <th>Joueur</th>
                  <th>Poste</th>
                  <th>Équipe</th>
                  <th className="num">Pred</th>
                  <th className="num">Avg</th>
                  <th>Tendance</th>
                  <th>Match</th>
                </tr>
              </thead>
              <tbody>
                {bench.map(p => {
                  const team = TEAMS[p.team];
                  return (
                    <tr key={p.slug} onClick={() => openHistory(p)}>
                      <td className="strong">{p.name}</td>
                      <td><span className={`pos-pill ${p.posAgg.toLowerCase()}`}>{p.posAgg}</span></td>
                      <td>
                        <span className="team-chip">
                          <span className="team-dot" style={{ background: team?.primary || 'var(--line-3)' }} />
                          {team?.name || p.team}
                        </span>
                      </td>
                      <td className="num strong" style={{ color: 'var(--pos)' }}>
                        {p.predicted.toFixed(1)}
                      </td>
                      <td className="num">{p.avg.toFixed(1)}</td>
                      <td><MiniBar data={p.spark} w={60} h={16} /></td>
                      <td style={{ color: 'var(--fg-2)' }}>
                        {p.home ? 'vs' : '@'} {p.target}
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

Object.assign(window, { EquipeView });
