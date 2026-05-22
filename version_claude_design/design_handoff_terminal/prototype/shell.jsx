/* eslint-disable */

// ────── ticker, sidebar, statusbar, top tabs ──────

function Ticker() {
  const items = [
    { sym: 'GW23',     val: 'OPEN',     cls: 'pos',  raw: true },
    { sym: 'IL/D7',    val: '12',       cls: 'neg',  delta: '+3'  },
    { sym: 'WX/SD',    val: 'RAIN 60%', cls: 'neg' },
    { sym: 'PCT.IS',   val: '92.8%',    cls: 'pos',  delta: '+1.2' },
    { sym: 'CARDS',    val: '347',      cls: 'pos' },
    { sym: 'ETH',      val: '3,184.20', cls: 'pos',  delta: '+0.8%' },
    { sym: 'SO5.SCR',  val: '193.8',    cls: 'pos',  delta: '+8.4'  },
    { sym: 'PP.TOD',   val: '8/30',     cls: 'pos' },
    { sym: 'NXT.LOCK', val: '2j 21h',   cls: 'warn' },
    { sym: 'ML.σ',     val: '5.42',     cls: 'pos' },
    { sym: 'RANK',     val: '#41',      cls: 'pos',  delta: '▲12' },
    { sym: 'REWARD',   val: '$8.40',    cls: 'pos' },
  ];
  const renderItems = (key) => items.map((it, i) => (
    <span key={`${key}-${i}`} className="ticker__item">
      <span className="sym">{it.sym}</span>
      {it.delta && <span className={`arrow ${it.cls === 'neg' ? 'neg' : 'pos'}`} />}
      <span className={`val ${it.cls}`}>{it.val}</span>
      {it.delta && <span className={`val ${it.cls === 'neg' ? 'neg' : 'pos'}`}
                         style={{ fontSize: 10 }}>{it.delta}</span>}
    </span>
  ));
  return (
    <div className="ticker">
      <div className="ticker__brand">
        <span className="ticker__brand-dot" />
        SORARE·MLB / TERMINAL
      </div>
      <div className="ticker__feed">
        <div className="ticker__feed-inner">
          {renderItems('a')}
          {renderItems('b')}
        </div>
      </div>
      <div className="ticker__clock">
        <span>UTC <span style={{ color: 'var(--fg-0)' }}>23:14:08</span></span>
        <span>PAR <span style={{ color: 'var(--fg-0)' }}>01:14:08</span></span>
        <span className="live">LIVE</span>
      </div>
    </div>
  );
}

function Tabs({ active, onSelect }) {
  return (
    <div className="tabs">
      {TABS.map((t, i) => (
        <button key={t.id}
                className={`tab ${active === t.id ? 'active' : ''}`}
                onClick={() => onSelect(t.id)}>
          <span className="num">{String(i + 1).padStart(2, '0')}</span>
          <span>{t.short}</span>
        </button>
      ))}
      <div className="tabs__spacer" />
      <button className="tabs__action">
        Documentation <span className="kbd">?</span>
      </button>
      <button className="tabs__action" style={{ color: 'var(--accent)' }}>
        ⟳ Refresh <span className="kbd">R</span>
      </button>
    </div>
  );
}

