'use strict';
// Top-down dungeon view of the agent team. Polls /api/office and animates it on a canvas.
// Agent-written text only ever reaches the page via fillText or textContent.

const T = 16, RW = 13, RH = 9, GAP = 3, M = 1, COLS = 3, ROWS = 3, SCALE = 2;
const W = (M * 2 + COLS * RW + (COLS - 1) * GAP) * T;
const H = (M * 2 + ROWS * RH + (ROWS - 1) * GAP) * T;
const EMOJI_FONT = '"Apple Color Emoji","Segoe UI Emoji","Noto Color Emoji",sans-serif';
const TEXT_FONT = 'system-ui,"Segoe UI",sans-serif,"Apple Color Emoji","Segoe UI Emoji","Noto Color Emoji"';
const STATIONS = {
  intel: '🔮', sales: '💰', content: '🎻', delivery: '⚒️', command: '🗺️',
  success: '❤️‍🩹', products: '⚗️', finance: '🪙', platform: '🛡️',
};
const HUES = { intel: 260, sales: 40, content: 320, delivery: 15, command: 48, success: 140, products: 190, finance: 55, platform: 210 };
const BASE_EMOTES = ['💭', '☕', '🎵', '😴', '📖', '🤔'];

// ---------------------------------------------------------------- seasons
// weather: fall (drifts down), rise (floats up), snow (white flakes), fireflies, fireworks
const THEMES = {
  halloween: {
    label: '🎃 Happy Halloween', accent: '#ff8c1a', floor: { sat: 16, light: 12 },
    tint: 'rgba(60,0,90,.20)', vignette: .62, flame: [120, 255, 140], torch: '🕯️',
    decorTop: ['🕸️'], decorBottom: ['🎃', '🎃', '🦴', '🕯️'],
    creatures: [{ emoji: '🦇', count: 6, kind: 'fly' }, { emoji: '👻', count: 3, kind: 'ghost' }],
    weather: { kind: 'fall', emojis: ['🍂'], count: 10 },
    emotes: ['🍬', '🎃', '👀', '🕷️'], confetti: ['🍬', '🍭', '✨'],
  },
  autumn: {
    label: '🍂 Autumn', accent: '#e9a23b', floor: { sat: 14, light: 15 },
    tint: 'rgba(120,50,0,.08)', vignette: .45, flame: [255, 170, 60], torch: '🔥',
    decorTop: ['🍂'], decorBottom: ['🍄', '🌰', '🍁'],
    creatures: [], weather: { kind: 'fall', emojis: ['🍂', '🍁'], count: 26 },
    emotes: ['🍁', '🥧'], confetti: ['🍁', '✨'],
  },
  holiday: {
    label: '🎄 Happy Holidays', accent: '#7bd88f', floor: { sat: 10, light: 17 },
    tint: 'rgba(140,180,255,.07)', vignette: .45, flame: [255, 170, 60], torch: '🔥',
    decorTop: ['🎀'], decorBottom: ['🎄', '🎁', '⛄'], lights: true,
    creatures: [], weather: { kind: 'snow', count: 90 },
    emotes: ['🎁', '🍪', '☃️'], confetti: ['🎁', '❄️', '✨'],
  },
  newyear: {
    label: '🎆 Happy New Year', accent: '#ffd166', floor: { sat: 10, light: 15 },
    tint: 'rgba(20,20,60,.12)', vignette: .55, flame: [255, 200, 90], torch: '🔥',
    decorTop: ['🎊'], decorBottom: ['🥂', '🎉'],
    creatures: [], weather: { kind: 'fireworks' },
    emotes: ['🥳', '🎉'], confetti: ['🎉', '🎊', '✨'],
  },
  winter: {
    label: '❄️ Winter', accent: '#9fd3ff', floor: { sat: 8, light: 18 },
    tint: 'rgba(140,180,255,.10)', vignette: .45, flame: [255, 170, 60], torch: '🔥',
    decorTop: ['❄️'], decorBottom: ['⛄', '🧣'],
    creatures: [], weather: { kind: 'snow', count: 110 },
    emotes: ['☕', '🧤', '🥶'], confetti: ['❄️', '✨'],
  },
  valentine: {
    label: '💘 Valentine’s Week', accent: '#ff7aa2', floor: { sat: 18, light: 15 },
    tint: 'rgba(255,60,120,.07)', vignette: .45, flame: [255, 120, 160], torch: '🔥',
    decorTop: ['💝'], decorBottom: ['🌹', '💌'],
    creatures: [], weather: { kind: 'rise', emojis: ['💕', '💗'], count: 18 },
    emotes: ['💌', '🥰'], confetti: ['💖', '✨'],
  },
  spring: {
    label: '🌸 Spring', accent: '#f5a3c7', floor: { sat: 16, light: 17 },
    tint: 'rgba(120,255,160,.05)', vignette: .38, flame: [255, 190, 90], torch: '🔥',
    decorTop: ['🌿'], decorBottom: ['🌷', '🌱', '🐣'],
    creatures: [{ emoji: '🦋', count: 4, kind: 'fly' }], weather: { kind: 'fall', emojis: ['🌸'], count: 22 },
    emotes: ['🌼', '🐝'], confetti: ['🌸', '✨'],
  },
  summer: {
    label: '☀️ Summer', accent: '#ffd166', floor: { sat: 18, light: 16 },
    tint: 'rgba(255,200,80,.05)', vignette: .35, flame: [255, 200, 90], torch: '🔥',
    decorTop: ['🌿'], decorBottom: ['🌻', '🍉', '🐚'],
    creatures: [{ emoji: '🐝', count: 4, kind: 'fly' }], weather: { kind: 'fireflies', count: 40 },
    emotes: ['🍦', '😎', '🍉'], confetti: ['🌻', '✨'],
  },
};

