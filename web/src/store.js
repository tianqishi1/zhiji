import { reactive } from 'vue'
import { api } from './api'

const TABS = ['today', 'tasks', 'memory', 'skills']
const fromHash = () => {
  const h = location.hash.replace(/^#\/?/, '')
  return TABS.includes(h) ? h : 'today'
}

export const S = reactive({
  tab: fromHash(),
  skills: [],
  today: { done: [], awaiting: [], active: [], metrics: null },
  tasks: [],
  memories: [],
  confirmations: [],
  metrics: null,
  toast: null,
  showNewTask: false,
  showMetrics: false,
})

let toastTimer = null
export function toast(msg, kind = 'ok') {
  S.toast = { msg, kind }
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => (S.toast = null), 2800)
}

export function setTab(t) {
  S.tab = t
  location.hash = t
  loadTab(t)
}

export async function loadSkills() { S.skills = await api.get('/api/skills') }
export async function loadToday() {
  const [d, c] = await Promise.all([api.get('/api/today'), api.get('/api/confirmations?status=pending')])
  S.today = d
  S.confirmations = c
  S.metrics = d.metrics
}
export async function loadTasks() {
  S.tasks = await api.get('/api/tasks')
  S.metrics = await api.get('/api/metrics')
}
export async function loadMemories() { S.memories = await api.get('/api/memories') }

export async function loadTab(tab = S.tab) {
  if (tab === 'today') await loadToday()
  else if (tab === 'tasks') await loadTasks()
  else if (tab === 'memory') await loadMemories()
  else if (tab === 'skills') await loadSkills()
}

export function confFor(taskId) {
  return S.confirmations.find((c) => c.task_id === taskId && c.status === 'pending') || null
}

export async function resolveConf(id, approve, reason = '') {
  const r = await api.post(`/api/confirmations/${id}/resolve`, { approve, reason })
  if (r.error) return toast(r.error, 'bad')
  toast(approve ? '已同意，继续执行 ✓' : '已拒绝，原因会回流记忆')
  await loadTab()
}

export async function sendFeedback(taskId, signal, note = '') {
  const r = await api.post(`/api/tasks/${taskId}/feedback`, { signal, note })
  if (r.error) return toast(r.error, 'bad')
  toast(signal === 'up' ? '谢谢反馈，已作为最高权重评测信号记录' : '已记录不满意，会触发重探索')
  await loadTab()
}

export { fromHash }
