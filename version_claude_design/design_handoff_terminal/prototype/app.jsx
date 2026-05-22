/* eslint-disable */

function App() {
  const [active, setActive] = React.useState('defis');
  const [history, setHistory] = React.useState(null);
  const [filters, setFilters] = React.useState({
    categorie: 'HITTING',
    stat: STATS_AVAILABLE[0],
    fenetre: 10,
    target: 0,
    saison: 'TOUS',
    poste: 'TOUS',
    rarities: ['unique', 'super_rare', 'rare', 'limited'],
    day: 'today',
  });

  const openHistory = (player) => setHistory(player);

  let view;
  if (active === 'defis')  view = <DefisView  filters={filters} openHistory={openHistory} />;
  else if (active === 'equipe') view = <EquipeView filters={filters} openHistory={openHistory} />;
  else view = (
    <div className="view-pad">
      <div className="panel">
        <div className="panel__hd">
          <span className="title">{TABS.find(t => t.id === active)?.label}</span>
          <span className="pill">STUB</span>
        </div>
        <div className="empty-state">
          Cette vue n'est pas encore convertie au design Terminal.<br />
          <span style={{ color: 'var(--fg-3)' }}>Cliquez sur DEFIS ou EQUIPE pour voir le nouveau dashboard.</span>
        </div>
      </div>
    </div>
  );

  return (
    <div className="shell">
      <Ticker />
      <Tabs active={active} onSelect={setActive} />
      <div className="main">
        <Sidebar filters={filters} setFilters={setFilters} />
        <div className="content">{view}</div>
      </div>
      <StatusBar active={active} filters={filters} />
      {history && <HistoryDrawer player={history} stat={filters.stat} onClose={() => setHistory(null)} />}
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