function seasonFor(d) {
  const m = d.getMonth() + 1, day = d.getDate();
  if (m === 10) return 'halloween';
  if ((m === 12 && day >= 27) || (m === 1 && day <= 2)) return 'newyear';
  if (m === 12) return 'holiday';
  if (m === 2 && day >= 7 && day <= 14) return 'valentine';
  if (m === 1 || m === 2) return 'winter';
  if (m >= 3 && m <= 5) return 'spring';
  if (m >= 6 && m <= 8) return 'summer';
  return 'autumn';
}

function storedTheme() {
  try { return localStorage.getItem('agentos-theme') || 'auto'; } catch { return 'auto'; }
}
let themeChoice = new URLSearchParams(location.search).get('theme') || storedTheme();
let themeKey = null, theme = null;

// ---------------------------------------------------------------- canvas + state
const canvas = document.getElementById('map');
canvas.width = W * SCALE;
canvas.height = H * SCALE;
const ctx = canvas.getContext('2d');
ctx.scale(SCALE, SCALE);

let rooms = [];          // from the API, plus pixel rects
let sprites = new Map(); // agent id -> sprite
let scrolls = [];        // handoff animations
let particles = [];      // short-lived effects
let weather = [];        // persistent seasonal particles
let creatures = [];      // bats, ghosts, butterflies
let selected = null;
let hovered = null;
let seen = null;         // task id -> status, null until the first poll
let background = null;
let nextChat = 4, nextFirework = 1;

// ---------------------------------------------------------------- geometry
function rect(col, row) {
  const x = (M + col * (RW + GAP)) * T, y = (M + row * (RH + GAP)) * T;
  return { x, y, w: RW * T, h: RH * T };
}
function station(room) { return { x: room.x + room.w / 2, y: room.y + 2.6 * T }; }
function homeSlot(room, index, count) {
  // A grid of personal spots below the station, so a crowded room doesn't pile up.
  const cols = Math.min(4, count), rows = Math.ceil(count / 4);
  const col = index % 4, row = Math.floor(index / 4);
  const x0 = room.x + 2 * T, x1 = room.x + room.w - 2 * T;
  const y0 = room.y + 4.6 * T, y1 = room.y + room.h - 1.4 * T;
  return {
    x: cols === 1 ? (x0 + x1) / 2 : x0 + (x1 - x0) * col / (cols - 1),
    y: rows === 1 ? (y0 + y1) / 2 : y0 + (y1 - y0) * row / (rows - 1),
  };
}
function wanderSpot(sp) {
  return { x: sp.home.x + (Math.random() - 0.5) * 1.6 * T, y: sp.home.y + (Math.random() - 0.5) * 0.8 * T };
}
function roomOf(dept) { return rooms.find(r => r.dept === dept); }
const rand = (a, b) => a + Math.random() * (b - a);
const pick = list => list[Math.floor(Math.random() * list.length)];

// ---------------------------------------------------------------- themes
function setTheme(choice) {
  const key = choice === 'auto' ? seasonFor(new Date()) : choice;
  if (choice !== themeChoice) {
    themeChoice = choice;
    try { localStorage.setItem('agentos-theme', choice); } catch { /* private mode */ }
  }
  if (key === themeKey) return;
  themeKey = key;
  theme = THEMES[key] || THEMES.autumn;
  document.documentElement.style.setProperty('--gold', theme.accent);
  document.getElementById('season').textContent = theme.label;
  weather = [];
  creatures = [];
  const wx = theme.weather;
  for (let i = 0; i < (wx.count || 0); i++) weather.push(newWeather(wx, true));
  for (const c of theme.creatures) for (let i = 0; i < c.count; i++) creatures.push(newCreature(c));
  if (rooms.length) buildBackground();
}

