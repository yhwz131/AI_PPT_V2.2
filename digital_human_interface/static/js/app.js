// ========== Auth ==========
let adminToken = sessionStorage.getItem('admin_token') || '';

function showLogin() {
    document.getElementById('loginOverlay').style.display = 'flex';
    document.getElementById('mainContainer').style.display = 'none';
}

function showMain() {
    document.getElementById('loginOverlay').style.display = 'none';
    document.getElementById('mainContainer').style.display = 'flex';
}

async function doLogin() {
    const username = document.getElementById('loginUsername').value.trim();
    const password = document.getElementById('loginPassword').value.trim();
    const errorEl = document.getElementById('loginError');
    errorEl.style.display = 'none';
    if (!username || !password) { errorEl.textContent = '请输入用户名和密码'; errorEl.style.display = 'block'; return; }
    try {
        const res = await fetch('/api/admin/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username, password }) });
        const data = await res.json();
        if (res.ok && data.token) {
            adminToken = data.token;
            sessionStorage.setItem('admin_token', adminToken);
            showMain();
            initApp();
        } else {
            errorEl.textContent = data.detail || '登录失败';
            errorEl.style.display = 'block';
        }
    } catch (e) { errorEl.textContent = '网络错误'; errorEl.style.display = 'block'; }
}

function doLogout() {
    adminToken = '';
    sessionStorage.removeItem('admin_token');
    showLogin();
    if (window._ws) { window._ws.close(); window._ws = null; }
    clearInterval(window._dashInterval);
    clearInterval(window._logfileInterval);
}

function authHeaders() { return { 'X-Admin-Token': adminToken }; }

// ========== Tab Switching ==========
let currentTab = 'dashboard';

function switchTab(tabId) {
    currentTab = tabId;
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b.dataset.tab === tabId));
    document.querySelectorAll('.tab-pane').forEach(p => p.classList.toggle('active', p.id === 'tab-' + tabId));
    if (tabId === 'dashboard') refreshDashboard();
    if (tabId === 'logfiles') loadLogFile();
    if (tabId === 'videos') loadVideoList();
    if (tabId === 'controls') { loadSchedulerJobs(); loadLogLevel(); }
}

// ========== Utilities ==========
function escHtml(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }
/** HTML 属性用（data-pdf 等） */
function escAttr(s) {
    if (s == null || s === '') return '';
    return String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
}
function fmtBytes(b) {
    if (!b || b === 0) return '0 B';
    const k = 1024, sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(b) / Math.log(k));
    return (b / Math.pow(k, i)).toFixed(1) + ' ' + sizes[i];
}

// ========== Dashboard ==========
async function refreshDashboard() {
    await Promise.all([loadSystemInfo(), loadGpuInfo(), loadServicesStatus(), loadConnectionInfo()]);
}

async function loadSystemInfo() {
    try {
        const res = await fetch('/api/system/info');
        const d = await res.json();
        if (d.status !== 'success') return;
        const s = d.system;
        document.getElementById('cpuPercent').textContent = s.cpu_percent || 0;
        document.getElementById('cpuBar').style.width = (s.cpu_percent || 0) + '%';
        document.getElementById('cpuCores').textContent = (s.cpu_count || '--') + ' 核心';
        document.getElementById('memPercent').textContent = s.memory_percent || 0;
        document.getElementById('memBar').style.width = (s.memory_percent || 0) + '%';
        document.getElementById('memDetail').textContent = fmtBytes(s.memory_used) + ' / ' + fmtBytes(s.memory_total);
        document.getElementById('diskPercent').textContent = s.disk_percent || 0;
        document.getElementById('diskBar').style.width = (s.disk_percent || 0) + '%';
        document.getElementById('diskDetail').textContent = fmtBytes(s.disk_used) + ' / ' + fmtBytes(s.disk_total);
    } catch (e) { console.error('loadSystemInfo', e); }
}

