const els = {
  form: document.getElementById('sourceForm'),
  platform: document.getElementById('platform'),
  externalId: document.getElementById('externalId'),
  title: document.getElementById('title'),
  sourceMode: document.getElementById('sourceMode'),
  modeHint: document.getElementById('modeHint'),
  apiBaseUrl: document.getElementById('apiBaseUrl'),
  apiToken: document.getElementById('apiToken'),
  formStatus: document.getElementById('formStatus'),
  tableBody: document.querySelector('#sourcesTable tbody'),
};

function formatPlatform(value) {
  return String(value || '').toUpperCase();
}

function setStatus(text) {
  els.formStatus.textContent = text;
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    let details = response.statusText;
    try {
      const payload = await response.json();
      details = payload.detail || details;
    } catch (err) {
      // Keep fallback details.
    }
    throw new Error(details);
  }

  if (response.status === 204) {
    return null;
  }
  return response.json();
}

function sourceStatusBadge(isActive) {
  return `<span class="badge ${isActive ? 'active' : 'inactive'}">${isActive ? 'активен' : 'выключен'}</span>`;
}

function makeActionButton(label, className, action, id, extraAttributes = '') {
  return `<button class="btn ${className}" data-action="${action}" data-id="${id}" ${extraAttributes}>${label}</button>`;
}

function renderTable(items) {
  els.tableBody.innerHTML = '';
  if (!items.length) {
    const row = document.createElement('tr');
    row.innerHTML = '<td colspan="7">Источники пока не добавлены.</td>';
    els.tableBody.append(row);
    return;
  }

  for (const item of items) {
    const nextState = item.is_active ? 'false' : 'true';
    const row = document.createElement('tr');
    row.innerHTML = `
      <td class="mono">${item.id}</td>
      <td class="mono">${formatPlatform(item.platform)}</td>
      <td>${item.title}</td>
      <td class="mono">${item.external_id}</td>
      <td class="mono">${item.source_mode}</td>
      <td>${sourceStatusBadge(item.is_active)}</td>
      <td>
        <div class="action-row">
          ${makeActionButton('Синхр.', 'btn-secondary', 'sync', item.id)}
          ${makeActionButton(item.is_active ? 'Отключить' : 'Включить', 'btn-ghost', 'toggle', item.id, `data-next-state="${nextState}"`)}
          ${makeActionButton('Удалить', 'btn-ghost', 'delete', item.id)}
        </div>
      </td>
    `;
    els.tableBody.append(row);
  }
}

async function loadSources() {
  const sources = await fetchJson('/api/accounts');
  renderTable(sources);
}

function applyModeHint() {
  const platform = els.platform.value;
  const sourceMode = els.sourceMode.value;

  if (sourceMode === 'mock') {
    els.modeHint.textContent = 'Тестовый режим: данные генерируются локально.';
    els.apiBaseUrl.placeholder = 'не используется в mock';
    els.apiToken.placeholder = 'не используется в mock';
    return;
  }

  if (platform === 'vk') {
    els.modeHint.textContent = 'Реальные данные VK: оставьте URL пустым и укажите API токен VK.';
    els.apiBaseUrl.placeholder = 'для VK можно оставить пустым';
    els.apiToken.placeholder = 'обязательно: токен VK';
    return;
  }

  els.modeHint.textContent = 'Для Telegram/MAX нужен внешний http-адаптер (URL + токен при необходимости).';
  els.apiBaseUrl.placeholder = 'https://adapter.domain/api';
  els.apiToken.placeholder = 'токен адаптера (если нужен)';
}

async function createSource(event) {
  event.preventDefault();
  setStatus('Создание источника...');

  const platform = els.platform.value;
  const sourceMode = els.sourceMode.value;
  const apiBaseUrl = els.apiBaseUrl.value.trim() || null;
  const apiToken = els.apiToken.value.trim() || null;

  if (sourceMode === 'http') {
    if (platform === 'vk' && !apiToken) {
      setStatus('Для VK в режиме http нужен API токен VK.');
      return;
    }
    if (platform !== 'vk' && !apiBaseUrl) {
      setStatus('Для http-адаптера укажите Базовый URL API.');
      return;
    }
  }

  const payload = {
    platform,
    external_id: els.externalId.value.trim(),
    title: els.title.value.trim(),
    source_mode: sourceMode,
    api_base_url: apiBaseUrl,
    api_token: apiToken,
  };

  if (!payload.external_id || !payload.title) {
    setStatus('Заполните обязательные поля.');
    return;
  }

  await fetchJson('/api/accounts', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  els.form.reset();
  applyModeHint();
  setStatus('Источник создан.');
  await loadSources();
}

async function handleTableClick(event) {
  const button = event.target.closest('button[data-action]');
  if (!button) {
    return;
  }

  const id = Number(button.dataset.id);
  const action = button.dataset.action;

  if (action === 'sync') {
    setStatus(`Запуск синхронизации для #${id}...`);
    await fetchJson(`/api/sync/run/${id}`, { method: 'POST' });
    setStatus('Фоновая синхронизация запущена.');
    return;
  }

  if (action === 'toggle') {
    const enableState = button.dataset.nextState === 'true';
    setStatus(`${enableState ? 'Включение' : 'Отключение'} источника #${id}...`);
    await fetchJson(`/api/accounts/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_active: enableState }),
    });
    setStatus('Статус источника обновлен.');
    await loadSources();
    return;
  }

  if (action === 'delete') {
    const ok = window.confirm(`Удалить источник #${id}?`);
    if (!ok) {
      return;
    }

    setStatus(`Удаление источника #${id}...`);
    await fetchJson(`/api/accounts/${id}`, { method: 'DELETE' });
    setStatus('Источник удален.');
    await loadSources();
  }
}

function attachEvents() {
  els.form.addEventListener('submit', (event) => {
    createSource(event).catch((err) => setStatus(`Ошибка: ${err.message}`));
  });

  els.tableBody.addEventListener('click', (event) => {
    handleTableClick(event).catch((err) => setStatus(`Ошибка: ${err.message}`));
  });

  els.platform.addEventListener('change', applyModeHint);
  els.sourceMode.addEventListener('change', applyModeHint);
}

async function init() {
  attachEvents();
  applyModeHint();
  try {
    await loadSources();
    setStatus('Готово');
  } catch (err) {
    setStatus(`Ошибка: ${err.message}`);
  }
}

init();
