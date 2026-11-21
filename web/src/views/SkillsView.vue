<script setup>
import { ref } from 'vue'
import { api } from '../api'
import { S, toast, loadSkills } from '../store'
import { skillMeta, SKILL_STATUS } from '../format'

const busyId = ref(null)

function rate(s) {
  const st = s.stats || {}
  return st.runs ? Math.round(((st.pass || 0) / st.runs) * 100) : 0
}
function regText(s) {
  const reg = (s.stats || {}).regression
  if (!reg) return '回归未跑'
  return reg.pass ? `回归 ✓ ${reg.total} 例全过` : '回归 ✗ 未通过'
}
async function promote(s) {
  busyId.value = s.id
  const r = await api.post(`/api/skills/${s.id}/promote`)
  busyId.value = null
  if (r.error) return toast(r.error, 'bad')
  toast(r.promoted ? '回归通过，已晋升快路径 ✓' : '回归未通过，保持候选状态', r.promoted ? 'ok' : 'bad')
  await loadSkills()
}
</script>

<template>
  <div>
    <div class="section" style="margin-top:18px">
      <div class="section-head">
        <span class="section-title">能力库</span>
        <span class="count-pill">{{ S.skills.length }}</span>
      </div>

      <div v-for="s in S.skills" :key="s.id" class="card skill-card">
        <div class="skill-head">
          <span class="skill-ico">{{ skillMeta(s.id).icon }}</span>
          <div style="flex:1">
            <div class="skill-name">{{ s.contract.title }}</div>
            <div class="skill-id">{{ s.id }} · v{{ s.version }} · 执行器 + 评测器 + 数据契约</div>
          </div>
          <span class="pill" :class="(SKILL_STATUS[s.status] || {}).cls">{{ (SKILL_STATUS[s.status] || { text: s.status }).text }}</span>
        </div>

        <div class="rate-wrap">
          <div class="rate-line"><span>核验成功率</span><b>{{ rate(s) }}%</b></div>
          <div class="rate-bar"><div class="rate-fill" :class="{ low: rate(s) < 80 }" :style="{ width: rate(s) + '%' }"></div></div>
        </div>

        <div class="stat-row">
          <span class="meta-chip">运行 {{ (s.stats || {}).runs || 0 }} 次</span>
          <span class="meta-chip fast">⚡ 快路径 {{ (s.stats || {}).fast || 0 }} 次</span>
          <span class="meta-chip">累计 {{ (s.stats || {}).tokens || 0 }} tokens</span>
          <span class="meta-chip">{{ regText(s) }}</span>
        </div>

        <div class="skill-foot">
          <button class="btn ghost small" :disabled="busyId === s.id" @click="promote(s)">
            {{ busyId === s.id ? '体检中…' : '🩺 体检 / 晋升' }}
          </button>
          <span class="fb-hint">连续失败 {{ s.fail_streak }} 次（≥2 自动降级）</span>
        </div>

        <details class="contract">
          <summary>查看三件套契约（开发者）</summary>
          <pre>{{ JSON.stringify(s.contract, null, 2) }}</pre>
        </details>
      </div>
    </div>
  </div>
</template>
