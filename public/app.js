/**
 * KINGMAILER v4.0 - Frontend JavaScript
 * Handles all dashboard interactions and API calls
 */

// Global state
let smtpAccounts = [];
let sesAccounts = [];
let ec2Instances = [];
let inputMode = 'csv'; // 'csv' or 'simple'
let bulkSendingActive = false;
let bulkPaused = false;
let bulkStopped = false;

// Attachment storage
let singleAttachmentData = null;
let bulkAttachmentData = null;

// Utility: sleep
function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    initTabs();
    loadAccounts();
    loadEc2Credentials(); // Load saved credentials first
    loadEc2Instances();
    syncBatchSection();
    renderAllLibraries();
    
    // Show/hide custom SMTP fields
    document.getElementById('smtpProvider').addEventListener('change', function() {
        const customFields = document.getElementById('customSmtpFields');
        customFields.style.display = this.value === 'custom' ? 'block' : 'none';
    });
    
    // Auto-update bulk stats when CSV changes
    const bulkCsv = document.getElementById('bulkCsv');
    if (bulkCsv) {
        bulkCsv.addEventListener('input', updateBulkStats);
    }
    
    // Auto-update bulk stats when method changes
    const bulkMethod = document.getElementById('bulkMethod');
    if (bulkMethod) {
        bulkMethod.addEventListener('change', updateBulkStats);
    }
});

// Tab switching
function initTabs() {
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');
    
    tabBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            const tabName = this.dataset.tab;
            
            // Remove active class from all
            tabBtns.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));
            
            // Add active class to current
            this.classList.add('active');
            document.getElementById(tabName).classList.add('active');
        });
    });
}

// Load saved accounts from API
async function loadAccounts() {
    try {
        const response = await fetch('/api/accounts');
        const data = await response.json();
        
        if (data.success) {
            smtpAccounts = data.accounts.smtp_accounts || [];
            sesAccounts = data.accounts.ses_accounts || [];
            
            renderSmtpAccounts();
            renderSesAccounts();
        }
    } catch (error) {
        console.error('Failed to load accounts:', error);
    }
}

async function loadEc2Instances() {
    try {
        // Get saved credentials from localStorage
        const savedCreds = localStorage.getItem('aws_credentials');
        if (!savedCreds) {
            console.log('No AWS credentials found in localStorage');
            ec2Instances = [];
            renderEc2Instances(ec2Instances);
            return;
        }
        
        const creds = JSON.parse(savedCreds);
        
        // First, send credentials to backend
        await fetch('/api/ec2_management', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                action: 'save_credentials',
                ...creds
            })
        });
        
        // Then fetch instances
        const response = await fetch('/api/ec2_management');
        const data = await response.json();
        
        if (data.success) {
            ec2Instances = data.instances || [];
            renderEc2Instances(ec2Instances);
            console.log('Loaded EC2 instances:', ec2Instances.length);
        }
    } catch (error) {
        console.error('Failed to load EC2 instances:', error);
        ec2Instances = [];
    }
}

// Load AWS credentials from localStorage
function loadEc2Credentials() {
    try {
        const savedCreds = localStorage.getItem('aws_credentials');
        if (savedCreds) {
            const creds = JSON.parse(savedCreds);
            document.getElementById('ec2AccessKey').value = creds.access_key || '';
            document.getElementById('ec2SecretKey').value = creds.secret_key || '';
            document.getElementById('ec2Region').value = creds.region || 'us-east-1';
            document.getElementById('ec2Keypair').value = creds.keypair || '';
            document.getElementById('ec2SecurityGroup').value = creds.security_group || '';
        }
    } catch (error) {
        console.error('Failed to load AWS credentials:', error);
    }
}

// SMTP Functions
async function testSmtpConnection() {
    const provider = document.getElementById('smtpProvider').value;
    const user = document.getElementById('smtpUser').value;
    const pass = document.getElementById('smtpPass').value;
    
    if (!user || !pass) {
        showResult('smtpResult', 'Please fill in all required fields', 'error');
        return;
    }
    
    const smtpConfig = {
        provider: provider,
        user: user,
        pass: pass
    };
    
    if (provider === 'custom') {
        smtpConfig.host = document.getElementById('smtpHost').value;
        smtpConfig.port = document.getElementById('smtpPort').value;
    }
    
    showResult('smtpResult', '🔄 Testing SMTP connection...', 'info');
    
    try {
        const response = await fetch('/api/test_smtp', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                type: 'smtp',
                smtp_config: smtpConfig
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showResult('smtpResult', `✅ ${data.message}`, 'success');
        } else {
            showResult('smtpResult', `❌ ${data.error}`, 'error');
        }
    } catch (error) {
        showResult('smtpResult', `❌ Connection failed: ${error.message}`, 'error');
    }
}

async function addSmtpAccount() {
    const provider = document.getElementById('smtpProvider').value;
    const user = document.getElementById('smtpUser').value;
    const pass = document.getElementById('smtpPass').value;
    const senderName = document.getElementById('smtpSenderName').value || 'KINGMAILER';
    const label = document.getElementById('smtpLabel').value || `${provider} - ${user}`;
    
    if (!user || !pass) {
        showResult('smtpResult', 'Please fill in all required fields', 'error');
        return;
    }
    
    const account = {
        type: 'smtp',
        provider: provider,
        user: user,
        pass: pass,
        sender_name: senderName,
        label: label
    };
    
    if (provider === 'custom') {
        account.host = document.getElementById('smtpHost').value;
        account.port = document.getElementById('smtpPort').value;
    }
    
    try {
        const response = await fetch('/api/accounts', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(account)
        });
        
        const data = await response.json();
        
        if (data.success) {
            showResult('smtpResult', '✅ SMTP account added successfully!', 'success');
            loadAccounts();
            
            // Clear form
            document.getElementById('smtpUser').value = '';
            document.getElementById('smtpPass').value = '';
            document.getElementById('smtpSenderName').value = '';
            document.getElementById('smtpLabel').value = '';
        } else {
            showResult('smtpResult', `❌ ${data.error}`, 'error');
        }
    } catch (error) {
        showResult('smtpResult', `❌ Failed to add account: ${error.message}`, 'error');
    }
}

function renderSmtpAccounts() {
    const container = document.getElementById('smtpAccountsList');
    
    if (smtpAccounts.length === 0) {
        container.innerHTML = '<p class="no-accounts">No SMTP accounts added yet</p>';
        return;
    }
    
    container.innerHTML = smtpAccounts.map(acc => `
        <div class="account-card">
            <div class="account-info">
                <strong>${acc.label}</strong><br>
                <small>${acc.user} (${acc.provider})</small><br>
                <small style="color: #888;">Sender: ${acc.sender_name || 'KINGMAILER'}</small>
            </div>
            <button class="btn btn-danger" onclick="deleteAccount('smtp', ${acc.id})">Delete</button>
        </div>
    `).join('');
}

// SES Functions
async function testSesConnection() {
    const accessKey = document.getElementById('sesAccessKey').value;
    const secretKey = document.getElementById('sesSecretKey').value;
    const region = document.getElementById('sesRegion').value;
    
    if (!accessKey || !secretKey) {
        showResult('sesResult', 'Please fill in all required fields', 'error');
        return;
    }
    
    showResult('sesResult', '🔄 Testing AWS SES connection...', 'info');
    
    try {
        const response = await fetch('/api/test_smtp', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                type: 'ses',
                aws_config: {
                    access_key: accessKey,
                    secret_key: secretKey,
                    region: region
                }
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showResult('sesResult', `✅ ${data.message}`, 'success');
        } else {
            showResult('sesResult', `❌ ${data.error}`, 'error');
        }
    } catch (error) {
        showResult('sesResult', `❌ Connection failed: ${error.message}`, 'error');
    }
}

