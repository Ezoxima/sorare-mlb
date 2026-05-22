// Mock data inspired by the Streamlit app's structure (gallery_stats, ml_predictions, etc.)
// Player roster pulled from the user's reference screenshots.

const RARITY = {
  unique:     { label: 'UNIQUE',     color: '#ffd166' },
  super_rare: { label: 'SUPER RARE', color: '#ff5d5d' },
  rare:       { label: 'RARE',       color: '#5fb3ff' },
  limited:    { label: 'LIMITED',    color: '#c894ff' },
};

const TEAMS = {
  PHI: { name: 'Phillies',  city: 'Philadelphia', primary: '#E81828', secondary: '#002D72' },
  CLE: { name: 'Guardians', city: 'Cleveland',    primary: '#E50022', secondary: '#0F223E' },
  MIL: { name: 'Brewers',   city: 'Milwaukee',    primary: '#FFC52F', secondary: '#12284B' },
  NYY: { name: 'Yankees',   city: 'New York',     primary: '#003087', secondary: '#E4002C' },
  MIN: { name: 'Twins',     city: 'Minnesota',    primary: '#D31145', secondary: '#002B5C' },
  ATL: { name: 'Braves',    city: 'Atlanta',      primary: '#CE1141', secondary: '#13274F' },
  PIT: { name: 'Pirates',   city: 'Pittsburgh',   primary: '#FDB827', secondary: '#27251F' },
  TEX: { name: 'Rangers',   city: 'Texas',        primary: '#003278', secondary: '#C0111F' },
  NYM: { name: 'Mets',      city: 'New York',     primary: '#FF5910', secondary: '#002D72' },
  BAL: { name: 'Orioles',   city: 'Baltimore',    primary: '#DF4601', secondary: '#000000' },
  LAA: { name: 'Angels',    city: 'Los Angeles',  primary: '#BA0021', secondary: '#003263' },
  BOS: { name: 'Red Sox',   city: 'Boston',       primary: '#BD3039', secondary: '#0C2340' },
  MIA: { name: 'Marlins',   city: 'Miami',        primary: '#00A3E0', secondary: '#EF3340' },
  STL: { name: 'Cardinals', city: 'St. Louis',    primary: '#C41E3A', secondary: '#0C2340' },
  SF:  { name: 'Giants',    city: 'San Francisco',primary: '#FD5A1E', secondary: '#27251F' },
  KC:  { name: 'Royals',    city: 'Kansas City',  primary: '#004687', secondary: '#BD9B60' },
  SEA: { name: 'Mariners',  city: 'Seattle',      primary: '#0C2C56', secondary: '#005C5C' },
  SD:  { name: 'Padres',    city: 'San Diego',    primary: '#2F241D', secondary: '#FFC425' },
  DET: { name: 'Tigers',    city: 'Detroit',      primary: '#0C2340', secondary: '#FA4616' },
  TOR: { name: 'Blue Jays', city: 'Toronto',      primary: '#134A8E', secondary: '#1D2D5C' },
};

// Mini sparkline = last 10 outings, normalized 0-1
const spark = (vals) => vals;

