/* 把机器字段翻译成人话 */
export const SKILL_META = {
  'daily-report': { icon: '📰', desc: '聚合你关注的资讯，去重后生成日报' },
  'price-watch': { icon: '🏷️', desc: '盯住商品价格，达到目标价提醒你' },
  'invoice-reconcile': { icon: '🧾', desc: '逐条核对账单，找出差异' },
}
export const skillMeta = (id) => SKILL_META[id] || { icon: '🤖', desc: '自定义技能' }

export const STATUS = {
  delivered: { text: '已交付', cls: 'ok', icon: '✓' },
  failed: { text: '未通过', cls: 'bad', icon: '✗' },
  rejected: { text: '已拒绝', cls: 'bad', icon: '⊘' },
  awaiting_confirmation: { text: '等你确认', cls: 'warn', icon: '🔔' },
  queued: { text: '排队中', cls: 'run', icon: '…' },
  planning: { text: '规划中', cls: 'run', icon: '…' },
  executing: { text: '执行中', cls: 'run', icon: '…' },
  evaluating: { text: '核验中', cls: 'run', icon: '…' },
}
export const statusInfo = (t) => STATUS[t.status] || { text: t.status, cls: '', icon: '•' }
export const isTerminal = (t) => ['delivered', 'failed', 'rejected'].includes(t.status)
export const isActive = (t) => !isTerminal(t) && t.status !== 'awaiting_confirmation'

export const ROUTE = { connector: '连接器直连', replay: '技能回放', vision: '视觉模型' }
export const routeLabel = (r) => ROUTE[r] || r || ''
export const isFast = (r) => r === 'connector' || r === 'replay'

export const DECIDED_BY = {
  assertions: '确定性断言', judge: 'LLM 评审', user: '你的反馈', user_reject: '你的拒绝',
}
export const decidedByLabel = (d) => DECIDED_BY[d] || d || ''

export const ACTION = { pay: '付款下单', send_message: '发送消息', delete: '删除数据' }
export const actionLabel = (a) => ACTION[a] || a

export const CHECK_LABEL = {
  price_hit: '价格不高于目标价',
  fresh: '价格数据足够新鲜（10 分钟内）',
  has_items: '至少聚合到 1 条资讯',
  fields_complete: '每条资讯都有标题和链接',
  dedup: '没有重复条目',
  balanced: '账目整体平衡',
  no_mismatch: '没有差异条目',
  totals_equal: '两侧合计金额一致',
}
export const checkLabel = (id) => CHECK_LABEL[id] || id

export const KIND = { profile: '画像', preference: '偏好', correction: '纠错', diary: '日记' }
export const kindLabel = (k) => KIND[k] || k

export const SKILL_STATUS = {
  active: { text: '已上线', cls: 'ok' },
  candidate: { text: '候选', cls: 'warn' },
  demoted: { text: '已降级', cls: 'bad' },
}

/* 结果摘要：一句人话 */
export function summary(t) {
  const r = t.result || {}
  const p = t.params || {}
  if (t.status === 'awaiting_confirmation') return '事情办到一半，有个敏感动作需要你点头'
  if (isActive(t)) return '正在执行，完成后会附上核验回执'
  if (t.skill_id === 'price-watch' && r.price != null) {
    let s = `当前 ¥${r.price}`
    if (p.target_price != null) {
      s += r.price <= p.target_price ? `，已低于目标价 ¥${p.target_price} 🎉` : `，高于目标价 ¥${p.target_price}，继续盯着`
    }
    if (r.order_id) s += ' · 已模拟下单'
    return s
  }
  if (t.skill_id === 'daily-report' && r.count != null) return `为你聚合了 ${r.count} 条资讯，已去重`
  if (t.skill_id === 'invoice-reconcile' && r.balanced != null) {
    return r.balanced ? '账目一致，每一笔都对上了' : `发现 ${(r.mismatches || []).length} 处不一致，详见回执`
  }
  if (t.status === 'rejected') return '你拒绝了这个敏感动作，任务已终止'
  if (t.status === 'failed') return (t.verdict && t.verdict.reason) || '执行或核验未通过'
  const keys = Object.keys(r)
  return keys.length ? JSON.stringify(r).slice(0, 80) : '已完成'
}

export function fmtTime(ts) {
  if (!ts) return ''
  const d = new Date(ts * 1000)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}
export function fmtClock(ts) {
  if (!ts) return ''
  const d = new Date(ts * 1000)
  return `${d.getMonth() + 1}月${d.getDate()}日 ${fmtTime(ts)}`
}
export function greeting() {
  const h = new Date().getHours()
  if (h < 5) return '夜深了'
  if (h < 11) return '早上好'
  if (h < 13) return '中午好'
  if (h < 18) return '下午好'
  return '晚上好'
}
export function dateLine() {
  const d = new Date()
  const w = '日一二三四五六'[d.getDay()]
  return `${d.getMonth() + 1}月${d.getDate()}日 · 周${w}`
}
export function fmtCost(tokens, ms) {
  const tok = tokens >= 1000 ? (tokens / 1000).toFixed(1) + 'k' : String(tokens || 0)
  const sec = ms >= 1000 ? (ms / 1000).toFixed(1) + 's' : (ms || 0) + 'ms'
  return `${tok} tokens · ${sec}`
}