async function addSesAccount() {
    const accessKey = document.getElementById('sesAccessKey').value;
    const secretKey = document.getElementById('sesSecretKey').value;
    const region = document.getElementById('sesRegion').value;
    const fromEmail = document.getElementById('sesFromEmail').value;
    
    if (!accessKey || !secretKey || !fromEmail) {
        showResult('sesResult', 'Please fill in all required fields', 'error');
        return;
    }
    
    try {
        const response = await fetch('/api/accounts', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                type: 'ses',
                access_key: accessKey,
                secret_key: secretKey,
                region: region,
                from_email: fromEmail,
                label: `SES - ${fromEmail}`
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showResult('sesResult', '✅ AWS SES account added successfully!', 'success');
            loadAccounts();
            
            // Clear form
            document.getElementById('sesAccessKey').value = '';
            document.getElementById('sesSecretKey').value = '';
            document.getElementById('sesFromEmail').value = '';
        } else {
            showResult('sesResult', `❌ ${data.error}`, 'error');
        }
    } catch (error) {
        showResult('sesResult', `❌ Failed to add account: ${error.message}`, 'error');
    }
}

function renderSesAccounts() {
    const container = document.getElementById('sesAccountsList');
    
    if (sesAccounts.length === 0) {
        container.innerHTML = '<p class="no-accounts">No SES accounts added yet</p>';
        return;
    }
    
    container.innerHTML = sesAccounts.map(acc => `
        <div class="account-card">
            <div class="account-info">
                <strong>${acc.label}</strong><br>
                <small>${acc.from_email} (${acc.region})</small>
            </div>
            <button class="btn btn-danger" onclick="deleteAccount('ses', ${acc.id})">Delete</button>
        </div>
    `).join('');
}

// EC2 Management Functions
async function saveAwsCredentials() {
    const accessKey = document.getElementById('ec2AccessKey').value;
    const secretKey = document.getElementById('ec2SecretKey').value;
    const region = document.getElementById('ec2Region').value;
    const keypair = document.getElementById('ec2Keypair').value;
    const securityGroup = document.getElementById('ec2SecurityGroup').value;
    
    if (!accessKey || !secretKey || !region || !keypair) {
        showResult('ec2Result', 'Please fill in all AWS credentials fields', 'error');
        return;
    }
    
    showResult('ec2Result', '🔄 Saving AWS credentials...', 'info');
    
    try {
        const response = await fetch('/api/ec2_management', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                action: 'save_credentials',
                access_key: accessKey,
                secret_key: secretKey,
                region: region,
                keypair: keypair,
                security_group: securityGroup || ''
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Save credentials to localStorage
            const credentials = {
                access_key: accessKey,
                secret_key: secretKey,
                region: region,
                keypair: keypair,
                security_group: securityGroup || ''
            };
            localStorage.setItem('aws_credentials', JSON.stringify(credentials));
            
            showResult('ec2Result', '✅ AWS credentials saved successfully!', 'success');
            
            // Reload instances after saving credentials
            setTimeout(() => loadEc2Instances(), 1000);
        } else {
            showResult('ec2Result', `❌ ${data.error}`, 'error');
        }
    } catch (error) {
        showResult('ec2Result', `❌ Failed to save credentials: ${error.message}`, 'error');
    }
}

async function restartRelay(instanceId) {
    showResult('ec2Result', `🔄 Connecting to ${instanceId} via SSM... (may take ~30s)`, 'info');
    try {
        const data = await safeFetchJson('/api/ec2_management', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ action: 'restart_relay', instance_id: instanceId })
        });

        if (data.success) {
            let msg = `✅ ${data.message}`;
            if (data.output) msg += `<br><pre style="font-size:11px;margin-top:6px;white-space:pre-wrap;overflow:auto;">${data.output}</pre>`;
            showResult('ec2Result', msg, 'success');
        } else if (data.ssm_role_attached) {
            // SSM role just attached — start a 60-second countdown then auto-retry
            let secs = 60;
            const el = document.getElementById('ec2Result');
            el.className = 'result-box info';
            el.style.display = 'block';
            const tick = setInterval(() => {
                secs--;
                el.innerHTML = `🔑 SSM role attached to instance.<br>⏳ Auto-retrying in <strong>${secs}</strong>s — SSM agent needs time to register...`;
                if (secs <= 0) {
                    clearInterval(tick);
                    el.innerHTML = `🔄 Retrying relay restart...`;
                    restartRelay(instanceId);
                }
            }, 1000);
            el.innerHTML = `🔑 SSM role attached to instance.<br>⏳ Auto-retrying in <strong>${secs}</strong>s — SSM agent needs time to register...`;
        } else if (data.ssm_not_available) {
            showResult('ec2Result',
                `⚠️ ${data.message || data.error}<br><br>` +
                `<strong>Fix:</strong> <button class="btn btn-danger" style="font-size:12px;" onclick="terminateAndRecreate('${instanceId}')">🔄 Terminate &amp; Create Fresh Instance</button>`,
                'error');
        } else {
            showResult('ec2Result', `❌ ${data.error || data.message}`, 'error');
        }
    } catch (error) {
        showResult('ec2Result', `❌ Restart failed: ${error.message}`, 'error');
    }
}

async function fixRelay(instanceId) {
    if (!confirm(`This will STOP the instance, update its setup script, then restart it.\n\nThe relay will be fully reinstalled on the next boot.\n\nProceed with Fix Relay on ${instanceId}?`)) return;
    showResult('ec2Result', `🔧 Fixing relay on ${instanceId}...<br><small>Step 1/3: Stopping instance (may take ~60s)...</small>`, 'info');
    try {
        const data = await safeFetchJson('/api/ec2_management', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ action: 'fix_relay', instance_id: instanceId })
        });

        if (data.success) {
            showResult('ec2Result',
                `✅ ${data.message}<br><br>` +
                `<strong>Next steps:</strong><ul style="margin:6px 0 0 16px;font-size:13px;">` +
                `<li>Wait 3-5 minutes for the instance to boot and install the relay</li>` +
                `<li>Click <strong>Check Health</strong> to verify the relay is running</li>` +
                `</ul>`,
                'success');
            setTimeout(() => refreshEc2Instances(), 5000);
        } else {
            showResult('ec2Result', `❌ ${data.error || data.message}`, 'error');
        }
    } catch (error) {
        showResult('ec2Result', `❌ Fix relay failed: ${error.message}`, 'error');
    }
}

async function terminateAndRecreate(instanceId) {
    if (!confirm(`Terminate ${instanceId} and create a fresh instance with the fixed setup?`)) return;
    showResult('ec2Result', '🔄 Terminating instance...', 'info');
    try {
        const termData = await safeFetchJson('/api/ec2_management', {
            method: 'DELETE',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ instance_id: instanceId })
        });
        if (!termData.success) {
            showResult('ec2Result', `❌ Terminate failed: ${termData.error}`, 'error');
            return;
        }
        showResult('ec2Result', '✅ Terminated. Creating fresh instance...', 'info');
        await sleep(2000);
        await createEc2Instance();
    } catch (err) {
        showResult('ec2Result', `❌ ${err.message}`, 'error');
    }
}