async function loadGpuInfo() {
    try {
        const res = await fetch('/api/system/gpu');
        const d = await res.json();
        if (d.status !== 'success' || !d.gpus.length) return;
        d.gpus.forEach((g, i) => {
            if (i > 1) return;
            const card = document.getElementById('gpuCard' + i);
            if (!card) return;
            card.style.display = '';
            document.getElementById('gpu' + i + 'Name').textContent = g.name;
            const memPct = g.memory_total > 0 ? Math.round(g.memory_used / g.memory_total * 100) : 0;
            document.getElementById('gpu' + i + 'MemBar').style.width = memPct + '%';
            document.getElementById('gpu' + i + 'Mem').textContent = g.memory_used + ' / ' + g.memory_total + ' MiB';
            document.getElementById('gpu' + i + 'UtilBar').style.width = g.utilization + '%';
            document.getElementById('gpu' + i + 'Util').textContent = g.utilization + '%';
            document.getElementById('gpu' + i + 'Temp').textContent = g.temperature + '°C';

            // 更新进程列表内容（保持展开/收起状态）
            const procs = g.processes || [];
            document.getElementById('gpu' + i + 'ProcCount').textContent = procs.length + ' 个进程';
            const listEl = document.getElementById('gpu' + i + 'ProcList');
            if (procs.length === 0) {
                listEl.innerHTML = '<div class="gpu-proc-empty">暂无运行中的进程</div>';
            } else {
                listEl.innerHTML = procs.map(p =>
                    `<div class="gpu-proc-row">
                        <span class="gpu-proc-pid">${p.pid}</span>
                        <span class="gpu-proc-name" title="${p.name}">${p.name}</span>
                        <span class="gpu-proc-mem">${p.memory_used} MiB</span>
                    </div>`
                ).join('');
            }
        });
    } catch (e) { console.error('loadGpuInfo', e); }
}

function toggleGpuProcs(idx) {
    const list = document.getElementById('gpu' + idx + 'ProcList');
    const chevron = document.getElementById('gpu' + idx + 'ProcChevron');
    const open = list.style.display === 'none';
    list.style.display = open ? '' : 'none';
    chevron.classList.toggle('open', open);
}

async function loadServicesStatus() {
    try {
        const res = await fetch('/api/system/services');
        const d = await res.json();
        if (d.status !== 'success') return;
        d.services.forEach(svc => {
            const el = document.getElementById('svc-' + svc.port);
            if (!el) return;
            const running = svc.status === 'running';
            el.textContent = running ? '运行中' : '已停止';
            el.style.color = running ? '#22c55e' : '#ef4444';
        });
    } catch (e) { console.error('loadServicesStatus', e); }
}

async function svcAction(action, service, btnEl) {
    const labels = { start: '启动', stop: '停止', restart: '重启' };
    const label = labels[action] || action;

    if (service === 'digital' && action === 'restart') {
        if (!confirm('重启 DigitalHuman 服务将导致控制台短暂断开，确定继续？')) return;
    } else if (action === 'stop') {
        if (!confirm(`确定${label} ${service} 服务？`)) return;
    }

    if (btnEl) { btnEl.disabled = true; btnEl.innerHTML = '<i class="fas fa-spinner fa-spin"></i>'; }

    try {
        const res = await fetch(`/api/admin/services/${action}`, {
            method: 'POST',
            headers: { ...authHeaders(), 'Content-Type': 'application/json' },
            body: JSON.stringify({ service })
        });
        if (res.status === 401) { doLogout(); return; }
        const d = await res.json();
        addSysMsg(`${service} ${label}: ${d.message || d.detail}`);
        if (d.output) addSysMsg(d.output);

        if (service === 'digital' && action === 'restart') {
            addSysMsg('服务正在重启，页面将在 10 秒后自动刷新...');
            if (btnEl) { btnEl.disabled = true; btnEl.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 重启中'; }
            setTimeout(() => location.reload(), 10000);
            return;
        }
    } catch (e) {
        if (service === 'digital' && action === 'restart') {
            addSysMsg('连接已断开，等待服务恢复...');
            setTimeout(() => location.reload(), 10000);
            return;
        }
        addSysMsg(`操作失败: ${e.message}`);
    }

    setTimeout(() => loadServicesStatus(), 3000);
    if (btnEl) {
        btnEl.disabled = false;
        const icons = { start: 'play', stop: 'stop', restart: 'redo' };
        btnEl.innerHTML = `<i class="fas fa-${icons[action] || 'cog'}"></i>${service === 'digital' ? ' 重启' : ''}`;
    }
}

async function loadConnectionInfo() {
    try {
        const res = await fetch('/api/connections');
        const d = await res.json();
        if (d.status !== 'success') return;
        const c = d.connections;
        document.getElementById('wsConnCount').textContent = c.total_connections || 0;
        const list = document.getElementById('wsConnList');
        if (c.connections_info && c.connections_info.length > 0) {
            list.innerHTML = c.connections_info.map(conn =>
                `<div style="font-size:.78rem;color:#94a3b8;padding:3px 0;border-bottom:1px dashed #334155;">ID:${conn.id} - ${conn.client || '未知'}</div>`
            ).join('');
        } else {
            list.innerHTML = '<div style="font-size:.78rem;color:#64748b;">暂无连接</div>';
        }
    } catch (e) { console.error('loadConnectionInfo', e); }
}

// ========== WebSocket Console ==========
let ws = null, wsConnected = false, reconnectAttempts = 0;
let autoScroll = true, paused = false, logCount = 0, logEntries = [], logFilter = 'all';
let heartbeatInterval = null;

function connectWebSocket() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${protocol}//${location.host}/ws`;
    try {
        ws = new WebSocket(url);
        window._ws = ws;
        ws.onopen = () => {
            wsConnected = true; reconnectAttempts = 0;
            updateWsStatus(true);
            addSysMsg('WebSocket 连接成功');
            heartbeatInterval = setInterval(() => { if (ws && ws.readyState === 1) ws.send(JSON.stringify({ type: 'ping' })); }, 30000);
        };
        ws.onmessage = (e) => {
            try { handleWsMessage(JSON.parse(e.data)); } catch (err) {}
            updateLastUpdate();
        };
        ws.onclose = () => {
            wsConnected = false; updateWsStatus(false);
            if (heartbeatInterval) { clearInterval(heartbeatInterval); heartbeatInterval = null; }
            if (reconnectAttempts < 10) { reconnectAttempts++; setTimeout(() => { if (!wsConnected) connectWebSocket(); }, 3000 * reconnectAttempts); }
        };
        ws.onerror = () => { wsConnected = false; updateWsStatus(false); };
    } catch (e) { console.error('WS connect error', e); }
}

