<script setup>
import { computed, onMounted, onUnmounted } from 'vue'
import { S, setTab, loadSkills, loadTab, fromHash } from './store'
import { greeting, dateLine } from './format'
import TodayView from './views/TodayView.vue'
import TasksView from './views/TasksView.vue'
import MemoryView from './views/MemoryView.vue'
import SkillsView from './views/SkillsView.vue'
import NewTaskModal from './components/NewTaskModal.vue'
import MetricsModal from './components/MetricsModal.vue'

const views = { today: TodayView, tasks: TasksView, memory: MemoryView, skills: SkillsView }
const current = computed(() => views[S.tab] || TodayView)
const tabs = [
  ['today', '今日'], ['tasks', '任务'], ['memory', '记忆'], ['skills', '技能'],
]

const brief = computed(() => {
  const m = S.metrics
  if (!m) return { text: '把事交给我，每件都带核验回执', warn: false }
  if (m.awaiting_confirmation > 0) return { text: `有 ${m.awaiting_confirmation} 件事等你确认`, warn: true }
  const done = S.today.done.length
  if (S.tab === 'today' && done > 0) {
    const passed = S.today.done.filter((t) => t.verdict && t.verdict.pass).length
    return { text: `已完成 ${done} 件事 · ${passed} 件核验通过`, warn: false }
  }
  return { text: '把事交给我，每件都带核验回执', warn: false }
})

let timer = null
const onHash = () => { const t = fromHash(); if (t !== S.tab) { S.tab = t; loadTab(t) } }
onMounted(async () => {
  window.addEventListener('hashchange', onHash)
  await loadSkills()
  await loadTab()
  timer = setInterval(() => { if (S.tab === 'today' && !S.showNewTask) loadTab('today') }, 5000)
})
onUnmounted(() => { window.removeEventListener('hashchange', onHash); clearInterval(timer) })
</script>

<template>
  <div class="app">
    <header class="topbar">
      <div class="brand">
        <span class="brand-dot">几</span>
        <span class="brand-name">知几</span>
        <span class="brand-tag">你的执行型个人代理</span>
      </div>
      <div class="top-actions">
        <button class="icon-btn" title="表现数据" @click="S.showMetrics = true">📊</button>
        <button class="icon-btn primary" title="新任务" @click="S.showNewTask = true">＋</button>
      </div>
    </header>

    <div class="greeting">
      <h1>{{ greeting() }} 👋</h1>
      <div class="date">{{ dateLine() }}</div>
      <div class="brief"><span class="dot" :class="{ warn: brief.warn }"></span>{{ brief.text }}</div>
    </div>

    <nav class="nav">
      <button v-for="[key, label] in tabs" :key="key" :class="{ on: S.tab === key }" @click="setTab(key)">{{ label }}</button>
    </nav>

    <main>
      <component :is="current" />
    </main>

    <NewTaskModal v-if="S.showNewTask" @close="S.showNewTask = false" />
    <MetricsModal v-if="S.showMetrics" @close="S.showMetrics = false" />

    <Transition name="fade">
      <div v-if="S.toast" class="toast" :class="S.toast.kind">{{ S.toast.msg }}</div>
    </Transition>
  </div>
</template>