async function createEc2Instance() {
    showResult('ec2Result', '🔄 Creating EC2 instance... This may take 2-3 minutes.', 'info');
    
    try {
        const response = await fetch('/api/ec2_management', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                action: 'create_instance'
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showResult('ec2Result', 
                `✅ EC2 instance created!<br>
                Instance ID: ${data.instance.instance_id}<br>
                Public IP: ${data.instance.public_ip}<br>
                Region: ${data.instance.region}`, 
                'success'
            );
            await refreshEc2Instances();
        } else {
            showResult('ec2Result', `❌ ${data.error}`, 'error');
        }
    } catch (error) {
        showResult('ec2Result', `❌ Failed to create instance: ${error.message}`, 'error');
    }
}

async function refreshEc2Instances() {
    showResult('ec2Result', '🔄 Refreshing EC2 instances list...', 'info');
    
    try {
        const response = await fetch('/api/ec2_management', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                action: 'list_instances'
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Update global ec2Instances array
            ec2Instances = data.instances || [];
            renderEc2Instances(ec2Instances);
            showResult('ec2Result', `✅ Found ${ec2Instances.length} instances`, 'success');
            console.log('EC2 instances refreshed:', ec2Instances.length);
            
            // Auto-refresh if there are pending instances
            const pendingCount = ec2Instances.filter(i => i.state === 'pending').length;
            if (pendingCount > 0) {
                console.log(`Auto-refresh: ${pendingCount} instances still pending`);
                setTimeout(() => refreshEc2Instances(), 30000); // Check again in 30 seconds
            }
        } else {
            showResult('ec2Result', `❌ ${data.error}`, 'error');
        }
    } catch (error) {
        showResult('ec2Result', `❌ Failed to refresh instances: ${error.message}`, 'error');
    }
}

async function terminateEc2Instance(instanceId) {
    if (!confirm(`Are you sure you want to terminate instance ${instanceId}?`)) {
        return;
    }
    
    showResult('ec2Result', '🔄 Terminating EC2 instance...', 'info');
    
    try {
        const response = await fetch('/api/ec2_management', {
            method: 'DELETE',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                instance_id: instanceId
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showResult('ec2Result', `✅ ${data.message}`, 'success');
            await refreshEc2Instances();
        } else {
            showResult('ec2Result', `❌ ${data.error}`, 'error');
        }
    } catch (error) {
        showResult('ec2Result', `❌ Failed to terminate instance: ${error.message}`, 'error');
    }
}

async function checkEc2Health() {
    if (ec2Instances.length === 0) {
        showResult('ec2HealthResult', '⚠️ No EC2 instances to check. Create instances first.', 'error');
        document.getElementById('ec2HealthResult').style.display = 'block';
        return;
    }
    
    showResult('ec2HealthResult', '🔄 Checking EC2 relay health...', 'info');
    document.getElementById('ec2HealthResult').style.display = 'block';
    
    try {
        const response = await fetch('/api/ec2_health', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                instances: ec2Instances
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            const summary = data.summary;
            let resultHtml = `
                <strong>EC2 Relay Health Check Results</strong><br><br>
                📊 Summary: ${summary.healthy}/${summary.total} instances healthy<br><br>
            `;
            
            data.instances.forEach(instance => {
                const statusIcon = instance.healthy ? '✅' : '❌';
                const statusColor = instance.healthy ? (instance.warnings ? '#ff9800' : '#00ff9d') : '#ff6b6b';
                
                resultHtml += `
                    <div style="border-left: 3px solid ${statusColor}; padding-left: 10px; margin: 10px 0;">
                        ${statusIcon} <strong>${instance.instance_id}</strong> (${instance.public_ip})<br>
                        <small>Status: ${instance.status}</small><br>
                `;
                
                if (instance.healthy) {
                    resultHtml += `
                        <small style="color: #00ff9d;">
                            ✓ Relay endpoint ready: ${instance.relay_url}<br>
                            ✓ Method: ${instance.method || 'Authenticated SMTP'}<br>
                            ✓ Port 587 Outbound: ${instance.port_587_outbound || 'unknown'}<br>
                            ✓ Port 465 Outbound: ${instance.port_465_outbound || 'unknown'}<br>
                    `;
                    
                    if (instance.info) {
                        resultHtml += `            <small style="color: #888;">💡 ${instance.info}</small><br>`;
                    }
                    
                    resultHtml += `            ✓ Checked at: ${instance.timestamp}
                        </small>
                    `;
                    
                    // Show warnings if any
                    if (instance.warnings && instance.warnings.length > 0) {
                        resultHtml += `
                        <div style="margin-top: 8px; padding: 8px; background: rgba(255, 152, 0, 0.1); border-radius: 4px;">
                            <small style="color: #ff9800; display: block;">
                                ${instance.warnings.join('<br>')}
                            </small>
                        </div>
                        `;
                    }
                } else {
                    resultHtml += `
                        <small style="color: #ff6b6b;">
                            ${instance.message}<br>
                            ${instance.help ? '💡 ' + instance.help : ''}
                        </small>
                    `;
                }
                
                resultHtml += `</div>`;
            });
            
            showResult('ec2HealthResult', resultHtml, summary.healthy === summary.total ? 'success' : 'error');
        } else {
            showResult('ec2HealthResult', `❌ ${data.error}`, 'error');
        }
    } catch (error) {
        showResult('ec2HealthResult', `❌ Health check failed: ${error.message}`, 'error');
    }
}

function renderEc2Instances(instances) {
    const container = document.getElementById('ec2InstancesList');
    
    if (!instances || instances.length === 0) {
        container.innerHTML = '<p class="no-accounts">No EC2 instances found</p>';
        return;
    }
    
    container.innerHTML = instances.map(instance => {
        const stateColors = {
            'running': '#00ff9d',
            'pending': '#f59e0b', 
            'stopped': '#888',
            'stopping': '#888',
            'terminated': '#f87171'
        };
        const stateColor = stateColors[instance.state] || '#888';
        const stateEmoji = instance.state === 'running' ? '✅' : instance.state === 'pending' ? '⏳' : '⚠️';
        
        return `
        <div class="account-card">
            <div class="account-info">
                <strong>Instance: ${instance.instance_id}</strong><br>
                <small>
                    IP: <strong>${instance.public_ip || 'Pending...'}</strong><br>
                    Region: ${instance.region}<br>
                    State: <span style="color: ${stateColor}; font-weight: bold;">${stateEmoji} ${instance.state.toUpperCase()}</span><br>
                    ${instance.state === 'pending' ? '<span style="color: #f59e0b;">⏳ Initializing... Auto-refreshing every 30s</span><br>' : ''}
                    ${instance.state === 'running' ? '<span style="color: #00ff9d;">✅ Ready for email relay (port 3000)</span><br>' : ''}
                    Created: ${instance.created_at}
                </small>
            </div>
            <div style="display:flex; flex-direction:column; gap:6px;">
                ${instance.state === 'running' ? `<button class="btn" style="background:#f59e0b;color:#000;font-size:12px;padding:5px 10px;" onclick="restartRelay('${instance.instance_id}')">🔄 Restart Relay</button>` : ''}
                ${(instance.state === 'running' || instance.state === 'stopped') ? `<button class="btn" style="background:#6366f1;color:#fff;font-size:12px;padding:5px 10px;" onclick="fixRelay('${instance.instance_id}')">🔧 Fix Relay</button>` : ''}
                <button class="btn btn-danger" onclick="terminateEc2Instance('${instance.instance_id}')">Terminate</button>
            </div>
        </div>
    `;
    }).join('');
}

// Delete account
async function deleteAccount(type, id) {
    if (!confirm('Are you sure you want to delete this account?')) {
        return;
    }
    
    try {
        const response = await fetch('/api/accounts', {
            method: 'DELETE',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ type, id })
        });
        
        const data = await response.json();
        
        if (data.success) {
            loadAccounts();
        }
    } catch (error) {
        console.error('Failed to delete account:', error);
    }
}

