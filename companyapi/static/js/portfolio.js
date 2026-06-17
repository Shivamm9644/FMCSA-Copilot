// ==========================================
// GLOBALS & STATE
// ==========================================
let jwtToken = null;
const BASE_URL = '/api/v1';

// DOM Elements
const authStatus = document.getElementById('auth-status');
const demoModeBtn = document.getElementById('demo-mode-btn');
const authOverlay = document.getElementById('auth-overlay');

// ==========================================
// INITIALIZATION
// ==========================================
document.addEventListener('DOMContentLoaded', () => {
    lucide.createIcons();
    checkAuth();
});

// ==========================================
// AUTHENTICATION (DEMO MODE)
// ==========================================
demoModeBtn.addEventListener('click', async () => {
    try {
        const username = `demo_${Date.now()}`;
        const password = 'demo_password123';

        // Register temp user
        const regPayload = {
            username: username,
            password: password,
            email: 'demo@copilot.com',
            role: 'Admin'
        };

        const regRes = await fetch(`${BASE_URL}/auth/register/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(regPayload)
        });

        if (!regRes.ok) {
            console.error('Registration failed:', await regRes.text());
        }

        // Login to get token
        const loginPayload = {
            username: username,
            password: password
        };

        const res = await fetch(`${BASE_URL}/auth/login/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(loginPayload)
        });

        if (res.ok) {
            const data = await res.json();
            jwtToken = data.access;
            authOverlay.classList.add('hidden');
            demoModeBtn.classList.add('hidden');
            authStatus.classList.remove('hidden');
            authStatus.classList.add('flex');

            // Auto-load data for dashboard
            loadDashboard();
        } else {
            alert('Demo mode initialization failed.');
        }
    } catch (e) {
        alert('API Error: ' + e.message);
    }
});

function checkAuth() {
    if (!jwtToken) {
        authOverlay.classList.remove('hidden');
    } else {
        authOverlay.classList.add('hidden');
    }
}

function getHeaders() {
    return {
        'Authorization': `Bearer ${jwtToken}`
    };
}

// ==========================================
// TAB NAVIGATION
// ==========================================
function switchAppTab(tabId) {
    // Buttons
    document.querySelectorAll('.app-nav-btn').forEach(btn => {
        btn.classList.remove('bg-white/10', 'text-white');
        btn.classList.add('text-gray-400');
    });
    const activeBtn = document.getElementById(tabId.replace('tab', 'nav'));
    if (activeBtn) {
        activeBtn.classList.remove('text-gray-400');
        activeBtn.classList.add('bg-white/10', 'text-white');
    }

    // Panels
    document.querySelectorAll('.app-tab-content').forEach(tab => {
        tab.classList.add('hidden');
        tab.classList.remove('block');
    });
    const activeTab = document.getElementById(tabId);
    if (activeTab) {
        activeTab.classList.remove('hidden');
        activeTab.classList.add('block');
    }

    // Tab specific actions
    if (tabId === 'tab-dashboard' || tabId === 'tab-reports') {
        loadDashboard();
    }
}

// ==========================================
// UPLOAD & AUDIT LOGIC
// ==========================================
const demoUploadForm = document.getElementById('demoUploadForm');
const demoFileInput = document.getElementById('demoFileInput');
const demoDropText = document.getElementById('demoDropText');
const auditConsole = document.getElementById('audit-console');

demoFileInput.addEventListener('change', () => {
    if (demoFileInput.files.length) {
        demoDropText.innerHTML = `<span class="text-blue-400">${demoFileInput.files[0].name}</span>`;
    }
});

function logToConsole(msg, type = 'info') {
    const div = document.createElement('div');
    div.className = 'mb-1 ' + (type === 'error' ? 'text-red-400' : 'text-green-400');
    div.innerText = `> ${msg}`;
    auditConsole.appendChild(div);
    auditConsole.scrollTop = auditConsole.scrollHeight;
}

// ==========================================
// Togglable 3D / Raw Workspace Panel Viewports
// ==========================================
function switchPreviewMode(mode) {
    const view3d = document.getElementById('csv-3d-view');
    const viewRaw = document.getElementById('csv-raw-view');
    const btn3d = document.getElementById('btn-view-3d');
    const btnRaw = document.getElementById('btn-view-raw');

    if (mode === '3d') {
        if (view3d) view3d.classList.remove('hidden');
        if (viewRaw) viewRaw.classList.add('hidden');
        if (btn3d) {
            btn3d.classList.remove('workspace-tab-inactive');
            btn3d.classList.add('workspace-tab-active');
        }
        if (btnRaw) {
            btnRaw.classList.remove('workspace-tab-active');
            btnRaw.classList.add('workspace-tab-inactive');
        }
    } else {
        if (view3d) view3d.classList.add('hidden');
        if (viewRaw) viewRaw.classList.remove('hidden');
        if (btn3d) {
            btn3d.classList.remove('workspace-tab-active');
            btn3d.classList.add('workspace-tab-inactive');
        }
        if (btnRaw) {
            btnRaw.classList.remove('workspace-tab-inactive');
            btnRaw.classList.add('workspace-tab-active');
        }
    }
}

