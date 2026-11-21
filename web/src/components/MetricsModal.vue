<script setup>
import { computed } from 'vue'
import Modal from './Modal.vue'
import { S } from '../store'

defineEmits(['close'])
const m = computed(() => S.metrics || {})
const items = computed(() => [
  { label: '核验通过率', value: (m.value.verification_pass_rate ?? 0) + '%', hint: 'verdict=pass / 已评测任务' },
  { label: '快路径覆盖', value: (m.value.fast_path_coverage ?? 0) + '%', hint: '连接器 / 技能回放，不调大模型' },
  { label: '平均成本', value: `${m.value.avg_cost_tokens ?? 0} tok`, hint: `平均时延 ${m.value.avg_cost_ms ?? 0}ms` },
  { label: '任务总数', value: m.value.tasks_total ?? 0, hint: `已终结 ${m.value.terminal ?? 0} 个` },
  { label: '待确认', value: m.value.awaiting_confirmation ?? 0, hint: '敏感动作收件箱' },
  { label: '误动作事故', value: m.value.incidents ?? 0, hint: '红线指标，永远为 0' },
])
</script>

<template>
  <Modal title="知几的表现" @close="$emit('close')">
    <div class="metrics-hero">
      <div class="big-num">{{ m.north_star_no_touch_rate ?? 0 }}%</div>
      <div class="big-label">北极星 · 免干预完成率（无人工介入且核验通过）</div>
    </div>
    <div class="metric-grid">
      <div v-for="it in items" :key="it.label" class="metric">
        <b>{{ it.value }}</b>
        <span>{{ it.label }}</span>
        <small>{{ it.hint }}</small>
      </div>
    </div>
    <div class="metrics-note">所有指标与评测系统同源，不做两套统计</div>
  </Modal>
</template>