// File upload handler
function handleFileUpload(event) {
    const file = event.target.files[0];
    if (!file) return;
    
    const reader = new FileReader();
    reader.onload = function(e) {
        const content = e.target.result;
        document.getElementById('bulkCsv').value = content;
        updateBulkStats();
    };
    reader.readAsText(file);
}

// Switch between CSV and simple email list mode
function switchInputMode() {
    inputMode = inputMode === 'csv' ? 'simple' : 'csv';
    const label = document.getElementById('inputModeLabel');
    const textarea = document.getElementById('bulkCsv');
    
    if (inputMode === 'simple') {
        label.textContent = 'Mode: Simple (One Email Per Line)';
        textarea.placeholder = 'john@example.com\njane@example.com\nbob@example.com\nalice@example.com';
    } else {
        label.textContent = 'Mode: CSV Format';
        textarea.placeholder = 'email,name,company\njohn@example.com,John,ACME Corp\njane@example.com,Jane,Tech Inc';
    }
}

// Update send method info
function updateSendMethodInfo() {
    const method = document.getElementById('bulkMethod').value;
    const infoBox = document.getElementById('sendMethodInfo');
    
    if (method === 'smtp') {
        infoBox.innerHTML = '<strong>Gmail SMTP Mode:</strong> Rotates between your configured Gmail accounts. Emails are sent from Gmail servers (Gmail IP addresses). Good for moderate volumes but Gmail may limit sending rate.';
        infoBox.style.display = 'block';
        infoBox.style.background = '#2d2d2d';
    } else if (method === 'ec2') {
        infoBox.innerHTML = '<strong>⭐ EC2 Relay Mode:</strong> Sends emails through your EC2 relay server. Emails originate from YOUR EC2 IP address (not Gmail). <span style="color: #00ff9d;">Best for inbox delivery - you control the IP reputation!</span> Make sure relay server is healthy (use Check Health button).';
        infoBox.style.display = 'block';
        infoBox.style.background = 'linear-gradient(135deg, #1a472a 0%, #2d5016 100%)';
    } else if (method === 'ses') {
        infoBox.innerHTML = '<strong>AWS SES Mode:</strong> Uses Amazon SES servers. Best for high volume (10,000+ emails/day). Requires verified domain or sender email.';
        infoBox.style.display = 'block';
        infoBox.style.background = '#2d2d2d';
    }
    
    updateBulkStats();
}

// Update bulk send statistics
function updateBulkStats() {
    const csv = document.getElementById('bulkCsv').value.trim();
    if (!csv) {
        document.getElementById('bulkStats').style.display = 'none';
        return;
    }
    
    // Count emails
    let emailCount = 0;
    if (inputMode === 'simple') {
        const lines = csv.split('\n').filter(line => line.trim() && line.includes('@'));
        emailCount = lines.length;
    } else {
        const lines = csv.split('\n').filter(line => line.trim());
        emailCount = Math.max(0, lines.length - 1); // Exclude header
    }
    
    // Count SMTP accounts
    const method = document.getElementById('bulkMethod').value;
    let smtpCount = 0;
    if (method === 'smtp') {
        smtpCount = smtpAccounts.length;
    } else if (method === 'ec2') {
        smtpCount = ec2Instances.filter(i => i.state === 'running').length;
    }
    
    // Update display
    document.getElementById('bulkStats').style.display = 'block';
    document.getElementById('totalEmails').textContent = emailCount;
    document.getElementById('smtpConfigured').textContent = smtpCount;
    
    if (!bulkSendingActive) {
        document.getElementById('sentCount').textContent = '0';
        document.getElementById('failedCount').textContent = '0';
        document.getElementById('progressBar').style.width = '0%';
        document.getElementById('progressText').textContent = '0%';
    }
}

// Update progress during bulk send
function updateBulkProgress(sent, failed, total) {
    document.getElementById('sentCount').textContent = sent;
    document.getElementById('failedCount').textContent = failed;
    
    const progress = Math.round(((sent + failed) / total) * 100);
    document.getElementById('progressBar').style.width = progress + '%';
    document.getElementById('progressText').textContent = progress + '%';
}

// Send single email
async function sendSingleEmail() {
    const to = document.getElementById('singleTo').value;
    const subject = document.getElementById('singleSubject').value;
    const html = document.getElementById('singleHtml').value;
    const method = document.getElementById('singleMethod').value;
    
    if (!to || !subject || !html) {
        showResult('singleResult', 'Please fill in all fields', 'error');
        return;
    }
    
    // Get config based on method
    let config = {};
    
    if (method === 'smtp') {
        if (smtpAccounts.length === 0) {
            showResult('singleResult', 'Please add an SMTP account first', 'error');
            return;
        }
        config.smtp_config = smtpAccounts[0];
    } else if (method === 'ses') {
        if (sesAccounts.length === 0) {
            showResult('singleResult', 'Please add an AWS SES account first', 'error');
            return;
        }
        config.aws_config = sesAccounts[0];
    } else if (method === 'ec2') {
        if (ec2Instances.length === 0) {
            showResult('singleResult', 'Please create an EC2 instance first', 'error');
            return;
        }
        // Get first running instance
        const runningInstance = ec2Instances.find(i => i.state === 'running');
        if (!runningInstance) {
            const pending = ec2Instances.filter(i => i.state === 'pending').length;
            showResult('singleResult', pending > 0 ? `⏳ EC2 instance still initializing. Wait 3-5 minutes.` : '❌ No running EC2 instances', 'error');
            return;
        }
        config.ec2_instance = runningInstance;
        // Auto-include SMTP accounts so EC2 relay can authenticate and send from EC2 IP
        if (smtpAccounts.length > 0) {
            config.smtp_config = smtpAccounts[0];
        }
    }
    
    showResult('singleResult', '🔄 Sending email...', 'info');
    
    // Get attachment if any
    const attachment = await getAttachmentData('single');
    if (attachmentTooLarge(attachment, 'singleResult')) return;
    
    try {
        const data = await safeFetchJson('/api/send', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                to: to,
                subject: subject,
                html: html,
                method: method,
                ...(attachment ? { attachment } : {}),
                ...config
            })
        });
        
        if (data.success) {
            showResult('singleResult', `✅ ${data.message}`, 'success');
        } else {
            showResult('singleResult', `❌ ${data.error}`, 'error');
        }
    } catch (error) {
        showResult('singleResult', `❌ Send failed: ${error.message}`, 'error');
    }
}

