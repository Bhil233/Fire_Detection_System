<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";

const apiBase = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

const manualSelectedFile = ref(null);
const manualPreviewUrl = ref("");
const manualLoading = ref(false);
const manualResultText = ref("");
const manualFireDetected = ref(false);
const manualErrorText = ref("");
const manualCanUpload = computed(
  () => !!manualSelectedFile.value && !manualLoading.value
);

const scriptPreviewUrl = ref("");
const scriptResultText = ref("");
const scriptFireDetected = ref(false);
const scriptErrorText = ref("");
const scriptSocketConnected = ref(false);
const activeMenu = ref("fire_detection");

const monitorRows = ref([]);
const monitorLoading = ref(false);
const monitorSubmitting = ref(false);
const monitorErrorText = ref("");
const monitorForm = ref({
  id: null,
  scene_image_file: null,
  scene_image_preview: "",
  remark: "",
});

let scriptSocket = null;
let scriptReconnectTimer = null;

function getWsBaseUrl(httpBase) {
  if (httpBase.startsWith("https://")) {
    return `wss://${httpBase.slice("https://".length)}`;
  }
  if (httpBase.startsWith("http://")) {
    return `ws://${httpBase.slice("http://".length)}`;
  }
  return httpBase;
}

function scheduleScriptReconnect() {
  if (scriptReconnectTimer !== null) {
    return;
  }
  scriptReconnectTimer = window.setTimeout(() => {
    scriptReconnectTimer = null;
    connectScriptSocket();
  }, 2000);
}

function connectScriptSocket() {
  if (
    scriptSocket &&
    (scriptSocket.readyState === WebSocket.OPEN ||
      scriptSocket.readyState === WebSocket.CONNECTING)
  ) {
    return;
  }

  const wsBase = getWsBaseUrl(apiBase);
  const wsUrl = `${wsBase}/ws/script/latest-upload-image`;
  const socket = new WebSocket(wsUrl);
  scriptSocket = socket;

  socket.onopen = () => {
    scriptSocketConnected.value = true;
    scriptErrorText.value = "";
  };

  socket.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data);
      if (payload.type !== "script_upload_result") {
        return;
      }
      if (payload.image_data_url) {
        scriptPreviewUrl.value = payload.image_data_url;
      }
      scriptFireDetected.value = !!payload.fire_detected;
      scriptResultText.value = payload.result_text || "";
      scriptErrorText.value = "";
    } catch {
      scriptErrorText.value = "脚本模块消息解析失败";
    }
  };

  socket.onclose = () => {
    if (scriptSocket === socket) {
      scriptSocket = null;
      scriptSocketConnected.value = false;
      scheduleScriptReconnect();
    }
  };

  socket.onerror = () => {
    socket.close();
  };
}

function onManualFileChange(event) {
  const file = event.target.files?.[0] || null;
  manualSelectedFile.value = file;
  manualResultText.value = "";
  manualErrorText.value = "";
  manualFireDetected.value = false;

  if (manualPreviewUrl.value) {
    URL.revokeObjectURL(manualPreviewUrl.value);
    manualPreviewUrl.value = "";
  }

  if (file) {
    manualPreviewUrl.value = URL.createObjectURL(file);
  }
}

async function detectManualFire() {
  if (!manualSelectedFile.value) {
    return;
  }

  manualLoading.value = true;
  manualResultText.value = "";
  manualErrorText.value = "";
  manualFireDetected.value = false;

  try {
    const formData = new FormData();
    formData.append("file", manualSelectedFile.value);

    const response = await fetch(`${apiBase}/api/manual/detect-fire`, {
      method: "POST",
      body: formData,
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "检测失败，请稍后重试。");
    }

    manualResultText.value = data.result_text || "";
    manualFireDetected.value = !!data.fire_detected;

    if (manualFireDetected.value) {
      window.alert("警告：检测到火灾！请立即处理并报警！");
    }
  } catch (error) {
    manualErrorText.value = error.message || "请求失败";
  } finally {
    manualLoading.value = false;
  }
}

function resetMonitorForm() {
  if (monitorForm.value.scene_image_preview?.startsWith("blob:")) {
    URL.revokeObjectURL(monitorForm.value.scene_image_preview);
  }
  monitorForm.value = {
    id: null,
    scene_image_file: null,
    scene_image_preview: "",
    remark: "",
  };
}

async function parseJsonResponse(response) {
  const text = await response.text();
  if (!text) {
    return {};
  }
  try {
    return JSON.parse(text);
  } catch {
    return { detail: text };
  }
}