const PLAYERS = [
  // Lineup actifs
  { slug: 'cristopher-sanchez', name: 'Cristopher Sánchez', team: 'PHI', pos: 'SP', posAgg: 'SP',  age: 29, rarity: 'limited',    serial: '170/1000', is: true,  pp: true,
    avg: 23.4, fenetre: 10, predicted: 25.5, low: 19.1, high: 31.0, target: 'PIT', home: true, time: '23:35',
    stat_label: 'Sorare Pts', stat_avg: 25.1,
    spark: spark([18,22,24,17,28,21,30,19,25,27]),
    badges: ['IS','PP'] },

  { slug: 'cade-smith', name: 'Cade Smith', team: 'CLE', pos: 'RP', posAgg: 'RP',  age: 27, rarity: 'limited',  serial: '265/1000', is: true,  pp: false,
    avg: 17.1, fenetre: 10, predicted: 17.3, low: 11.2, high: 22.4, target: 'CWS', home: false, time: '01:05',
    stat_label: 'Sorare Pts', stat_avg: 16.8,
    spark: spark([12,15,8,19,17,22,11,18,16,14]),
    badges: ['IS'] },

  { slug: 'jose-ramirez', name: 'José Ramírez', team: 'CLE', pos: '3B', posAgg: 'CI', age: 33, rarity: 'limited', serial: '168/1000', is: true,  pp: false,
    avg: 28.3, fenetre: 10, predicted: 28.3, low: 22.0, high: 34.7, target: 'CWS', home: false, time: '01:05',
    stat_label: 'Sorare Pts', stat_avg: 27.4,
    spark: spark([26,31,18,29,33,25,30,27,22,28]),
    badges: ['IS'] },

  { slug: 'brice-turang', name: 'Brice Turang', team: 'MIL', pos: '2B', posAgg: 'MI', age: 26, rarity: 'limited', serial: '191/1000', is: true,  pp: false,
    avg: 29.0, fenetre: 10, predicted: 29.2, low: 22.8, high: 36.0, target: 'CIN', home: true, time: '02:10',
    stat_label: 'Sorare Pts', stat_avg: 28.7,
    spark: spark([22,27,33,18,31,29,25,34,28,30]),
    badges: ['IS'] },

  { slug: 'cody-bellinger', name: 'Cody Bellinger', team: 'NYY', pos: 'OF', posAgg: 'OF', age: 30, rarity: 'limited', serial: '369/1000', is: true, pp: false,
    avg: 29.8, fenetre: 10, predicted: 30.2, low: 23.5, high: 37.1, target: 'TOR', home: false, time: '01:07',
    stat_label: 'Sorare Pts', stat_avg: 29.2,
    spark: spark([24,33,29,21,32,27,31,28,35,30]),
    badges: ['IS'] },

  { slug: 'aaron-judge', name: 'Aaron Judge', team: 'NYY', pos: 'OF', posAgg: 'FLEX', age: 34, rarity: 'limited', serial: '417/1000', is: true, pp: false,
    avg: 31.7, fenetre: 10, predicted: 29.9, low: 22.1, high: 38.4, target: 'TOR', home: false, time: '01:07',
    stat_label: 'Sorare Pts', stat_avg: 31.7,
    spark: spark([22,38,27,41,29,34,33,28,36,30]),
    badges: ['IS'] },

  { slug: 'byron-buxton', name: 'Byron Buxton', team: 'MIN', pos: 'OF', posAgg: 'LIBRE', age: 31, rarity: 'unique', serial: '25/1000', is: false, pp: false,
    avg: 32.2, fenetre: 10, predicted: 33.4, low: 24.0, high: 41.2, target: 'KC',  home: true, time: '02:40',
    stat_label: 'Sorare Pts', stat_avg: 32.2,
    spark: spark([28,35,42,18,38,29,33,40,31,37]),
    badges: ['Classic'] },

  // Bench / candidats du marché (issus des refs)
  { slug: 'paul-skenes', name: 'Paul Skenes', team: 'PIT', pos: 'SP', posAgg: 'SP', age: 23, rarity: 'limited', serial: '—', is: true, pp: true,
    avg: 30.4, fenetre: 10, predicted: 30.6, low: 24.2, high: 36.5, target: 'COL', home: true, time: '02:10',
    stat_label: 'Sorare Pts', stat_avg: 30.4,
    spark: spark([28,33,29,31,35,27,32,30,29,34]),
    badges: ['IS','PP'] },

  { slug: 'jacob-degrom', name: 'Jacob DeGrom', team: 'TEX', pos: 'SP', posAgg: 'SP', age: 38, rarity: 'limited', serial: '—', is: true, pp: true,
    avg: 26.0, fenetre: 10, predicted: 26.0, low: 19.3, high: 32.6, target: 'OAK', home: false, time: '04:05',
    stat_label: 'Sorare Pts', stat_avg: 26.0,
    spark: spark([24,28,22,29,27,25,26,30,23,28]),
    badges: ['IS','PP'] },

  { slug: 'spencer-strider', name: 'Spencer Strider', team: 'ATL', pos: 'SP', posAgg: 'SP', age: 27, rarity: 'limited', serial: '—', is: true, pp: true,
    avg: 22.1, fenetre: 10, predicted: 21.8, low: 15.0, high: 28.6, target: 'PHI', home: true, time: '02:40',
    stat_label: 'Sorare Pts', stat_avg: 22.1,
    spark: spark([18,24,20,17,26,21,23,19,25,22]),
    badges: ['IS','PP'] },

  { slug: 'chris-sale', name: 'Chris Sale', team: 'ATL', pos: 'SP', posAgg: 'SP', age: 37, rarity: 'limited', serial: '—', is: true, pp: true,
    avg: 30.2, fenetre: 10, predicted: 30.2, low: 23.4, high: 37.0, target: 'PHI', home: true, time: '02:45',
    stat_label: 'Sorare Pts', stat_avg: 30.2,
    spark: spark([26,32,29,33,28,31,27,34,30,29]),
    badges: ['IS','PP'] },

  { slug: 'tarik-skubal', name: 'Tarik Skubal', team: 'DET', pos: 'SP', posAgg: 'SP', age: 29, rarity: 'limited', serial: '—', is: true, pp: true,
    avg: 31.0, fenetre: 10, predicted: 31.0, low: 24.8, high: 37.2, target: 'CHC', home: false, time: '03:40',
    stat_label: 'Sorare Pts', stat_avg: 31.0,
    spark: spark([30,33,28,32,29,34,31,28,33,30]),
    badges: ['IS','PP'] },

  { slug: 'zack-wheeler', name: 'Zack Wheeler', team: 'PHI', pos: 'SP', posAgg: 'SP', age: 36, rarity: 'limited', serial: '—', is: true, pp: true,
    avg: 26.2, fenetre: 10, predicted: 26.2, low: 19.4, high: 32.9, target: 'ATL', home: false, time: '02:45',
    stat_label: 'Sorare Pts', stat_avg: 26.2,
    spark: spark([24,27,22,28,29,25,26,30,23,27]),
    badges: ['IS','PP'] },

  // Hitters bench
  { slug: 'shohei-ohtani', name: 'Shohei Ohtani', team: 'LAA', pos: 'DH', posAgg: 'CI', age: 32, rarity: 'super_rare', serial: '14/100', is: true, pp: false,
    avg: 34.8, fenetre: 10, predicted: 34.8, low: 25.6, high: 43.7, target: 'OAK', home: true, time: '03:10',
    stat_label: 'Sorare Pts', stat_avg: 34.8,
    spark: spark([30,42,28,38,31,40,33,36,29,41]),
    badges: ['IS'] },

  { slug: 'mookie-betts', name: 'Mookie Betts', team: 'KC', pos: 'SS', posAgg: 'MI', age: 33, rarity: 'rare', serial: '—', is: true, pp: false,
    avg: 24.5, fenetre: 10, predicted: 24.5, low: 17.2, high: 31.8, target: 'MIN', home: false, time: '02:40',
    stat_label: 'Sorare Pts', stat_avg: 24.5,
    spark: spark([22,26,18,28,21,27,23,29,24,25]),
    badges: ['IS'] },

  { slug: 'juan-soto', name: 'Juan Soto', team: 'NYM', pos: 'OF', posAgg: 'OF', age: 27, rarity: 'super_rare', serial: '42/100', is: true, pp: false,
    avg: 28.9, fenetre: 10, predicted: 28.9, low: 21.3, high: 36.4, target: 'WAS', home: true, time: '01:10',
    stat_label: 'Sorare Pts', stat_avg: 28.9,
    spark: spark([25,30,27,32,24,29,31,26,33,28]),
    badges: ['IS'] },

  { slug: 'bobby-witt', name: 'Bobby Witt Jr.', team: 'KC', pos: 'SS', posAgg: 'MI', age: 26, rarity: 'limited', serial: '—', is: true, pp: false,
    avg: 26.7, fenetre: 10, predicted: 26.7, low: 19.4, high: 33.9, target: 'MIN', home: false, time: '02:40',
    stat_label: 'Sorare Pts', stat_avg: 26.7,
    spark: spark([23,28,21,30,25,27,29,24,31,26]),
    badges: ['IS'] },

  { slug: 'francisco-lindor', name: 'Francisco Lindor', team: 'NYM', pos: 'SS', posAgg: 'MI', age: 32, rarity: 'rare', serial: '—', is: true, pp: false,
    avg: 23.6, fenetre: 10, predicted: 23.6, low: 16.8, high: 30.5, target: 'WAS', home: true, time: '01:10',
    stat_label: 'Sorare Pts', stat_avg: 23.6,
    spark: spark([21,24,19,26,22,25,23,27,20,25]),
    badges: ['IS'] },

  { slug: 'rafael-devers', name: 'Rafael Devers', team: 'BOS', pos: '3B', posAgg: 'CI', age: 29, rarity: 'limited', serial: '—', is: true, pp: false,
    avg: 25.2, fenetre: 10, predicted: 25.2, low: 18.0, high: 32.4, target: 'TB',  home: true, time: '01:10',
    stat_label: 'Sorare Pts', stat_avg: 25.2,
    spark: spark([22,27,21,28,23,26,24,29,22,27]),
    badges: ['IS'] },

  { slug: 'gunnar-henderson', name: 'Gunnar Henderson', team: 'BAL', pos: 'SS', posAgg: 'MI', age: 25, rarity: 'limited', serial: '—', is: true, pp: false,
    avg: 27.1, fenetre: 10, predicted: 27.1, low: 19.8, high: 34.5, target: 'TOR', home: true, time: '01:35',
    stat_label: 'Sorare Pts', stat_avg: 27.1,
    spark: spark([24,29,22,30,26,28,25,31,23,28]),
    badges: ['IS'] },

  { slug: 'corbin-carroll', name: 'Corbin Carroll', team: 'PIT', pos: 'OF', posAgg: 'OF', age: 25, rarity: 'rare', serial: '—', is: true, pp: false,
    avg: 22.9, fenetre: 10, predicted: 22.9, low: 16.2, high: 29.6, target: 'COL', home: true, time: '02:10',
    stat_label: 'Sorare Pts', stat_avg: 22.9,
    spark: spark([20,24,18,26,21,25,23,27,19,24]),
    badges: ['IS'] },
];