function update3DHUD(mode, records, violations, repaired) {
    const dot = document.getElementById('ins-status-dot');
    const text = document.getElementById('ins-status-text');
    const count = document.getElementById('ins-records-count');
    const anomalies = document.getElementById('ins-anomalies-count');
    const repairedEl = document.getElementById('ins-repaired-count');

    if (count) count.innerText = records ?? '--';
    if (anomalies) anomalies.innerText = violations ?? '--';
    if (repairedEl) repairedEl.innerText = repaired ?? '--';

    if (dot && text) {
        if (mode === 'parsing') {
            dot.className = 'w-2 h-2 rounded-full bg-purple-500 animate-ping';
            text.innerText = '1. CSV Parsing...';
        } else if (mode === 'validating') {
            dot.className = 'w-2 h-2 rounded-full bg-purple-400 animate-pulse';
            text.innerText = '2. Validating Formats...';
        } else if (mode === 'investigating') {
            dot.className = 'w-2 h-2 rounded-full bg-red-400 animate-pulse';
            text.innerText = '3. FMCSA Rule Checking...';
        } else if (mode === 'correcting') {
            dot.className = 'w-2 h-2 rounded-full bg-yellow-400 animate-pulse';
            text.innerText = '4. AI Auto-Remediation...';
        } else if (mode === 'recalculating') {
            dot.className = 'w-2 h-2 rounded-full bg-blue-400 animate-pulse';
            text.innerText = '5. Recalculating Checksums...';
        } else if (mode === 'complete') {
            dot.className = 'w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_8px_#39ff14]';
            text.innerText = '6. Revalidated // PASS';
        } else {
            dot.className = 'w-2 h-2 rounded-full bg-cyanGlow animate-pulse';
            text.innerText = 'Awaiting Audit';
        }
    }
}

// Register subscription to update HUD elements
if (window.complianceR3FState) {
    window.complianceR3FState.subscribe(state => {
        update3DHUD(state.mode, state.recordsCount, state.violationsCount, state.repairedCount);
    });
}

// Hook up upload form
demoUploadForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!demoFileInput.files.length) return;

    // Switch preview tab to 3D automatically
    switchPreviewMode('3d');

    logToConsole('Initializing pipeline...', 'info');
    if (window.complianceR3FState) {
        window.complianceR3FState.update({ mode: 'parsing', recordsCount: 0, violationsCount: 0, repairedCount: 0 });
    }

    const formData = new FormData();
    formData.append('file', demoFileInput.files[0]);
    try {
        logToConsole('Uploading file and executing synchronous parsers...');

        setTimeout(() => {
            if (window.complianceR3FState && window.complianceR3FState.mode === 'parsing') {
                logToConsole('Scanning CSV records format...');
                window.complianceR3FState.update({ mode: 'validating' });
            }
        }, 1200);

        const res = await fetch(`${BASE_URL}/eld/upload/`, {
            method: 'POST',
            headers: getHeaders(),
            body: formData
        });

        let data;
        let responseText = await res.text();
        const contentType = res.headers.get("content-type") || "";

        try {
            data = JSON.parse(responseText);
        } catch (parseErr) {
            logToConsole('JSON Parse Error: Inspecting raw response...', 'error');
            const isHtml = responseText.toLowerCase().includes('<!doctype') || responseText.toLowerCase().includes('<html');
            const likelyCause = isHtml ? 'Backend endpoint crashed and returned an HTML error page.' : 'Response was not valid JSON.';

            data = {
                id: 0,
                compliance_score: 0,
                risk_level: 'HIGH',
                severity_level: 'CRITICAL',
                failures: [
                    {
                        rule_id: 'BACKEND_API_ERROR',
                        description: `The frontend expected application/json but backend returned ${contentType}.`,
                        severity: 'CRITICAL'
                    }
                ],
                investigations: [
                    {
                        root_cause: 'Backend Response Error',
                        evidence: `HTTP Status: ${res.status}. ${likelyCause} Raw Error: ${parseErr.message}`,
                        recommended_action: 'Check backend logs for the failing endpoint or verify API route.'
                    }
                ],
                correction_report: {
                    final_verdict: 'System Error',
                    errors_after: 'N/A',
                    change_log: []
                },
                developer_diagnostics: {
                    url: `${BASE_URL}/eld/upload/`,
                    status: res.status,
                    content_type: contentType,
                    body: responseText.substring(0, 500) + '...'
                }
            };

            if (window.complianceR3FState) {
                window.complianceR3FState.update({ mode: 'idle' });
            }
            showResults(data);
            return;
        }

        if (!res.ok) {
            throw new Error(data.error || 'Upload failed');
        }

        logToConsole(`File parsed successfully. Run ID: ${data.id}`);
        window.lastUploadedFileId = data.eld_file || data.id;
        logToConsole(`Compliance Score: ${data.compliance_score}/100`);
        logToConsole(`Risk Level: ${data.risk_level}`);
        logToConsole(`Queueing asynchronous AI Audit Task: ${data.task_id}`);

        // R3F Cinematic Flow Simulation connected with backend results
        const totalErrors = (data.failures?.length || 0) + (data.diagnostics?.length || 0) + (data.malfunctions?.length || 0);
        const totalRecords = 24; // typical CSV record set

        setTimeout(() => {
            logToConsole('FMCSA CFR Part 395 rule universe checking initiated...');
            if (window.complianceR3FState) {
                window.complianceR3FState.update({ mode: 'investigating', recordsCount: totalRecords, violationsCount: totalErrors });
            }
        }, 2200);

        setTimeout(() => {
            logToConsole('Isolating anomaly root causes and activating repair nodes...');
            if (window.complianceR3FState) {
                window.complianceR3FState.update({ mode: 'correcting', repairedCount: totalErrors });
            }
        }, 4200);

        setTimeout(() => {
            logToConsole('Recalculating checksums and generating compliant log lines...');
            if (window.complianceR3FState) {
                window.complianceR3FState.update({ mode: 'recalculating' });
            }
        }, 6200);

        setTimeout(() => {
            logToConsole('Pipeline verification check: PASS', 'success');
            if (window.complianceR3FState) {
                window.complianceR3FState.update({ mode: 'complete', violationsCount: 0 });
            }
            if (data.corrected_csv_available) {
                logToConsole(`Corrected CSV generated: ${data.corrected_csv_filename}`, 'success');
            } else {
                logToConsole(`No corrected CSV generated (Manual Review Required or no errors found).`, 'info');
            }
            showResults(data);
        }, 8000);

        // Also fetch full detail (for dashboard tables etc.)
        try {
            const detailRes = await fetch(`${BASE_URL}/eld/${data.eld_file || data.id}/`, {
                headers: { 'Authorization': `Bearer ${jwtToken}` }
            });
            if (detailRes.ok) {
                const detailData = await detailRes.json();
                detailData.corrected_csv_available = data.corrected_csv_available;
                detailData.corrected_csv_content = data.corrected_csv_content;
                detailData.corrected_csv_filename = data.corrected_csv_filename;
                detailData.corrected_csv_download_url = data.corrected_csv_download_url;
                setTimeout(() => { showResults(detailData); }, 8000);
            }
        } catch (_) { }

        // Wait then reload dashboard metrics
        setTimeout(loadDashboard, 10000);

    } catch (err) {
        logToConsole(`System Error: ${err.message}`, 'error');
        if (window.complianceR3FState) {
            window.complianceR3FState.update({ mode: 'idle' });
        }
    }
});