function updateWsStatus(connected) {
    const el = document.getElementById('connectionStatus');
    if (connected) {
        el.innerHTML = '<i class="fas fa-circle"></i><span>已连接</span>';
        el.className = 'status-indicator connected';
        document.getElementById('serverStatus').className = 'status-up';
        document.getElementById('serverStatus').textContent = '运行中';
    } else {
        el.innerHTML = '<i class="fas fa-circle"></i><span>未连接</span>';
        el.className = 'status-indicator disconnected';
        document.getElementById('serverStatus').className = 'status-down';
        document.getElementById('serverStatus').textContent = '断开';
    }
}

function handleWsMessage(data) {
    switch (data.type) {
        case 'log': addLogEntry(data); break;
        case 'system': addSysMsg(data.message); break;
        case 'command_result': showCmdResult(data); break;
        case 'pong': break;
    }
}

function addLogEntry(d) {
    if (paused) return;
    logCount++;
    document.getElementById('logCount').textContent = logCount;
    logEntries.push({ timestamp: d.timestamp || new Date().toISOString(), level: d.level || 'INFO', message: d.message || '' });
    if (logEntries.length > 1000) logEntries = logEntries.slice(-500);
    renderLogs();
}

function renderLogs() {
    const out = document.getElementById('consoleOutput');
    if (!out) return;
    out.innerHTML = '';
    const filtered = logFilter === 'all' ? logEntries : logEntries.filter(l => l.level === logFilter);
    filtered.forEach(log => {
        const div = document.createElement('div');
        div.className = 'console-line';
        const t = new Date(log.timestamp).toLocaleTimeString('zh-CN', { hour12: false });
        div.innerHTML = `<span class="log-level ${log.level.toLowerCase()}">${log.level}</span><span style="color:#64748b;margin-right:8px;">[${t}]</span><span>${escHtml(log.message)}</span>`;
        out.appendChild(div);
    });
    if (autoScroll) out.scrollTop = out.scrollHeight;
}

function addSysMsg(msg) {
    const out = document.getElementById('consoleOutput');
    if (!out) return;
        const div = document.createElement('div');
    div.className = 'system-message';
    const t = new Date().toLocaleTimeString('zh-CN', { hour12: false });
    div.innerHTML = `<i class="fas fa-info-circle" style="margin-right:6px;"></i><strong>[${t}]</strong> ${escHtml(msg)}`;
    out.appendChild(div);
    if (autoScroll) out.scrollTop = out.scrollHeight;
}