// Send bulk emails — client-side loop for real-time progress, stop, pause
async function sendBulkEmails() {
    let csv = document.getElementById('bulkCsv').value.trim();
    const subject = document.getElementById('bulkSubject').value;
    const html = document.getElementById('bulkHtml').value;
    const method = document.getElementById('bulkMethod').value;
    const minDelay = parseFloat(document.getElementById('bulkMinDelay').value) || 1;
    const maxDelay = parseFloat(document.getElementById('bulkMaxDelay').value) || 3;
    
    if (!csv || !subject || !html) {
        showResult('bulkResult', 'Please fill in all fields', 'error');
        return;
    }
    
    // Convert simple format to CSV if needed
    if (inputMode === 'simple') {
        const emails = csv.split('\n').filter(line => line.trim() && line.includes('@'));
        csv = 'email\n' + emails.join('\n');
    }
    
    // Parse CSV
    const lines = csv.split('\n').filter(line => line.trim());
    if (lines.length < 2) {
        showResult('bulkResult', 'CSV must have a header row and at least one email', 'error');
        return;
    }
    const headers = lines[0].split(',').map(h => h.trim().toLowerCase());
    const emailIndex = headers.indexOf('email');
    if (emailIndex === -1) {
        showResult('bulkResult', 'CSV must have an "email" column header', 'error');
        return;
    }
    
    // Build rows array from CSV
    const rows = [];
    for (let i = 1; i < lines.length; i++) {
        const vals = lines[i].split(',').map(v => v.trim());
        if (!vals[emailIndex] || !vals[emailIndex].includes('@')) continue;
        const row = {};
        headers.forEach((h, idx) => { row[h] = vals[idx] || ''; });
        rows.push(row);
    }
    
    if (rows.length === 0) {
        showResult('bulkResult', 'No valid email addresses found in CSV', 'error');
        return;
    }
    
    // Validate config
    let runningInstances = [];
    if (method === 'smtp') {
        if (smtpAccounts.length === 0) {
            showResult('bulkResult', 'Please add at least one SMTP account first', 'error');
            return;
        }
    } else if (method === 'ses') {
        if (sesAccounts.length === 0) {
            showResult('bulkResult', 'Please add an AWS SES account first', 'error');
            return;
        }
    } else if (method === 'ec2') {
        runningInstances = ec2Instances.filter(i => i.state === 'running');
        if (runningInstances.length === 0) {
            const pending = ec2Instances.filter(i => i.state === 'pending').length;
            showResult('bulkResult', pending > 0 ?
                `⏳ EC2 instances still initializing (${pending} pending). Wait 3-5 min.` :
                '❌ No running EC2 instances', 'error');
            return;
        }
    }
    
    // Prepare attachment (convert HTML file to selected format BEFORE starting loop)
    showResult('bulkResult', '⏳ Preparing attachment (if any)...', 'info');
    const attachment = await getAttachmentData('bulk');
    
    // Set send state
    bulkSendingActive = true;
    bulkStopped = false;
    bulkPaused = false;
    
    // Show stop/pause buttons, hide start
    document.getElementById('startBulkBtn').style.display = 'none';
    document.getElementById('pauseBulkBtn').style.display = 'inline-block';
    document.getElementById('pauseBulkBtn').textContent = '⏸ Pause';
    document.getElementById('stopBulkBtn').style.display = 'inline-block';
    
    // Show real-time log
    document.getElementById('bulkLog').style.display = 'block';
    document.getElementById('bulkLogContent').innerHTML = '';
    
    const methodNames = { smtp: 'Gmail SMTP', ec2: 'EC2 Relay', ses: 'AWS SES' };
    showResult('bulkResult', `🔄 Bulk sending via ${methodNames[method]} — ${rows.length} emails...`, 'info');
    updateBulkStats();
    
    let sent = 0;
    let failed = 0;
    let rotateIdx = 0;
    
    for (let i = 0; i < rows.length; i++) {
        // Stop check
        if (bulkStopped) break;
        
        // Pause — wait until resumed or stopped
        while (bulkPaused && !bulkStopped) {
            await sleep(400);
        }
        if (bulkStopped) break;
        
        const row = rows[i];
        const toEmail = row['email'];
        
        // Build payload for this email
        const emailPayload = {
            to: toEmail,
            subject: subject,
            html: html,
            method: method,
            csv_row: row
        };
        
        if (method === 'smtp') {
            emailPayload.smtp_config = smtpAccounts[rotateIdx % smtpAccounts.length];
            // Rotate SMTP account after each batch
            const batchSz = Math.max(1, parseInt((document.getElementById('batchSize') || {}).value) || 50);
            if ((i + 1) % batchSz === 0 && smtpAccounts.length > 1) {
                const rotMode = (document.getElementById('smtpRotation') || {}).value || 'sequential';
                if (rotMode === 'random') {
                    rotateIdx = Math.floor(Math.random() * smtpAccounts.length);
                } else {
                    rotateIdx++;
                }
                const batchInfoEl = document.getElementById('batchInfoDisplay');
                if (batchInfoEl) {
                    const acc = smtpAccounts[rotateIdx % smtpAccounts.length];
                    batchInfoEl.style.display = 'block';
                    batchInfoEl.textContent = `🔄 SMTP rotated → ${acc.user} (account ${(rotateIdx % smtpAccounts.length) + 1}/${smtpAccounts.length}, after ${i + 1} emails)`;
                }
            } else {
                // No rotation — still track index per-email for sequential mode when batch not met
                if (smtpAccounts.length === 1) rotateIdx = 0;
            }
        } else if (method === 'ses') {
            emailPayload.aws_config = sesAccounts[0];
        } else if (method === 'ec2') {
            emailPayload.ec2_instance = runningInstances[rotateIdx % runningInstances.length];
            if (smtpAccounts.length > 0) {
                emailPayload.smtp_config = smtpAccounts[rotateIdx % smtpAccounts.length];
            }
            rotateIdx++;
        }
        
        if (attachment) emailPayload.attachment = attachment;
        
        // Log entry for this email
        const logLine = document.createElement('div');
        logLine.style.color = '#aaa';
        logLine.textContent = `[${i+1}/${rows.length}] Sending to ${toEmail}...`;
        document.getElementById('bulkLogContent').appendChild(logLine);
        document.getElementById('bulkLog').scrollTop = document.getElementById('bulkLog').scrollHeight;
        
        try {
            const result = await safeFetchJson('/api/send', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(emailPayload)
            });
            
            if (result.success) {
                sent++;
                logLine.style.color = '#00ff9d';
                logLine.textContent = `[${i+1}/${rows.length}] ✅ ${toEmail}`;
            } else {
                failed++;
                logLine.style.color = '#f87171';
                logLine.textContent = `[${i+1}/${rows.length}] ❌ ${toEmail}: ${result.error}`;
            }
        } catch (err) {
            failed++;
            logLine.style.color = '#f87171';
            logLine.textContent = `[${i+1}/${rows.length}] ❌ ${toEmail}: ${err.message}`;
        }
        
        // Update progress bar in real-time
        updateBulkProgress(sent, failed, rows.length);
        
        // Delay between emails (skip on last or if stopped)
        if (i < rows.length - 1 && !bulkStopped) {
            const delayMs = (Math.random() * (maxDelay - minDelay) + minDelay) * 1000;
            await sleep(delayMs);
        }
    }
    
    // Wrap up
    bulkSendingActive = false;
    bulkPaused = false;
    bulkStopped = false;
    
    document.getElementById('startBulkBtn').style.display = 'inline-block';
    document.getElementById('pauseBulkBtn').style.display = 'none';
    document.getElementById('stopBulkBtn').style.display = 'none';
    
    const stopped = sent + failed < rows.length;
    const msg = stopped
        ? `⏹ Stopped. Sent: ${sent} ✅ &nbsp; Failed: ${failed} ❌ &nbsp; Remaining: ${rows.length - sent - failed}`
        : `✅ Done! Sent: ${sent} ✅ &nbsp; Failed: ${failed} ❌ &nbsp; Total: ${rows.length}`;
    showResult('bulkResult', msg, sent > 0 ? 'success' : 'error');
}

