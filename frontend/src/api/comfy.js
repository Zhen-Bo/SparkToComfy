import { MESSAGE_TYPE } from '@/api/ws-contract.generated'

const BASE = '/v1'

// Allow for the backend's heartbeat interval (PING_SECONDS in app/main.py).
const PING_TIMEOUT_MS = 45000

// Read the cap from the backend rather than duplicating its configured limit.
const LIMIT_HEADER = 'X-History-Limit'

/** sessionId acts as a bearer secret: it is the only thing keeping one person's history private from another. */
export const sessionId = (() => {
  let id = localStorage.getItem('comfy.sessionId')
  if (!id) {
    // crypto.randomUUID exists only in a secure context, which a plain-HTTP LAN address is not.
    // getRandomValues carries no such condition, and the backend accepts any string of up to 64 characters.
    id = Array.from(crypto.getRandomValues(new Uint8Array(16)), (b) =>
      b.toString(16).padStart(2, '0'),
    ).join('')
    localStorage.setItem('comfy.sessionId', id)
  }
  return id
})()

export class ApiError extends Error {
  constructor(code, requestId, status) {
    super(code)
    this.name = 'ApiError'
    this.code = code
    this.requestId = requestId
    this.status = status
  }
}

/** Error mapping happens here and the raw Response comes back, for callers that need to read a header. */
async function requestRaw(path, init) {
  let res
  try {
    res = await fetch(BASE + path, init)
  } catch {
    // Normalize fetch failures to the same error shape as API rejections.
    throw new ApiError('network_error', null, 0)
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new ApiError(body.code ?? `http_${res.status}`, body.requestId ?? null, res.status)
  }
  return res
}

async function request(path, init) {
  const res = await requestRaw(path, init)
  return res.status === 204 ? null : res.json()
}

export const fetchWorkflows = () => request('/workflows')

export async function fetchHistory() {
  const res = await requestRaw(`/history?sessionId=${encodeURIComponent(sessionId)}`)
  const limit = Number(res.headers.get(LIMIT_HEADER))
  return { items: await res.json(), limit: Number.isInteger(limit) && limit > 0 ? limit : null }
}

export const clearHistory = () =>
  request(`/history?sessionId=${encodeURIComponent(sessionId)}`, { method: 'DELETE' })

/** Returns `{ promptId }` as soon as the job is accepted, without waiting for an image.
 * Every step after that arrives over the WebSocket; the receipt repeats the id for a page that connects while the job is in flight. */
export const submitGeneration = (payload) =>
  request('/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...payload, sessionId }),
  })

export const cancelJob = (promptId) =>
  request(`/jobs/${encodeURIComponent(promptId)}/cancel`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sessionId }),
  })

export const fetchJob = (promptId) =>
  request(`/jobs/${encodeURIComponent(promptId)}?sessionId=${encodeURIComponent(sessionId)}`)

export const loraCoverUrl = (file) => `${BASE}/lora/cover?lora=${encodeURIComponent(file)}`

export const preloadImage = (url) =>
  new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => resolve(url)
    img.onerror = () => reject(new ApiError('image_load_failed', null, 0))
    img.src = url
  })

/* Reconnect from the server's current-state replay; past terminal events are not replayed. */
export function connectEvents(handlers) {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  const url = `${proto}://${location.host}${BASE}/ws?sessionId=${encodeURIComponent(sessionId)}`
  let timer = null
  let attempts = 0 // consecutive failures: both the backoff exponent and the retry readout in the UI

  const open = () => {
    const ws = new WebSocket(url)
    let watchdog = null
    const dropped = () => {
      clearTimeout(watchdog)
      const nextRetryMs = Math.min(1000 * 2 ** attempts, 15000)
      attempts += 1
      handlers.onClose?.({ nextRetryMs })
      clearTimeout(timer)
      timer = setTimeout(open, nextRetryMs)
    }
    // Silent network failures can leave readyState OPEN; use frame activity rather than waiting for onclose.
    const alive = () => {
      clearTimeout(watchdog)
      watchdog = setTimeout(() => {
        ws.onmessage = ws.onclose = null
        ws.close()
        dropped()
      }, PING_TIMEOUT_MS)
    }
    ws.onopen = alive
    ws.onmessage = (e) => {
      alive()
      let msg
      try {
        msg = JSON.parse(e.data)
      } catch {
        return console.error('[ws] frame is not valid JSON, dropped', e.data)
      }
      dispatch(msg)
    }
    ws.onclose = dropped
  }

  const dispatch = (msg) => {
    switch (msg.type) {
      case MESSAGE_TYPE.RECEIPT:
        return handlers.onReceipt?.({ promptId: msg.promptId })
      case MESSAGE_TYPE.JOB:
        return handlers.onJob?.(msg)
      case MESSAGE_TYPE.PROGRESS: {
        const { value, max } = msg
        if (max <= 0) return
        return handlers.onProgress?.({ step: value, total: max })
      }
      case MESSAGE_TYPE.PREVIEW:
        return handlers.onPreview?.({ url: `data:${msg.mime};base64,${msg.data}` })
      case MESSAGE_TYPE.SYSTEM:
        attempts = 0
        return handlers.onSystem?.({ comfyOnline: msg.comfyOnline })
      case MESSAGE_TYPE.PING:
        return // liveness only; the watchdog already counted the frame
    }
  }

  open()
}
