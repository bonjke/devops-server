const API_BASE = '/api';

// API Key — берём из sessionStorage или просим ввести
function getApiKey() {
    let key = sessionStorage.getItem('devops_api_key');
    if (!key) {
        key = prompt('🔑 Enter API Key:', '');
        if (!key) { alert('API Key required'); return null; }
        sessionStorage.setItem('devops_api_key', key);
    }
    return key;
}

function clearApiKey() {
    sessionStorage.removeItem('devops_api_key');
    location.reload();
}

function apiFetch(url, options = {}) {
    const key = getApiKey();
    if (!key) return Promise.reject(new Error('No API key'));
    options.headers = { 'X-API-Key': key, 'Content-Type': 'application/json', ...options.headers };
    return fetch(url, options).then(resp => {
        if (resp.status === 403) {
            sessionStorage.removeItem('devops_api_key');
            alert('❌ Invalid API Key. Please reload and try again.');
            throw new Error('Invalid API key');
        }
        return resp;
    });
}

// ============= TABS =============

document.querySelectorAll('.tab-button').forEach(button => {
    button.addEventListener('click', () => {
        const tabId = button.dataset.tab;
        document.querySelectorAll('.tab-button').forEach(b => b.classList.remove('active'));
        button.classList.add('active');
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        document.getElementById(tabId).classList.add('active');
        if (tabId === 'servers') loadServers();
        if (tabId === 'services') loadServices();
        if (tabId === 'tasks') loadTasks();
        if (tabId === 'vdsina') loadVDSina();
    });
});

// ============= ACTION TYPE CHANGE =============

document.getElementById('action-type').addEventListener('change', (e) => {
    document.querySelectorAll('.params-section').forEach(s => s.style.display = 'none');
    const section = document.getElementById(`params-${e.target.value}`);
    if (section) section.style.display = 'block';
});

// ============= TASK GENERATOR =============

function generateTaskJSON() {
    const action = document.getElementById('action-type').value;
    const taskId = `${action}-${Date.now()}`;
    let task = { task_id: taskId, action, params: {} };

    switch(action) {
        case 'local_command':
            task.params = { command: document.getElementById('local-command').value, timeout: parseInt(document.getElementById('local-timeout').value) };
            const cwd = document.getElementById('local-cwd').value;
            if (cwd) task.params.cwd = cwd;
            break;
        case 'ssh_command':
            task.target = document.getElementById('ssh-server').value;
            task.params = { command: document.getElementById('ssh-command').value, timeout: parseInt(document.getElementById('ssh-timeout').value) };
            break;
        case 'chain':
            try { task.chain = JSON.parse(document.getElementById('chain-tasks').value); }
            catch(e) { alert('Invalid JSON'); return; }
            break;
        case 'vdsina_get_balance':
        case 'vdsina_list_servers':
        case 'vdsina_list_ssh_keys':
        case 'vdsina_list_templates':
        case 'vdsina_list_datacenters':
            task.params = {};
            break;
        case 'vdsina_get_server':
            task.params = { server_id: parseInt(document.getElementById('vdsina-server-id').value) };
            break;
        case 'vdsina_reboot_server':
            task.params = { server_id: parseInt(document.getElementById('vdsina-reboot-id').value), type: document.getElementById('vdsina-reboot-type').value };
            break;
        case 'vdsina_delete_server':
            task.params = { server_id: parseInt(document.getElementById('vdsina-delete-id').value) };
            break;
        case 'vdsina_create_backup':
            task.params = { server_id: parseInt(document.getElementById('vdsina-backup-id').value) };
            break;
        case 'vdsina_list_plans':
            task.params = { group_id: parseInt(document.getElementById('vdsina-group-id').value) };
            break;
        case 'vdsina_create_server':
            task.params = {
                name: document.getElementById('vdsina-create-name').value,
                datacenter: parseInt(document.getElementById('vdsina-create-dc').value),
                server_plan: parseInt(document.getElementById('vdsina-create-plan').value),
                template: parseInt(document.getElementById('vdsina-create-tpl').value),
                ssh_key: parseInt(document.getElementById('vdsina-create-key').value),
            };
            break;
        case 'vdsina_create_ssh_key':
            task.params = { name: document.getElementById('vdsina-key-name').value, public_key: document.getElementById('vdsina-key-data').value };
            break;
        case 'jira_create_issue':
            task.params = { project_key: document.getElementById('jira-project').value, summary: document.getElementById('jira-summary').value, description: document.getElementById('jira-desc').value, issue_type: document.getElementById('jira-type').value };
            break;
        case 'jira_get_issue':
            task.params = { issue_key: document.getElementById('jira-get-key').value };
            break;
        case 'jira_search':
            task.params = { jql: document.getElementById('jira-jql').value, max_results: parseInt(document.getElementById('jira-max').value) };
            break;
        case 'jira_add_comment':
            task.params = { issue_key: document.getElementById('jira-comment-key').value, comment: document.getElementById('jira-comment-text').value };
            break;
        case 'jira_transition_issue':
            task.params = { issue_key: document.getElementById('jira-trans-key').value, transition: document.getElementById('jira-trans-name').value };
            break;
        case 'confluence_create_page':
            task.params = { title: document.getElementById('conf-title').value, body: document.getElementById('conf-body').value, space_key: document.getElementById('conf-space').value };
            break;
        case 'confluence_get_page':
            task.params = { title: document.getElementById('conf-get-title').value };
            break;
        case 'confluence_search':
            task.params = { cql: document.getElementById('conf-cql').value };
            break;
        case 'server_install_software':
            task.target = document.getElementById('install-server').value;
            task.params = { software: document.getElementById('install-packages').value.split(',').map(s => s.trim()).filter(Boolean) };
            break;
        case 'server_run_script':
            task.target = document.getElementById('script-server').value;
            task.params = {};
            const scriptUrl = document.getElementById('script-url').value;
            const scriptContent = document.getElementById('script-content').value;
            if (scriptUrl) task.params.script_url = scriptUrl;
            else if (scriptContent) task.params.script = scriptContent;
            break;
    }

    document.getElementById('json-content').textContent = JSON.stringify(task, null, 2);
    document.getElementById('json-output').style.display = 'block';
    return task;
}