function newWeather(wx, anywhere) {
  const w = { kind: wx.kind, x: rand(0, W), phase: rand(0, 6) };
  if (wx.kind === 'snow') Object.assign(w, { y: anywhere ? rand(0, H) : -4, vy: rand(8, 20), r: rand(.5, 1.6) });
  else if (wx.kind === 'fireflies') Object.assign(w, { y: rand(0, H), vx: rand(-6, 6), vy: rand(-6, 6) });
  else if (wx.kind === 'rise') Object.assign(w, { y: anywhere ? rand(0, H) : H + 8, vy: -rand(8, 16), emoji: pick(wx.emojis), size: rand(6, 9) });
  else Object.assign(w, { y: anywhere ? rand(0, H) : -8, vy: rand(10, 22), emoji: pick(wx.emojis), size: rand(6, 9), spin: rand(-2, 2) });
  return w;
}

function newCreature(c) {
  const dir = Math.random() < .5 ? 1 : -1;
  return {
    ...c, dir, x: rand(0, W), y: rand(T * 2, H - T * 2), base: 0, phase: rand(0, 6),
    speed: c.kind === 'ghost' ? rand(6, 12) : rand(25, 45), wait: 0,
  };
}

// ---------------------------------------------------------------- particles
function emit(p) {
  if (particles.length < 450) particles.push({ vx: 0, vy: 0, g: 0, age: 0, life: 1, size: 8, ...p });
}
function burst(x, y, emojis, n = 10) {
  for (let i = 0; i < n; i++) {
    const a = rand(0, Math.PI * 2), s = rand(25, 60);
    emit({ x, y, vx: Math.cos(a) * s, vy: Math.sin(a) * s - 25, g: 70, life: rand(.8, 1.3), emoji: pick(emojis), size: rand(5, 8) });
  }
}
function floatText(x, y, text, color) {
  emit({ x, y, vy: -18, life: 1.6, text, color, size: 8 });
}
function celebrate(sp) {
  sp.jump = 1;
  burst(sp.x, sp.y - 6, theme.confetti, 12);
  floatText(sp.x, sp.y - 18, '✓ done', '#7bd88f');
}
function fizzle(sp) {
  sp.shake = .7;
  for (let i = 0; i < 4; i++) emit({ x: sp.x + rand(-4, 4), y: sp.y - 4, vx: rand(-8, 8), vy: -rand(8, 16), life: 1.2, emoji: '💨', size: 8 });
  floatText(sp.x, sp.y - 18, '✗ failed', '#ef6a6a');
}
function emote(sp, icon, secs = 2.2) { sp.emote = { icon, t: secs }; }

// ---------------------------------------------------------------- static map
function rng(seed) {
  return () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };
}

function floor(g, x, y, w, h, hue, r) {
  const f = theme.floor;
  for (let ty = y; ty < y + h; ty += T) for (let tx = x; tx < x + w; tx += T) {
    g.fillStyle = `hsl(${hue} ${f.sat}% ${f.light + r() * 6}%)`;
    g.fillRect(tx, ty, T, T);
    g.strokeStyle = 'rgba(0,0,0,.35)';
    g.strokeRect(tx + .5, ty + .5, T - 1, T - 1);
  }
}

function buildBackground() {
  const off = document.createElement('canvas');
  off.width = W * SCALE; off.height = H * SCALE;
  const g = off.getContext('2d');
  g.scale(SCALE, SCALE);
  const r = rng(7);
  g.fillStyle = '#07060a';
  g.fillRect(0, 0, W, H);

  for (const room of rooms) {
    floor(g, room.x, room.y, room.w, room.h, HUES[room.dept] ?? 30, r);
    g.fillStyle = '#2a2433';
    g.fillRect(room.x, room.y, room.w, T * 1.5);
    g.fillStyle = '#3a3247';
    for (let bx = room.x; bx < room.x + room.w; bx += 8) for (let by = room.y; by < room.y + T * 1.5; by += 6) {
      g.fillRect(bx + ((by / 6) % 2 ? 4 : 0), by, 7, 5);
    }
    g.strokeStyle = '#1b1722';
    g.lineWidth = 3;
    g.strokeRect(room.x + 1.5, room.y + 1.5, room.w - 3, room.h - 3);
    g.lineWidth = 1;
  }
  // corridors drawn after the walls so they punch doorways through them
  for (const room of rooms) {
    const right = rooms.find(o => o.col === room.col + 1 && o.row === room.row);
    if (right) floor(g, room.x + room.w - T, room.y + room.h / 2 - T + 8, GAP * T + 2 * T, 2 * T, 30, r);
    const below = rooms.find(o => o.col === room.col && o.row === room.row + 1);
    if (below) floor(g, room.x + room.w / 2 - T, room.y + room.h - T, 2 * T, GAP * T + 2 * T, 30, r);
  }
  g.textAlign = 'center'; g.textBaseline = 'middle';
  for (const room of rooms) {
    const s = station(room);
    g.fillStyle = '#5b3a21';
    g.fillRect(s.x - 1.6 * T, s.y - 6, 3.2 * T, 12);
    g.fillStyle = '#7a5130';
    g.fillRect(s.x - 1.6 * T, s.y - 6, 3.2 * T, 3);
    g.font = `12px ${EMOJI_FONT}`;
    g.fillText(STATIONS[room.dept] || '⭐', s.x, s.y - 1);
    // seasonal decorations in the corners, away from the agents' spots
    g.font = `10px ${EMOJI_FONT}`;
    g.fillText(pick(theme.decorTop), room.x + T * .9, room.y + T * 2.1);
    g.fillText(pick(theme.decorTop), room.x + room.w - T * .9, room.y + T * 2.1);
    g.fillText(pick(theme.decorBottom), room.x + T * .9, room.y + room.h - T * .9);
    g.fillText(pick(theme.decorBottom), room.x + room.w - T * .9, room.y + room.h - T * .9);
    g.font = 'bold 8px ui-monospace,monospace';
    g.fillStyle = theme.accent;
    g.textAlign = 'left';
    g.fillText(room.name.toUpperCase(), room.x + 6, room.y + 7);
    g.textAlign = 'center';
  }
  g.fillStyle = theme.tint;
  g.fillRect(0, 0, W, H);
  background = off;
}