function Sidebar({ filters, setFilters }) {
  const set = (k, v) => setFilters(f => ({ ...f, [k]: v }));

  return (
    <div className="sidebar">
      {/* Manager */}
      <div className="side-section">
        <div className="side-title">
          Manager <span className="badge">●</span>
        </div>
        <div className="manager-row">
          <div className="manager-avatar">FX</div>
          <div className="manager-info">
            <div className="name">F. Xavier</div>
            <div className="sub">347 cartes · 12 lineups</div>
          </div>
        </div>
      </div>

      {/* Category */}
      <div className="side-section">
        <div className="side-title">Filtres galerie</div>
        <div className="side-label">Catégorie</div>
        <div className="seg" style={{ marginBottom: 12 }}>
          {['HITTING', 'PITCHING'].map(c => (
            <button key={c}
                    className={filters.categorie === c ? 'active' : ''}
                    onClick={() => set('categorie', c)}>{c}</button>
          ))}
        </div>

        <div className="side-label">Statistique</div>
        <select className="select" style={{ marginBottom: 12 }}
                value={filters.stat.key}
                onChange={e => {
                  const s = STATS_AVAILABLE.find(x => x.key === e.target.value);
                  if (s) set('stat', s);
                }}>
          {STATS_AVAILABLE
            .filter(s => s.cat === filters.categorie || filters.categorie === 'HITTING' && s.cat === 'HITTING')
            .map(s => (
              <option key={s.key} value={s.key}>{s.label} — {s.name}</option>
            ))}
        </select>

        <div className="side-label">Fenêtre</div>
        <div className="seg" style={{ marginBottom: 12 }}>
          {[5, 10, 20].map(n => (
            <button key={n}
                    className={filters.fenetre === n ? 'active' : ''}
                    onClick={() => set('fenetre', n)}>{n}G</button>
          ))}
        </div>

        <div className="side-label">Objectif</div>
        <input type="number" className="num-input"
               value={filters.target}
               onChange={e => set('target', parseFloat(e.target.value) || 0)}
               step="0.5" min="0" />
      </div>

      {/* Saison */}
      <div className="side-section">
        <div className="side-label">Saison</div>
        <div className="seg" style={{ marginBottom: 14 }}>
          {['TOUS', 'IS', 'Classic'].map(s => (
            <button key={s}
                    className={filters.saison === s ? 'active' : ''}
                    onClick={() => set('saison', s)}>{s}</button>
          ))}
        </div>

        <div className="side-label">Position</div>
        <div className="chips" style={{ marginBottom: 14 }}>
          {['TOUS', 'SP', 'RP', 'CI', 'MI', 'OF'].map(p => (
            <span key={p}
                  className={`chip ${filters.poste === p ? 'active' : ''}`}
                  onClick={() => set('poste', p)}>{p}</span>
          ))}
        </div>

        <div className="side-label">Rareté</div>
        <div className="chips">
          {Object.keys(RARITY).map(r => {
            const active = filters.rarities.includes(r);
            return (
              <span key={r}
                    className={`chip ${active ? 'active' : ''}`}
                    style={active ? { color: RARITY[r].color, borderColor: RARITY[r].color } : {}}
                    onClick={() => set('rarities',
                       active ? filters.rarities.filter(x => x !== r)
                              : [...filters.rarities, r])}>
                {RARITY[r].label}
              </span>
            );
          })}
        </div>
      </div>

      {/* Calendar */}
      <div className="side-section">
        <div className="side-title">Calendrier</div>
        <div className="side-label">Jour de match</div>
        <select className="select"
                value={filters.day}
                onChange={e => set('day', e.target.value)}>
          <option value="all">Tous les jours</option>
          <option value="today">Aujourd'hui — ven. 22 mai</option>
          <option value="tomorrow">Demain — sam. 23 mai</option>
          <option value="d2">dim. 24 mai</option>
          <option value="d3">lun. 25 mai</option>
        </select>
      </div>

      {/* Live notices */}
      <div className="side-section">
        <div className="side-title">
          <span>Alertes</span>
          <span style={{ color: 'var(--warn)' }}>3</span>
        </div>
        <Alert type="warn" k="IL +1" v="Mike Trout (LAA, OF) — 10-Day IL" t="il y a 1h" />
        <Alert type="info" k="PP" v="Skenes confirmé contre COL" t="2h" />
        <Alert type="pos"  k="STREAK" v="Aaron Judge: 5 GP > 30 pts" t="3h" />
      </div>
    </div>
  );
}

function Alert({ type, k, v, t }) {
  const color = type === 'warn' ? 'var(--warn)' : type === 'pos' ? 'var(--pos)' : 'var(--info)';
  return (
    <div style={{
      padding: '8px 0',
      borderBottom: '1px dashed var(--line)',
      fontSize: 10,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <span className="dot" style={{ background: color, boxShadow: `0 0 6px ${color}` }} />
        <span style={{ color, letterSpacing: '0.1em', fontWeight: 600 }}>{k}</span>
        <span style={{ marginLeft: 'auto', color: 'var(--fg-3)' }}>{t}</span>
      </div>
      <div style={{ color: 'var(--fg-1)', marginTop: 2, fontSize: 11 }}>{v}</div>
    </div>
  );
}

function StatusBar({ active, filters }) {
  return (
    <div className="statusbar">
      <span className="statusbar__cell">
        <span className="dot live" />
        <span className="k">CONN</span>
        <span className="v">api.sorare.com</span>
      </span>
      <span className="statusbar__cell">
        <span className="k">VIEW</span>
        <span className="v">{TABS.find(t => t.id === active)?.label}</span>
      </span>
      <span className="statusbar__cell">
        <span className="k">CACHE</span>
        <span className="v">ttl 3600s</span>
      </span>
      <span className="statusbar__cell">
        <span className="k">FILTERS</span>
        <span className="v">
          {filters.categorie} · {filters.stat.label} · {filters.fenetre}G · {filters.saison}
          {filters.poste !== 'TOUS' ? ` · ${filters.poste}` : ''}
          {filters.rarities.length ? ` · ${filters.rarities.length}R` : ''}
        </span>
      </span>
      <span className="statusbar__spacer" />
      <span className="statusbar__cell">
        <span className="k">LAST.UPD</span>
        <span className="v">22 mai 2026 — 23:12 UTC</span>
      </span>
      <span className="statusbar__cell">
        <span className="k">v</span>
        <span className="v">2.3.7-mlb</span>
      </span>
    </div>
  );
}

Object.assign(window, { Ticker, Tabs, Sidebar, StatusBar });
