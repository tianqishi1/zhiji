<script setup>
defineEmits(['close'])
defineProps({ title: { type: String, default: '' } })
</script>

<template>
  <Teleport to="body">
    <div class="overlay" @click.self="$emit('close')">
      <div class="modal">
        <div class="modal-head">
          <div class="modal-title">{{ title }}</div>
          <button class="modal-close" @click="$emit('close')">✕</button>
        </div>
        <slot />
      </div>
    </div>
  </Teleport>
</template>