// Lineup courante (slots Sorare Classic)
const LINEUP_SLOTS = [
  { slot: 'SP',    fill: 'cristopher-sanchez' },
  { slot: 'RP',    fill: 'cade-smith' },
  { slot: 'CI',    fill: 'jose-ramirez' },
  { slot: 'MI',    fill: 'brice-turang' },
  { slot: 'OF',    fill: 'cody-bellinger' },
  { slot: 'FLEX',  fill: 'aaron-judge' },
  { slot: 'LIBRE', fill: 'byron-buxton' },
];

// Pour le drawer historique : 20 derniers matchs d'un joueur
function genHistory(seed) {
  // determinist pseudo-rng
  let s = 0; for (const c of seed) s = (s * 31 + c.charCodeAt(0)) % 100000;
  const rand = () => (s = (s * 9301 + 49297) % 233280) / 233280;
  return Array.from({ length: 20 }, (_, i) => {
    const dnp = rand() < 0.1;
    return {
      date: new Date(Date.UTC(2026, 4, 22 - (20 - i))).toISOString().slice(0, 10),
      gw: 21 + Math.floor(i / 3),
      played: !dnp,
      score: dnp ? 0 : Math.round((rand() * 35 + 8) * 10) / 10,
      stat:  dnp ? 0 : Math.round(rand() * 6 * 10) / 10,
    };
  });
}