function showCmdResult(data) {
    const out = document.getElementById('consoleOutput');
    if (!out) return;
        const div = document.createElement('div');
        div.className = 'command-result';
    let body = data.result?.message || '命令执行完成';
    if (data.result && typeof data.result === 'object') body += `<pre style="margin-top:6px;background:#0f172a;padding:8px;border-radius:4px;overflow:auto;font-size:.78rem;">${escHtml(JSON.stringify(data.result, null, 2))}</pre>`;
    div.innerHTML = `<div class="command-result-header"><i class="fas fa-check-circle" style="margin-right:6px;"></i>${data.command || '命令'}</div>${body}`;
    out.appendChild(div);
    if (autoScroll) out.scrollTop = out.scrollHeight;
}

function toggleAutoScroll() {
    autoScroll = !autoScroll;
    const btn = document.getElementById('autoScrollBtn');
    btn.style.background = autoScroll ? 'rgba(34,197,94,.15)' : '';
    btn.style.borderColor = autoScroll ? '#22c55e' : '';
}

function togglePause() {
    paused = !paused;
    const btn = document.getElementById('pauseBtn');
    btn.innerHTML = `<i class="fas fa-${paused ? 'play' : 'pause'}"></i> ${paused ? '继续' : '暂停'}`;
    btn.style.background = paused ? 'rgba(245,158,11,.15)' : '';
    btn.style.borderColor = paused ? '#f59e0b' : '';
}

function clearConsole() {
    document.getElementById('consoleOutput').innerHTML = '';
    logEntries = []; logCount = 0;
    document.getElementById('logCount').textContent = 0;
    addSysMsg('控制台已清空');
}

function exportLogs() {
    let text = `控制台日志导出 - ${new Date().toLocaleString('zh-CN')}\n${'='.repeat(50)}\n\n`;
    logEntries.forEach(l => { text += `[${new Date(l.timestamp).toLocaleTimeString('zh-CN', { hour12: false })}] [${l.level}] ${l.message}\n`; });
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = `console_${new Date().toISOString().slice(0, 10)}.txt`;
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
}

function sendCommand() {
    const input = document.getElementById('consoleInput');
    if (!input || !input.value.trim()) return;
    const cmd = input.value.trim();
    addSysMsg('执行命令: ' + cmd);
    if (cmd === 'help') { addSysMsg('可用命令: help, clear, stats'); input.value = ''; return; }
    if (cmd === 'clear') { clearConsole(); input.value = ''; return; }
    if (wsConnected && ws && ws.readyState === 1) ws.send(JSON.stringify({ type: 'command', command: cmd }));
    else addSysMsg('WebSocket 未连接');
    input.value = ''; input.focus();
}

async function loadRecentLogs() {
    try {
        const res = await fetch('/api/logs/recent?limit=50');
        const d = await res.json();
        if (d.status === 'success' && d.logs) {
            d.logs.forEach(line => {
                let level = 'INFO';
                if (line.includes(' - DEBUG - ')) level = 'DEBUG';
                else if (line.includes(' - WARNING - ')) level = 'WARNING';
                else if (line.includes(' - ERROR - ')) level = 'ERROR';
                else if (line.includes(' - CRITICAL - ')) level = 'CRITICAL';
                const ts = line.match(/\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}/);
                addLogEntry({ message: line, level, timestamp: ts ? new Date(ts[0]).toISOString() : new Date().toISOString() });
            });
        }
    } catch (e) {}
}

// ========== Log Files (Tab 3) ==========
let currentLogService = 'digital';

function loadLogFile() {
    const lines = document.getElementById('logLineCount')?.value || 100;
    const out = document.getElementById('logfileOutput');
    out.innerHTML = '<div class="loading">加载中...</div>';
    fetch(`/api/admin/logs/${currentLogService}?lines=${lines}`, { headers: authHeaders() })
        .then(r => { if (r.status === 401) { doLogout(); throw new Error('auth'); } return r.json(); })
        .then(d => {
            if (d.lines && d.lines.length > 0) {
                out.textContent = d.lines.join('');
                out.scrollTop = out.scrollHeight;
            } else {
                out.innerHTML = '<div class="loading">日志文件为空</div>';
            }
        })
        .catch(e => { if (e.message !== 'auth') out.innerHTML = '<div class="loading" style="color:#f87171;">加载失败</div>'; });
}

