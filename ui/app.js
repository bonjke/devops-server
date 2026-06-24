const API_BASE = '/api';
const API_KEY = 'devops-2match-secret-2026';

// Обёртка с автоматическим X-API-Key
function apiFetch(url, options = {}) {
    options.headers = {
        'X-API-Key': API_KEY,
        'Content-Type': 'application/json',
        ...options.headers
    };
    return fetch(url, options);
}

// Cache for DO data
let doRegionsCache = null;
let doSizesCache = null;
let doImagesCache = null;
let doSSHKeysCache = null;

// ============= TAB NAVIGATION =============

document.querySelectorAll('.tab-button').forEach(button => {
    button.addEventListener('click', () => {
        const tabId = button.dataset.tab;
        document.querySelectorAll('.tab-button').forEach(b => b.classList.remove('active'));
        button.classList.add('active');
        document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
        document.getElementById(tabId).classList.add('active');
        if (tabId === 'servers') loadServers();
        if (tabId === 'services') loadServices();
        if (tabId === 'tasks') loadTasks();
    });
});

// ============= TASK CREATOR =============

document.getElementById('action-type').addEventListener('change', (e) => {
    const actionType = e.target.value;
    document.querySelectorAll('.params-section').forEach(section => { section.style.display = 'none'; });
    const paramsSection = document.getElementById(`params-${actionType}`);
    if (paramsSection) paramsSection.style.display = 'block';
    if (actionType === 'do_droplet_create') {
        if (!doRegionsCache) loadDORegions();
        if (!doSizesCache) loadDOSizes();
        if (!doImagesCache) loadDOImages();
        if (!doSSHKeysCache) loadDOSSHKeys();
    }
});

// ============= DIGITAL OCEAN DATA LOADERS =============