// Defis journaliers — classement complet (utilise tous les joueurs)
const STATS_AVAILABLE = [
  { key: 'sorare_score', label: 'SCR', name: 'Sorare Score', cat: 'HITTING' },
  { key: 'hits',         label: 'H',   name: 'Hits',         cat: 'HITTING' },
  { key: 'home_runs',    label: 'HR',  name: 'Home Runs',    cat: 'HITTING' },
  { key: 'rbi',          label: 'RBI', name: 'Runs Batted In', cat: 'HITTING' },
  { key: 'stolen_bases', label: 'SB',  name: 'Stolen Bases',   cat: 'HITTING' },
  { key: 'strikeouts',   label: 'K',   name: 'Strikeouts',     cat: 'PITCHING' },
  { key: 'innings',      label: 'IP',  name: 'Innings Pitched',cat: 'PITCHING' },
  { key: 'era',          label: 'ERA', name: 'Earned Run Avg', cat: 'PITCHING' },
];

const TABS = [
  { id: 'defis',     label: 'Défis journaliers', short: 'DEFIS' },
  { id: 'equipe',    label: 'Mon équipe',        short: 'EQUIPE' },
  { id: 'cartes',    label: 'Mes cartes',        short: 'CARTES' },
  { id: 'db',        label: 'Base de données',   short: 'DB' },
  { id: 'vv',        label: 'Vis-à-vis',         short: 'VV' },
  { id: 'proj',      label: 'Projections',       short: 'PROJ' },
  { id: 'comp',      label: 'Compétitions',      short: 'COMP' },
  { id: 'lineups',   label: 'Mes lineups',       short: 'LU' },
  { id: 'marche',    label: 'Marché',            short: 'MKT' },
];

Object.assign(window, {
  RARITY, TEAMS, PLAYERS, LINEUP_SLOTS, STATS_AVAILABLE, TABS, genHistory,
});
