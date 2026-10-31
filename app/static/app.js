const state = {
  accounts: [],
  charts: {
    postTrend: null,
    audienceFlow: null,
    cumulative: null,
  },
};

const platformTitles = {
  vk: 'VK',
  telegram: 'Telegram',
  max: 'MAX',
};

const els = {
  startDate: document.getElementById('startDate'),
  endDate: document.getElementById('endDate'),
  intervalSelect: document.getElementById('intervalSelect'),
  platformSelect: document.getElementById('platformSelect'),
  accountSelect: document.getElementById('accountSelect'),
  applyFiltersBtn: document.getElementById('applyFiltersBtn'),
  exportCsvBtn: document.getElementById('exportCsvBtn'),
  syncAllBtn: document.getElementById('syncAllBtn'),
  statusText: document.getElementById('statusText'),

  kpiInflow: document.getElementById('kpiInflow'),
  kpiOutflow: document.getElementById('kpiOutflow'),
  kpiNet: document.getElementById('kpiNet'),
  kpiViews: document.getElementById('kpiViews'),
  kpiEngagement: document.getElementById('kpiEngagement'),

  topPostsTbody: document.querySelector('#topPostsTable tbody'),
  postTrendChart: document.getElementById('postTrendChart'),
  audienceFlowChart: document.getElementById('audienceFlowChart'),
  cumulativeChart: document.getElementById('cumulativeChart'),
};

function formatNumber(value) {
  return new Intl.NumberFormat('ru-RU').format(value || 0);
}

function formatPlatform(value) {
  return platformTitles[value] || String(value || '').toUpperCase();
}

function formatDateLabel(isoString, interval) {
  const date = new Date(isoString);
  if (interval === 'hour') {
    return date.toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
  }
  if (interval === 'month') {
    return date.toLocaleString('ru-RU', { month: 'short', year: 'numeric' });
  }
  return date.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' });
}

function setStatus(message) {
  els.statusText.textContent = message;
}

function buildQueryParams() {
  const params = new URLSearchParams();
  if (els.startDate.value) {
    params.set('start', `${els.startDate.value}T00:00:00Z`);
  }
  if (els.endDate.value) {
    params.set('end', `${els.endDate.value}T23:59:59Z`);
  }
  if (els.intervalSelect.value) {
    params.set('interval', els.intervalSelect.value);
  }
  if (els.platformSelect.value) {
    params.set('platform', els.platformSelect.value);
  }
  if (els.accountSelect.value) {
    params.set('account_id', els.accountSelect.value);
  }
  return params;
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    let details = response.statusText;
    try {
      const payload = await response.json();
      details = payload.detail || details;
    } catch (err) {
      // Ignore parse errors and use fallback message.
    }
    throw new Error(details);
  }
  return response.json();
}

async function loadAccounts() {
  state.accounts = await fetchJson('/api/accounts');

  const platform = els.platformSelect.value;
  const filteredAccounts = platform
    ? state.accounts.filter((item) => item.platform === platform)
    : state.accounts;

  const current = els.accountSelect.value;
  els.accountSelect.innerHTML = '<option value="">Все</option>';

  for (const account of filteredAccounts) {
    const option = document.createElement('option');
    option.value = String(account.id);
    option.textContent = `${account.title} (${formatPlatform(account.platform)})`;
    els.accountSelect.append(option);
  }

  if ([...els.accountSelect.options].some((opt) => opt.value === current)) {
    els.accountSelect.value = current;
  }
}

function destroyCharts() {
  Object.values(state.charts).forEach((chart) => {
    if (chart) {
      chart.destroy();
    }
  });
}

function renderKpis(kpis) {
  els.kpiInflow.textContent = formatNumber(kpis.inflow);
  els.kpiOutflow.textContent = formatNumber(kpis.outflow);
  els.kpiNet.textContent = formatNumber(kpis.net_growth);
  els.kpiViews.textContent = formatNumber(kpis.total_views);
  els.kpiEngagement.textContent = `${kpis.engagement_rate.toFixed(2)}%`;
}

function renderTopPosts(posts) {
  els.topPostsTbody.innerHTML = '';
  if (!posts.length) {
    const row = document.createElement('tr');
    row.innerHTML = '<td colspan="8">Нет постов для выбранных фильтров.</td>';
    els.topPostsTbody.append(row);
    return;
  }

  for (const item of posts) {
    const row = document.createElement('tr');
    row.innerHTML = `
      <td class="mono">${formatPlatform(item.platform)}</td>
      <td>${item.account_title}</td>
      <td title="${item.content_preview.replaceAll('"', '&quot;')}">${item.content_preview.slice(0, 90)}</td>
      <td>${formatNumber(item.views)}</td>
      <td>${formatNumber(item.reactions)}</td>
      <td>${formatNumber(item.comments)}</td>
      <td>${formatNumber(item.reposts)}</td>
      <td>${item.engagement_rate.toFixed(2)}%</td>
    `;
    els.topPostsTbody.append(row);
  }
}