async function loadDORegions() {
    const select = document.getElementById('do-create-region');
    const loading = document.getElementById('region-loading');
    try {
        loading.style.display = 'inline';
        const response = await apiFetch(`${API_BASE}/do/regions`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        doRegionsCache = data.regions;
        select.innerHTML = doRegionsCache.map(r => `<option value="${r.slug}">${r.name} (${r.slug})</option>`).join('');
    } catch(error) {
        console.error('Error loading regions:', error);
    } finally {
        loading.style.display = 'none';
    }
}

async function loadDOSizes() {
    const select = document.getElementById('do-create-size');
    const loading = document.getElementById('size-loading');
    try {
        loading.style.display = 'inline';
        const response = await apiFetch(`${API_BASE}/do/sizes`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        doSizesCache = data.sizes;
        select.innerHTML = doSizesCache.map(size => {
            const memory = (size.memory / 1024).toFixed(0);
            return `<option value="${size.slug}">${size.slug}: ${size.vcpus} vCPU, ${memory}GB RAM ($${size.price_monthly}/mo)</option>`;
        }).join('');
    } catch(error) {
        console.error('Error loading sizes:', error);
    } finally {
        loading.style.display = 'none';
    }
}

async function loadDOImages() {
    const select = document.getElementById('do-create-image');
    const loading = document.getElementById('image-loading');
    try {
        loading.style.display = 'inline';
        const response = await apiFetch(`${API_BASE}/do/images?image_type=distribution`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        doImagesCache = data.images;
        const grouped = {};
        doImagesCache.forEach(image => {
            const dist = image.distribution || 'Other';
            if (!grouped[dist]) grouped[dist] = [];
            grouped[dist].push(image);
        });
        let html = '';
        Object.keys(grouped).sort().forEach(dist => {
            html += `<optgroup label="${dist}">`;
            grouped[dist].forEach(image => { html += `<option value="${image.slug}">${image.name}</option>`; });
            html += `</optgroup>`;
        });
        select.innerHTML = html;
    } catch(error) {
        console.error('Error loading images:', error);
    } finally {
        loading.style.display = 'none';
    }
}

async function loadDOSSHKeys() {
    const select = document.getElementById('do-create-ssh-keys');
    const loading = document.getElementById('ssh-keys-loading');
    try {
        loading.style.display = 'inline';
        const response = await apiFetch(`${API_BASE}/do/ssh-keys`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        doSSHKeysCache = data.ssh_keys;
        select.innerHTML = doSSHKeysCache.length === 0
            ? '<option value="">No SSH keys found</option>'
            : doSSHKeysCache.map(key => `<option value="${key.id}">${key.name} (${key.fingerprint.substring(0, 20)}...)</option>`).join('');
    } catch(error) {
        console.error('Error loading SSH keys:', error);
    } finally {
        loading.style.display = 'none';
    }
}

// ============= TASK GENERATOR =============

function generateTaskJSON() {
    const actionType = document.getElementById('action-type').value;
    const taskId = generateUUID();

    let task = {
        task_id: taskId,
        action: actionType,
        params: {},
        metadata: { created_by: "ui", created_at: new Date().toISOString() }
    };

    switch(actionType) {
        case 'local_command':
            task.params = {
                command: document.getElementById('local-command').value,
                cwd: document.getElementById('local-cwd').value || undefined,
                timeout: parseInt(document.getElementById('local-timeout').value)
            };
            break;
        case 'ssh_command':
            task.target = document.getElementById('ssh-server').value;
            task.params = {
                command: document.getElementById('ssh-command').value,
                timeout: parseInt(document.getElementById('ssh-timeout').value)
            };
            break;
        case 'chain':
            try { task.chain = JSON.parse(document.getElementById('chain-tasks').value); }
            catch(e) { alert('Invalid JSON for chain tasks'); return; }
            break;
        case 'do_droplet_list':
            const tag = document.getElementById('do-list-tag').value;
            if (tag) task.params.tag = tag;
            break;
        case 'do_droplet_create':
            const name = document.getElementById('do-create-name').value;
            if (!name) { alert('Droplet name is required!'); return; }
            task.params = {
                name: name,
                region: document.getElementById('do-create-region').value,
                size: document.getElementById('do-create-size').value,
                image: document.getElementById('do-create-image').value
            };
            const tags = document.getElementById('do-create-tags').value;
            if (tags) task.params.tags = tags.split(',').map(t => t.trim());
            const sshKeySelect = document.getElementById('do-create-ssh-keys');
            const selectedKeys = Array.from(sshKeySelect.selectedOptions).map(opt => opt.value).filter(val => val !== '');
            if (selectedKeys.length > 0) task.params.ssh_keys = selectedKeys;
            break;
    }

    const jsonContent = document.getElementById('json-content');
    const jsonOutput = document.getElementById('json-output');
    jsonContent.textContent = JSON.stringify(task, null, 2);
    jsonOutput.style.display = 'block';
    return task;
}

async function submitTask() {
    const task = generateTaskJSON();
    if (!task) return;
    try {
        const response = await apiFetch(`${API_BASE}/tasks`, {
            method: 'POST',
            body: JSON.stringify(task)
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const result = await response.json();
        alert(`Task created: ${result.task_id}\n\nCheck Tasks tab for status.`);
    } catch(error) {
        alert(`Error creating task: ${error.message}`);
    }
}

function copyJSON() {
    const jsonContent = document.getElementById('json-content').textContent;
    navigator.clipboard.writeText(jsonContent).then(() => { alert('JSON copied to clipboard!'); });
}

function saveAsFile() {
    const jsonContent = document.getElementById('json-content').textContent;
    const task = JSON.parse(jsonContent);
    const blob = new Blob([jsonContent], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `task_${task.task_id}.json`;
    a.click();
    URL.revokeObjectURL(url);
}

// ============= SERVERS =============

async function loadServers() {
    try {
        const response = await apiFetch(`${API_BASE}/servers`);
        const servers = await response.json();
        displayServers(servers);
        updateServerDropdown(servers);
    } catch(error) {
        console.error('Error loading servers:', error);
    }
}

function displayServers(servers) {
    const container = document.getElementById('servers-list');
    if (servers.length === 0) { container.innerHTML = '<p class="empty">No servers configured</p>'; return; }
    container.innerHTML = servers.map(server => `
        <div class="item-card">
            <div class="item-header">
                <h3>${server.name}</h3>
                <span class="badge ${server.is_active ? 'badge-success' : 'badge-danger'}">${server.is_active ? 'Active' : 'Inactive'}</span>
            </div>
            <div class="item-details">
                <p><strong>ID:</strong> ${server.id}</p>
                <p><strong>IP:</strong> ${server.ip}:${server.ssh_port}</p>
                <p><strong>User:</strong> ${server.ssh_user}</p>
                <p><strong>Tags:</strong> ${server.tags.join(', ') || 'none'}</p>
            </div>
            <div class="item-actions">
                <button onclick="deleteServer('${server.id}')" class="btn btn-danger btn-sm">Delete</button>
            </div>
        </div>
    `).join('');
}

function updateServerDropdown(servers) {
    const dropdown = document.getElementById('ssh-server');
    dropdown.innerHTML = servers.map(s => `<option value="${s.id}">${s.name} (${s.ip})</option>`).join('');
}

function showAddServerForm() {
    const serverId = prompt('Server ID:');
    if (!serverId) return;
    const name = prompt('Server Name:');
    const ip = prompt('IP Address:');
    const sshKeyName = prompt('SSH Key Name:');
    if (!name || !ip || !sshKeyName) { alert('All fields are required'); return; }
    addServer({ id: serverId, name, ip, ssh_port: 22, ssh_user: 'root', ssh_key_name: sshKeyName, tags: [], services: [], is_active: true });
}

async function addServer(server) {
    try {
        const response = await apiFetch(`${API_BASE}/servers`, { method: 'POST', body: JSON.stringify(server) });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        alert('Server added successfully');
        loadServers();
    } catch(error) {
        alert(`Error adding server: ${error.message}`);
    }
}

async function deleteServer(serverId) {
    if (!confirm(`Delete server ${serverId}?`)) return;
    try {
        const response = await apiFetch(`${API_BASE}/servers/${serverId}`, { method: 'DELETE' });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        alert('Server deleted');
        loadServers();
    } catch(error) {
        alert(`Error deleting server: ${error.message}`);
    }
}

// ============= SERVICES =============

async function loadServices() {
    try {
        const response = await apiFetch(`${API_BASE}/services`);
        const services = await response.json();
        displayServices(services);
    } catch(error) {
        console.error('Error loading services:', error);
    }
}

function displayServices(services) {
    const container = document.getElementById('services-list');
    if (services.length === 0) { container.innerHTML = '<p class="empty">No services configured</p>'; return; }
    container.innerHTML = services.map(service => `
        <div class="item-card">
            <div class="item-header">
                <h3>${service.name}</h3>
                <span class="badge ${service.is_active ? 'badge-success' : 'badge-danger'}">${service.is_active ? 'Active' : 'Inactive'}</span>
            </div>
            <div class="item-details">
                <p><strong>ID:</strong> ${service.id}</p>
                <p><strong>Stack:</strong> ${service.stack}</p>
                <p><strong>Port:</strong> ${service.port || 'N/A'}</p>
                <p><strong>Deploy Path:</strong> ${service.deploy_path}</p>
            </div>
            <div class="item-actions">
                <button onclick="deleteService('${service.id}')" class="btn btn-danger btn-sm">Delete</button>
            </div>
        </div>
    `).join('');
}

function showAddServiceForm() {
    const serviceId = prompt('Service ID:');
    if (!serviceId) return;
    const name = prompt('Service Name:');
    const stack = prompt('Stack (e.g., node:18-alpine):');
    const deployPath = prompt('Deploy Path:');
    const startCommand = prompt('Start Command:');
    if (!name || !stack || !deployPath || !startCommand) { alert('All fields are required'); return; }
    addService({ id: serviceId, name, stack, deploy_path: deployPath, start_command: startCommand, is_active: true });
}

async function addService(service) {
    try {
        const response = await apiFetch(`${API_BASE}/services`, { method: 'POST', body: JSON.stringify(service) });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        alert('Service added successfully');
        loadServices();
    } catch(error) {
        alert(`Error adding service: ${error.message}`);
    }
}

async function deleteService(serviceId) {
    if (!confirm(`Delete service ${serviceId}?`)) return;
    try {
        const response = await apiFetch(`${API_BASE}/services/${serviceId}`, { method: 'DELETE' });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        alert('Service deleted');
        loadServices();
    } catch(error) {
        alert(`Error deleting service: ${error.message}`);
    }
}

// ============= TASKS =============

async function loadTasks() {
    try {
        const response = await apiFetch(`${API_BASE}/tasks`);
        const taskIds = await response.json();
        const tasks = await Promise.all(
            taskIds.slice(0, 50).map(async taskId => {
                try {
                    const res = await apiFetch(`${API_BASE}/tasks/${taskId}`);
                    return res.json();
                } catch(e) { return null; }
            })
        );
        let validTasks = tasks.filter(t => t !== null);
        const statusFilter = document.getElementById('status-filter').value;
        if (statusFilter) validTasks = validTasks.filter(t => t.status === statusFilter);
        validTasks.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
        displayTasks(validTasks);
    } catch(error) {
        console.error('Error loading tasks:', error);
    }
}

function displayTasks(tasks) {
    const container = document.getElementById('tasks-list');
    if (tasks.length === 0) { container.innerHTML = '<p class="empty">No tasks found</p>'; return; }
    container.innerHTML = tasks.map(task => {
        const statusClass = task.status === 'completed' ? 'badge-success' : task.status === 'failed' ? 'badge-danger' : 'badge-warning';
        const localTimestamp = new Date(task.timestamp).toLocaleString(undefined, { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
        return `
            <div class="item-card">
                <div class="item-header">
                    <h3>${task.task_id}</h3>
                    <span class="badge ${statusClass}">${task.status}</span>
                </div>
                <div class="item-details">
                    <p><strong>Execution Time:</strong> ${task.execution_time ? task.execution_time.toFixed(2) + 's' : 'N/A'}</p>
                    <p><strong>Timestamp:</strong> ${localTimestamp}</p>
                    ${task.error ? `<p class="error"><strong>Error:</strong> ${task.error}</p>` : ''}
                    ${task.result ? `<details><summary>Result</summary><pre>${JSON.stringify(task.result, null, 2)}</pre></details>` : ''}
                </div>
            </div>
        `;
    }).join('');
}

// ============= UTILITIES =============

function generateUUID() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        const r = Math.random() * 16 | 0;
        const v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

document.addEventListener('DOMContentLoaded', () => { loadServers(); });
