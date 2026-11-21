<script setup>
import { ref, computed } from 'vue'
import Modal from './Modal.vue'
import { api } from '../api'
import { S, toast, loadTab } from '../store'
import { skillMeta } from '../format'

const emit = defineEmits(['close'])
const sel = ref(S.skills[0] ? S.skills[0].id : '')
const intent = ref('')
const item = ref('')
const targetPrice = ref('')
const autoBuy = ref(false)
const topics = ref('')
const srcChecked = ref([])
const invMode = ref('demo')
const invExpected = ref('')
const invActual = ref('')
const advanced = ref(false)
const json = ref('{\n}')
const busy = ref(false)
const err = ref('')

const RSS_PRESETS = [
  { name: '少数派', url: 'https://sspai.com/feed' },
  { name: '阮一峰的网络日志', url: 'https://www.ruanyifeng.com/blog/atom.xml' },
  { name: 'Hacker News', url: 'https://news.ycombinator.com/rss' },
  { name: '36氪', url: 'https://36kr.com/feed' },
]
const demoItems = ['降噪耳机 WH-1000XM6', '机械键盘 Keychron K3', '显示器支架']

const INTENT_ROUTES = [
  { id: 'price-watch', re: /盯|降价|比价|价格|目标价|多少钱|便宜/ },
  { id: 'invoice-reconcile', re: /对账|账单|账目|核对|报销|发票/ },
  { id: 'daily-report', re: /日报|晨报|资讯|新闻|聚合|动态|关注|rss/i },
]

function onIntent() {
  const t = intent.value
  for (const r of INTENT_ROUTES) {
    if (r.re.test(t)) { sel.value = r.id; break }
  }
  const m = t.match(/(\d+(?:\.\d+)?)\s*(?:元|块|¥)/)
  if (m && sel.value === 'price-watch') targetPrice.value = m[1]
}

const skill = computed(() => S.skills.find((s) => s.id === sel.value))

function buildParams() {
  if (advanced.value) return JSON.parse(json.value || '{}')
  if (sel.value === 'price-watch') {
    const p = { item: item.value.trim() }
    if (targetPrice.value !== '') p.target_price = Number(targetPrice.value)
    if (autoBuy.value) p.auto_buy = true
    return p
  }
  if (sel.value === 'daily-report') {
    const ts = topics.value.split(/[,，、\s]+/).map((s) => s.trim()).filter(Boolean)
    const p = {}
    if (ts.length) p.topics = ts
    if (srcChecked.value.length) p.sources = [...srcChecked.value]
    return p
  }
  if (sel.value === 'invoice-reconcile') {
    if (invMode.value === 'demo') return { demo: true }
    return { demo: false, expected: invExpected.value.trim(), actual: invActual.value.trim() }
  }
  return {}
}

async function submit() {
  err.value = ''
  let params
  try { params = buildParams() } catch { err.value = '参数不是合法 JSON'; return }
  if (sel.value === 'price-watch' && !advanced.value && !params.item) { err.value = '请填写要盯的商品'; return }
  if (sel.value === 'invoice-reconcile' && !advanced.value && invMode.value === 'file' && (!params.expected || !params.actual)) {
    err.value = '请填写两个账单文件的路径'; return
  }
  busy.value = true
  const r = await api.post('/api/tasks', { skill_id: sel.value, params, title: intent.value.trim() || undefined })
  busy.value = false
  if (r.error) { err.value = r.error; return }
  toast('任务已提交，完成后会附上核验回执 ✓')
  emit('close')
  await loadTab()
}
</script>

<template>
  <Modal title="交给我一件事" @close="$emit('close')">
    <div class="field intent-field">
      <input v-model="intent" type="text" class="intent-input" @input="onIntent"
        placeholder="直接说，如：帮我盯降噪耳机降到 1500 元 / 来一份 AI 晨报 / 核对这个月账单">
    </div>

    <div class="skill-pick">
      <button v-for="s in S.skills" :key="s.id" class="pick" :class="{ on: sel === s.id }" @click="sel = s.id">
        <span class="pick-ico">{{ skillMeta(s.id).icon }}</span>
        <span>
          <span class="pick-name">{{ s.contract.title }}</span><br>
          <span class="pick-desc">{{ skillMeta(s.id).desc }}</span>
        </span>
      </button>
    </div>

    <template v-if="sel === 'price-watch' && !advanced">
      <div class="field">
        <label>盯什么商品</label>
        <input v-model="item" type="text" list="demo-items" placeholder="如：降噪耳机 WH-1000XM6">
        <datalist id="demo-items"><option v-for="i in demoItems" :key="i" :value="i" /></datalist>
      </div>
      <div class="field">
        <label>目标价（元）</label>
        <input v-model="targetPrice" type="number" placeholder="如：1500">
      </div>
      <label class="check-field">
        <input v-model="autoBuy" type="checkbox">
        达到目标价时模拟下单（仍需你确认，不会真花钱）
      </label>
    </template>

    <template v-else-if="sel === 'daily-report' && !advanced">
      <div class="field">
        <label>关注主题（逗号分隔，留空则不过滤）</label>
        <input v-model="topics" type="text" placeholder="如：AI, agent, 个人代理">
      </div>
      <div class="field">
        <label>信息源（勾选后真实联网抓取；全不勾则用内置演示数据）</label>
        <div class="src-list">
          <label v-for="s in RSS_PRESETS" :key="s.url" class="src-chip" :class="{ on: srcChecked.includes(s.url) }">
            <input type="checkbox" :value="s.url" v-model="srcChecked">
            {{ s.name }}
          </label>
        </div>
      </div>
    </template>

    <template v-else-if="sel === 'invoice-reconcile' && !advanced">
      <div class="field">
        <label>对哪份账单</label>
        <div class="radio-row">
          <label class="src-chip" :class="{ on: invMode === 'demo' }"><input type="radio" value="demo" v-model="invMode"> 内置演示账单</label>
          <label class="src-chip" :class="{ on: invMode === 'file' }"><input type="radio" value="file" v-model="invMode"> 我自己的账单文件</label>
        </div>
      </div>
      <template v-if="invMode === 'file'">
        <div class="field">
          <label>应有账目文件（JSON，含 entries: [{id, amount}]）</label>
          <input v-model="invExpected" type="text" placeholder="如：D:\bills\expected.json">
        </div>
        <div class="field">
          <label>实际流水文件（CSV，含 id, amount, desc 三列）</label>
          <input v-model="invActual" type="text" placeholder="如：D:\bills\alipay.csv">
        </div>
        <div class="form-note">支付宝/微信导出的账单列名不同，需先转成上述格式（转换脚本见 README）。</div>
      </template>
      <div v-else class="form-note">将使用内置演示账单逐条对账，结果附对账断言回执。</div>
    </template>

    <button class="link adv-toggle" @click="advanced = !advanced">{{ advanced ? '▴ 收起开发者模式' : '▾ 开发者：直接写 JSON 参数' }}</button>
    <div v-if="advanced" class="field">
      <textarea v-model="json" spellcheck="false" placeholder='{"item":"降噪耳机 WH-1000XM6","target_price":1500}'></textarea>
    </div>

    <div v-if="err" class="err-text">{{ err }}</div>
    <button class="btn primary block" :disabled="busy || !sel" @click="submit">{{ busy ? '提交中…' : '提交任务' }}</button>
  </Modal>
</template>