function renderCharts(report) {
  destroyCharts();
  const interval = els.intervalSelect.value;

  const trendLabels = report.post_trend.map((row) => formatDateLabel(row.timestamp, interval));
  state.charts.postTrend = new Chart(els.postTrendChart, {
    type: 'line',
    data: {
      labels: trendLabels,
      datasets: [
        {
          label: 'Просмотры',
          data: report.post_trend.map((row) => row.views),
          borderColor: '#2cd4b9',
          backgroundColor: 'rgba(44, 212, 185, 0.16)',
          fill: true,
          tension: 0.35,
          borderWidth: 2,
        },
        {
          label: 'Реакции',
          data: report.post_trend.map((row) => row.reactions),
          borderColor: '#ff8a3d',
          backgroundColor: 'rgba(255, 138, 61, 0.1)',
          fill: false,
          tension: 0.35,
          borderWidth: 2,
        },
      ],
    },
    options: chartOptions(),
  });

  const flowLabels = report.audience_flow.map((row) => formatDateLabel(row.timestamp, interval));
  state.charts.audienceFlow = new Chart(els.audienceFlowChart, {
    type: 'bar',
    data: {
      labels: flowLabels,
      datasets: [
        {
          label: 'Приток',
          data: report.audience_flow.map((row) => row.inflow),
          backgroundColor: 'rgba(44, 212, 185, 0.7)',
        },
        {
          label: 'Отток',
          data: report.audience_flow.map((row) => row.outflow),
          backgroundColor: 'rgba(255, 92, 115, 0.7)',
        },
      ],
    },
    options: chartOptions(),
  });

  const cumulativeLabels = report.cumulative_growth.map((row) => formatDateLabel(row.timestamp, interval));
  state.charts.cumulative = new Chart(els.cumulativeChart, {
    type: 'line',
    data: {
      labels: cumulativeLabels,
      datasets: [
        {
          label: 'Накопленный рост',
          data: report.cumulative_growth.map((row) => row.value),
          borderColor: '#7aa9ff',
          backgroundColor: 'rgba(122, 169, 255, 0.2)',
          fill: true,
          tension: 0.24,
          borderWidth: 2,
        },
      ],
    },
    options: chartOptions(),
  });
}

function chartOptions() {
  return {
    maintainAspectRatio: false,
    responsive: true,
    plugins: {
      legend: {
        labels: {
          color: '#c7d5f8',
          font: {
            family: 'Space Mono',
            size: 11,
          },
        },
      },
    },
    scales: {
      x: {
        ticks: {
          color: '#8ea2cc',
          maxRotation: 0,
          autoSkip: true,
        },
        grid: {
          color: 'rgba(39, 51, 86, 0.5)',
        },
      },
      y: {
        ticks: {
          color: '#8ea2cc',
        },
        grid: {
          color: 'rgba(39, 51, 86, 0.5)',
        },
      },
    },
  };
}

async function loadReport() {
  setStatus('Загрузка отчета...');
  const params = buildQueryParams();
  const report = await fetchJson(`/api/reports/overview?${params.toString()}`);
  renderKpis(report.kpis);
  renderTopPosts(report.top_posts);
  renderCharts(report);
  setStatus('Отчет обновлен');
}

async function runSyncAll() {
  setStatus('Запуск синхронизации...');
  await fetchJson('/api/sync/run-all', { method: 'POST' });
  setStatus('Синхронизация запущена в фоне. Обновляю отчет через 2 секунды...');
  window.setTimeout(() => {
    loadReport().catch((err) => setStatus(`Ошибка: ${err.message}`));
  }, 2000);
}

function exportCsv() {
  const params = buildQueryParams();
  const url = `/api/reports/overview.csv?${params.toString()}`;
  window.open(url, '_blank', 'noopener');
}

function setupDefaults() {
  const today = new Date();
  const monthAgo = new Date();
  monthAgo.setDate(today.getDate() - 30);

  els.startDate.value = monthAgo.toISOString().slice(0, 10);
  els.endDate.value = today.toISOString().slice(0, 10);
}

function attachEvents() {
  els.applyFiltersBtn.addEventListener('click', () => {
    loadReport().catch((err) => setStatus(`Ошибка: ${err.message}`));
  });

  els.platformSelect.addEventListener('change', () => {
    loadAccounts().catch((err) => setStatus(`Ошибка: ${err.message}`));
  });

  els.syncAllBtn.addEventListener('click', () => {
    runSyncAll().catch((err) => setStatus(`Ошибка: ${err.message}`));
  });

  els.exportCsvBtn.addEventListener('click', exportCsv);
}

async function init() {
  setupDefaults();
  attachEvents();

  try {
    await loadAccounts();
    await loadReport();
  } catch (err) {
    setStatus(`Ошибка: ${err.message}`);
  }
}

init();