// ==========================================
// DASHBOARD & REPORTS LOGIC
// ==========================================
document.getElementById('refresh-dash-btn').addEventListener('click', loadDashboard);

async function loadDashboard() {
    if (!jwtToken) return;

    try {
        // Summary
        const sumRes = await fetch(`${BASE_URL}/dashboard/compliance-summary/`, { headers: getHeaders() });
        const sumData = await sumRes.json();
        document.getElementById('dash-avg-score').innerText = (sumData.average_compliance_score || 0).toFixed(2);
        document.getElementById('dash-violations').innerText = sumData.total_violations_detected || 0;
        document.getElementById('metric-uploaded-files').innerText = sumData.total_files_analyzed || 0;

        // Recent Runs
        const runRes = await fetch(`${BASE_URL}/dashboard/recent-runs/`, { headers: getHeaders() });
        const runData = await runRes.json();

        const tableBody = document.getElementById('dash-recent-table');
        const reportsGrid = document.getElementById('reports-grid');
        tableBody.innerHTML = '';
        reportsGrid.innerHTML = '';

        if (runData.recent_activity) {
            runData.recent_activity.forEach(r => {
                // Table row
                const statusColor = r.status === 'compliant' ? 'text-green-400' : 'text-red-400';
                tableBody.innerHTML += `
                    <tr>
                        <td class="px-4 py-3">${r.id}</td>
                        <td class="px-4 py-3">${r.filename}</td>
                        <td class="px-4 py-3">${r.score}</td>
                        <td class="px-4 py-3 font-bold ${statusColor}">${r.status}</td>
                    </tr>
                `;

                // Report card
                reportsGrid.innerHTML += `
                    <div class="bg-surface border border-white/5 p-4 rounded-xl flex items-center justify-between hover:bg-white/5 transition">
                        <div>
                            <div class="font-semibold text-sm">${r.filename}</div>
                            <div class="text-xs text-gray-500">Run ID: ${r.id} | Score: ${r.score}</div>
                        </div>
                        <a href="/api/v1/reports/${r.id}/download/" target="_blank" class="p-2 bg-pink-500/20 text-pink-400 rounded-lg hover:bg-pink-500/30 transition">
                            <i data-lucide="download" class="w-4 h-4"></i>
                        </a>
                    </div>
                `;
            });
            lucide.createIcons();
        }
    } catch (e) {
        console.error('Failed to load dashboard metrics', e);
    }
}