// ---------------------------------------------------------------- state sync
function applyState(s) {
  document.getElementById('spent').textContent = `$${s.spent.toFixed(2)} / $${s.budget}`;
  document.getElementById('pending').textContent = String(s.pending);
  document.getElementById('paused').style.display = s.paused ? 'inline' : 'none';
  if (themeChoice === 'auto') setTheme('auto'); // rolls over to the next season at midnight

  if (!rooms.length) {
    rooms = s.rooms.map(r => ({ ...r, ...rect(r.col, r.row) }));
    buildBackground();
  } else {
    for (const r of rooms) Object.assign(r, s.rooms.find(n => n.dept === r.dept) || {});
  }

  const live = new Set();
  const active = s.agents.filter(a => a.active && roomOf(a.dept));
  for (const a of active) {
    const room = roomOf(a.dept);
    const mates = active.filter(o => o.dept === a.dept).map(o => o.id).sort();
    const home = homeSlot(room, mates.indexOf(a.id), mates.length);
    live.add(a.id);
    let sp = sprites.get(a.id);
    if (!sp) {
      sp = { x: home.x, y: home.y, tx: home.x, ty: home.y, wait: Math.random() * 3, phase: Math.random() * 6,
        jump: 0, shake: 0, dust: 0, spark: 0, emote: null, nextEmote: rand(6, 20) };
      sprites.set(a.id, sp);
    }
    Object.assign(sp, { agent: a, room, home });
  }
  for (const id of [...sprites.keys()]) if (!live.has(id)) sprites.delete(id);
  assignStations();
  renderCard();

  if (seen === null) {
    // Opening the page: show recent history without replaying animations.
    seen = new Map(s.events.map(e => [e.id, e.status]));
    const icons = { done: '✨', failed: '💥', skipped: '💤', running: '⚒', queued: '⏳' };
    for (const e of s.events.slice(0, 10).reverse()) log(`${icons[e.status] || '•'} #${e.id} ${e.agent} (${e.status}): ${e.input}`);
    return;
  }
  for (const e of [...s.events].reverse()) {
    const prev = seen.get(e.id);
    if (prev === e.status) continue;
    seen.set(e.id, e.status);
    const sp = sprites.get(e.agent);
    if (prev === undefined) {
      if (e.source === 'handoff' && e.parent && sprites.has(e.parent) && sp) {
        const from = sprites.get(e.parent);
        scrolls.push({ x: from.x, y: from.y, to: e.agent, t: 0 });
        if (from) emote(from, '📜', 1.5);
      }
      log(`📥 #${e.id} ${e.agent}${e.parent ? ` ← ${e.parent}` : ''}: ${e.input}`);
    } else if (e.status === 'done') {
      if (sp) celebrate(sp);
      log(`✨ #${e.id} ${e.agent} finished`);
    } else if (e.status === 'failed') {
      if (sp) fizzle(sp);
      log(`💥 #${e.id} ${e.agent} failed`);
    } else if (e.status === 'skipped') {
      if (sp) emote(sp, '💤');
      log(`💤 #${e.id} ${e.agent} skipped (budget)`);
    }
  }
}

