<script setup>
import { ref } from 'vue'
import { api } from '../api'
import { S, toast, loadMemories } from '../store'
import { kindLabel, fmtClock } from '../format'
import Modal from '../components/Modal.vue'

const kinds = [['profile', '画像'], ['preference', '偏好'], ['correction', '纠错']]
const kind = ref('preference')
const content = ref('')
const busy = ref(false)
const editing = ref(null)
const editText = ref('')
const diary = ref(null)
const diaryBusy = ref(false)

async function add() {
  if (!content.value.trim()) return
  busy.value = true
  await api.post('/api/memories', { kind: kind.value, content: content.value.trim(), source: 'user' })
  content.value = ''
  busy.value = false
  toast('已记住 ✓')
  await loadMemories()
}
function startEdit(m) { editing.value = m.id; editText.value = m.content }
async function saveEdit(m) {
  await api.patch(`/api/memories/${m.id}`, { content: editText.value })
  editing.value = null
  toast('记忆已更新')
  await loadMemories()
}
async function del(m) {
  await api.del(`/api/memories/${m.id}`)
  toast('已删除这条记忆')
  await loadMemories()
}
async function writeDiary() {
  diaryBusy.value = true
  const r = await api.post('/api/consolidate')
  diaryBusy.value = false
  diary.value = r
  await loadMemories()
}
</script>

<template>
  <div>
    <div class="card composer" style="margin-top:18px">
      <div class="kind-pills">
        <button v-for="[k, label] in kinds" :key="k" class="kind-pill" :class="{ on: kind === k }" @click="kind = k">{{ label }}</button>
      </div>
      <textarea v-model="content" placeholder="告诉知几一件关于你的事，它会带着来源记下来…" @keydown.ctrl.enter="add"></textarea>
      <div class="composer-foot">
        <button class="btn ghost small" :disabled="diaryBusy" @click="writeDiary">{{ diaryBusy ? '整理中…' : '🌙 写今晚的日记' }}</button>
        <button class="btn primary small" :disabled="busy || !content.trim()" @click="add">记住</button>
      </div>
    </div>

    <div v-for="m in S.memories" :key="m.id" class="card mem-card">
      <div class="mem-top">
        <span class="mem-kind" :class="{ diary: m.kind === 'diary' }">{{ kindLabel(m.kind) }}</span>
        <div v-if="editing !== m.id" class="mem-content">{{ m.content }}</div>
        <textarea v-else v-model="editText" style="flex:1"></textarea>
      </div>
      <div class="mem-meta">
        <span>来源：{{ m.source || '-' }} · 置信度 {{ m.confidence }} · {{ fmtClock(m.created_at) }}</span>
        <span v-if="m.locked" class="pill warn">锁定</span>
        <span class="spacer"></span>
        <span class="mem-actions">
          <template v-if="editing === m.id">
            <button class="link" @click="saveEdit(m)">保存</button>
            <button class="link" style="color:var(--dim)" @click="editing = null">取消</button>
          </template>
          <template v-else>
            <button class="link" @click="startEdit(m)">编辑</button>
            <button class="link" style="color:var(--bad)" @click="del(m)">删除</button>
          </template>
        </span>
      </div>
    </div>

    <div v-if="!S.memories.length" class="empty">
      <span class="empty-ico">🧠</span>
      还没有记忆。你告诉知几的每件事，都存在本地、随时可改可删。
    </div>

    <Modal v-if="diary" title="🌙 今晚的日记" @close="diary = null">
      <p style="font-size:14px;line-height:1.9">{{ diary.diary.content }}</p>
      <div v-if="diary.added && diary.added.length" style="margin-top:14px">
        <div class="section-title" style="margin-bottom:8px">新增记忆 {{ diary.added.length }} 条</div>
        <div v-for="m in diary.added" :key="m.id" class="form-note">{{ m.content }}</div>
      </div>
      <button class="btn primary block" style="margin-top:14px" @click="diary = null">晚安</button>
    </Modal>
  </div>
</template>
