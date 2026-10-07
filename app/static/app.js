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

