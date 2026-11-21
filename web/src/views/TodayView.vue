<script setup>
import { computed } from 'vue'
import { S } from '../store'
import TaskCard from '../components/TaskCard.vue'

const awaiting = computed(() => S.today.awaiting)
const active = computed(() => S.today.active)
const done = computed(() => S.today.done)
const nothing = computed(() => !awaiting.value.length && !active.value.length && !done.value.length)
</script>

<template>
  <div>
    <section v-if="awaiting.length" class="section">
      <div class="section-head">
        <span class="section-title">等你确认</span>
        <span class="count-pill warn">{{ awaiting.length }}</span>
      </div>
      <TaskCard v-for="t in awaiting" :key="t.id" :task="t" />
    </section>

    <section v-if="active.length" class="section">
      <div class="section-head">
        <span class="section-title">正在进行</span>
        <span class="count-pill">{{ active.length }}</span>
      </div>
      <TaskCard v-for="t in active" :key="t.id" :task="t" />
    </section>

    <section v-if="done.length" class="section">
      <div class="section-head">
        <span class="section-title">已完成</span>
        <span class="count-pill">{{ done.length }}</span>
      </div>
      <TaskCard v-for="t in done" :key="t.id" :task="t" />
    </section>

    <div v-if="nothing" class="empty" style="margin-top:24px">
      <span class="empty-ico">🌤️</span>
      今天还没有任务。<br>点右上角「＋」，把一件事交给知几。
    </div>
  </div>
</template>
