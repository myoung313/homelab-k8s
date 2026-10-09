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

const canvas = document.getElementById('map');
canvas.width = W * SCALE;
canvas.height = H * SCALE;
const ctx = canvas.getContext('2d');
ctx.scale(SCALE, SCALE);

let rooms = [];          // from the API, plus pixel rects
let sprites = new Map(); // agent id -> sprite
let scrolls = [];        // handoff animations
let selected = null;
let hovered = null;
let seen = null;         // task id -> status, null until the first poll
let background = null;

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

// ---------------------------------------------------------------- static map
function rng(seed) {
  return () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };
}

function floor(g, x, y, w, h, hue, rand) {
  for (let ty = y; ty < y + h; ty += T) for (let tx = x; tx < x + w; tx += T) {
    g.fillStyle = `hsl(${hue} 12% ${15 + rand() * 6}%)`;
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
  const rand = rng(7);
  g.fillStyle = '#07060a';
  g.fillRect(0, 0, W, H);

  for (const r of rooms) {
    floor(g, r.x, r.y, r.w, r.h, HUES[r.dept] ?? 30, rand);
    // walls: a brick top wall and a thin rim
    g.fillStyle = '#2a2433';
    g.fillRect(r.x, r.y, r.w, T * 1.5);
    g.fillStyle = '#3a3247';
    for (let bx = r.x; bx < r.x + r.w; bx += 8) for (let by = r.y; by < r.y + T * 1.5; by += 6) {
      g.fillRect(bx + ((by / 6) % 2 ? 4 : 0), by, 7, 5);
    }
    g.strokeStyle = '#1b1722';
    g.lineWidth = 3;
    g.strokeRect(r.x + 1.5, r.y + 1.5, r.w - 3, r.h - 3);
    g.lineWidth = 1;
  }
  // corridors drawn last so they punch doors through the walls
  for (const r of rooms) {
    const right = rooms.find(o => o.col === r.col + 1 && o.row === r.row);
    if (right) floor(g, r.x + r.w - T, r.y + r.h / 2 - T + 8, GAP * T + 2 * T, 2 * T, 30, rand);
    const below = rooms.find(o => o.col === r.col && o.row === r.row + 1);
    if (below) floor(g, r.x + r.w / 2 - T, r.y + r.h - T, 2 * T, GAP * T + 2 * T, 30, rand);
  }
  for (const r of rooms) {
    const s = station(r);
    g.fillStyle = '#5b3a21';
    g.fillRect(s.x - 1.6 * T, s.y - 6, 3.2 * T, 12);
    g.fillStyle = '#7a5130';
    g.fillRect(s.x - 1.6 * T, s.y - 6, 3.2 * T, 3);
    g.font = `12px ${EMOJI_FONT}`;
    g.textAlign = 'center'; g.textBaseline = 'middle';
    g.fillText(STATIONS[r.dept] || '⭐', s.x, s.y - 1);
    g.font = 'bold 8px ui-monospace,monospace';
    g.fillStyle = '#e9c46a';
    g.textAlign = 'left';
    g.fillText(r.name.toUpperCase(), r.x + 6, r.y + 7);
  }
  background = off;
}

// ---------------------------------------------------------------- state sync
function applyState(s) {
  document.getElementById('spent').textContent = `$${s.spent.toFixed(2)} / $${s.budget}`;
  document.getElementById('pending').textContent = String(s.pending);
  document.getElementById('paused').style.display = s.paused ? 'inline' : 'none';

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
      sp = { x: home.x, y: home.y, tx: home.x, ty: home.y, wait: Math.random() * 3, phase: Math.random() * 6 };
      sprites.set(a.id, sp);
    }
    Object.assign(sp, { agent: a, room, home });
  }
  for (const id of [...sprites.keys()]) if (!live.has(id)) sprites.delete(id);
  assignStations();
  renderCard();

  const fresh = seen === null;
  if (fresh) {
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
    if (prev === undefined) {
      if (e.source === 'handoff' && e.parent && sprites.has(e.parent) && sprites.has(e.agent)) {
        const from = sprites.get(e.parent);
        scrolls.push({ x: from.x, y: from.y, to: e.agent, t: 0 });
      }
      log(`📥 #${e.id} ${e.agent}${e.parent ? ` ← ${e.parent}` : ''}: ${e.input}`);
    } else if (e.status === 'done') log(`✨ #${e.id} ${e.agent} finished`);
    else if (e.status === 'failed') log(`💥 #${e.id} ${e.agent} failed`);
    else if (e.status === 'skipped') log(`💤 #${e.id} ${e.agent} skipped (budget)`);
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

// ---------------------------------------------------------------- animation
function update(dt) {
  for (const sp of sprites.values()) {
    const working = sp.agent.state === 'working';
    const dx = sp.tx - sp.x, dy = sp.ty - sp.y, dist = Math.hypot(dx, dy);
    if (dist > 1) {
      const step = Math.min(dist, (working ? 45 : 22) * dt);
      sp.x += dx / dist * step; sp.y += dy / dist * step;
      sp.moving = true;
    } else {
      sp.moving = false;
      if (!working && sp.agent.state !== 'needs_you') {
        sp.wait -= dt;
        if (sp.wait <= 0) {
          const p = wanderSpot(sp);
          sp.tx = p.x; sp.ty = p.y; sp.wait = 2 + Math.random() * 5;
        }
      }
    }
    sp.phase += dt * (sp.moving ? 12 : 2);
  }
  for (const sc of scrolls) sc.t += dt / 1.6;
  scrolls = scrolls.filter(sc => sc.t < 1 && sprites.has(sc.to));
}

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

function draw(now) {
  ctx.clearRect(0, 0, W, H);
  if (background) ctx.drawImage(background, 0, 0, W, H);

  // torches flicker on every top wall
  for (const r of rooms) for (const tx of [r.x + 2 * T, r.x + r.w - 2 * T]) {
    const f = 0.55 + 0.2 * Math.sin(now / 90 + tx) + 0.1 * Math.random();
    const grad = ctx.createRadialGradient(tx, r.y + 12, 1, tx, r.y + 12, 26);
    grad.addColorStop(0, `rgba(255,170,60,${0.35 * f})`);
    grad.addColorStop(1, 'rgba(255,170,60,0)');
    ctx.fillStyle = grad;
    ctx.fillRect(tx - 26, r.y - 14, 52, 52);
    ctx.font = `8px ${EMOJI_FONT}`;
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText('🔥', tx, r.y + 12);
  }

  const list = [...sprites.values()].sort((a, b) => a.y - b.y);
  for (const sp of list) {
    const a = sp.agent;
    const bob = sp.moving ? Math.abs(Math.sin(sp.phase)) * 2 : Math.sin(sp.phase) * 0.6;
    ctx.fillStyle = 'rgba(0,0,0,.45)';
    ctx.beginPath(); ctx.ellipse(sp.x, sp.y + 7, 6, 2.5, 0, 0, Math.PI * 2); ctx.fill();
    if (selected === a.id) {
      ctx.strokeStyle = '#e9c46a'; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.ellipse(sp.x, sp.y + 7, 9, 4, 0, 0, Math.PI * 2); ctx.stroke();
    }
    ctx.font = `14px ${EMOJI_FONT}`;
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText(a.emoji, sp.x, sp.y - bob);
    if (hovered === a.id || selected === a.id) {
      ctx.font = `7px ${TEXT_FONT}`;
      ctx.lineWidth = 2.5; ctx.strokeStyle = 'rgba(0,0,0,.9)'; ctx.fillStyle = '#f3e9d2';
      ctx.strokeText(a.id, sp.x, sp.y + 14);
      ctx.fillText(a.id, sp.x, sp.y + 14);
    }

    const top = sp.y - bob - 4;
    if (a.state === 'working' && !sp.moving) bubble(sp.x, top, '⚒ ' + a.task.slice(0, 26));
    else if (a.state === 'needs_you') bubble(sp.x, top - Math.abs(Math.sin(now / 250)) * 3, '❗');
    else if (a.state === 'queued') bubble(sp.x, top, '⏳');
    else if (a.state === 'failed') bubble(sp.x, top, '💥');
  }

  for (const sc of scrolls) {
    const to = sprites.get(sc.to);
    const t = sc.t, x = sc.x + (to.x - sc.x) * t, y = sc.y + (to.y - sc.y) * t - Math.sin(t * Math.PI) * 30;
    ctx.font = `10px ${EMOJI_FONT}`;
    ctx.fillText('📜', x, y);
  }

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
}

let last = performance.now();
function frame(now) {
  update(Math.min((now - last) / 1000, 0.1));
  last = now;
  draw(now);
  requestAnimationFrame(frame);
}

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
canvas.addEventListener('click', e => { selected = agentAt(e); renderCard(); });
canvas.addEventListener('mousemove', e => { hovered = agentAt(e); canvas.title = hovered || ''; });

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