function assignStations() {
  // Working agents line up in front of their room's station.
  const byRoom = new Map();
  for (const sp of sprites.values()) {
    if (sp.agent.state !== 'working') continue;
    if (!byRoom.has(sp.room.dept)) byRoom.set(sp.room.dept, []);
    byRoom.get(sp.room.dept).push(sp);
  }
  for (const list of byRoom.values()) list.forEach((sp, i) => {
    const s = station(sp.room);
    sp.tx = s.x + (i - (list.length - 1) / 2) * 1.4 * T;
    sp.ty = s.y + 1.4 * T;
  });
}

function log(text) {
  const li = document.createElement('li');
  const t = document.createElement('span');
  t.className = 't';
  t.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + ' ';
  li.append(t, document.createTextNode(text));
  const ul = document.getElementById('log');
  ul.prepend(li);
  while (ul.children.length > 60) ul.lastChild.remove();
}

function renderCard() {
  const card = document.getElementById('card');
  const sp = selected && sprites.get(selected);
  card.replaceChildren();
  const h = document.createElement('h2');
  h.textContent = 'Adventurer';
  card.append(h);
  const add = (cls, text) => { const d = document.createElement('div'); d.className = cls; d.textContent = text; card.append(d); };
  if (!sp) { add('row', 'Click an agent on the map.'); return; }
  const a = sp.agent;
  const labels = { working: '⚒ working', queued: '⏳ queued', needs_you: '❗ waiting on you', failed: '💥 last task failed', idle: '🌿 idle' };
  add('big', a.emoji);
  add('name', a.id);
  add('row', `${a.avatar} · ${sp.room.name} · ${a.model}`);
  if (a.reason) add('row', `“${a.reason}”`);
  add('row', `${labels[a.state] || a.state} · $${a.spent.toFixed(3)} of $${a.budget.toFixed(2)} today`);
  if (a.task) add('task', a.task);
}

// ---------------------------------------------------------------- simulation
function update(dt) {
  for (const sp of sprites.values()) {
    const a = sp.agent, working = a.state === 'working';
    const dx = sp.tx - sp.x, dy = sp.ty - sp.y, dist = Math.hypot(dx, dy);
    if (dist > 1) {
      const step = Math.min(dist, (working ? 45 : 22) * dt);
      sp.x += dx / dist * step; sp.y += dy / dist * step;
      sp.moving = true;
      sp.dust -= dt;
      if (sp.dust <= 0) {
        sp.dust = .16;
        emit({ x: sp.x + rand(-2, 2), y: sp.y + 7, vx: rand(-4, 4), vy: -rand(2, 6), life: .5, color: 'rgba(200,190,170,.5)', size: rand(.8, 1.6) });
      }
    } else {
      sp.moving = false;
      if (!working && a.state !== 'needs_you') {
        sp.wait -= dt;
        if (sp.wait <= 0) {
          const p = wanderSpot(sp);
          sp.tx = p.x; sp.ty = p.y; sp.wait = 2 + Math.random() * 5;
        }
      }
    }
    if (working && !sp.moving) {
      sp.spark -= dt;
      if (sp.spark <= 0) {
        sp.spark = rand(.12, .3);
        const s = station(sp.room);
        emit({ x: s.x + rand(-8, 8), y: s.y - 2, vx: rand(-14, 14), vy: -rand(20, 40), g: 60, life: rand(.4, .8),
          color: `hsl(${HUES[sp.room.dept] ?? 40} 95% 65%)`, size: rand(.7, 1.4), glow: true });
      }
    }
    if (a.state === 'idle' && !sp.moving) {
      sp.nextEmote -= dt;
      if (sp.nextEmote <= 0) {
        sp.nextEmote = rand(12, 30);
        emote(sp, pick([...BASE_EMOTES, ...theme.emotes]));
      }
    }
    if (sp.emote) { sp.emote.t -= dt; if (sp.emote.t <= 0) sp.emote = null; }
    sp.jump = Math.max(0, sp.jump - dt * 1.4);
    sp.shake = Math.max(0, sp.shake - dt);
    sp.phase += dt * (sp.moving ? 12 : 2);
  }

  // two idle teammates standing close strike up a chat
  nextChat -= dt;
  if (nextChat <= 0) {
    nextChat = rand(5, 12);
    const idle = [...sprites.values()].filter(s => s.agent.state === 'idle' && !s.moving && !s.emote);
    for (const s of idle) {
      const mate = idle.find(o => o !== s && o.room === s.room && Math.hypot(o.x - s.x, o.y - s.y) < 3.5 * T);
      if (mate) { emote(s, '💬', 2.5); setTimeout(() => emote(mate, '💬', 2.5), 900); break; }
    }
  }

  for (const sc of scrolls) {
    sc.t += dt / 1.6;
    const p = scrollPos(sc);
    if (p) emit({ x: p.x, y: p.y, vx: rand(-5, 5), vy: rand(-5, 5), life: .6, color: theme.accent, size: rand(.6, 1.2), glow: true });
  }
  scrolls = scrolls.filter(sc => sc.t < 1 && sprites.has(sc.to));

  for (const p of particles) { p.age += dt; p.vy += p.g * dt; p.x += p.vx * dt; p.y += p.vy * dt; }
  particles = particles.filter(p => p.age < p.life);

  updateWeather(dt);
  for (const c of creatures) {
    c.phase += dt;
    if (c.kind === 'ghost') {
      c.x += c.dir * c.speed * dt;
      c.y += Math.sin(c.phase * .8) * 4 * dt;
    } else {
      c.x += c.dir * c.speed * dt;
      c.y += Math.sin(c.phase * 3) * 18 * dt;
    }
    if (c.x < -20 || c.x > W + 20) { Object.assign(c, newCreature(c)); c.x = c.dir > 0 ? -16 : W + 16; }
  }
}

