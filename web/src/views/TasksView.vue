<script setup>
import { ref, computed } from 'vue'
import { S } from '../store'
import TaskCard from '../components/TaskCard.vue'
import { isTerminal, isActive } from '../format'

const filter = ref('all')
const filters = [
  ['all', '全部'], ['awaiting_confirmation', '待确认'], ['active', '进行中'], ['done', '已完成'],
]
const list = computed(() => {
  if (filter.value === 'all') return S.tasks
  if (filter.value === 'active') return S.tasks.filter(isActive)
  if (filter.value === 'done') return S.tasks.filter(isTerminal)
  return S.tasks.filter((t) => t.status === filter.value)
})
</script>

<template>
  <div>
    <div class="toolbar">
      <div class="filter-chips">
        <button v-for="[k, label] in filters" :key="k" class="chip-btn" :class="{ on: filter === k }" @click="filter = k">{{ label }}</button>
      </div>
      <button class="btn primary small" @click="S.showNewTask = true">＋ 新任务</button>
    </div>
    <TaskCard v-for="t in list" :key="t.id" :task="t" />
    <div v-if="!list.length" class="empty">
      <span class="empty-ico">🗂️</span>
      这里还没有任务记录
    </div>
  </div>
</template>
