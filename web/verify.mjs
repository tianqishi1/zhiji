// CDP 验收脚本：真实视口 + 布局测量 + 交互流程 + 截图
import { writeFileSync } from 'node:fs'

const BASE = 'http://127.0.0.1:8765'
const list = await (await fetch('http://127.0.0.1:9222/json/list')).json()
const page = list.find((t) => t.type === 'page')
const ws = new WebSocket(page.webSocketDebuggerUrl)
await new Promise((r) => (ws.onopen = r))
let id = 0
const pending = new Map()
ws.onmessage = (ev) => {
  const m = JSON.parse(ev.data)
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id) }
}
const send = (method, params = {}) =>
  new Promise((res) => { const i = ++id; pending.set(i, res); ws.send(JSON.stringify({ id: i, method, params })) })
const evaluate = async (expression) => {
  const r = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })
  if (r.result.exceptionDetails) throw new Error(JSON.stringify(r.result.exceptionDetails))
  return r.result.result.value
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const shot = async (name) => {
  const r = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true })
  writeFileSync(`D:/codex/zhiji/web/shots/${name}.png`, Buffer.from(r.result.data, 'base64'))
  console.log('shot:', name)
}

await send('Page.enable')
await send('Emulation.setDeviceMetricsOverride', { width: 480, height: 1500, deviceScaleFactor: 1, mobile: false })
await send('Page.navigate', { url: BASE + '/#today' })
await sleep(2500)

console.log('LAYOUT', await evaluate(`(() => {
  const app = document.querySelector('.app').getBoundingClientRect()
  const card = document.querySelector('.task').getBoundingClientRect()
  return { innerWidth: innerWidth, scrollWidth: document.documentElement.scrollWidth,
           app: [app.left, app.right], card: [card.left, card.right] }
})()`))
await shot('v-today')

// 打开新任务弹窗，走一遍 price-watch + auto_buy 全流程
await evaluate(`document.querySelectorAll('.top-actions .icon-btn')[1].click()`)
await sleep(400)
await shot('v-newtask')
await evaluate(`(() => {
  const picks = [...document.querySelectorAll('.pick')]
  picks.find((p) => p.textContent.includes('盯价')).click()
})()`)
await sleep(200)
const setVal = (sel, v) => evaluate(`(() => {
  const el = document.querySelector(${JSON.stringify(sel)})
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set
  setter.call(el, ${JSON.stringify(v)})
  el.dispatchEvent(new Event('input', { bubbles: true }))
})()`)
await setVal('.skill-pick ~ .field input[list]', '降噪耳机 WH-1000XM6')
await setVal('input[type=number]', '1500')
await evaluate(`document.querySelector('.check-field input').click()`)
await sleep(200)
await shot('v-newtask-filled')
await evaluate(`[...document.querySelectorAll('.modal .btn.primary')].pop().click()`)
await sleep(1200)
console.log('AFTER SUBMIT', await evaluate(`(() => {
  const t = [...document.querySelectorAll('.task')].map((x) => x.querySelector('.task-title').textContent)
  return { titles: t.slice(0, 3), conf: !!document.querySelector('.conf') }
})()`))
await shot('v-after-submit')

// 同意执行敏感动作
await evaluate(`document.querySelector('.conf .btn.primary').click()`)
await sleep(1200)
console.log('AFTER APPROVE', await evaluate(`(() => {
  const first = document.querySelector('.task')
  return { title: first.querySelector('.task-title').textContent,
           sub: first.querySelector('.task-sub').textContent,
           pill: first.querySelector('.pill').textContent }
})()`))

// 展开核验回执 + 轨迹
await evaluate(`document.querySelector('.task .link').click()`)
await sleep(300)
await shot('v-receipt')

// 其余三个 tab
for (const tab of ['tasks', 'memory', 'skills']) {
  await evaluate(`location.hash = '${tab}'`)
  await sleep(900)
  await shot('v-' + tab)
}
// 记忆页写日记弹窗
await evaluate(`location.hash = 'memory'`)
await sleep(600)
await evaluate(`[...document.querySelectorAll('.composer-foot .btn')].find((b) => b.textContent.includes('日记')).click()`)
await sleep(900)
await shot('v-diary')
// 指标弹窗
await evaluate(`document.querySelector('.modal-close').click()`)
await sleep(300)
await evaluate(`document.querySelectorAll('.top-actions .icon-btn')[0].click()`)
await sleep(400)
await shot('v-metrics')
console.log('DONE')
ws.close()
process.exit(0)


