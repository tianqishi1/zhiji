<script setup>
import { ref, computed } from 'vue'
import { api } from '../api'
import { confFor, resolveConf, sendFeedback } from '../store'
import {
  skillMeta, statusInfo, isTerminal, summary, routeLabel, isFast,
  decidedByLabel, actionLabel, checkLabel, fmtTime, fmtCost,
} from '../format'

const props = defineProps({ task: { type: Object, required: true } })
const t = computed(() => props.task)
const st = computed(() => statusInfo(t.value))
const meta = computed(() => skillMeta(t.value.skill_id))
const conf = computed(() => confFor(t.value.id))

const open = ref(false)
const trajOpen = ref(false)
const traj = ref(null)
const rejecting = ref(false)
const reason = ref('')
const downing = ref(false)
const note = ref('')
const busy = ref(false)

const checks = computed(() => (t.value.verdict && t.value.verdict.checks) || [])
const artifacts = computed(() => {
  const r = t.value.receipt
  return (r && r.evidence && r.evidence.artifacts) || []
})
const userSignal = computed(() => t.value.verdict && t.value.verdict.user_signal)

async function approve() {
  busy.value = true
  await resolveConf(conf.value.id, true)
  busy.value = false
}
async function reject() {
  busy.value = true
  await resolveConf(conf.value.id, false, reason.value)
  rejecting.value = false
  reason.value = ''
  busy.value = false
}
async function fb(signal) {
  if (signal === 'down' && !downing.value) { downing.value = true; return }
  busy.value = true
  await sendFeedback(t.value.id, signal, signal === 'down' ? note.value : '')
  downing.value = false
  note.value = ''
  busy.value = false
}
async function toggleTraj() {
  trajOpen.value = !trajOpen.value
  if (trajOpen.value && !traj.value) {
    const d = await api.get(`/api/tasks/${t.value.id}`)
    traj.value = (d.trajectory || []).map((e) => `[${e.kind}] ${JSON.stringify(e.payload)}`).join('\n') || '（暂无轨迹）'
  }
}
function previewLines(p) {
  if (!p) return []
  const lines = []
  if (p.item) lines.push(`商品：${p.item}`)
  if (p.price != null) lines.push(`价格：¥${p.price}`)
  if (p.target_price != null) lines.push(`目标价：¥${p.target_price}`)
  if (p.note) lines.push(p.note)
  const rest = Object.entries(p).filter(([k]) => !['item', 'price', 'target_price', 'note'].includes(k))
  for (const [k, v] of rest) lines.push(`${k}：${typeof v === 'object' ? JSON.stringify(v) : v}`)
  return lines
}
</script>

<template>
  <article class="card task">
    <div class="task-head">
      <span class="task-ico" :class="st.cls">{{ st.icon }}</span>
      <div class="task-main">
        <div class="task-title">{{ t.title }}</div>
        <div class="task-sub">{{ summary(t) }}</div>
      </div>
      <span class="pill" :class="st.cls">{{ st.text }}</span>
    </div>

    <!-- 敏感动作确认 -->
    <div v-if="t.status === 'awaiting_confirmation' && conf" class="conf">
      <div class="conf-label">🔔 「{{ actionLabel(conf.action) }}」需要你点头才会执行</div>
      <div class="conf-preview">
        <div v-for="(line, i) in previewLines(conf.preview)" :key="i">{{ line }}</div>
      </div>
      <div v-if="!rejecting" class="conf-actions">
        <button class="btn primary" :disabled="busy" @click="approve">同意执行</button>
        <button class="btn ghost" :disabled="busy" @click="rejecting = true">拒绝</button>
      </div>
      <template v-else>
        <div class="inline-note">
          <input v-model="reason" type="text" placeholder="拒绝原因（可选，会写入记忆）" @keyup.enter="reject">
        </div>
        <div class="conf-actions">
          <button class="btn danger" :disabled="busy" @click="reject">确认拒绝</button>
          <button class="btn ghost" @click="rejecting = false; reason = ''">取消</button>
        </div>
      </template>
      <div class="conf-note">花钱 / 发消息 / 删除永远人工确认，自进化不能扩权</div>
    </div>

    <div class="meta-row">
      <span class="meta-chip">{{ meta.icon }} {{ t.skill_id }} v{{ t.skill_version }}</span>
      <span v-if="t.route" class="meta-chip" :class="{ fast: isFast(t.route) }">
        {{ isFast(t.route) ? '⚡ 快路径 · ' : '' }}{{ routeLabel(t.route) }}
      </span>
      <span class="meta-chip">{{ fmtCost(t.cost_tokens, t.cost_ms) }}</span>
      <span class="meta-chip">{{ fmtTime(t.created_at) }}</span>
    </div>

    <!-- 核验回执 -->
    <div v-if="t.verdict" class="receipt-toggle">
      <button class="link" @click="open = !open">{{ open ? '收起核验回执 ▴' : '核验回执 ▾' }}</button>
      <button class="link" @click="toggleTraj">{{ trajOpen ? '收起执行轨迹 ▴' : '执行轨迹 ▾' }}</button>
    </div>
    <div v-if="open && t.verdict" class="receipt">
      <div class="verdict-line" :class="t.verdict.pass ? 'ok' : 'bad'">
        {{ t.verdict.pass ? '✓ 核验通过' : '✗ 核验未通过' }}
        <span class="verdict-by">判定来源：{{ decidedByLabel(t.verdict.decided_by) }}</span>
      </div>
      <div v-if="t.verdict.reason" class="check-err">{{ t.verdict.reason }}</div>
      <div v-for="c in checks" :key="c.id" class="check-line">
        <span class="check-mark" :class="c.pass ? 'p' : 'f'">{{ c.pass ? '✓' : '✗' }}</span>
        <span>{{ checkLabel(c.id) }}</span>
        <span class="check-expr">{{ c.expr }}</span>
        <span v-if="c.error" class="check-err">{{ c.error }}</span>
      </div>
      <div v-if="!checks.length" class="check-line">
        <span class="check-expr">{{ t.verdict.reason || '无断言明细' }}</span>
      </div>
      <div v-if="artifacts.length" class="evidence">
        证据：<span v-for="(a, i) in artifacts" :key="i">{{ JSON.stringify(a) }} </span>
      </div>
    </div>
    <pre v-if="trajOpen && traj" class="traj">{{ traj }}</pre>

    <!-- 用户反馈（最高权重评测信号） -->
    <div v-if="isTerminal(t)" class="feedback-row">
      <button class="fb-btn" :class="{ 'on-up': userSignal === 'up' }" :disabled="busy" @click="fb('up')">👍 有用</button>
      <button class="fb-btn" :class="{ 'on-down': userSignal === 'down' }" :disabled="busy" @click="fb('down')">👎 不对</button>
      <span class="fb-hint">你的反馈是评测的最终裁决</span>
      <div v-if="downing" class="inline-note">
        <input v-model="note" type="text" placeholder="哪里不对？（可选，触发重探索）" @keyup.enter="fb('down')">
        <button class="btn small danger" :disabled="busy" @click="fb('down')">提交</button>
        <button class="btn small ghost" @click="downing = false; note = ''">取消</button>
      </div>
    </div>
  </article>
</template>