// Pause bulk send toggle
function pauseBulkSend() {
    if (!bulkSendingActive) return;
    bulkPaused = !bulkPaused;
    document.getElementById('pauseBulkBtn').textContent = bulkPaused ? '▶ Resume' : '⏸ Pause';
    if (bulkPaused) {
        showResult('bulkResult', '⏸ Paused — click Resume to continue', 'info');
    } else {
        showResult('bulkResult', '▶ Resumed...', 'info');
    }
}

// Stop bulk send
function stopBulkSend() {
    bulkStopped = true;
    bulkPaused = false;
    showResult('bulkResult', '⏹ Stopping... finishing current email.', 'info');
}

// Toggle placeholder reference panel
function togglePlaceholders(divId) {
    const div = document.getElementById(divId);
    const btn = div.previousElementSibling;
    if (div.style.display === 'none') {
        div.style.display = 'block';
        btn.textContent = '📋 Hide Placeholders';
    } else {
        div.style.display = 'none';
        btn.textContent = '📋 Show Placeholders';
    }
}

// Load HTML file for attachment
function loadHtmlAttachment(context, event) {
    const file = event.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = function(e) {
        const data = { name: file.name, content: e.target.result };
        if (context === 'single') {
            singleAttachmentData = data;
            document.getElementById('singleAttachName').textContent = `📎 ${file.name}`;
            document.getElementById('singleClearAttach').style.display = 'inline-block';
        } else {
            bulkAttachmentData = data;
            document.getElementById('bulkAttachName').textContent = `📎 ${file.name}`;
            document.getElementById('bulkClearAttach').style.display = 'inline-block';
        }
    };
    reader.readAsText(file);
}

// Remove loaded attachment
function clearAttachment(context) {
    if (context === 'single') {
        singleAttachmentData = null;
        document.getElementById('singleAttachName').textContent = '';
        document.getElementById('singleClearAttach').style.display = 'none';
        document.getElementById('singleHtmlFile').value = '';
    } else {
        bulkAttachmentData = null;
        document.getElementById('bulkAttachName').textContent = '';
        document.getElementById('bulkClearAttach').style.display = 'none';
        document.getElementById('bulkHtmlFile').value = '';
    }
}

// Generate a unique hyphen-formatted filename (10-16 digits total)
// format '5-6-5' → 5+6+5=16 digits e.g. '73291-847362-10583'
function generateAttachName(format) {
    if (!format || format === 'none') return null;
    const presets = ['5-6-5','8-8','4-4-4-4','6-4-6','4-6-4','6-6','4-4-4','3-4-3','5-5'];
    if (format === 'random') format = presets[Math.floor(Math.random() * presets.length)];
    return format.split('-').map(seg => {
        const n = parseInt(seg);
        const min = Math.pow(10, n - 1);
        const max = Math.pow(10, n) - 1;
        return String(Math.floor(Math.random() * (max - min + 1)) + min);
    }).join('-');
}

// Convert HTML attachment to selected format and return base64 object
async function getAttachmentData(context) {
    const raw = context === 'single' ? singleAttachmentData : bulkAttachmentData;
    const format = document.getElementById(context + 'AttachFormat').value;
    if (!raw) return null;

    // Build unique filename with selected format
    const nameFmtEl = document.getElementById(context + 'AttachNameFormat');
    const nameFmt = nameFmtEl ? nameFmtEl.value : 'random';
    const uniqueCode = generateAttachName(nameFmt);
    const buildName = (ext) => uniqueCode ? (uniqueCode + ext) : raw.name.replace(/\.(html|htm)$/i, ext);

    if (format === 'html') {
        try {
            // Reliable Unicode → base64 (handles all HTML charsets)
            let b64;
            try {
                b64 = btoa(unescape(encodeURIComponent(raw.content)));
            } catch (_) {
                // Fallback for edge-case Unicode
                const bytes = new TextEncoder().encode(raw.content);
                let bin = '';
                for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
                b64 = btoa(bin);
            }
            return { name: buildName('.html'), content: b64, type: 'text/html' };
        } catch (e) {
            console.error('HTML attachment encode error:', e);
            return null;
        }
    }

    // For PNG-as-JPEG or PDF — render at low scale to keep size down
    return new Promise((resolve) => {
        const iframe = document.createElement('iframe');
        iframe.style.cssText = 'position:fixed;top:-9999px;left:-9999px;width:900px;height:700px;border:none;';
        document.body.appendChild(iframe);
        iframe.onload = async function() {
            try {
                const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
                const canvas = await html2canvas(iframeDoc.body, { useCORS: true, scale: 0.7, logging: false });
                document.body.removeChild(iframe);

                const MAX_B64 = 3.5 * 1024 * 1024; // 3.5 MB base64 target

                if (format === 'png') {
                    // Use JPEG (much smaller than PNG) with progressive quality reduction
                    let quality = 0.75;
                    let dataUrl, b64;
                    do {
                        dataUrl = canvas.toDataURL('image/jpeg', quality);
                        b64 = dataUrl.split(',')[1];
                        quality -= 0.15;
                    } while (b64.length > MAX_B64 && quality > 0.1);
                    resolve({ name: buildName('.jpg'), content: b64, type: 'image/jpeg' });

                } else {
                    // PDF — embed as JPEG internally for smaller size
                    const { jsPDF } = window.jspdf;
                    const jpegUrl = canvas.toDataURL('image/jpeg', 0.7);
                    const W = 595, H = Math.round((canvas.height / canvas.width) * 595);
                    const pdf = new jsPDF({ orientation: H > W ? 'portrait' : 'landscape', unit: 'pt', format: [W, H] });
                    pdf.addImage(jpegUrl, 'JPEG', 0, 0, W, H, '', 'FAST');
                    const pdfB64 = pdf.output('datauristring').split(',')[1];
                    resolve({ name: buildName('.pdf'), content: pdfB64, type: 'application/pdf' });
                }
            } catch (err) {
                if (document.body.contains(iframe)) document.body.removeChild(iframe);
                console.error('Attachment conversion error:', err);
                resolve(null);
            }
        };
        iframe.srcdoc = raw.content;
    });
}

// Safe fetch: always returns a parsed object even if server sends non-JSON (413, 502, etc.)
async function safeFetchJson(url, options) {
    const resp = await fetch(url, options);
    const text = await resp.text();
    try {
        return JSON.parse(text);
    } catch (_) {
        if (resp.status === 413 || text.toLowerCase().includes('entity too large') || text.toLowerCase().includes('request entity')) {
            return { success: false, error: 'Attachment too large (Vercel 4.5 MB limit). Use HTML format or a smaller file.' };
        }
        if (resp.status === 504 || resp.status === 502) {
            return { success: false, error: `Server timeout (${resp.status}). Email may still have sent — check your inbox.` };
        }
        return { success: false, error: `Server error ${resp.status}: ${text.slice(0, 150)}` };
    }
}