async function loadMonitorRecords() {
  monitorLoading.value = true;
  monitorErrorText.value = "";

  try {
    const response = await fetch(`${apiBase}/api/data-monitor/records`);
    const data = await parseJsonResponse(response);
    if (!response.ok) {
      throw new Error(data.detail || "获取数据监控列表失败");
    }

    monitorRows.value = Array.isArray(data) ? data : [];
  } catch (error) {
    monitorErrorText.value = error.message || "请求失败";
    monitorRows.value = [];
  } finally {
    monitorLoading.value = false;
  }
}

function onMonitorImageChange(event) {
  const file = event.target.files?.[0] || null;
  if (monitorForm.value.scene_image_preview?.startsWith("blob:")) {
    URL.revokeObjectURL(monitorForm.value.scene_image_preview);
  }
  monitorForm.value.scene_image_file = file;
  if (file) {
    monitorForm.value.scene_image_preview = URL.createObjectURL(file);
  } else {
    monitorForm.value.scene_image_preview = "";
  }
}

async function saveMonitorRecord() {
  monitorSubmitting.value = true;
  monitorErrorText.value = "";

  try {
    const remark = monitorForm.value.remark.trim();

    const editingId = monitorForm.value.id;
    const isEdit = editingId !== null;
    if (!isEdit && !monitorForm.value.scene_image_file) {
      throw new Error("新增记录必须上传 jpg 图片");
    }

    const formData = new FormData();
    formData.append("remark", remark);
    if (monitorForm.value.scene_image_file) {
      formData.append("scene_image", monitorForm.value.scene_image_file);
    }

    const url = isEdit
      ? `${apiBase}/api/data-monitor/records/${editingId}`
      : `${apiBase}/api/data-monitor/records`;

    const response = await fetch(url, {
      method: isEdit ? "PUT" : "POST",
      body: formData,
    });

    const data = await parseJsonResponse(response);
    if (!response.ok) {
      throw new Error(data.detail || (isEdit ? "更新失败" : "新增失败"));
    }

    resetMonitorForm();
    await loadMonitorRecords();
  } catch (error) {
    monitorErrorText.value = error.message || "请求失败";
  } finally {
    monitorSubmitting.value = false;
  }
}

function startEditMonitorRecord(record) {
  if (monitorForm.value.scene_image_preview?.startsWith("blob:")) {
    URL.revokeObjectURL(monitorForm.value.scene_image_preview);
  }
  monitorForm.value = {
    id: record.id,
    scene_image_file: null,
    scene_image_preview: resolveMonitorImageUrl(record.scene_image_url),
    remark: record.remark ?? "",
  };
}

function cancelEditMonitorRecord() {
  resetMonitorForm();
}

async function deleteMonitorRecord(recordId) {
  if (!window.confirm("确认删除这条监控记录吗？")) {
    return;
  }

  monitorErrorText.value = "";
  try {
    const response = await fetch(`${apiBase}/api/data-monitor/records/${recordId}`, {
      method: "DELETE",
    });

    const data = await parseJsonResponse(response);
    if (!response.ok) {
      throw new Error(data.detail || "删除失败");
    }

    await loadMonitorRecords();
    if (monitorForm.value.id === recordId) {
      resetMonitorForm();
    }
  } catch (error) {
    monitorErrorText.value = error.message || "请求失败";
  }
}

