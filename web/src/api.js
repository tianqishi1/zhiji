const j = (r) => r.json()
const opts = (method, body) => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: body === undefined ? undefined : JSON.stringify(body),
})
export const api = {
  get: (p) => fetch(p).then(j),
  post: (p, b) => fetch(p, opts('POST', b ?? {})).then(j),
  patch: (p, b) => fetch(p, opts('PATCH', b)).then(j),
  del: (p) => fetch(p, opts('DELETE')).then(j),
}