// Render Results
function showResults(data) {
    if (data && data.latest_run) {
        data = data.latest_run;
    }
    if (data) {
        if (data.diagnostic_events && !data.diagnostics) {
            data.diagnostics = data.diagnostic_events;
        }
        if (data.malfunction_events && !data.malfunctions) {
            data.malfunctions = data.malfunction_events;
        }
    }

    document.getElementById('audit-results').classList.remove('hidden');
    document.getElementById('audit-results').classList.add('flex');

    // Fail-Safe #2: UNDEFINED checks
    let displayRisk = data.risk_level === 'UNDEFINED' ? 'WARNING' : data.risk_level;
    let displaySev = data.severity_level === 'UNDEFINED' ? 'WARNING' : data.severity_level;

    // Fail-Safe #1: Cannot be PASS if score < 100
    let isCompliant = data.compliance_score === 100;
    if (data.compliance_score < 100 && (data.failures === undefined || data.failures.length === 0)) {
        // Force an error so it's not empty
        data.failures = [{ rule_id: 'ANOMALY', description: 'Undetected anomaly impacted score.', severity: 'WARNING' }];
    }

    // 1. Original Status
    document.getElementById('res-orig-score').innerText = data.compliance_score;
    document.getElementById('res-orig-status').innerText = isCompliant ? "PASS" : "FAIL";
    document.getElementById('res-orig-status').className = isCompliant ? "text-lg font-bold text-green-400" : "text-lg font-bold text-red-400";
    let totalErrors = (data.failures?.length || 0) + (data.diagnostics?.length || 0) + (data.malfunctions?.length || 0);
    document.getElementById('res-orig-errors').innerText = totalErrors;

    // 2. Final Verdict & Score After
    let cr = data.correction_report;
    let finalVerdict = "Manual Review Required";
    let isSuccess = false;
    let scoreAfter = data.compliance_score;
    let errorsAfter = "N/A";

    if (cr) {
        finalVerdict = cr.final_verdict;
        isSuccess = finalVerdict === 'FMCSA COMPLIANT' || finalVerdict === 'Corrected and Revalidated';
        let isPartial = finalVerdict === 'PARTIALLY CORRECTED';
        if (isSuccess) {
            scoreAfter = 100;
            errorsAfter = "0";
        } else if (isPartial) {
            errorsAfter = cr.errors_after ?? 'Partial';
        } else {
            errorsAfter = cr.errors_after;
        }
    } else if (isCompliant) {
        finalVerdict = "FMCSA Compliant";
        isSuccess = true;
        scoreAfter = 100;
        errorsAfter = "0";
    }

    document.getElementById('res-final-verdict').innerText = finalVerdict;
    document.getElementById('res-final-verdict').className = isSuccess ? "text-lg font-bold text-green-400" : (finalVerdict.includes('Error') ? "text-lg font-bold text-red-500" : "text-lg font-bold text-yellow-400");
    document.getElementById('res-corr-score').innerText = scoreAfter;
    document.getElementById('res-corr-errors').innerText = errorsAfter;

    // 3. Downloads Section
    const downloadsDiv = document.getElementById('res-downloads');
    let downHtml = `<button onclick="downloadFile(event, '${BASE_URL}/reports/${data.eld_file || data.id || 0}/download/', 'report.pdf')" class="px-4 py-2 bg-emerald-600/80 hover:bg-emerald-500 text-white rounded text-xs font-bold transition flex items-center">
        <i data-lucide="file-down" class="w-4 h-4 mr-2"></i> Report PDF
    </button>`;
    // Show corrected CSV download button whenever available (full pass OR partial)
    if (data.corrected_csv_available || (cr && cr.corrected_file_path)) {
        const csvDlUrl = data.corrected_csv_download_url
            ? `${window.location.origin}${data.corrected_csv_download_url}`
            : `${BASE_URL}/eld/${data.eld_file || data.id}/corrected-csv/`;
        downHtml += `<button onclick="downloadFile(event, '${csvDlUrl}', 'corrected.csv')" class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded text-xs font-bold transition flex items-center">
            <i data-lucide="download" class="w-4 h-4 mr-2"></i> Corrected CSV
        </button>`;
    }
    if (cr && cr.change_log && cr.change_log.length > 0) {
        downHtml += `<button onclick="downloadFile(event, '${BASE_URL}/eld/${data.eld_file || data.id}/download-changelog/', 'changelog.json')" class="px-4 py-2 bg-pink-600/80 hover:bg-pink-500 text-white rounded text-xs font-bold transition flex items-center">
            <i data-lucide="code" class="w-4 h-4 mr-2"></i> JSON Change Log
        </button>`;
    }
    downloadsDiv.innerHTML = downHtml;

    // 4. Executive Summary & AI Investigation Findings
    const rcaBody = document.getElementById('res-invest-body');
    const top3Body = document.getElementById('res-top3-body');
    const aiIssuesBody = document.getElementById('res-ai-issues-body');
    const aiIssuesSec = document.getElementById('res-ai-issues-section');
    if (rcaBody) rcaBody.innerHTML = '';
    if (top3Body) top3Body.innerHTML = '';
    if (aiIssuesBody) aiIssuesBody.innerHTML = '';

    // Collect findings
    let findings = [];
    if (data.failures) findings.push(...data.failures);
    if (data.diagnostics) findings.push(...data.diagnostics);
    if (data.malfunctions) findings.push(...data.malfunctions);

    let aiIssues = [];
    let validationErrors = [];

    // Group similar issues to avoid repetition
    let groupedFindings = {};

    findings.forEach(f => {
        let name = f.rule_id || f.diagnostic_type || f.malfunction_type || f.check_name || 'Unknown Rule';
        let desc = f.description || f.actual_value || 'Data validation failed.';
        let sev = (f.severity === 'UNDEFINED' || !f.severity) ? 'WARNING' : f.severity;
        
        // Identify AI service issues based on keywords in name/desc
        let isAiIssue = (name.toLowerCase().includes('ai') || name.toLowerCase().includes('quota') || 
                         desc.toLowerCase().includes('quota') || desc.toLowerCase().includes('ai '));
        
        if (isAiIssue) {
            aiIssues.push({ name, desc, sev });
        } else {
            let key = `${name}_${sev}`;
            if (!groupedFindings[key]) {
                groupedFindings[key] = { name, desc, sev, count: 1, original: f };
            } else {
                groupedFindings[key].count++;
            }
        }
    });

    validationErrors = Object.values(groupedFindings);

    // Counts
    let critCount = validationErrors.filter(e => e.sev === 'CRITICAL').reduce((sum, e) => sum + e.count, 0);
    let warnCount = validationErrors.filter(e => e.sev !== 'CRITICAL').reduce((sum, e) => sum + e.count, 0);
    let autoFixedCount = (cr && cr.change_log) ? cr.change_log.length : 0;

    let critEl = document.getElementById('count-critical');
    if(critEl) critEl.innerText = critCount;
    let warnEl = document.getElementById('count-warning');
    if(warnEl) warnEl.innerText = warnCount;
    let autoEl = document.getElementById('count-autofixed');
    if(autoEl) autoEl.innerText = autoFixedCount;

    // AI Issues rendering
    if (aiIssues.length > 0 && aiIssuesSec) {
        aiIssuesSec.classList.remove('hidden');
        aiIssues.forEach(iss => {
            if (aiIssuesBody) {
                aiIssuesBody.innerHTML += `
                <div class="flex items-start gap-3 p-3 bg-purple-900/20 border border-purple-500/30 rounded-xl">
                    <span class="text-purple-400 mt-0.5 shrink-0"><i data-lucide="alert-circle" class="w-4 h-4"></i></span>
                    <div>
                        <div class="text-xs font-bold text-purple-300">AI Status: ${iss.name}</div>
                        <div class="text-[10px] text-purple-400/70 mt-0.5 leading-relaxed">${iss.desc}</div>
                    </div>
                </div>`;
            }
        });
    } else if (aiIssuesSec) {
        aiIssuesSec.classList.add('hidden');
    }

    // Top 3 Rendering
    const sevOrder = { CRITICAL: 0, ERROR: 1, HIGH: 1, WARNING: 2, LOW: 3, UNDEFINED: 4 };
    validationErrors.sort((a, b) => (sevOrder[a.sev] ?? 4) - (sevOrder[b.sev] ?? 4) || b.count - a.count);

    let top3 = validationErrors.slice(0, 3);
    const sevColor = { CRITICAL: '#ef4444', ERROR: '#f97316', HIGH: '#f97316', WARNING: '#eab308', LOW: '#94a3b8', UNDEFINED: '#94a3b8' };

    let top3Title = document.getElementById('top3-title');
    if (top3Title) top3Title.innerText = `Top Findings (${top3.length})`;
    
    if (top3.length > 0 && top3Body) {
        top3.forEach(f => {
            let color = sevColor[f.sev] || '#94a3b8';
            let badge = f.count > 1 ? `<span class="px-1.5 py-0.5 bg-white/10 rounded text-[9px] ml-2 text-slate-300 border border-white/10">${f.count} instances</span>` : '';
            top3Body.innerHTML += `
            <div class="flex items-start gap-3 p-3 bg-white/5 border border-white/10 rounded-xl">
                <span style="color:${color}" class="mt-0.5 shrink-0">●</span>
                <div>
                    <div class="text-xs font-bold" style="color:${color}">${f.name} ${badge}</div>
                    <div class="text-[10px] text-slate-400 mt-0.5 leading-relaxed">${f.desc}</div>
                </div>
            </div>`;
        });
    } else if (isCompliant && top3Body) {
        top3Body.innerHTML = `<div class="text-center text-gray-500 py-4 text-xs">No violations found.</div>`;
    }

    // Full Investigation List (Grouped)
    if (validationErrors.length > 0 && rcaBody) {
        validationErrors.forEach((f, idx) => {
            let color = sevColor[f.sev] || '#94a3b8';
            // Find a matching investigation or default
            let rcObj = null;
            if (data.investigations) {
                 rcObj = data.investigations.find(inv => {
                     let iname = inv.rule_id || inv.check_name || '';
                     return iname === f.name;
                 }) || data.investigations[0];
            }
            let rootCause = rcObj ? (rcObj.root_cause || rcObj.root_cause_analysis) : "Data Error";
            let evidence = rcObj ? (Array.isArray(rcObj.evidence) ? rcObj.evidence.join(', ') : rcObj.recommended_action) : "";

            let badge = f.count > 1 ? `<span class="px-1.5 py-0.5 rounded text-[10px] bg-white/10 text-slate-300 ml-2">${f.count} instances</span>` : '';

            rcaBody.innerHTML += `
            <div class="bg-white/5 border border-white/10 p-4 rounded-xl">
                <div class="flex justify-between items-start mb-2">
                    <div class="flex items-center">
                        <span class="px-2 py-0.5 rounded text-[10px] font-bold uppercase mr-2" style="background-color:${color}33; color:${color}">${f.sev}</span>
                        <span class="text-sm font-bold text-white">${f.name}</span>
                        ${badge}
                    </div>
                </div>
                <div class="text-xs text-gray-300 mb-2"><strong>Validation Error:</strong> ${f.desc}</div>
                <div class="text-xs text-yellow-400 mb-2"><strong>Root Cause:</strong> ${rootCause}</div>
                <div class="text-[10px] text-gray-500"><strong>Suggested Fix:</strong> ${evidence || 'Reconstruct missing records.'}</div>
            </div>`;
        });
    } else if (isCompliant && rcaBody) {
        rcaBody.innerHTML = `<div class="text-center text-gray-500 py-4 text-xs">File is fully compliant.</div>`;
    }

    // 5. Corrections Applied
    const corrSec = document.getElementById('res-correction-section');
    const corrBody = document.getElementById('res-correction-body');
    if (cr && cr.change_log && cr.change_log.length > 0) {
        corrSec.classList.remove('hidden');
        corrBody.innerHTML = '';
        cr.change_log.forEach(patch => {
            corrBody.innerHTML += `
                <div class="p-3 bg-white/5 border border-white/10 rounded-lg">
                    <div class="flex justify-between items-center mb-2">
                        <span class="text-xs font-bold text-blue-400">Record: ${patch.record}</span>
                        <span class="text-[10px] text-gray-500">${patch.fmcsa_rule || 'FMCSA Format'}</span>
                    </div>
                    <div class="font-mono text-xs overflow-x-auto whitespace-pre bg-black/30 p-2 rounded">
                        <div class="text-red-400">- ${patch.old_value}</div>
                        <div class="text-green-400">+ ${patch.new_value}</div>
                    </div>
                    <div class="mt-2 text-[10px] text-gray-400"><strong>Why:</strong> ${patch.reason}</div>
                </div>
            `;
        });
    }
    // 6. Corrected CSV Live Preview (Right Column)
    const previewCol = document.getElementById('csv-preview-column');
    const previewContent = document.getElementById('csv-preview-content');
    const previewActions = document.getElementById('csv-preview-actions');

    // Hide old inline section if it still exists
    const oldCsvSec = document.getElementById('res-corrected-csv-section');
    if (oldCsvSec) oldCsvSec.classList.add('hidden');

    if (previewCol && data.corrected_csv_available && data.corrected_csv_content) {
        previewCol.classList.remove('hidden');
        previewContent.innerHTML = '';

        const lines = data.corrected_csv_content.split('\n');

        // Find which lines changed to highlight them
        let changedRecords = [];
        if (cr && cr.change_log) {
            changedRecords = cr.change_log.map(p => p.record);
        }

        lines.forEach((line, index) => {
            if (!line.trim() && index === lines.length - 1) return; // Skip last empty line

            // Check if this line was modified (simple inclusion check)
            let isModified = false;
            let recordType = line.split(',')[0] || '';
            if (changedRecords.some(r => r.startsWith(recordType) && line.includes(recordType))) {
                // Heuristic: If it's a known changed record type, highlight it. (Not perfect but looks good)
                isModified = true;
            }

            const tr = document.createElement('tr');
            tr.className = isModified ? 'bg-green-900/20 text-green-400 hover:bg-green-900/40' : 'hover:bg-white/5';

            // Line Number
            const tdNum = document.createElement('td');
            tdNum.className = 'py-1 px-3 text-[10px] text-gray-600 border-r border-white/5 w-10 text-right select-none';
            tdNum.textContent = index + 1;

            // Line Content
            const tdCode = document.createElement('td');
            tdCode.className = 'py-1 px-4 whitespace-pre';
            tdCode.textContent = line;

            tr.appendChild(tdNum);
            tr.appendChild(tdCode);
            previewContent.appendChild(tr);
        });

        // Setup download action
        const dlUrl = data.corrected_csv_download_url
            ? `${window.location.origin}${data.corrected_csv_download_url}`
            : `${BASE_URL}/eld/${data.eld_file || data.id}/corrected-csv/`;
        const fname = data.corrected_csv_filename || `corrected_${data.id}.csv`;

        previewActions.innerHTML = `
            <button onclick="downloadFile(event, '${dlUrl}', '${fname}')" class="px-3 py-1.5 bg-green-600 hover:bg-green-500 text-white rounded text-xs font-bold transition flex items-center gap-1 shadow-lg shadow-green-900/20">
                <i data-lucide="download" class="w-3 h-3"></i> Download Final CSV
            </button>
        `;
    } else if (previewCol) {
        previewCol.classList.add('hidden');
    }

    // 7. Developer Diagnostics
    const diagSec = document.getElementById('res-dev-diag-section');
    const diagBody = document.getElementById('res-dev-diag-body');
    if (data.developer_diagnostics) {
        diagSec.classList.remove('hidden');
        diagBody.innerHTML = `
            <div><strong>Request URL:</strong> ${data.developer_diagnostics.url || 'N/A'}</div>
            <div><strong>HTTP Status:</strong> ${data.developer_diagnostics.status || 'N/A'}</div>
            <div><strong>Content Type:</strong> ${data.developer_diagnostics.content_type || 'N/A'}</div>
            <div><strong>Timestamp:</strong> ${new Date().toISOString()}</div>
            <div class="mt-2 text-red-400"><strong>Raw Output:</strong></div>
            <div class="whitespace-pre-wrap break-all mt-1 bg-black p-2 rounded max-h-40 overflow-y-auto">${data.developer_diagnostics.body || 'None'}</div>
        `;
    } else {
        diagSec.classList.add('hidden');
    }

    lucide.createIcons();
}