function formatDateTime(value) {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

function resolveMonitorImageUrl(url) {
  if (!url) {
    return "";
  }
  if (url.startsWith("http://") || url.startsWith("https://")) {
    return url;
  }
  if (url.startsWith("/")) {
    return `${apiBase}${url}`;
  }
  return `${apiBase}/${url}`;
}

watch(
  activeMenu,
  (menu) => {
    if (menu === "data_monitor") {
      void loadMonitorRecords();
    }
  },
  { immediate: true }
);

onMounted(() => {
  connectScriptSocket();
});

onBeforeUnmount(() => {
  if (manualPreviewUrl.value) {
    URL.revokeObjectURL(manualPreviewUrl.value);
  }
  if (scriptSocket) {
    scriptSocket.close();
    scriptSocket = null;
  }
  if (scriptReconnectTimer !== null) {
    clearTimeout(scriptReconnectTimer);
    scriptReconnectTimer = null;
  }
  if (monitorForm.value.scene_image_preview?.startsWith("blob:")) {
    URL.revokeObjectURL(monitorForm.value.scene_image_preview);
  }
});
</script>

<template>
  <main class="page">
    <h1 class="title">AI智能火灾监测系统</h1>

    <nav class="menu">
      <button
        type="button"
        class="menu-btn"
        :class="{ active: activeMenu === 'fire_detection' }"
        @click="activeMenu = 'fire_detection'"
      >
        火灾检测
      </button>
      <button
        type="button"
        class="menu-btn"
        :class="{ active: activeMenu === 'data_monitor' }"
        @click="activeMenu = 'data_monitor'"
      >
        数据监控
      </button>
    </nav>

    <div v-if="activeMenu === 'fire_detection'" class="layout">
      <aside class="sidebar">
        <section class="panel">
          <h2>模块一：手动上传</h2>
          <p class="hint">在网页手动选择图片并检测。</p>

          <input type="file" accept="image/*" @change="onManualFileChange" />

          <button :disabled="!manualCanUpload" @click="detectManualFire">
            {{ manualLoading ? "检测中..." : "开始检测" }}
          </button>
        </section>

        <section class="panel">
          <h2>模块二：脚本上传</h2>
          <p class="hint">运行上传脚本后，此处会实时显示图片与检测结果。</p>
          <p class="hint">该模块由上传脚本触发，无需网页按钮操作。</p>
        </section>
      </aside>

      <section class="workspace">
        <h2>工作区</h2>
        <section class="result-card">
          <h3>模块一结果（手动上传）</h3>
          <div v-if="manualPreviewUrl" class="preview-wrap">
            <img :src="manualPreviewUrl" alt="手动上传预览图" />
          </div>
          <p v-else class="hint">请先在左侧选择图片。</p>
          <p v-if="manualErrorText" class="error">{{ manualErrorText }}</p>
          <p v-else-if="manualResultText" :class="manualFireDetected ? 'danger' : 'safe'">
            {{ manualResultText }}
          </p>
        </section>

        <section class="result-card">
          <h3>模块二结果（脚本上传）</h3>
          <p :class="scriptSocketConnected ? 'connected' : 'disconnected'">
            {{ scriptSocketConnected ? "实时连接正常" : "连接断开，正在重连..." }}
          </p>
          <div v-if="scriptPreviewUrl" class="preview-wrap">
            <img :src="scriptPreviewUrl" alt="脚本上传预览图" />
          </div>
          <p v-else class="hint">等待脚本上传图片...</p>
          <p v-if="scriptErrorText" class="error">{{ scriptErrorText }}</p>
          <p v-else-if="scriptResultText" :class="scriptFireDetected ? 'danger' : 'safe'">
            {{ scriptResultText }}
          </p>
        </section>
      </section>
    </div>

    <section v-else class="monitor-page">
      <h2>数据监控</h2>

      <section class="monitor-form-card">
        <h3>{{ monitorForm.id === null ? "新增监控记录" : `编辑记录 #${monitorForm.id}` }}</h3>

        <div class="monitor-form-grid">
          <label class="form-item">
            <span>现场图片 (jpg)</span>
            <input type="file" accept=".jpg,.jpeg,image/jpeg,image/jpg" @change="onMonitorImageChange" />
          </label>
          <p class="hint">状态将由系统自动识别（fire/normal）。</p>

          <label class="form-item full">
            <span>备注</span>
            <textarea
              v-model="monitorForm.remark"
              rows="2"
              placeholder="可选，补充说明"
            ></textarea>
          </label>
          <div v-if="monitorForm.scene_image_preview" class="form-item full">
            <span>图片预览</span>
            <img class="table-image" :src="monitorForm.scene_image_preview" alt="现场图片预览" />
          </div>
        </div>

        <div class="monitor-actions">
          <button :disabled="monitorSubmitting" @click="saveMonitorRecord">
            {{ monitorSubmitting ? "提交中..." : monitorForm.id === null ? "新增" : "更新" }}
          </button>
          <button
            v-if="monitorForm.id !== null"
            type="button"
            class="ghost-btn"
            :disabled="monitorSubmitting"
            @click="cancelEditMonitorRecord"
          >
            取消编辑
          </button>
          <button type="button" class="ghost-btn" :disabled="monitorLoading" @click="loadMonitorRecords">
            {{ monitorLoading ? "刷新中..." : "刷新列表" }}
          </button>
        </div>
      </section>

      <p v-if="monitorErrorText" class="error">{{ monitorErrorText }}</p>

      <section class="result-card">
        <h3>监控数据列表</h3>

        <p v-if="monitorLoading" class="hint">加载中...</p>
        <p v-else-if="!monitorRows.length" class="hint">暂无数据。</p>

        <div v-else class="table-wrap">
          <table class="monitor-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>现场图片</th>
                <th>状态</th>
                <th>备注</th>
                <th>创建时间</th>
                <th>更新时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in monitorRows" :key="row.id">
                <td>{{ row.id }}</td>
                <td>
                  <img class="table-image" :src="resolveMonitorImageUrl(row.scene_image_url)" alt="现场图片" />
                  <p class="image-path">{{ row.scene_image_path }}</p>
                </td>
                <td>{{ row.status }}</td>
                <td>{{ row.remark || "-" }}</td>
                <td>{{ formatDateTime(row.created_at) }}</td>
                <td>{{ formatDateTime(row.updated_at) }}</td>
                <td class="table-actions">
                  <button type="button" class="table-btn" @click="startEditMonitorRecord(row)">编辑</button>
                  <button type="button" class="table-btn danger-btn" @click="deleteMonitorRecord(row.id)">
                    删除
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
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
  padding: 24px;
  display: grid;
  gap: 16px;
  align-content: start;
  width: min(1200px, 100%);
  margin: 0 auto;
}