// Check attachment size before sending (Vercel body limit ≈ 4.5 MB)
function attachmentTooLarge(attachment, resultElementId) {
    if (!attachment) return false;
    const bytes = Math.ceil(attachment.content.length * 0.75);
    const mb = bytes / (1024 * 1024);
    if (mb > 3.5) {
        showResult(resultElementId,
            `❌ Attachment is ~${mb.toFixed(1)} MB — too large for Vercel (4.5 MB limit).<br>` +
            `Try: switch format to <strong>HTML</strong>, or use a smaller/simpler HTML file.`, 'error');
        return true;
    }
    return false;
}

// Utility: Show result message
function showResult(elementId, message, type) {
    const element = document.getElementById(elementId);
    element.innerHTML = message;
    element.className = `result-box ${type}`;
    element.style.display = 'block';
}

// ── Batch section visibility ───────────────────────────────────────────────
function syncBatchSection() {
    const methodEl = document.getElementById('bulkMethod');
    const section  = document.getElementById('smtpBatchSection');
    if (!section || !methodEl) return;
    section.style.display = (methodEl.value === 'smtp') ? 'block' : 'none';
}

// ── Spintax resolver ───────────────────────────────────────────────────────
function resolveSpintax(text) {
    if (!text) return text;
    const pat = /\{([^{}]+)\}/g;
    let out = text, iter = 0;
    while (out.includes('{') && iter < 30) {
        out = out.replace(pat, (_, opts) => {
            const choices = opts.split('|');
            return choices[Math.floor(Math.random() * choices.length)];
        });
        iter++;
    }
    return out;
}

function previewSpintax(fieldId, previewId) {
    const field   = document.getElementById(fieldId);
    const preview = document.getElementById(previewId);
    if (!field || !preview) return;
    const resolved = resolveSpintax(field.value || '');
    // Strip HTML tags for preview
    const plain = resolved.replace(/<[^>]+>/g, ' ').replace(/\s{2,}/g, ' ').trim().slice(0, 250);
    preview.textContent = plain || '(empty)';
    preview.style.display = 'block';
    clearTimeout(preview._hideTimer);
    preview._hideTimer = setTimeout(() => { preview.style.display = 'none'; }, 7000);
}

// ── Library helpers ────────────────────────────────────────────────────────
const LIBRARY_KEY = 'km_library_v1';

function loadLibrary() {
    try {
        const raw = localStorage.getItem(LIBRARY_KEY);
        return raw ? JSON.parse(raw) : { subjects: [], bodies: [] };
    } catch { return { subjects: [], bodies: [] }; }
}

function saveLibrary(lib) {
    try { localStorage.setItem(LIBRARY_KEY, JSON.stringify(lib)); } catch {}
}

function escHtml(s) {
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// Save subject or body to library
// listKey: 'subjectLib' | 'bodyLib'   listElId: id of the <div> to re-render
function saveToLibrary(fieldId, listKey, listElId) {
    const field = document.getElementById(fieldId);
    if (!field || !field.value.trim()) { alert('Field is empty'); return; }
    const lib  = loadLibrary();
    const key  = listKey === 'subjectLib' ? 'subjects' : 'bodies';
    const cap  = key === 'subjects' ? 50 : 30;
    const val  = field.value.trim();
    // Deduplicate
    if (lib[key].includes(val)) { alert('Already saved'); return; }
    lib[key].unshift(val);
    if (lib[key].length > cap) lib[key].pop();
    saveLibrary(lib);
    renderLibraryList(key, listElId, fieldId);
}

function renderLibraryList(key, listElId, fieldId) {
    const el  = document.getElementById(listElId);
    if (!el) return;
    const lib  = loadLibrary();
    const items = lib[key] || [];
    if (!items.length) {
        el.innerHTML = '<div class="library-empty">No saved items yet</div>';
        return;
    }
    el.innerHTML = items.map((item, idx) => {
        const preview = item.replace(/<[^>]+>/g, '').slice(0, 80);
        return `<div class="library-item" onclick="loadFromLibrary('${escHtml(fieldId)}','${escHtml(key)}',${idx},'${escHtml(listElId)}')">
            <span class="library-item-text" title="${escHtml(item)}">${escHtml(preview)}</span>
            <button class="library-item-del" onclick="deleteFromLibrary(event,'${escHtml(key)}',${idx},'${escHtml(listElId)}','${escHtml(fieldId)}')">✕</button>
        </div>`;
    }).join('');
}

function loadFromLibrary(fieldId, key, idx, listElId) {
    const field = document.getElementById(fieldId);
    const lib   = loadLibrary();
    if (!field || !lib[key] || !lib[key][idx]) return;
    field.value = lib[key][idx];
    // Mark active row
    const rows = document.querySelectorAll(`#${CSS.escape(listElId)} .library-item`);
    rows.forEach((r, i) => r.classList.toggle('active', i === idx));
}

function deleteFromLibrary(evt, key, idx, listElId, fieldId) {
    evt.stopPropagation();
    const lib = loadLibrary();
    lib[key].splice(idx, 1);
    saveLibrary(lib);
    renderLibraryList(key, listElId, fieldId);
}

// Render all libraries on load (single + bulk share the same localStorage)
function renderAllLibraries() {
    renderLibraryList('subjects', 'singleSubjectList', 'singleSubject');
    renderLibraryList('bodies',   'singleBodyList',    'singleHtml');
    renderLibraryList('subjects', 'bulkSubjectList',   'bulkSubject');
    renderLibraryList('bodies',   'bulkBodyList',      'bulkHtml');
}

// ── Client-side HTML conversion helpers ───────────────────────────────────
function htmlToPlainText(html) {
    try {
        const doc = new DOMParser().parseFromString(html, 'text/html');
        // Insert newlines at block elements
        doc.querySelectorAll('br,p,div,li,h1,h2,h3,h4,h5,h6,tr').forEach(el => {
            el.insertAdjacentText('beforebegin', '\n');
        });
        return (doc.body ? doc.body.textContent : doc.documentElement.textContent)
            .replace(/[ \t]+/g, ' ')
            .replace(/\n{3,}/g, '\n\n')
            .trim();
    } catch { return html.replace(/<[^>]+>/g, '').trim(); }
}

function htmlToMarkdown(html) {
    try {
        let md = html;
        md = md.replace(/<h([1-6])[^>]*>([\s\S]*?)<\/h\1>/gi, (_, n, t) => '#'.repeat(parseInt(n)) + ' ' + t.replace(/<[^>]+>/g,'') + '\n');
        md = md.replace(/<strong[^>]*>([\s\S]*?)<\/strong>/gi, '**$1**');
        md = md.replace(/<b[^>]*>([\s\S]*?)<\/b>/gi, '**$1**');
        md = md.replace(/<em[^>]*>([\s\S]*?)<\/em>/gi, '*$1*');
        md = md.replace(/<i[^>]*>([\s\S]*?)<\/i>/gi, '*$1*');
        md = md.replace(/<a[^>]+href="([^"]+)"[^>]*>([\s\S]*?)<\/a>/gi, '[$2]($1)');
        md = md.replace(/<br\s*\/?>/gi, '\n');
        md = md.replace(/<\/?p[^>]*>/gi, '\n');
        md = md.replace(/<li[^>]*>/gi, '\n- ');
        md = md.replace(/<[^>]+>/g, '');
        return md.replace(/\n{3,}/g, '\n\n').trim();
    } catch { return htmlToPlainText(html); }
}