function downloadLogFile() {
    const lines = document.getElementById('logLineCount')?.value || 500;
    fetch(`/api/admin/logs/${currentLogService}?lines=${lines}`, { headers: authHeaders() })
        .then(r => r.json())
        .then(d => {
            const text = (d.lines || []).join('');
            const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
            const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
            a.download = `${currentLogService}_${new Date().toISOString().slice(0, 10)}.log`;
            document.body.appendChild(a); a.click(); document.body.removeChild(a);
        });
}

// ========== Video Management (Tab 4) ==========
async function loadVideoList() {
    const wrap = document.getElementById('videoTableWrap');
    wrap.innerHTML = '<div class="loading">加载中...</div>';
    try {
        const res = await fetch('/api/admin/videos', { headers: authHeaders() });
        if (res.status === 401) { doLogout(); return; }
        const d = await res.json();
        if (!d.videos || d.videos.length === 0) {
            wrap.innerHTML = '<div class="video-empty"><i class="fas fa-inbox"></i> 暂无视频</div>';
            return;
        }
        const rows = d.videos.map((v) => {
            const idx = v._index;
            const name = escHtml(v.file_name || '--');
            const ok = '<i class="fas fa-check" style="color:#22c55e;"></i>';
            const no = '<i class="fas fa-times" style="color:#64748b;"></i>';
            return `<tr id="vrow-${idx}">` +
                `<td class="v-idx">${idx}</td>` +
                `<td title="${escHtml(v.file_name || '')}">${name}</td>` +
                `<td>${v.pdf_path ? ok : no}</td>` +
                `<td>${v.video_path ? ok : no}</td>` +
                `<td>${v.m3u8_url ? ok : no}</td>` +
                `<td><button type="button" class="btn-delete" data-idx="${idx}" data-pdf="${escAttr(v.pdf_path || '')}" data-fname="${escAttr(v.file_name || '')}"><i class="fas fa-trash-alt"></i> 删除</button></td></tr>`;
        }).join('');
        wrap.innerHTML = `<table class="v-table"><thead><tr><th>#</th><th>文件名</th><th>PDF</th><th>视频</th><th>HLS</th><th>操作</th></tr></thead><tbody>${rows}</tbody></table>`;
        wrap.querySelectorAll('.btn-delete').forEach((btn) => {
            btn.addEventListener('click', () => {
                deleteVideo(
                    parseInt(btn.getAttribute('data-idx'), 10),
                    btn.getAttribute('data-pdf') || '',
                    btn.getAttribute('data-fname') || '',
                    btn
                );
            });
        });
    } catch (e) { wrap.innerHTML = '<div class="video-empty" style="color:#f87171;">加载失败</div>'; }
}

async function deleteVideo(index, pdfPath, fileName, btnEl) {
    if (!confirm(`确定删除第 ${index} 条「${fileName}」及其关联文件？\n（仅删除这一条记录，不影响其他同名记录；共享文件会保留）\n此操作不可恢复！`)) return;
    if (btnEl) { btnEl.disabled = true; btnEl.innerHTML = '<i class="fas fa-spinner fa-spin"></i>'; }
    try {
        const res = await fetch('/api/admin/videos/delete', {
                method: 'POST',
            headers: { ...authHeaders(), 'Content-Type': 'application/json' },
                body: JSON.stringify({
                index: index,
                pdf_path: (pdfPath || '').trim() || null,
                file_name: fileName || null
                })
            });
        if (res.status === 401) { doLogout(); return; }
        const d = await res.json().catch(() => ({}));
        if (res.ok) {
            let msg = `已删除 #${index}: ${fileName} (${d.deleted_files?.length || 0} 个路径)`;
            if (d.skipped_files?.length) msg += `，跳过 ${d.skipped_files.length} 个共享路径`;
            addSysMsg(msg);
        } else {
            alert(d.detail || '删除失败');
        }
    } catch (e) { alert('网络错误'); }
    loadVideoList();
}

// ========== Controls (Tab 5) ==========
async function executeCleanup() {
    const el = document.getElementById('cleanupResult');
    el.textContent = '清理任务执行中...';
    try {
        const res = await fetch('/api/cleanup/run-sync');
        const d = await res.json();
        el.textContent = d.message || JSON.stringify(d, null, 2);
        addSysMsg('文件清理完成');
    } catch (e) { el.textContent = '请求失败: ' + e.message; }
}