function updateWeather(dt) {
  const wx = theme.weather;
  if (wx.kind === 'fireworks') {
    nextFirework -= dt;
    if (nextFirework <= 0) {
      nextFirework = rand(.6, 1.8);
      const x = rand(T * 3, W - T * 3), y = rand(T * 2, H * .6), hue = rand(0, 360);
      for (let i = 0; i < 26; i++) {
        const a = (i / 26) * Math.PI * 2, s = rand(30, 55);
        emit({ x, y, vx: Math.cos(a) * s, vy: Math.sin(a) * s, g: 25, life: rand(.9, 1.4), color: `hsl(${hue} 95% 65%)`, size: rand(.8, 1.4), glow: true });
      }
    }
    return;
  }
  for (const w of weather) {
    w.phase += dt;
    if (w.kind === 'fireflies') {
      w.vx += rand(-20, 20) * dt; w.vy += rand(-20, 20) * dt;
      w.vx = Math.max(-10, Math.min(10, w.vx)); w.vy = Math.max(-10, Math.min(10, w.vy));
      w.x = (w.x + w.vx * dt + W) % W; w.y = (w.y + w.vy * dt + H) % H;
      continue;
    }
    w.y += w.vy * dt;
    w.x += Math.sin(w.phase * 1.5) * (w.kind === 'snow' ? 6 : 12) * dt;
    if (w.y > H + 10 || w.y < -12) Object.assign(w, newWeather(wx, false));
  }
}

function scrollPos(sc) {
  const to = sprites.get(sc.to);
  if (!to) return null;
  const t = Math.min(sc.t, 1);
  return { x: sc.x + (to.x - sc.x) * t, y: sc.y + (to.y - sc.y) * t - Math.sin(t * Math.PI) * 30 };
}

// ---------------------------------------------------------------- drawing
function bubble(x, y, text) {
  ctx.font = `7px ${TEXT_FONT}`;
  while (text.length > 4 && ctx.measureText(text).width > 110) text = text.slice(0, -2) + '…';
  const w = ctx.measureText(text).width + 8;
  ctx.fillStyle = 'rgba(245,238,220,.95)';
  ctx.beginPath();
  ctx.roundRect(x - w / 2, y - 20, w, 11, 3);
  ctx.moveTo(x - 3, y - 9); ctx.lineTo(x, y - 6); ctx.lineTo(x + 3, y - 9);
  ctx.fill();
  ctx.fillStyle = '#1b1722';
  ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  ctx.fillText(text, x, y - 14.5);
}

function glowDot(x, y, r, color, alpha) {
  ctx.globalAlpha = alpha;
  ctx.fillStyle = color;
  ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();
  ctx.globalAlpha = alpha * .25;
  ctx.beginPath(); ctx.arc(x, y, r * 3, 0, Math.PI * 2); ctx.fill();
  ctx.globalAlpha = 1;
}

function drawTorches(now) {
  const [r, g, b] = theme.flame;
  ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  for (const room of rooms) for (const tx of [room.x + 2 * T, room.x + room.w - 2 * T]) {
    const f = 0.55 + 0.2 * Math.sin(now / 90 + tx) + 0.1 * Math.random();
    const grad = ctx.createRadialGradient(tx, room.y + 12, 1, tx, room.y + 12, 30);
    grad.addColorStop(0, `rgba(${r},${g},${b},${0.38 * f})`);
    grad.addColorStop(1, `rgba(${r},${g},${b},0)`);
    ctx.fillStyle = grad;
    ctx.fillRect(tx - 30, room.y - 18, 60, 60);
    ctx.font = `8px ${EMOJI_FONT}`;
    ctx.fillText(theme.torch, tx, room.y + 12);
  }
  if (theme.lights) {
    // blinking string lights along each top wall
    const colors = ['#ff5a5a', '#ffd166', '#7bd88f', '#5ab0ff'];
    for (const room of rooms) for (let i = 0, x = room.x + 10; x < room.x + room.w - 6; x += 12, i++) {
      const on = Math.sin(now / 400 + i * 1.7) > -.2;
      glowDot(x, room.y + T * 1.5 + Math.sin(i) * 1.5, 1.3, colors[i % 4], on ? .95 : .25);
    }
  }
}

