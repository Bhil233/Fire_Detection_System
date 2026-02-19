<script setup>
import { computed, ref } from "vue";

const apiBase = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";
const selectedFile = ref(null);
const previewUrl = ref("");
const loading = ref(false);
const resultText = ref("");
const fireDetected = ref(false);
const errorText = ref("");

const canUpload = computed(() => !!selectedFile.value && !loading.value);

function onFileChange(event) {
  const file = event.target.files?.[0] || null;
  selectedFile.value = file;
  resultText.value = "";
  errorText.value = "";
  fireDetected.value = false;

  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value);
    previewUrl.value = "";
  }

  if (file) {
    previewUrl.value = URL.createObjectURL(file);
  }
}

async function detectFire() {
  if (!selectedFile.value) {
    return;
  }

  loading.value = true;
  resultText.value = "";
  errorText.value = "";
  fireDetected.value = false;

  try {
    const formData = new FormData();
    formData.append("file", selectedFile.value);

    const response = await fetch(`${apiBase}/api/detect-fire`, {
      method: "POST",
      body: formData,
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "检测失败，请稍后重试。");
    }

    resultText.value = data.result_text || "";
    fireDetected.value = !!data.fire_detected;

    if (fireDetected.value) {
      window.alert("警告：检测到火灾！请立即处理并报警！");
    }
  } catch (error) {
    errorText.value = error.message || "请求失败";
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <main class="page">
    <section class="panel">
      <h1>AI智能火灾监测系统</h1>
      <p class="hint">上传现场图片，系统将通过 Qwen 模型判断是否发生火灾。</p>

      <input type="file" accept="image/*" @change="onFileChange" />

      <div v-if="previewUrl" class="preview-wrap">
        <img :src="previewUrl" alt="上传预览图" />
      </div>

      <button :disabled="!canUpload" @click="detectFire">
        {{ loading ? "检测中..." : "开始检测" }}
      </button>

      <p v-if="errorText" class="error">{{ errorText }}</p>
      <p v-else-if="resultText" :class="fireDetected ? 'danger' : 'safe'">
        {{ resultText }}
      </p>
    </section>
  </main>
</template>

<style scoped>
:global(*) {
  box-sizing: border-box;
}

:global(body) {
  margin: 0;
  min-height: 100vh;
  font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
  background: linear-gradient(135deg, #fff8f5 0%, #ffe4d9 100%);
  color: #1f2937;
}

.page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 24px;
}

.panel {
  width: min(560px, 100%);
  background: #ffffff;
  border-radius: 16px;
  padding: 24px;
  box-shadow: 0 18px 40px rgba(187, 52, 0, 0.15);
  display: grid;
  gap: 14px;
}

h1 {
  margin: 0;
  font-size: 28px;
  color: #7c2d12;
}

.hint {
  margin: 0;
  color: #4b5563;
}

input[type="file"] {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 10px;
}

.preview-wrap {
  width: 100%;
}

.preview-wrap img {
  width: 100%;
  max-height: 300px;
  object-fit: contain;
  border-radius: 12px;
  border: 1px solid #f3f4f6;
  background: #fff;
}

button {
  appearance: none;
  border: 0;
  border-radius: 10px;
  padding: 12px 16px;
  font-size: 16px;
  font-weight: 700;
  color: #fff;
  background: linear-gradient(135deg, #ef4444, #ea580c);
  cursor: pointer;
}

button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.error {
  margin: 0;
  color: #b91c1c;
}

.danger {
  margin: 0;
  color: #b91c1c;
  font-weight: 700;
}

.safe {
  margin: 0;
  color: #047857;
  font-weight: 700;
}
</style>