function htmlToRtf(html) {
    const text = htmlToPlainText(html);
    const lines = text.split('\n').map(l =>
        l.replace(/\\/g,'\\\\').replace(/\{/g,'\\{').replace(/\}/g,'\\}') + '\\par'
    );
    return ['{\\rtf1\\ansi\\deff0', ...lines, '}'].join('\n');
}

// ── Export body as chosen format (client-side) ─────────────────────────────
async function exportBodyContent(which, format) {
    const fieldId = which === 'single' ? 'singleHtml' : 'bulkHtml';
    const statusId = 'exportStatus_' + which;
    const el = document.getElementById(fieldId);
    const status = document.getElementById(statusId);
    if (!el || !el.value.trim()) { alert('HTML body is empty — nothing to export.'); return; }
    const html = el.value;

    function setStatus(msg) {
        if (status) { status.textContent = msg; status.style.display = msg ? 'block' : 'none'; }
    }
    function triggerDownload(blob, filename) {
        const url = URL.createObjectURL(blob);
        const a   = document.createElement('a');
        a.href = url; a.download = filename; a.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
    }

    setStatus('Exporting...');
    try {
        // ── Text formats ──────────────────────────────────────────────────
        if (format === 'txt') {
            triggerDownload(new Blob([htmlToPlainText(html)], { type: 'text/plain' }), 'export.txt');

        } else if (format === 'md') {
            triggerDownload(new Blob([htmlToMarkdown(html)], { type: 'text/markdown' }), 'export.md');

        } else if (format === 'rtf') {
            triggerDownload(new Blob([htmlToRtf(html)], { type: 'application/rtf' }), 'export.rtf');

        // ── Word (HTML wrapped in .doc MIME — opens in Word/LibreOffice) ─
        } else if (format === 'docx') {
            const wordHtml = `<html xmlns:o="urn:schemas-microsoft-com:office:office"
                xmlns:w="urn:schemas-microsoft-com:office:word"
                xmlns="http://www.w3.org/TR/REC-html40">
                <head><meta charset="utf-8">
                <meta name=ProgId content=Word.Document>
                <meta name=Generator content="Microsoft Word 15">
                <!--[if gte mso 9]><xml><w:WordDocument><w:View>Print</w:View></w:WordDocument></xml><![endif]-->
                </head><body>${html}</body></html>`;
            triggerDownload(new Blob([wordHtml], { type: 'application/vnd.ms-word' }), 'export.doc');

        // ── XLSX via SheetJS ──────────────────────────────────────────────
        } else if (format === 'xlsx') {
            if (window.XLSX) {
                // Try to extract tables first; fallback to plain text rows
                const doc = new DOMParser().parseFromString(html, 'text/html');
                const tables = doc.querySelectorAll('table');
                const wb = XLSX.utils.book_new();
                if (tables.length) {
                    tables.forEach((tbl, ti) => {
                        const ws = XLSX.utils.table_to_sheet(tbl);
                        XLSX.utils.book_append_sheet(wb, ws, `Sheet${ti + 1}`);
                    });
                } else {
                    const rows = htmlToPlainText(html).split('\n').map(l => [l]);
                    const ws   = XLSX.utils.aoa_to_sheet(rows);
                    XLSX.utils.book_append_sheet(wb, ws, 'Content');
                }
                const data = XLSX.write(wb, { bookType: 'xlsx', type: 'array' });
                triggerDownload(new Blob([data], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' }), 'export.xlsx');
            } else {
                // Fallback: CSV
                const rows = htmlToPlainText(html).split('\n').map(l => '"' + l.replace(/"/g, '""') + '"').join('\n');
                triggerDownload(new Blob([rows], { type: 'text/csv' }), 'export.csv');
                setStatus('✓ SheetJS not loaded — exported as CSV instead'); return;
            }

        // ── PPTX via PptxGenJS ────────────────────────────────────────────
        } else if (format === 'pptx') {
            if (typeof PptxGenJS !== 'undefined') {
                const pptx  = new PptxGenJS();
                const text  = htmlToPlainText(html);
                const paras = text.split('\n\n').filter(p => p.trim()).slice(0, 20);
                (paras.length ? paras : [text]).forEach(para => {
                    const slide = pptx.addSlide();
                    slide.addText(para.slice(0, 500), { x: 0.5, y: 0.5, w: 9, h: 5, fontSize: 16, wrap: true });
                });
                const buf = await pptx.stream();
                triggerDownload(new Blob([buf], { type: 'application/vnd.openxmlformats-officedocument.presentationml.presentation' }), 'export.pptx');
            } else {
                setStatus('❌ PptxGenJS library not available'); return;
            }

        // ── PDF via jsPDF + html2canvas ───────────────────────────────────
        } else if (format === 'pdf') {
            await _exportViaCanvas(html, 'pdf', 'export.pdf', setStatus, triggerDownload);
            return;

        // ── Image formats via html2canvas ─────────────────────────────────
        } else if (['png','jpeg','gif','webp','tiff'].includes(format)) {
            await _exportViaCanvas(html, format, `export.${format === 'tiff' ? 'tiff' : format}`, setStatus, triggerDownload);
            return;

        } else {
            setStatus(`❌ Unknown format: ${format}`); return;
        }

        setStatus(`✓ Downloaded export.${format}`);
        setTimeout(() => setStatus(''), 4000);
    } catch (err) {
        setStatus(`❌ Export failed: ${err.message}`);
        console.error('exportBodyContent error:', err);
    }
}

// Render HTML in hidden iframe → html2canvas → export as PDF or image
async function _exportViaCanvas(html, format, filename, setStatus, triggerDownload) {
    setStatus(`Rendering HTML → ${format.toUpperCase()}...`);
    return new Promise((resolve) => {
        const iframe = document.createElement('iframe');
        iframe.style.cssText = 'position:fixed;top:-9999px;left:-9999px;width:900px;height:600px;border:none;';
        document.body.appendChild(iframe);
        iframe.onload = async () => {
            try {
                const iDoc = iframe.contentDocument || iframe.contentWindow.document;
                const canvas = await html2canvas(iDoc.body, { scale: 0.8, useCORS: true, logging: false });
                document.body.removeChild(iframe);

                if (format === 'pdf') {
                    const { jsPDF } = window.jspdf;
                    const W = 595, H = Math.round((canvas.height / canvas.width) * 595);
                    const pdf = new jsPDF({ orientation: H > W ? 'portrait' : 'landscape', unit: 'pt', format: [W, H] });
                    pdf.addImage(canvas.toDataURL('image/jpeg', 0.85), 'JPEG', 0, 0, W, H, '', 'FAST');
                    triggerDownload(new Blob([pdf.output('arraybuffer')], { type: 'application/pdf' }), filename);
                } else {
                    // For GIF/WebP/TIFF → use JPEG/PNG as those MIME types aren't natively supported by canvas
                    const mimeMap = { png:'image/png', jpeg:'image/jpeg', gif:'image/jpeg', webp:'image/webp', tiff:'image/png' };
                    const mime = mimeMap[format] || 'image/png';
                    canvas.toBlob(blob => { if (blob) triggerDownload(blob, filename); }, mime, 0.9);
                }
                setStatus(`✓ Downloaded ${filename}`);
                setTimeout(() => setStatus(''), 4000);
            } catch (err) {
                if (document.body.contains(iframe)) document.body.removeChild(iframe);
                setStatus(`❌ Render error: ${err.message}`);
            }
            resolve();
        };
        iframe.srcdoc = html;
    });
}