async function submitTask() {
    const task = generateTaskJSON();
    if (!task) return;
    try {
        const resp = await apiFetch(`${API_BASE}/tasks`, { method: 'POST', body: JSON.stringify(task) });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const result = await resp.json();
        alert(`✅ Task created: ${result.task_id}\n\nCheck Tasks History for result.`);
    } catch(e) {
        alert(`❌ Error: ${e.message}`);
    }
}

function copyJSON() {
    navigator.clipboard.writeText(document.getElementById('json-content').textContent)
        .then(() => alert('Copied!'));
}

function saveAsFile() {
    const text = document.getElementById('json-content').textContent;
    const task = JSON.parse(text);
    const blob = new Blob([text], { type: 'application/json' });
    const a = Object.assign(document.createElement('a'), { href: URL.createObjectURL(blob), download: `${task.task_id}.json` });
    a.click();
}

// ============= TASKS HISTORY =============

async function loadTasks() {
    const container = document.getElementById('tasks-list');
    const countEl = document.getElementById('tasks-count');
    container.innerHTML = '<p style="color:#555;">Loading...</p>';

    try {
        const resp = await apiFetch(`${API_BASE}/tasks`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const taskIds = await resp.json();

        const statusFilter = document.getElementById('status-filter').value;

        const tasks = (await Promise.all(
            taskIds.slice(0, 100).map(id =>
                apiFetch(`${API_BASE}/tasks/${id}`).then(r => r.ok ? r.json() : null).catch(() => null)
            )
        )).filter(Boolean);

        let filtered = statusFilter ? tasks.filter(t => t.status === statusFilter) : tasks;
        filtered.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

        countEl.textContent = `${filtered.length} tasks`;

        if (filtered.length === 0) {
            container.innerHTML = '<div class="empty-state">No tasks found</div>';
            return;
        }

        container.innerHTML = filtered.map(task => renderTaskCard(task)).join('');

    } catch(e) {
        container.innerHTML = `<p style="color:#f44336;">Error: ${e.message}</p>`;
    }
}

function renderTaskCard(task) {
    const statusClass = { completed: 'badge-success', failed: 'badge-danger', processing: 'badge-warning', pending: 'badge-info' }[task.status] || 'badge-info';
    const statusIcon = { completed: '✅', failed: '❌', processing: '⏳', pending: '🕐' }[task.status] || '❓';
    const ts = new Date(task.timestamp).toLocaleString('ru-RU', { day:'2-digit', month:'2-digit', year:'numeric', hour:'2-digit', minute:'2-digit', second:'2-digit' });
    const execTime = task.execution_time ? `${task.execution_time.toFixed(2)}s` : '—';

    const inputJson = {
        task_id: task.task_id,
        action: task.action || '—',
        ...(task.target ? { target: task.target } : {}),
        ...(task.params ? { params: task.params } : {}),
    };

    // Экранируем task_id для использования в id атрибуте
    const safeId = task.task_id.replace(/[^a-zA-Z0-9-_]/g, '_');

    return `
    <div class="task-card">
        <div class="task-header" onclick="toggleTask('${safeId}')">
            <div style="display:flex; align-items:center; gap:10px; flex-wrap:wrap;">
                <span class="task-id">${task.task_id}</span>
                <span class="action-badge">${task.action || '—'}</span>
            </div>
            <div style="display:flex; align-items:center; gap:12px;">
                <span style="color:#555; font-size:12px;">${ts}</span>
                <span style="color:#555; font-size:12px;">${execTime}</span>
                <span class="badge ${statusClass}">${statusIcon} ${task.status}</span>
                <span style="color:#555;">▼</span>
            </div>
        </div>
        <div class="task-body" id="task-body-${safeId}">
            <div class="task-meta">
                <span>⏱ ${execTime}</span>
                <span>🕐 ${ts}</span>
                ${task.target ? `<span>🎯 ${task.target}</span>` : ''}
            </div>

            ${task.error ? `
                <div class="json-label">❌ Error</div>
                <div class="json-block" style="color:#f44336;">${escapeHtml(task.error)}</div>
            ` : ''}

            <div class="json-label">📥 Request JSON</div>
            <pre class="json-block">${escapeHtml(JSON.stringify(inputJson, null, 2))}</pre>

            <div class="json-label">📤 Response</div>
            <pre class="json-block">${task.result ? escapeHtml(JSON.stringify(task.result, null, 2)) : '<span style="color:#555;">—</span>'}</pre>
        </div>
    </div>`;
}

function toggleTask(safeId) {
    const body = document.getElementById(`task-body-${safeId}`);
    if (body) body.classList.toggle('open');
}

function escapeHtml(str) {
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ============= VDSINA TAB =============

async function loadVDSina() {
    const container = document.getElementById('vdsina-content');
    container.innerHTML = '<p style="color:#555;">Loading VDSina data...</p>';

    try {
        const [balanceResp, serversResp, keysResp] = await Promise.all([
            submitAndPoll('vdsina-balance-ui', 'vdsina_get_balance', {}),
            submitAndPoll('vdsina-servers-ui', 'vdsina_list_servers', {}),
            submitAndPoll('vdsina-keys-ui', 'vdsina_list_ssh_keys', {}),
        ]);

        const balance = balanceResp?.balance || {};
        const servers = serversResp?.servers || [];
        const keys = keysResp?.ssh_keys || [];

        container.innerHTML = `
            <div class="vdsina-card">
                <h4>💰 Balance</h4>
                <div class="vdsina-grid">
                    <div class="vdsina-stat"><div class="label">Real</div><div class="value">${balance.real || '—'} ₽</div></div>
                    <div class="vdsina-stat"><div class="label">Bonus</div><div class="value">${balance.bonus || '0'} ₽</div></div>
                    <div class="vdsina-stat"><div class="label">Partner</div><div class="value">${balance.partner || '0'} ₽</div></div>
                </div>
            </div>
            <div class="vdsina-card">
                <h4>🖥️ Servers (${servers.length})</h4>
                ${servers.length === 0 ? '<p style="color:#555;">No servers</p>' : servers.map(s => `
                    <div style="background:#16213e; padding:10px; border-radius:6px; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center;">
                        <div>
                            <span style="color:#7eb8f7; font-weight:600;">${s.name || s.id}</span>
                            <span style="color:#555; font-size:12px; margin-left:10px;">ID: ${s.id}</span>
                        </div>
                        <div style="display:flex; gap:8px; align-items:center;">
                            ${s.ip ? `<span style="color:#ccc; font-size:13px;">${Array.isArray(s.ip) ? (s.ip[0]?.ip || '—') : s.ip}</span>` : ''}
                            <span class="badge ${s.status === 'active' ? 'badge-success' : 'badge-warning'}">${s.status || 'unknown'}</span>
                        </div>
                    </div>
                `).join('')}
            </div>
            <div class="vdsina-card">
                <h4>🔑 SSH Keys (${keys.length})</h4>
                ${keys.length === 0 ? '<p style="color:#555;">No SSH keys</p>' : keys.map(k => `
                    <div style="background:#16213e; padding:8px 12px; border-radius:6px; margin-bottom:6px; display:flex; justify-content:space-between;">
                        <span style="color:#ccc;">${k.name}</span>
                        <span style="color:#555; font-size:12px;">ID: ${k.id}</span>
                    </div>
                `).join('')}
            </div>
        `;
    } catch(e) {
        container.innerHTML = `<p style="color:#f44336;">Error: ${e.message}</p>`;
    }
}

async function submitAndPoll(taskId, action, params) {
    const task = { task_id: taskId, action, params };
    await apiFetch(`${API_BASE}/tasks`, { method: 'POST', body: JSON.stringify(task) });
    for (let i = 0; i < 20; i++) {
        await new Promise(r => setTimeout(r, 1500));
        const r = await apiFetch(`${API_BASE}/tasks/${taskId}`);
        if (r.ok) {
            const data = await r.json();
            if (data.status === 'completed') return data.result;
            if (data.status === 'failed') throw new Error(data.error);
        }
    }
    throw new Error('Timeout');
}

// ============= SERVERS =============

async function loadServers() {
    try {
        const resp = await apiFetch(`${API_BASE}/servers`);
        const servers = await resp.json();
        renderServers(servers);
        updateServerSelects(servers);
    } catch(e) { console.error(e); }
}

function renderServers(servers) {
    const el = document.getElementById('servers-list');
    if (!servers.length) { el.innerHTML = '<div class="empty-state">No servers</div>'; return; }
    el.innerHTML = servers.map(s => `
        <div class="vdsina-card">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <h4 style="margin:0 0 4px;">${s.name}</h4>
                    <span style="color:#555; font-size:12px;">ID: ${s.id} | ${s.ip}:${s.ssh_port} | ${s.ssh_user}</span>
                </div>
                <div style="display:flex; gap:8px; align-items:center;">
                    <span class="badge ${s.is_active ? 'badge-success' : 'badge-danger'}">${s.is_active ? 'Active' : 'Inactive'}</span>
                    <button onclick="deleteServer('${s.id}')" class="btn btn-danger btn-sm">Delete</button>
                </div>
            </div>
            ${s.tags?.length ? `<div style="margin-top:8px;">${s.tags.map(t => `<span style="background:#1e2a3a;color:#7eb8f7;padding:2px 8px;border-radius:4px;font-size:11px;margin-right:4px;">${t}</span>`).join('')}</div>` : ''}
        </div>
    `).join('');
}

function updateServerSelects(servers) {
    const opts = servers.map(s => `<option value="${s.id}">${s.name} (${s.ip})</option>`).join('');
    ['ssh-server', 'install-server', 'script-server'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.innerHTML = opts;
    });
}

function showAddServerForm() {
    const id = prompt('Server ID:'); if (!id) return;
    const name = prompt('Name:'); if (!name) return;
    const ip = prompt('IP:'); if (!ip) return;
    const key = prompt('SSH Key Name:'); if (!key) return;
    addServer({ id, name, ip, ssh_port: 22, ssh_user: 'root', ssh_key_name: key, tags: [], services: [], is_active: true });
}

async function addServer(server) {
    try {
        const r = await apiFetch(`${API_BASE}/servers`, { method: 'POST', body: JSON.stringify(server) });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        alert('Server added'); loadServers();
    } catch(e) { alert(`Error: ${e.message}`); }
}

async function deleteServer(id) {
    if (!confirm(`Delete ${id}?`)) return;
    try { await apiFetch(`${API_BASE}/servers/${id}`, { method: 'DELETE' }); loadServers(); }
    catch(e) { alert(`Error: ${e.message}`); }
}

// ============= SERVICES =============

async function loadServices() {
    try {
        const resp = await apiFetch(`${API_BASE}/services`);
        const services = await resp.json();
        const el = document.getElementById('services-list');
        if (!services.length) { el.innerHTML = '<div class="empty-state">No services</div>'; return; }
        el.innerHTML = services.map(s => `
            <div class="vdsina-card">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div><h4 style="margin:0 0 4px;">${s.name}</h4><span style="color:#555;font-size:12px;">${s.stack} | ${s.deploy_path}</span></div>
                    <div style="display:flex; gap:8px;">
                        <span class="badge ${s.is_active ? 'badge-success' : 'badge-danger'}">${s.is_active ? 'Active' : 'Inactive'}</span>
                        <button onclick="deleteService('${s.id}')" class="btn btn-danger btn-sm">Delete</button>
                    </div>
                </div>
            </div>
        `).join('');
    } catch(e) { console.error(e); }
}

function showAddServiceForm() {
    const id = prompt('Service ID:'); if (!id) return;
    const name = prompt('Name:'); if (!name) return;
    const stack = prompt('Stack:'); if (!stack) return;
    const path = prompt('Deploy Path:'); if (!path) return;
    const cmd = prompt('Start Command:'); if (!cmd) return;
    addService({ id, name, stack, deploy_path: path, start_command: cmd, is_active: true });
}

async function addService(service) {
    try {
        const r = await apiFetch(`${API_BASE}/services`, { method: 'POST', body: JSON.stringify(service) });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        alert('Service added'); loadServices();
    } catch(e) { alert(`Error: ${e.message}`); }
}

async function deleteService(id) {
    if (!confirm(`Delete ${id}?`)) return;
    try { await apiFetch(`${API_BASE}/services/${id}`, { method: 'DELETE' }); loadServices(); }
    catch(e) { alert(`Error: ${e.message}`); }
}

// ============= INIT =============
document.addEventListener('DOMContentLoaded', () => {
    loadServers();
    loadTasks();
});