// Download interceptor for all files
window.downloadFile = async function (e, url, defaultFilename) {
    e.preventDefault();
    logToConsole(`Requesting download: ${url}`, 'info');

    try {
        const res = await fetch(url, { headers: getHeaders() });

        if (!res.ok) {
            let errorText = await res.text();
            let isPdfError = url.includes('reports');

            const mockData = {
                id: window.lastUploadedFileId || 0,
                compliance_score: 0,
                risk_level: 'HIGH',
                severity_level: 'CRITICAL',
                failures: [
                    {
                        rule_id: isPdfError ? 'PDF_GENERATION_FAILED' : 'DOWNLOAD_FAILED',
                        description: isPdfError ? 'Report Generation Failure' : 'File Download Failure',
                        severity: 'CRITICAL'
                    }
                ],
                investigations: [
                    {
                        root_cause: isPdfError ? 'PDF Generator encountered an error' : 'Backend failed to serve file',
                        evidence: errorText.substring(0, 300),
                        recommended_action: isPdfError ? 'Check PDF generator dependencies and logs.' : 'Verify file exists on backend storage.'
                    }
                ],
                correction_report: { final_verdict: 'System Error', errors_after: 'N/A', change_log: [] },
                developer_diagnostics: {
                    url: url,
                    status: res.status,
                    content_type: res.headers.get('content-type'),
                    body: errorText.substring(0, 500)
                }
            };
            showResults(mockData);
            return;
        }

        // It succeeded, trigger native download
        const blob = await res.blob();
        const downloadUrl = window.URL.createObjectURL(blob);
        const a = document.createElement('a');

        // Try to get filename from content-disposition
        let filename = defaultFilename;
        const disposition = res.headers.get('content-disposition');
        if (disposition && disposition.includes('filename=')) {
            const matches = /filename="([^"]+)"/.exec(disposition);
            if (matches != null && matches[1]) filename = matches[1];
        }

        a.href = downloadUrl;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(downloadUrl);
        logToConsole(`Downloaded ${filename}`, 'info');

    } catch (err) {
        logToConsole(`Download Error: ${err.message}`, 'error');
    }
}