function drawStationsGlow(now) {
  for (const room of rooms) {
    const busy = [...sprites.values()].some(sp => sp.room === room && sp.agent.state === 'working' && !sp.moving);
    if (!busy) continue;
    const s = station(room), pulse = .5 + .25 * Math.sin(now / 200);
    const grad = ctx.createRadialGradient(s.x, s.y, 2, s.x, s.y, 34);
    grad.addColorStop(0, `hsla(${HUES[room.dept] ?? 40},95%,65%,${.35 * pulse})`);
    grad.addColorStop(1, `hsla(${HUES[room.dept] ?? 40},95%,65%,0)`);
    ctx.fillStyle = grad;
    ctx.fillRect(s.x - 34, s.y - 34, 68, 68);
  }
}

function drawWeather(now) {
  const wx = theme.weather;
  ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  for (const w of weather) {
    if (w.kind === 'snow') glowDot(w.x, w.y, w.r, '#ffffff', .85);
    else if (w.kind === 'fireflies') glowDot(w.x, w.y, .9, '#f6ff8a', .35 + .6 * Math.max(0, Math.sin(now / 300 + w.phase * 5)));
    else {
      ctx.save();
      ctx.translate(w.x, w.y);
      if (w.spin) ctx.rotate(Math.sin(w.phase * w.spin) * .8);
      ctx.globalAlpha = .85;
      ctx.font = `${w.size}px ${EMOJI_FONT}`;
      ctx.fillText(w.emoji, 0, 0);
      ctx.restore();
    }
  }
  if (wx.kind === 'snow') ctx.globalAlpha = 1;
}

function drawCreatures() {
  ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  for (const c of creatures) {
    ctx.save();
    ctx.translate(c.x, c.y);
    if (c.kind === 'ghost') {
      ctx.globalAlpha = .35 + .3 * Math.sin(c.phase * 1.3);
      ctx.font = `13px ${EMOJI_FONT}`;
    } else {
      ctx.scale(c.dir * (.75 + .25 * Math.abs(Math.sin(c.phase * 14))), 1); // wing flap
      ctx.font = `10px ${EMOJI_FONT}`;
    }
    ctx.fillText(c.emoji, 0, 0);
    ctx.restore();
  }
}

function drawAgents(now) {
  const list = [...sprites.values()].sort((a, b) => a.y - b.y);
  for (const sp of list) {
    const a = sp.agent;
    const bob = sp.moving ? Math.abs(Math.sin(sp.phase)) * 2 : Math.sin(sp.phase) * 0.6;
    const hop = Math.sin(sp.jump * Math.PI) * 10 * (sp.jump > 0 ? 1 : 0);
    const shakeX = sp.shake > 0 ? Math.sin(now / 25) * 2.5 * sp.shake : 0;
    const x = sp.x + shakeX, y = sp.y - bob - hop;

    ctx.fillStyle = 'rgba(0,0,0,.45)';
    ctx.beginPath(); ctx.ellipse(sp.x, sp.y + 7, 6 - hop * .2, 2.5, 0, 0, Math.PI * 2); ctx.fill();
    if (a.state === 'needs_you') {
      const p = .5 + .5 * Math.sin(now / 220);
      ctx.strokeStyle = `rgba(233,196,106,${.4 + .5 * p})`; ctx.lineWidth = 1.2;
      ctx.beginPath(); ctx.ellipse(sp.x, sp.y + 7, 8 + p * 3, 3.5 + p, 0, 0, Math.PI * 2); ctx.stroke();
    }
    if (selected === a.id) {
      ctx.strokeStyle = theme.accent; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.ellipse(sp.x, sp.y + 7, 9, 4, 0, 0, Math.PI * 2); ctx.stroke();
    }
    ctx.font = `14px ${EMOJI_FONT}`;
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText(a.emoji, x, y);
    if (hovered === a.id || selected === a.id) {
      ctx.font = `7px ${TEXT_FONT}`;
      ctx.lineWidth = 2.5; ctx.strokeStyle = 'rgba(0,0,0,.9)'; ctx.fillStyle = '#f3e9d2';
      ctx.strokeText(a.id, sp.x, sp.y + 14);
      ctx.fillText(a.id, sp.x, sp.y + 14);
    }

    const top = y - 4;
    if (a.state === 'working' && !sp.moving) bubble(x, top, '⚒ ' + a.task.slice(0, 26));
    else if (a.state === 'needs_you') bubble(x, top - Math.abs(Math.sin(now / 250)) * 3, '❗');
    else if (a.state === 'queued') bubble(x, top, Math.sin(now / 500) > 0 ? '⏳' : '⌛');
    else if (a.state === 'failed') bubble(x, top, '💥');
    else if (sp.emote) bubble(x, top - (1 - Math.min(1, sp.emote.t)) * 2, sp.emote.icon);
  }
}

