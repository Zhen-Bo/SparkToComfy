/**
 * The backend API boundary.
 * HTTP and WebSocket details appear only in this file: components and stores never call fetch or new WebSocket themselves.
 * Every address is the relative /v1 path, which the vite proxy forwards in development.
*/

import { MESSAGE_TYPE } from '@/api/ws-contract.generated'

const BASE = '/v1'

/** Where the history cap comes from: the backend sends it in a GET /v1/history response header, so the frontend keeps no copy of its own. */
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

/** Backend errors are always {code, requestId}.
 * The code is rethrown as-is, never swallowed and never turned into undefined. */
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
    // Unreachable, because the backend is down or the network dropped.
    // The TypeError that fetch throws carries no code, so it is given the contract shape here.
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

/** The cap is a backend fact (HISTORY_LIMIT in app/database.py), not a frontend guess. */
export async function fetchHistory() {
  const res = await requestRaw(`/history?sessionId=${encodeURIComponent(sessionId)}`)
  const limit = Number(res.headers.get(LIMIT_HEADER))
  return { items: await res.json(), limit: Number.isInteger(limit) && limit > 0 ? limit : null }
}

/** Clear all history; the backend soft-deletes and answers 204 with no body. */
export const clearHistory = () =>
  request(`/history?sessionId=${encodeURIComponent(sessionId)}`, { method: 'DELETE' })

/** Returns as soon as the job is accepted, 204 with no body, without waiting for an image.
 * The receipt arrives over the WebSocket and every step after that is driven by WebSocket events. */
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

export const loraCoverUrl = (file) => `${BASE}/lora/cover?lora=${encodeURIComponent(file)}`

/** Resolves when the output image has finished downloading.
 * The response carries no Content-Length, so there is no percentage to compute and waiting is the only option. */
export const preloadImage = (url) =>
  new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => resolve(url)
    img.onerror = () => reject(new ApiError('image_load_failed', null, 0))
    img.src = url
  })

/**
 * One long-lived WebSocket.
 * It reconnects itself with exponential backoff, 1s to 2s to 4s and so on up to 15s, resetting as soon as a system message arrives.
 * State is rebuilt from the system, receipt and job messages of the new connection, because the backend does not replay events.
 * Shape conversion happens here: progress {value, max} becomes {step, total}, and a preview becomes a data URL.
 * The message type strings come from the generated contract file, never written by hand.
*/
export function connectEvents(handlers) {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  const url = `${proto}://${location.host}${BASE}/ws?sessionId=${encodeURIComponent(sessionId)}`
  let timer = null
  let attempts = 0 // consecutive failures: both the backoff exponent and the retry readout in the UI

  const open = () => {
    const ws = new WebSocket(url)
    // A bad frame is dropped on its own rather than letting the exception take the handler down.
    // The connection itself is still covered by the backoff reconnect in onclose.
    ws.onmessage = (e) => {
      let msg
      try {
        msg = JSON.parse(e.data)
      } catch {
        return console.error('[ws] frame is not valid JSON, dropped', e.data)
      }
      dispatch(msg)
    }
    ws.onclose = () => {
      const nextRetryMs = Math.min(1000 * 2 ** attempts, 15000)
      attempts += 1
      // Report the drop and the next retry interval.
      // The UI locks the generate button and shows the countdown on the overlay until a reconnect brings a system message.
      handlers.onClose?.({ nextRetryMs })
      clearTimeout(timer)
      timer = setTimeout(open, nextRetryMs)
    }
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
        attempts = 0 // connected: the backoff resets, so the next drop starts again at 1s
        return handlers.onSystem?.({ comfyOnline: msg.comfyOnline })
    }
  }

  open()
}