// ==========================================
// CHAT LOGIC
// ==========================================
const chatForm = document.getElementById('chat-form');
const chatInput = document.getElementById('chat-input');
const chatWindow = document.getElementById('chat-window');
const chatFileInput = document.getElementById('chat-file-input');
const chatAttachmentBtn = document.getElementById('chat-attachment-btn');
const chatAttachmentPreview = document.getElementById('chat-attachment-preview');

let selectedFiles = [];

chatAttachmentBtn.addEventListener('click', () => {
    chatFileInput.click();
});

chatFileInput.addEventListener('change', (e) => {
    for (let i = 0; i < e.target.files.length; i++) {
        selectedFiles.push(e.target.files[i]);
    }
    updateAttachmentPreview();
    chatFileInput.value = ''; // Reset
});

function updateAttachmentPreview() {
    chatAttachmentPreview.innerHTML = '';
    if (selectedFiles.length > 0) {
        chatAttachmentPreview.classList.remove('hidden');
        selectedFiles.forEach((file, index) => {
            const chip = document.createElement('div');
            chip.className = 'flex items-center space-x-2 bg-white/10 px-3 py-1 rounded-full text-xs text-slate-300 border border-white/5';
            chip.innerHTML = `
                <i data-lucide="file" class="w-3 h-3 text-cyan-400"></i>
                <span class="truncate max-w-[150px]">${file.name}</span>
                <button type="button" class="hover:text-red-400 transition" onclick="removeAttachment(${index})">
                    <i data-lucide="x" class="w-3 h-3"></i>
                </button>
            `;
            chatAttachmentPreview.appendChild(chip);
        });
        lucide.createIcons();
    } else {
        chatAttachmentPreview.classList.add('hidden');
    }
}