function drawParticles() {
  ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  for (const p of particles) {
    const alpha = Math.max(0, 1 - p.age / p.life);
    if (p.text) {
      ctx.globalAlpha = alpha;
      ctx.font = `bold ${p.size}px ${TEXT_FONT}`;
      ctx.lineWidth = 2.5; ctx.strokeStyle = 'rgba(0,0,0,.85)'; ctx.fillStyle = p.color;
      ctx.strokeText(p.text, p.x, p.y); ctx.fillText(p.text, p.x, p.y);
    } else if (p.emoji) {
      ctx.globalAlpha = alpha;
      ctx.font = `${p.size}px ${EMOJI_FONT}`;
      ctx.fillText(p.emoji, p.x, p.y);
    } else if (p.glow) glowDot(p.x, p.y, p.size, p.color, alpha);
    else {
      ctx.globalAlpha = alpha;
      ctx.fillStyle = p.color;
      ctx.beginPath(); ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2); ctx.fill();
    }
  }
  ctx.globalAlpha = 1;
}

function draw(now) {
  ctx.clearRect(0, 0, W, H);
  if (background) ctx.drawImage(background, 0, 0, W, H);
  drawTorches(now);
  drawStationsGlow(now);
  drawAgents(now);
  for (const sc of scrolls) {
    const p = scrollPos(sc);
    if (!p) continue;
    ctx.save(); ctx.translate(p.x, p.y); ctx.rotate(Math.sin(sc.t * 12) * .3);
    ctx.font = `10px ${EMOJI_FONT}`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText('📜', 0, 0); ctx.restore();
  }
  drawParticles();
  drawCreatures();
  drawWeather(now);

  // rooms that unlock in a later phase stay dark
  for (const r of rooms) if (!r.active) {
    ctx.fillStyle = 'rgba(5,4,8,.72)';
    ctx.fillRect(r.x, r.y, r.w, r.h);
    ctx.font = `16px ${EMOJI_FONT}`;
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText('🔒', r.x + r.w / 2, r.y + r.h / 2 - 6);
    ctx.font = 'bold 8px ui-monospace,monospace';
    ctx.fillStyle = '#9c93ad';
    ctx.fillText(`${r.name} · phase ${r.unlocks ?? '?'}`, r.x + r.w / 2, r.y + r.h / 2 + 12);
  }

  const v = ctx.createRadialGradient(W / 2, H / 2, H * .35, W / 2, H / 2, H * .85);
  v.addColorStop(0, 'rgba(0,0,0,0)');
  v.addColorStop(1, `rgba(0,0,0,${theme.vignette})`);
  ctx.fillStyle = v;
  ctx.fillRect(0, 0, W, H);
}

let last = performance.now();
function frame(now) {
  update(Math.min((now - last) / 1000, 0.1));
  last = now;
  draw(now);
  requestAnimationFrame(frame);
}

// ---------------------------------------------------------------- input
function agentAt(e) {
  const b = canvas.getBoundingClientRect();
  const x = (e.clientX - b.left) * (W / b.width), y = (e.clientY - b.top) * (H / b.height);
  let best = null, bestD = 14;
  for (const [id, sp] of sprites) {
    const d = Math.hypot(sp.x - x, sp.y - y);
    if (d < bestD) { best = id; bestD = d; }
  }
  return best;
}
canvas.addEventListener('click', e => {
  selected = agentAt(e);
  const sp = selected && sprites.get(selected);
  if (sp) { sp.jump = Math.max(sp.jump, .6); emote(sp, '👋', 1.5); }
  renderCard();
});
canvas.addEventListener('mousemove', e => { hovered = agentAt(e); canvas.title = hovered || ''; });

const picker = document.getElementById('theme');
for (const [key, t] of Object.entries(THEMES)) {
  const o = document.createElement('option');
  o.value = key; o.textContent = t.label;
  picker.append(o);
}
picker.value = THEMES[themeChoice] ? themeChoice : 'auto';
picker.addEventListener('change', () => setTheme(picker.value));
setTheme(picker.value);

async function poll() {
  const conn = document.getElementById('conn');
  try {
    const res = await fetch('/api/office', { cache: 'no-store' });
    if (!res.ok) throw new Error(String(res.status));
    applyState(await res.json());
    conn.textContent = 'live · ' + new Date().toLocaleTimeString();
  } catch (err) {
    conn.textContent = 'offline, retrying (' + err.message + ')';
  }
}

poll();
setInterval(poll, 4000);
requestAnimationFrame(frame);
