// Thin fetch wrappers. Paths are based on import.meta.env.BASE_URL (vite
// injects it from `base`): '/hiking/' in production, '/' in dev — single
// source of truth for where the app is mounted.

const BASE = import.meta.env.BASE_URL
const api = (p) => `${BASE}api/${p}`

async function getJson(path) {
  const resp = await fetch(path, { headers: { Accept: 'application/json' } })
  if (resp.status === 404) return null
  if (!resp.ok) throw new Error(`${path} → ${resp.status}`)
  return resp.json()
}

async function sendJson(method, path, body) {
  const resp = await fetch(path, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!resp.ok) {
    const text = await resp.text().catch(() => '')
    throw new Error(`${method} ${path} → ${resp.status} ${text}`)
  }
  return resp.json()
}

/** @param {'NH'|'ADK'} range */
export function getPeaks(range) {
  return getJson(api(`peaks?range=${range}`))
}

export function getPeak(id) {
  return getJson(api(`peaks/${id}`))
}

export function createHike(body) {
  return sendJson('POST', api('hikes'), body)
}

export function updateHike(id, body) {
  return sendJson('PUT', api(`hikes/${id}`), body)
}

/**
 * Weather for a trailhead on a given date. Never throws — resolves to
 * {ok: false} on any failure so callers degrade to manual entry.
 */
export async function getWeather(lat, lon, dateStr) {
  try {
    return await getJson(api(`weather?lat=${lat}&lon=${lon}&date=${dateStr}`))
  } catch {
    return { ok: false }
  }
}