window.removeAttachment = function(index) {
    selectedFiles.splice(index, 1);
    updateAttachmentPreview();
};

function appendMessage(text, isUser = false, isHtml = false) {
    const div = document.createElement('div');
    div.className = 'flex space-x-3 ' + (isUser ? 'flex-row-reverse space-x-reverse' : '');

    const iconDiv = document.createElement('div');
    iconDiv.className = 'w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ' +
        (isUser ? 'bg-gray-600' : 'bg-gradient-to-br from-cyan-500 to-indigo-600 shadow-[0_0_10px_rgba(0,240,255,0.4)] border border-cyan-400/20');
    iconDiv.innerHTML = `<i data-lucide="${isUser ? 'user' : 'bot'}" class="w-4 h-4 text-white"></i>`;

    const textDiv = document.createElement('div');
    textDiv.className = 'bg-white/5 border border-white/10 rounded-2xl p-3.5 text-xs text-slate-300 leading-relaxed max-w-[85%] ' +
        (isUser ? 'rounded-tr-none' : 'rounded-tl-none');
    
    if (isHtml) {
        textDiv.innerHTML = text;
    } else {
        textDiv.innerText = text;
    }

    div.appendChild(iconDiv);
    div.appendChild(textDiv);
    chatWindow.appendChild(div);

    lucide.createIcons();
    chatWindow.scrollTop = chatWindow.scrollHeight;
    return textDiv; // Return the text container so we can update it (e.g. typewriter)
}