async function loadSchedulerJobs() {
    const el = document.getElementById('schedulerJobs');
    try {
        const res = await fetch('/api/scheduler/jobs');
        const d = await res.json();
        if (!d.jobs || d.jobs.length === 0) { el.innerHTML = '<div style="color:#64748b;">暂无定时任务</div>'; return; }
        el.innerHTML = d.jobs.map(j =>
            `<div style="padding:6px 0;border-bottom:1px dashed #334155;font-size:.82rem;">
                <strong>${escHtml(j.id || j.name || '--')}</strong>
                <span style="color:#64748b;margin-left:8px;">下次: ${j.next_run_time || '--'}</span>
            </div>`
        ).join('');
    } catch (e) { el.innerHTML = '<div style="color:#f87171;">加载失败</div>'; }
}

async function loadLogLevel() {
    try {
        const res = await fetch('/api/logs/level');
        const d = await res.json();
        document.getElementById('currentLogLevel').textContent = d.levels?.main_logger_name || d.levels?.main_logger || '--';
    } catch (e) {}
}

async function changeLogLevel() {
    const level = document.getElementById('logLevelSelect').value;
    try {
        const res = await fetch(`/api/logs/level/${level}`, { method: 'POST' });
        const d = await res.json();
        document.getElementById('currentLogLevel').textContent = level;
        addSysMsg(`日志级别已设为: ${level}`);
    } catch (e) { alert('设置失败'); }
}

async function testLog(level) {
    try {
        await fetch('/api/commands/test-log', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message: `测试 ${level} 日志`, level }) });
    } catch (e) {}
}

async function sendCustomLog() {
    const msg = document.getElementById('customMessage');
    const lvl = document.getElementById('testLogLevel');
    if (!msg || !msg.value.trim()) return;
    try {
        await fetch('/api/commands/test-log', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message: msg.value, level: lvl.value }) });
        msg.value = '';
    } catch (e) {}
}

// ========== Time & Status ==========
function updateTime() {
    const el = document.getElementById('currentTime');
    if (el) el.textContent = new Date().toLocaleString('zh-CN', { hour12: false });
}

function updateLastUpdate() {
    const el = document.getElementById('lastUpdate');
    if (el) el.textContent = new Date().toLocaleTimeString('zh-CN', { hour12: false });
}

// ========== Init ==========
let appInited = false;

function initApp() {
    if (appInited) return;
    appInited = true;

    // Tab click handlers
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => switchTab(btn.dataset.tab));
    });

    // Console filter
    const filterEl = document.getElementById('logFilter');
    if (filterEl) filterEl.addEventListener('change', (e) => { logFilter = e.target.value; renderLogs(); });

    // Console input enter
    const ci = document.getElementById('consoleInput');
    if (ci) ci.addEventListener('keypress', (e) => { if (e.key === 'Enter') sendCommand(); });

    // Log file sub-tabs
    document.querySelectorAll('.logfile-tab').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.logfile-tab').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentLogService = btn.dataset.log;
            loadLogFile();
        });
    });

    // Start WebSocket
    connectWebSocket();
    loadRecentLogs();

    // Dashboard refresh interval (5s)
    updateTime();
    refreshDashboard();
    window._dashInterval = setInterval(() => {
        updateTime();
        if (currentTab === 'dashboard') refreshDashboard();
    }, 5000);

    // Log file auto-refresh (5s)
    window._logfileInterval = setInterval(() => {
        if (currentTab === 'logfiles' && document.getElementById('logAutoRefresh')?.checked) loadLogFile();
    }, 5000);

    // Load initial log file
    loadLogFile();
}

// ========== Page Load ==========
document.addEventListener('DOMContentLoaded', () => {
    const pwdInput = document.getElementById('loginPassword');
    const usrInput = document.getElementById('loginUsername');
    if (pwdInput) pwdInput.addEventListener('keypress', (e) => { if (e.key === 'Enter') doLogin(); });
    if (usrInput) usrInput.addEventListener('keypress', (e) => { if (e.key === 'Enter') document.getElementById('loginPassword').focus(); });

    if (adminToken) {
        fetch('/api/admin/videos', { headers: authHeaders() })
            .then(r => {
                if (r.ok) { showMain(); initApp(); }
                else { sessionStorage.removeItem('admin_token'); adminToken = ''; showLogin(); }
            })
            .catch(() => showLogin());
    } else {
        showLogin();
    }
});