.title {
  margin: 0;
  color: #7c2d12;
  font-size: 30px;
}

.menu {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.layout {
  display: grid;
  grid-template-columns: minmax(320px, 380px) minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

.sidebar {
  display: grid;
  gap: 16px;
}

.panel {
  background: #ffffff;
  border-radius: 16px;
  padding: 20px;
  box-shadow: 0 18px 40px rgba(187, 52, 0, 0.15);
  display: grid;
  gap: 12px;
}

.workspace {
  min-height: 240px;
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid #fed7aa;
  border-radius: 16px;
  padding: 20px;
  display: grid;
  gap: 12px;
  align-content: start;
}

.monitor-page {
  background: rgba(255, 255, 255, 0.8);
  border: 1px solid #fed7aa;
  border-radius: 16px;
  padding: 20px;
  display: grid;
  gap: 12px;
}

.monitor-form-card,
.result-card {
  background: #fff;
  border-radius: 12px;
  border: 1px solid #fed7aa;
  padding: 14px;
  display: grid;
  gap: 10px;
}

.monitor-form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(200px, 1fr));
  gap: 10px;
}

.form-item {
  display: grid;
  gap: 6px;
}

.form-item span {
  font-size: 14px;
  color: #7c2d12;
  font-weight: 600;
}

.form-item.full {
  grid-column: 1 / -1;
}

.monitor-actions,
.table-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.table-wrap {
  overflow-x: auto;
}

.monitor-table {
  width: 100%;
  border-collapse: collapse;
  min-width: 820px;
}

.monitor-table th,
.monitor-table td {
  border: 1px solid #fde3cf;
  padding: 8px 10px;
  text-align: left;
  font-size: 14px;
}

.monitor-table th {
  background: #fff7ed;
  color: #7c2d12;
}

.table-image {
  width: 96px;
  height: 72px;
  object-fit: cover;
  border-radius: 8px;
  border: 1px solid #f3f4f6;
  background: #fff;
}

.image-path {
  margin: 6px 0 0;
  max-width: 240px;
  font-size: 12px;
  color: #6b7280;
  word-break: break-all;
}

h3 {
  margin: 0;
  color: #7c2d12;
  font-size: 17px;
}

h2 {
  margin: 0;
  color: #7c2d12;
}

.hint {
  margin: 0;
  color: #4b5563;
}

input[type="file"],
input[type="text"],
input[type="number"],
textarea {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 10px;
  font: inherit;
}

textarea {
  resize: vertical;
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

.menu .menu-btn {
  border: 1px solid #fed7aa;
  padding: 10px 14px;
  font-size: 15px;
  color: #9a3412;
  background: #fff7ed;
}

.menu .menu-btn.active {
  color: #fff;
  border-color: #ea580c;
  background: linear-gradient(135deg, #ef4444, #ea580c);
}

.ghost-btn {
  color: #9a3412;
  border: 1px solid #fdba74;
  background: #fff7ed;
}

.table-btn {
  padding: 6px 10px;
  font-size: 13px;
  border-radius: 8px;
}

.danger-btn {
  background: linear-gradient(135deg, #dc2626, #b91c1c);
}

.connected {
  margin: 0;
  color: #047857;
  font-weight: 700;
}

.disconnected {
  margin: 0;
  color: #b45309;
  font-weight: 700;
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

@media (max-width: 900px) {
  .layout {
    grid-template-columns: 1fr;
  }

  .monitor-form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
