const BASE_PATH = document.querySelector('meta[name="app-base"]').content;
const panel = document.querySelector('[data-job]');
if (panel && ['queued','running','export_queued','exporting'].includes(panel.dataset.status)) {
  const timer = setInterval(async () => {
    try {
      const response = await fetch(`${BASE_PATH}/jobs/${panel.dataset.job}/status`);
      if (!response.ok) return;
      const state = await response.json();
      document.querySelector('#job-status').textContent = state.status;
      document.querySelector('#job-progress').textContent = state.progress;
      document.querySelector('progress').value = state.progress;
      if (['done','failed'].includes(state.status)) { clearInterval(timer); location.reload(); }
    } catch (_) { /* Next poll retries local service. */ }
  }, 2500);
}


const modelDownload = document.querySelector('[data-model-download]');
if (modelDownload && ['queued','metadata','downloading','verifying'].includes(modelDownload.dataset.modelDownload)) {
  const downloadTimer = setInterval(async () => {
    try {
      const response = await fetch(`${BASE_PATH}/admin/models/download/status`);
      if (!response.ok) return;
      const state = await response.json();
      document.querySelector('#model-download-message').textContent = state.message || '';
      const progress = document.querySelector('#model-download-progress');
      progress.max = state.total_bytes || 1;
      progress.value = state.completed_bytes || 0;
      document.querySelector('#model-download-bytes').textContent = `${((state.completed_bytes || 0)/1048576).toFixed(1)} / ${((state.total_bytes || 0)/1048576).toFixed(1)} Mo`;
      if (['ready','failed'].includes(state.status)) { clearInterval(downloadTimer); location.reload(); }
    } catch (_) { /* Retry status without launching a second download. */ }
  }, 2500);
}