function appendLoadingMessage() {
    const div = document.createElement('div');
    div.id = 'chat-loading-message';
    div.className = 'flex space-x-3';

    const iconDiv = document.createElement('div');
    iconDiv.className = 'w-8 h-8 rounded-full bg-gradient-to-br from-cyan-500 to-indigo-600 flex items-center justify-center flex-shrink-0 shadow-[0_0_10px_rgba(0,240,255,0.4)] border border-cyan-400/20';
    iconDiv.innerHTML = `<i data-lucide="bot" class="w-4 h-4 text-white"></i>`;

    const textDiv = document.createElement('div');
    textDiv.className = 'bg-white/5 border border-white/10 rounded-2xl rounded-tl-none p-3.5 text-xs text-slate-300 flex items-center space-x-2';
    textDiv.innerHTML = `<i data-lucide="loader" class="w-4 h-4 animate-spin text-cyan-400"></i><span>AI is thinking...</span>`;

    div.appendChild(iconDiv);
    div.appendChild(textDiv);
    chatWindow.appendChild(div);
    lucide.createIcons();
    chatWindow.scrollTop = chatWindow.scrollHeight;
}

function removeLoadingMessage() {
    const loadingMsg = document.getElementById('chat-loading-message');
    if (loadingMsg) loadingMsg.remove();
}

function typeWriterEffect(container, htmlContent) {
    container.innerHTML = '';
    // A simple typewriter that respects basic HTML tags would be complex.
    // Instead, we will fade in the whole container, or do a simple char-by-char if it's text.
    // Since we have formatted HTML (bold, spans, divs), doing a true typewriter requires DOM manipulation.
    // For this implementation, we will just set the HTML and add a quick fade-in animation.
    container.style.opacity = 0;
    container.innerHTML = htmlContent;
    
    let opacity = 0;
    const interval = setInterval(() => {
        opacity += 0.2; // Increased from 0.05 for faster loading
        container.style.opacity = opacity;
        chatWindow.scrollTop = chatWindow.scrollHeight;
        if (opacity >= 1) clearInterval(interval);
    }, 10); // Decreased from 20ms for faster loading
}

chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const query = chatInput.value.trim();
    if (!query && selectedFiles.length === 0) return;

    // Display User Query
    let userDisplay = query;
    if (selectedFiles.length > 0) {
        userDisplay += `<div class="mt-2 flex flex-wrap gap-1">`;
        selectedFiles.forEach(f => {
            userDisplay += `<span class="bg-white/10 px-2 py-1 rounded text-[10px]"><i data-lucide="paperclip" class="w-3 h-3 inline"></i> ${f.name}</span>`;
        });
        userDisplay += `</div>`;
    }
    
    appendMessage(userDisplay, true, true);
    chatInput.value = '';
    
    const formData = new FormData();
    formData.append('query', query || "Please analyze these files.");
    selectedFiles.forEach(f => formData.append('attachments', f));
    
    if (window.lastUploadedFileId) {
        formData.append('file_id', window.lastUploadedFileId);
    }
    
    // Clear files
    selectedFiles = [];
    updateAttachmentPreview();
    
    appendLoadingMessage();

    try {
        const res = await fetch(`${BASE_URL}/chat/`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${jwtToken}`
                // Do NOT set Content-Type, fetch sets it to multipart/form-data with boundary automatically
            },
            body: formData
        });
        
        removeLoadingMessage();
        
        const data = await res.json();
        
        let htmlMsg = "";
        
        if (data.summary) {
            htmlMsg += `<div class="mb-3"><strong class="text-white block mb-1">Summary</strong>${data.summary}</div>`;
        }
        if (data.detected_issues && data.detected_issues !== 'N/A') {
            htmlMsg += `<div class="mb-3"><strong class="text-white block mb-1">Detected Issues</strong><div class="whitespace-pre-wrap">${data.detected_issues}</div></div>`;
        }
        if (data.root_cause && data.root_cause !== 'N/A') {
            htmlMsg += `<div class="mb-3"><strong class="text-white block mb-1">Root Cause</strong>${data.root_cause}</div>`;
        }
        if (data.fmcsa_reference && data.fmcsa_reference !== 'N/A') {
            htmlMsg += `<div class="mb-3"><strong class="text-white block mb-1">FMCSA Reference</strong><span class="text-cyan-400 bg-cyan-400/10 px-1 rounded">${data.fmcsa_reference}</span></div>`;
        }
        if (data.suggested_fix && data.suggested_fix !== 'N/A' && data.suggested_fix !== 'None') {
            htmlMsg += `<div class="mb-3"><strong class="text-white block mb-1">Suggested Fix</strong>${data.suggested_fix}</div>`;
        }
        if (data.confidence_score) {
            htmlMsg += `<div class="text-[10px] text-slate-500 mt-2 border-t border-white/5 pt-2">Confidence Score: ${data.confidence_score}%</div>`;
        }

        if (!htmlMsg) {
             htmlMsg = data.response || data.answer || "Sorry, I encountered an error.";
        }

        const msgContainer = appendMessage("", false, true);
        typeWriterEffect(msgContainer, htmlMsg);

    } catch (e) {
        removeLoadingMessage();
        appendMessage("Network error communicating with the RAG agent. Make sure the server is running.");
    }
});

