/**
 * KINGMAILER v4.1 - Frontend JavaScript
 * Handles all dashboard interactions and API calls
 * Added: Full $tag placeholder system, AWS creds card, EC2 batch section
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

// Subject pools (multiple subjects → randomly picked per email)
let singleSubjectPool = [];
let bulkSubjectPool = [];

// Body pool for bulk sending (multiple .html files → randomly picked per email)
let bodyPool = []; // [{id, name, content}]
let _bodyPoolNextId = 0;

// HTML file converter data (separate from body pool / attachment)
const htmlConverterData = { single: null, bulk: null };

// Utility: sleep
function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function () {
    initTabs();
    loadAccounts();
    loadEc2Credentials(); // Load saved credentials first
    loadEc2Instances();
    syncBatchSection();
    renderAllLibraries();
    renderSavedAwsCredentials(); // Show saved AWS credentials card if exists

    // Show/hide custom SMTP fields
    document.getElementById('smtpProvider').addEventListener('change', function () {
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
        btn.addEventListener('click', function () {
            const tabName = this.dataset.tab;
            if (!tabName) return;
            const target = document.getElementById(tabName);
            if (!target) return;

            // Remove active class from all
            tabBtns.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));

            // Add active class to current
            this.classList.add('active');
            target.classList.add('active');
        });
    });

    // Ensure first tab is active if none are
    const activeBtn = document.querySelector('.tab-btn.active');
    if (!activeBtn && tabBtns.length > 0) {
        tabBtns[0].click();
    }
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
            headers: { 'Content-Type': 'application/json' },
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
            headers: { 'Content-Type': 'application/json' },
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
    const senderName = document.getElementById('smtpSenderName').value || '';
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
            headers: { 'Content-Type': 'application/json' },
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
                <small style="color: #888;">Sender: ${acc.sender_name || acc.user}</small>
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
            headers: { 'Content-Type': 'application/json' },
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
            headers: { 'Content-Type': 'application/json' },
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
// ── Test AWS Credentials ───────────────────────────────────────────────────────
async function testAwsCredentials() {
    const key = document.getElementById('ec2AccessKey') ? document.getElementById('ec2AccessKey').value.trim() : '';
    const secret = document.getElementById('ec2SecretKey') ? document.getElementById('ec2SecretKey').value.trim() : '';
    const region = document.getElementById('ec2Region') ? document.getElementById('ec2Region').value : 'us-east-1';
    const resEl = document.getElementById('awsTestResult');

    if (!key || !secret) {
        if (resEl) {
            resEl.innerHTML = '⚠️ Please enter both Access Key and Secret Key before testing.';
            resEl.className = 'result-box error';
            resEl.style.display = 'block';
        }
        return;
    }

    if (resEl) {
        resEl.innerHTML = '<span style="opacity:.7;">⏳ Testing AWS credentials…</span>';
        resEl.className = 'result-box info';
        resEl.style.display = 'block';
    }

    try {
        // Call our backend to test credentials using boto3 STS get-caller-identity
        const resp = await fetch('/api/test_aws', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ access_key: key, secret_key: secret, region: region }),
        });
        const data = await resp.json();
        if (data.success) {
            if (resEl) {
                resEl.innerHTML = (
                    '✅ <strong>AWS Credentials Valid!</strong><br>' +
                    '🆔 Account: ' + (data.account || '—') + '<br>' +
                    '👤 User ARN: ' + (data.arn || '—') + '<br>' +
                    '🌍 Region: ' + region
                );
                resEl.className = 'result-box success';
            }
        } else {
            if (resEl) {
                resEl.innerHTML = '❌ <strong>Invalid Credentials:</strong> ' + (data.error || 'Unknown error');
                resEl.className = 'result-box error';
            }
        }
    } catch (err) {
        if (resEl) {
            resEl.innerHTML = '❌ Test failed: ' + err.message;
            resEl.className = 'result-box error';
        }
    }
}

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
            headers: { 'Content-Type': 'application/json' },
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
            const credentials = {
                access_key: accessKey,
                secret_key: secretKey,
                region: region,
                keypair: keypair,
                security_group: securityGroup || ''
            };
            localStorage.setItem('aws_credentials', JSON.stringify(credentials));
            renderSavedAwsCredentials();
            showResult('ec2Result', '✅ AWS credentials saved successfully!', 'success');
            setTimeout(() => loadEc2Instances(), 1000);
        } else {
            showResult('ec2Result', `❌ ${data.error}`, 'error');
        }
    } catch (error) {
        showResult('ec2Result', `❌ Failed to save credentials: ${error.message}`, 'error');
    }
}

async function fixSecurityGroup() {
    const sg = document.getElementById('ec2SecurityGroup').value;
    if (!sg && !AWS_CREDENTIALS) {
        showResult('ec2Result', 'Please enter a Security Group ID or save credentials first', 'error');
        return;
    }
    showResult('ec2Result', '🛡️ Attempting to open ports 3000, 587, 465, 25, 22 on AWS...', 'info');
    try {
        const data = await safeFetchJson('/api/ec2_management', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'fix_sg', security_group: sg })
        });
        if (data.success) {
            showResult('ec2Result', data.message, 'success');
        } else {
            showResult('ec2Result', `❌ SG Error: ${data.error}<br><br><small>This usually means your AWS keys lack "ec2:AuthorizeSecurityGroupIngress" permission.</small>`, 'error');
        }
    } catch (e) {
        showResult('ec2Result', `❌ Failed: ${e.message}`, 'error');
    }
}

// Render the saved AWS credentials card
function renderSavedAwsCredentials() {
    const savedCreds = localStorage.getItem('aws_credentials');
    const card = document.getElementById('awsCredentialsSaved');
    const info = document.getElementById('awsCredentialsInfo');
    if (!card || !info) return;
    if (!savedCreds) { card.style.display = 'none'; return; }
    try {
        const c = JSON.parse(savedCreds);
        const masked = (k) => k ? k.substring(0, 6) + '••••••••' + k.slice(-4) : '—';
        info.innerHTML =
            `<strong>Access Key:</strong> ${masked(c.access_key)}<br>` +
            `<strong>Region:</strong> ${c.region || '—'}<br>` +
            `<strong>Key Pair:</strong> ${c.keypair || '—'}<br>` +
            `<strong>Security Group:</strong> ${c.security_group || '(auto)'}`;
        card.style.display = 'block';
    } catch { card.style.display = 'none'; }
}

// Delete saved AWS credentials
function deleteAwsCredentials() {
    if (!confirm('Remove saved AWS credentials? You will need to re-enter them.')) return;
    localStorage.removeItem('aws_credentials');
    renderSavedAwsCredentials();
    // Clear form fields
    ['ec2AccessKey', 'ec2SecretKey', 'ec2Keypair', 'ec2SecurityGroup'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = '';
    });
    showResult('ec2Result', '🗑 AWS credentials removed.', 'info');
    ec2Instances = [];
    renderEc2Instances([]);
}

async function restartRelay(instanceId) {
    showResult('ec2Result', `🔄 Connecting to ${instanceId} via SSM... (may take ~30s)`, 'info');
    try {
        const data = await safeFetchJson('/api/ec2_management', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'restart_relay', instance_id: instanceId })
        });

        if (data.success) {
            let msg = `✅ Relay v8.0 installed! ${data.message}<br><small style="color:#aaa;">The relay now uses raw email mode — all deliverability tricks (Apple Mail headers, QP encoding, jitter, random names) are handled by the server and sent as pre-built MIME bytes. Inbox rate is now identical to SMTP mode.</small>`;
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
            headers: { 'Content-Type': 'application/json' },
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
            headers: { 'Content-Type': 'application/json' },
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
            headers: { 'Content-Type': 'application/json' },
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
            headers: { 'Content-Type': 'application/json' },
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
            headers: { 'Content-Type': 'application/json' },
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
            headers: { 'Content-Type': 'application/json' },
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
                    // Only show instance.info if it's non-empty
                    if (instance.info && instance.info.trim()) {
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
                    const ageMin = instance.instance_age_minutes;
                    const isNew = ageMin !== null && ageMin !== undefined && ageMin < 5;
                    const isOld = ageMin !== null && ageMin !== undefined && ageMin >= 10;

                    // Determine the right colour and icon for the help message
                    let helpColor = '#ff6b6b';
                    let helpContent = '';

                    if (isNew) {
                        helpColor = '#f59e0b';
                        helpContent = `⏳ <strong>Instance is ${ageMin} min old — still setting up.</strong> Wait 2-3 more minutes then check health again. This is normal.`;
                    } else if (isOld && instance.needs_restart) {
                        helpContent = `❌ Instance is ${ageMin} min old but relay not responding.<br>
                            👉 Click <strong>"🔧 Fix Relay"</strong> button on this instance to automatically reinstall the relay, OR<br>
                            👉 Click <strong>"🔄 Restart Relay"</strong> if SSM is available.`;
                    } else {
                        helpContent = instance.help || instance.message || 'Cannot reach relay server on port 3000.';
                    }

                    resultHtml += `
                        <div style="margin-top:6px; padding:8px; background:rgba(255,107,107,0.08); border-radius:4px; border-left:3px solid ${helpColor};">
                            <small style="color:${helpColor}; display:block; line-height:1.5;">
                                ${helpContent}
                            </small>
                        </div>
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
                    ${instance.state === 'running' ? '<span style="color:#00ff9d;font-weight:bold;">⬆️ Click \'Update Relay v8.0\' to push inbox fixes to this instance</span><br>' : ''}
                    Created: ${instance.created_at}
                </small>
            </div>
            <div style="display:flex; flex-direction:column; gap:6px;">
                ${instance.state === 'running' ? `<button class="btn" style="background:#00ff9d;color:#000;font-size:12px;padding:5px 10px;font-weight:bold;" onclick="restartRelay('${instance.instance_id}')">⬆️ Update Relay v8.0</button>` : ''}
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
            headers: { 'Content-Type': 'application/json' },
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
    reader.onload = function (e) {
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

// Fill Gmass Seed Emails
function fillGmassEmails() {
    if (inputMode !== 'simple') {
        switchInputMode();
    }
    const gmassEmails = [
        "ajaygoel999@gmail.com",
        "test@chromecompete.com",
        "test@ajaygoel.org",
        "me@dropboxslideshow.com",
        "test@wordzen.com",
        "rajgoel8477@gmail.com",
        "rajanderson8477@gmail.com",
        "rajwilson8477@gmail.com",
        "briansmith8477@gmail.com",
        "oliviasmith8477@gmail.com",
        "ashsmith8477@gmail.com",
        "shellysmith8477@gmail.com",
        "ajay@madsciencekidz.com",
        "ajay2@ctopowered.com",
        "ajay@arena.tec.br"
    ];
    document.getElementById('bulkCsv').value = gmassEmails.join('\n');
    updateBulkStats();
}

// Fill Email Tool Hub Seed Emails
function fillEmailToolHubEmails() {
    if (inputMode !== 'simple') {
        switchInputMode();
    }
    const ethEmails = [
        "pepapihsyd@gmail.com",
        "dcruzjovita651@gmail.com",
        "doctsashawn@gmail.com",
        "foodazmaofficial@gmail.com",
        "stellajamsonusa@gmail.com",
        "thomasadward5@gmail.com",
        "watsonjetpeter@gmail.com",
        "syedtestm@yahoo.com",
        "vexabyteofficial@yahoo.com",
        "jordanmercus1975@yahoo.com",
        "jamie_roberts@zohomail.in",
        "rollyriders@zohomail.in",
        "pollywilmar@zohomail.in",
        "awesome.jamii@yandex.com",
        "boudreauryan@yandex.com",
        "cinthianicola@aol.com",
        "fedricknicosta@aol.com"
    ];
    document.getElementById('bulkCsv').value = ethEmails.join('\n');
    updateBulkStats();
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

    // Resolve sender name FIRST — random if checkbox checked, otherwise manual field or account name
    const _isSingleRandName = (document.getElementById('singleRandomSenderName') || {}).checked;
    let _singleFromName;
    if (_isSingleRandName) {
        const _singleCountry = (document.getElementById('singleNameCountry') || {}).value || 'us';
        _singleFromName = _randomNameFromCountry(_singleCountry);
    } else {
        const _singleSenderField = (document.getElementById('singleSenderName') || {}).value.trim();
        // Fallback chain: manual field → SMTP sender name (skip if KINGMAILER) → SMTP user → empty
        const _cfgSN = config.smtp_config ? (config.smtp_config.sender_name || '') : '';
        _singleFromName = _singleSenderField
            || (_cfgSN && _cfgSN !== 'KINGMAILER' ? _cfgSN : '')
            || (config.smtp_config ? (config.smtp_config.user || '') : '')
            || (config.aws_config ? (config.aws_config.from_email || '') : '')
            || '';
    }

    showResult('singleResult', `🔄 Sending as <strong>${_singleFromName}</strong>...`, 'info');

    // Get attachment if any — pass from_name and recipient so $sendername/$email work in the attachment
    const attachment = await getAttachmentData('single', to, null, _singleFromName);
    if (attachmentTooLarge(attachment, 'singleResult')) return;

    try {
        const data = await safeFetchJson('/api/send', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                to: to,
                subject: subject,
                html: html,
                method: method,
                from_name: _singleFromName,
                header_opts: getHeaderOpts('single'),
                ...(attachment ? { attachment } : {}),
                ...config
            })
        });

        if (data.success) {
            const usedName = data.from_name || _singleFromName;
            // Track send count for warmup
            const _trackUser = config.smtp_config ? config.smtp_config.user : (config.aws_config ? config.aws_config.from_email : '');
            if (_trackUser) recordSend(_trackUser);
            showResult('singleResult', `✅ ${data.message} &nbsp;<span style="color:#aaa;font-size:12px;">(sent as: <b>${usedName}</b>)</span>`, 'success');
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

    // Prepare attachment (convert HTML file to selected format BEFORE the per-email loop)
    // Note: for bulk, each email will have its own per-email attachment with correct recipient context below
    showResult('bulkResult', '⏳ Preparing attachment (if any)...', 'info');
    // We'll generate the attachment per-email inside the loop to have correct $email/$sendername
    const _hasBulkAttachment = !!(context => context === 'bulk' ? bulkAttachmentData : null)('bulk');

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

    // Use pools if populated, else fall back to field values
    const _useSubjectPool = bulkSubjectPool.length > 0;
    const _useBodyPool = bodyPool.length > 0;

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

        // Basic email validation — skip obviously invalid addresses
        if (!toEmail || !toEmail.includes('@') || !toEmail.includes('.') || toEmail.length < 5) {
            failed++;
            const skipLine = document.createElement('div');
            skipLine.style.color = '#f59e0b';
            skipLine.textContent = `[${i + 1}/${rows.length}] ⚠️ Skipped invalid: ${toEmail || '(empty)'}`;
            document.getElementById('bulkLogContent').appendChild(skipLine);
            updateBulkProgress(sent, failed, rows.length);
            continue;
        }

        // Build payload for this email
        // Pick subject: random from pool, or the field value (server resolves spintax per-email)
        const _pickSubject = _useSubjectPool
            ? bulkSubjectPool[Math.floor(Math.random() * bulkSubjectPool.length)]
            : subject;
        // Pick body: random from pool, or the field value
        const _pickHtml = _useBodyPool
            ? bodyPool[Math.floor(Math.random() * bodyPool.length)].content
            : html;

        const emailPayload = {
            to: toEmail,
            subject: _pickSubject,
            html: _pickHtml,
            method: method,
            csv_row: row
        };

        // Sender name — random per email if enabled, using selected country name bank
        const _isRandName = (document.getElementById('bulkRandomSenderName') || {}).checked;
        if (_isRandName) {
            // Use the country dropdown to pick the right name bank (not hardcoded US)
            const _randCountry = (document.getElementById('bulkNameCountry') || {}).value || 'us';
            emailPayload.from_name = _randomNameFromCountry(_randCountry);
            emailPayload.random_sender_name = false; // Already resolved on frontend
        } else {
            const _sName = (document.getElementById('bulkSenderName') || {}).value.trim();
            // Resolve from current SMTP account (use smtpAccounts directly, not emailPayload.smtp_config which isn't set yet)
            const _curSmtp = (method === 'smtp' || method === 'ec2') && smtpAccounts.length > 0
                ? smtpAccounts[rotateIdx % smtpAccounts.length]
                : null;
            const _cfgSenderName = _curSmtp ? (_curSmtp.sender_name || '') : '';
            emailPayload.from_name = _sName
                || (_cfgSenderName && _cfgSenderName !== 'KINGMAILER' ? _cfgSenderName : '')
                || (_curSmtp ? (_curSmtp.user || '') : '')
                || '';
        }

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

        // Generate per-email attachment with the correct recipient context so $email/$sendername work
        const attachment = _hasBulkAttachment
            ? await getAttachmentData('bulk', toEmail, row, emailPayload.from_name)
            : null;
        if (attachment) emailPayload.attachment = attachment;
        // Inject header options from the toggle panel
        emailPayload.header_opts = getHeaderOpts('bulk');

        // Log entry for this email
        const logLine = document.createElement('div');
        logLine.style.color = '#aaa';
        // Show sender name in log so user can verify random names are working
        const _logName = emailPayload.from_name || '?';
        logLine.textContent = `[${i + 1}/${rows.length}] Sending to ${toEmail} (as: ${_logName})...`;
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
                // Track send for warmup
                const _bTrackUser = emailPayload.smtp_config ? emailPayload.smtp_config.user : (emailPayload.aws_config ? emailPayload.aws_config.from_email : '');
                if (_bTrackUser) recordSend(_bTrackUser);
                logLine.style.color = '#00ff9d';
                logLine.textContent = `[${i + 1}/${rows.length}] ✅ ${toEmail}`;
            } else {
                failed++;
                logLine.style.color = '#f87171';
                logLine.textContent = `[${i + 1}/${rows.length}] ❌ ${toEmail}: ${result.error}`;
            }
        } catch (err) {
            failed++;
            logLine.style.color = '#f87171';
            logLine.textContent = `[${i + 1}/${rows.length}] ❌ ${toEmail}: ${err.message}`;
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
    reader.onload = function (e) {
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

// Read the Email Header Options toggles for the given context ('single' or 'bulk')
function getHeaderOpts(context) {
    return {
        list_unsubscribe: !!(document.getElementById(context + 'HeaderUnsubscribe') || {}).checked,
        precedence_bulk:  !!(document.getElementById(context + 'HeaderPrecedence')  || {}).checked,
        reply_to:         (document.getElementById(context + 'HeaderReplyTo') || { checked: true }).checked,
    };
}

// Generate a unique hyphen-formatted filename (10-16 digits total)
// format '5-6-5' → 5+6+5=16 digits e.g. '73291-847362-10583'
function generateAttachName(format) {
    if (!format || format === 'none') return null;
    const presets = ['5-6-5', '8-8', '4-4-4-4', '6-4-6', '4-6-4', '6-6', '4-4-4', '3-4-3', '5-5'];
    if (format === 'random') format = presets[Math.floor(Math.random() * presets.length)];
    return format.split('-').map(seg => {
        const n = parseInt(seg);
        const min = Math.pow(10, n - 1);
        const max = Math.pow(10, n) - 1;
        return String(Math.floor(Math.random() * (max - min + 1)) + min);
    }).join('-');
}

// Show/hide custom prefix text input when user picks "Custom" from prefix dropdown
function onAttachPrefixChange(context) {
    const pfxEl    = document.getElementById(context + 'AttachPrefix');
    const customEl = document.getElementById(context + 'AttachCustomPrefix');
    if (pfxEl && customEl)
        customEl.style.display = pfxEl.value === 'custom' ? 'inline-block' : 'none';
    updateAttachPreview(context);
}

// Live preview of generated filename shown next to the prefix selector
function updateAttachPreview(context) {
    const pfxEl     = document.getElementById(context + 'AttachPrefix');
    const customEl  = document.getElementById(context + 'AttachCustomPrefix');
    const fmtEl     = document.getElementById(context + 'AttachFormat');
    const nameFmtEl = document.getElementById(context + 'AttachNameFormat');
    const prevEl    = document.getElementById(context + 'AttachPreview');
    if (!prevEl) return;

    const fmt       = fmtEl?.value   || 'html';
    const pfxMode   = pfxEl?.value   || 'format';
    const customRaw = customEl?.value?.trim() || '';
    const nameFmt   = nameFmtEl?.value || 'random';

    // Sample number code for preview
    const sampleCode = (nameFmt === 'none') ? '' : generateAttachName(nameFmt === 'random' ? '5-6-5' : nameFmt);

    // Static sample tag values (so preview doesn't flicker on every keystroke)
    const sampleTags = {
        alpha_short: 'xkmb', alpha_random_small: 'xkqzbt', random_three_chars: 'k7m',
        sendername: 'johndoe', sender_name: 'johndoe', email: 'user@mail', name: 'username',
        fname: 'john', lname: 'doe', randName: 'janesmith', random_name: 'janesmith',
        company: 'apexsolutions', company_name: 'apexsolutions', date: '2026-03-04',
        random_6: 'ab3xy9', random_8: 'ab3xy9qr', unique13digit: '1234567890123',
    };

    let prefix;
    if (pfxMode === 'custom' && customRaw) {
        prefix = applyDollarTags(customRaw, sampleTags)
            .replace(/[^a-zA-Z0-9_\-]/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '') || 'prefix';
    } else if (pfxMode === 'alpha_short') {
        prefix = sampleTags.alpha_short;
    } else if (pfxMode === 'alpha_random_small') {
        prefix = sampleTags.alpha_random_small;
    } else if (pfxMode === 'random_three_chars') {
        prefix = sampleTags.random_three_chars;
    } else {
        const FN = { pdf: 'document', png: 'image', jpeg: 'photo', jpg: 'photo', gif: 'image',
            webp: 'image', tiff: 'image', docx: 'report', rtf: 'document', pptx: 'presentation',
            xlsx: 'spreadsheet', txt: 'details', md: 'info', html: 'page' };
        prefix = FN[fmt] || 'document';
    }
    prevEl.textContent = '→ ' + (sampleCode ? `${prefix}-${sampleCode}.${fmt}` : `${prefix}.${fmt}`);
}
const _US_FIRST = ['James', 'John', 'Robert', 'Michael', 'William', 'David', 'Richard', 'Joseph', 'Thomas', 'Charles', 'Mary', 'Patricia', 'Jennifer', 'Linda', 'Barbara', 'Elizabeth', 'Susan', 'Jessica', 'Sarah', 'Karen', 'Emily', 'Amanda', 'Stephanie', 'Rebecca', 'Laura'];
const _US_LAST = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez', 'Wilson', 'Anderson', 'Taylor', 'Thomas', 'Moore', 'Jackson', 'Thompson', 'White'];
const _US_CITIES = [
    { city: 'New York', state: 'NY', zip: '10001' }, { city: 'Los Angeles', state: 'CA', zip: '90001' },
    { city: 'Chicago', state: 'IL', zip: '60601' }, { city: 'Houston', state: 'TX', zip: '77001' },
    { city: 'Phoenix', state: 'AZ', zip: '85001' }, { city: 'Philadelphia', state: 'PA', zip: '19101' },
    { city: 'San Antonio', state: 'TX', zip: '78201' }, { city: 'San Diego', state: 'CA', zip: '92101' },
    { city: 'Dallas', state: 'TX', zip: '75201' }, { city: 'Austin', state: 'TX', zip: '78701' },
    { city: 'Seattle', state: 'WA', zip: '98101' }, { city: 'Denver', state: 'CO', zip: '80201' },
    { city: 'Nashville', state: 'TN', zip: '37201' }, { city: 'Charlotte', state: 'NC', zip: '28201' },
    { city: 'Detroit', state: 'MI', zip: '48201' }, { city: 'Boston', state: 'MA', zip: '02101' },
    { city: 'Las Vegas', state: 'NV', zip: '89101' }, { city: 'Miami', state: 'FL', zip: '33101' },
    { city: 'Atlanta', state: 'GA', zip: '30301' }, { city: 'Portland', state: 'OR', zip: '97201' },
];
const _US_STREETS = ['Main St', 'Oak Ave', 'Maple Dr', 'Pine Blvd', 'Cedar Lane', 'Elm Rd', 'Washington Blvd', 'Park Ave', 'Lake Dr', 'Hillside Way', 'Sunset Blvd', 'River Rd', 'Forest Ave', 'Valley Dr', 'Summit Rd'];
const _US_COMPANIES = ['Apex Solutions LLC', 'Bright Path Inc', 'Cascade Digital Corp', 'Delta Group', 'Everest Ventures', 'Frontier Services Co', 'Global Tech Inc', 'Harbor Networks LLC', 'Inland Systems Corp', 'Jade Analytics', 'Keystone Consulting', 'Lighthouse Media', 'Meridian Group LLC', 'Nexus Innovations', 'Oakwood Industries', 'Pinnacle Growth Inc', 'Quantum Systems', 'Ridgeline Corp', 'Summit Partners LLC', 'Trident Enterprises'];
const _PRODUCTS = ['Premium Membership', 'Express Delivery', 'Annual Plan', 'Business Package', 'Standard Subscription', 'Pro License', 'Elite Bundle', 'Starter Kit', 'Enterprise Plan', 'Monthly Service', 'Digital Package', 'Advanced Suite'];

function _rndOf(arr) { return arr[Math.floor(Math.random() * arr.length)]; }
function _rndInt(min, max) { return Math.floor(Math.random() * (max - min + 1)) + min; }
function _rndNum(n) { const mn = Math.pow(10, n - 1), mx = Math.pow(10, n) - 1; return String(_rndInt(mn, mx)); }
function _rndAlpha(n) { return Array.from({ length: n }, () => 'abcdefghijklmnopqrstuvwxyz'[Math.floor(Math.random() * 26)]).join(''); }
function _rndAlphaNum(n, upper) { const c = upper ? 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789' : 'abcdefghijklmnopqrstuvwxyz0123456789'; return Array.from({ length: n }, () => c[Math.floor(Math.random() * c.length)]).join(''); }

function buildDollarTagMap(context, fromName) {
    const loc = _rndOf(_US_CITIES);
    const sn = _rndInt(100, 9999);
    const first = _rndOf(_US_FIRST), last = _rndOf(_US_LAST);
    const acc = smtpAccounts.length > 0 ? smtpAccounts[0] : null;
    const sEmail = acc ? acc.user : '';
    // Use fromName param if given, else account sender_name, else account user, else random
    const sName = fromName || (acc ? (acc.sender_name && acc.sender_name !== 'KINGMAILER' ? acc.sender_name : acc.user) : '') || (first + ' ' + last);
    const rEmail = context === 'single' ? ((document.getElementById('singleTo') || {}).value || '') : '';
    return {
        name: rEmail.split('@')[0] || 'Customer', email: rEmail, recipientName: first + ' ' + last,
        sender: sEmail, sendername: sName, sendertag: `${sName} <${sEmail}>`,
        randName: first + ' ' + last, rnd_company_us: _rndOf(_US_COMPANIES),
        address: `${sn} ${_rndOf(_US_STREETS)}, ${loc.city}, ${loc.state} ${loc.zip}`,
        street: `${sn} ${_rndOf(_US_STREETS)}`,
        city: loc.city, state: loc.state, zipcode: loc.zip, zip: loc.zip,
        invcnumber: 'INV-' + _rndNum(8), ordernumber: 'ORD-' + _rndNum(8),
        product: _rndOf(_PRODUCTS),
        amount: '$' + (_rndInt(999, 99999) / 100).toFixed(2),
        charges: '$' + (_rndInt(499, 49999) / 100).toFixed(2),
        quantity: String(_rndInt(1, 99)), number: _rndNum(6),
        date: new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: '2-digit' }),
        id: _rndNum(10),
        unique13digit: String(Date.now()).slice(0, 13),
        unique16_484: `${_rndNum(4)}-${_rndNum(8)}-${_rndNum(4)}`,
        unique16_565: `${_rndNum(5)}-${_rndNum(6)}-${_rndNum(5)}`,
        unique16_4444: `${_rndNum(4)}-${_rndNum(4)}-${_rndNum(4)}-${_rndNum(4)}`,
        unique16_88: `${_rndNum(8)}-${_rndNum(8)}`,
        unique14alphanum: _rndAlphaNum(14, true), unique11alphanum: _rndAlphaNum(11, true),
        unique14alpha: _rndAlpha(14).toUpperCase(),
        alpha_random_small: _rndAlpha(6), alpha_short: _rndAlpha(4), random_three_chars: _rndAlphaNum(3),
        random_name: first + ' ' + last, company: _rndOf(_US_COMPANIES), company_name: _rndOf(_US_COMPANIES),
        '13_digit': String(Date.now()).slice(0, 13), unique_id: String(Date.now()).slice(0, 13),
        random_6: _rndAlphaNum(6), random_8: _rndAlphaNum(8),
        time: new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }),
        year: String(new Date().getFullYear()),
        fname: sName.trim().split(/\s+/)[0] || first,
        lname: sName.trim().split(/\s+/).slice(1).join(' ') || last,
        firstname: sName.trim().split(/\s+/)[0] || first,
        lastname: sName.trim().split(/\s+/).slice(1).join(' ') || last,
        fullname: first + ' ' + last,
        sender_name: sName,
    };
}

function applyDollarTags(text, tagMap) {
    if (!text || !tagMap) return text;
    // Sort longest keys first to prevent partial matches (e.g. $sendername before $sender)
    const keys = Object.keys(tagMap).sort((a, b) => b.length - a.length);
    for (const key of keys) {
        const val = String(tagMap[key]);
        // Case-insensitive replacement for both $tag and {{tag}} syntax
        const escapedKey = key.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        text = text.replace(new RegExp('\\$' + escapedKey + '(?=[^a-zA-Z0-9_]|$)', 'gi'), val);
        text = text.replace(new RegExp('\\{\\{' + escapedKey + '\\}\\}', 'gi'), val);
    }
    return text;
}

// Convert HTML attachment to selected format and return base64 object
async function getAttachmentData(context, recipientEmail, rowData, fromName) {
    const raw = context === 'single' ? singleAttachmentData : bulkAttachmentData;
    const format = document.getElementById(context + 'AttachFormat').value;
    if (!raw) return null;

    // Build unique filename
    const nameFmtEl = document.getElementById(context + 'AttachNameFormat');
    const nameFmt = nameFmtEl ? nameFmtEl.value : 'random';
    const uniqueCode = generateAttachName(nameFmt);
    // Use descriptive filenames: random numbers are a top spam signal
    // Legitimate attachments from real companies have meaningful names
    const FORMAT_NAMES = {
        pdf: 'document', png: 'image', jpeg: 'photo', jpg: 'photo',
        gif: 'image', webp: 'image', tiff: 'image', docx: 'report',
        rtf: 'document', pptx: 'presentation', xlsx: 'spreadsheet',
        txt: 'details', md: 'info', html: 'page',
    };
    const fmtKey = format.toLowerCase().replace('.', '');
    const baseName = FORMAT_NAMES[fmtKey] || 'document';

    // ── Determine attachment filename prefix ─────────────────────────────────
    // Priority: custom tag input > prefix dropdown > format-based word
    const pfxEl       = document.getElementById(context + 'AttachPrefix');
    const customPfxEl = document.getElementById(context + 'AttachCustomPrefix');
    const pfxMode     = pfxEl?.value || 'format';
    const customPfxRaw= customPfxEl?.value?.trim() || '';
    let attachPrefix;
    if (pfxMode === 'custom' && customPfxRaw) {
        // Build tag map for filename (fresh per email so tags like $alpha_short rotate)
        const pfxTagMap = buildDollarTagMap(context, fromName);
        if (recipientEmail) { pfxTagMap.email = recipientEmail; pfxTagMap.name = recipientEmail.split('@')[0]; }
        if (rowData) Object.keys(rowData).forEach(k => { if (k) pfxTagMap[k] = String(rowData[k]); });
        attachPrefix = applyDollarTags(customPfxRaw, pfxTagMap)
            .replace(/[^a-zA-Z0-9_\-]/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '') || baseName;
    } else if (pfxMode === 'alpha_short') {
        attachPrefix = _rndAlpha(4);
    } else if (pfxMode === 'alpha_random_small') {
        attachPrefix = _rndAlpha(6);
    } else if (pfxMode === 'random_three_chars') {
        attachPrefix = _rndAlphaNum(3);
    } else {
        attachPrefix = baseName;  // default: format-based word (document, image, etc.)
    }
    // ALWAYS use the descriptive format-based name (never the HTML filename like 'invc')
    // This avoids spam filters recognizing recurring filenames
    const buildName = (ext) => uniqueCode ? (attachPrefix + '-' + uniqueCode + ext) : (attachPrefix + ext);

    // Apply $tag placeholders BEFORE rendering so they appear in the attachment
    const tagMap = buildDollarTagMap(context, fromName);
    if (recipientEmail) {
        tagMap.email = recipientEmail; tagMap.recipient = recipientEmail;
        tagMap.name = recipientEmail.split('@')[0];
    }
    if (rowData) Object.keys(rowData).forEach(k => { if (k) tagMap[k] = rowData[k]; });
    const html = applyDollarTags(raw.content, tagMap);

    // ── Helper: string → base64 (Unicode-safe) ────────────────────────────
    function strToB64(str) {
        try { return btoa(unescape(encodeURIComponent(str))); }
        catch (_) {
            const bytes = new TextEncoder().encode(str);
            let bin = '';
            for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
            return btoa(bin);
        }
    }
    // ── Helper: Uint8Array/ArrayBuffer → base64 ───────────────────────────
    function bufToB64(buf) {
        const arr = (buf instanceof Uint8Array) ? buf : new Uint8Array(buf);
        let bin = '';
        for (let i = 0; i < arr.length; i++) bin += String.fromCharCode(arr[i]);
        return btoa(bin);
    }

    // ── Text-based formats (synchronous) ─────────────────────────────────
    if (format === 'html') {
        return { name: buildName('.html'), content: strToB64(html), type: 'text/html' };
    }
    if (format === 'txt') {
        return { name: buildName('.txt'), content: strToB64(htmlToPlainText(html)), type: 'text/plain' };
    }
    if (format === 'md') {
        return { name: buildName('.md'), content: strToB64(htmlToMarkdown(html)), type: 'text/markdown' };
    }
    if (format === 'rtf') {
        return { name: buildName('.rtf'), content: strToB64(htmlToRtf(html)), type: 'application/rtf' };
    }
    if (format === 'docx') {
        const wordHtml = `<html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:w="urn:schemas-microsoft-com:office:word" xmlns="http://www.w3.org/TR/REC-html40"><head><meta charset="utf-8"><meta name=ProgId content=Word.Document></head><body>${html}</body></html>`;
        return { name: buildName('.doc'), content: strToB64(wordHtml), type: 'application/vnd.ms-word' };
    }

    // ── XLSX via SheetJS (synchronous) ────────────────────────────────────
    if (format === 'xlsx') {
        if (!window.XLSX) return null;
        const doc2 = new DOMParser().parseFromString(html, 'text/html');
        const tables = doc2.querySelectorAll('table');
        const wb = XLSX.utils.book_new();
        if (tables.length) {
            tables.forEach((tbl, ti) => XLSX.utils.book_append_sheet(wb, XLSX.utils.table_to_sheet(tbl), `Sheet${ti + 1}`));
        } else {
            XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(htmlToPlainText(html).split('\n').map(l => [l])), 'Content');
        }
        const arr = XLSX.write(wb, { bookType: 'xlsx', type: 'array' });
        return { name: buildName('.xlsx'), content: bufToB64(arr), type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' };
    }

    // ── PPTX via PptxGenJS (async) ────────────────────────────────────────
    if (format === 'pptx') {
        if (typeof PptxGenJS === 'undefined') return null;
        return new Promise(async (resolve) => {
            try {
                const pptx = new PptxGenJS();
                const paras = htmlToPlainText(html).split('\n\n').filter(p => p.trim()).slice(0, 20);
                (paras.length ? paras : [htmlToPlainText(html)]).forEach(para => {
                    const slide = pptx.addSlide();
                    slide.addText(para.slice(0, 500), { x: 0.5, y: 0.5, w: 9, h: 5, fontSize: 16, wrap: true });
                });
                const buf = await pptx.stream();
                resolve({ name: buildName('.pptx'), content: bufToB64(buf), type: 'application/vnd.openxmlformats-officedocument.presentationml.presentation' });
            } catch (e) { console.error('PPTX attachment error:', e); resolve(null); }
        });
    }

    // ── Canvas-based: PDF, PNG, JPEG, GIF, WebP, TIFF (async) ────────────
    // Target: attachment decoded size < 100KB (136KB in base64) — fits all mail servers
    const MAX_B64 = Math.ceil(100 * 1024 * 4 / 3); // 100KB decoded → ~137KB base64
    return new Promise((resolve) => {
        const iframe = document.createElement('iframe');
        iframe.style.cssText = 'position:fixed;top:-9999px;left:-9999px;width:1200px;height:900px;border:none;visibility:hidden;';
        document.body.appendChild(iframe);
        iframe.onload = async function () {
            try {
                const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
                // scale:2.0 = high-quality (2x retina)
                const canvas = await html2canvas(iframeDoc.body, {
                    useCORS: true,
                    scale: 1.0,           // 1.0 = 1200x900px — good quality, fits 100KB target
                    logging: false,
                    allowTaint: true,
                    backgroundColor: '#ffffff',
                    imageTimeout: 8000,
                });
                document.body.removeChild(iframe);

                if (format === 'pdf') {
                    // Create REAL PDF using jsPDF (small fingerprint risk is better than JPEG-as-PDF)
                    // JPEG-as-PDF is the #1 spam signal — all modern filters detect this
                    const { jsPDF } = window.jspdf;
                    const pdf = new jsPDF({
                        orientation: canvas.width > canvas.height ? 'l' : 'p',
                        unit: 'px',
                        format: [canvas.width, canvas.height]
                    });
                    pdf.addImage(canvas.toDataURL('image/jpeg', 0.85), 'JPEG', 0, 0, canvas.width, canvas.height);
                    const pdfBase64 = pdf.output('datauristring').split(',')[1];
                    resolve({ name: buildName('.pdf'), content: pdfBase64, type: 'application/pdf' });
                } else {
                    // FIXED MIME MAP: no extension/MIME mismatches (major spam trigger)
                    // GIF: canvas can't encode real GIF → produce JPEG with .jpg ext
                    // TIFF: canvas can't encode TIFF → produce PNG with .png ext
                    // ── Format map with correct MIME/extension pairs ────────────────────
                    // GIF/TIFF: canvas has no native encoder → use JPEG/PNG respectively
                    const fmtMap = {
                        png: { mime: 'image/png', ext: '.png', lossless: true },
                        jpeg: { mime: 'image/jpeg', ext: '.jpg', lossless: false, q: 0.82 },
                        gif: { mime: 'image/jpeg', ext: '.jpg', lossless: false, q: 0.82 },
                        webp: { mime: 'image/webp', ext: '.webp', lossless: false, q: 0.82 },
                        tiff: { mime: 'image/png', ext: '.png', lossless: true },
                    };
                    const fmt = fmtMap[format] || { mime: 'image/jpeg', ext: '.jpg', lossless: false, q: 0.82 };

                    let dataUrl;
                    if (fmt.lossless) {
                        // PNG/TIFF: quality param is IGNORED by canvas — must reduce dimensions
                        // Strategy: shrink working canvas by 0.82× each pass until under 100KB
                        let workCanvas = canvas;
                        let scale2 = 1.0;
                        for (let attempt = 0; attempt < 8; attempt++) {
                            if (scale2 < 1.0) {
                                // Draw original canvas at reduced size
                                const wc = document.createElement('canvas');
                                wc.width = Math.round(canvas.width * scale2);
                                wc.height = Math.round(canvas.height * scale2);
                                const wctx = wc.getContext('2d');
                                // Smooth downscaling
                                wctx.imageSmoothingEnabled = true;
                                wctx.imageSmoothingQuality = 'high';
                                wctx.drawImage(canvas, 0, 0, wc.width, wc.height);
                                workCanvas = wc;
                            }
                            dataUrl = workCanvas.toDataURL(fmt.mime);
                            if (dataUrl.split(',')[1].length <= MAX_B64) break; // fits!
                            scale2 = Math.round((scale2 - 0.12) * 100) / 100;
                            if (scale2 < 0.2) break; // safety floor
                        }
                    } else {
                        // JPEG/WebP/GIF: reduce quality until under 100KB
                        let quality = fmt.q;
                        do {
                            dataUrl = canvas.toDataURL(fmt.mime, quality);
                            quality = Math.round((quality - 0.05) * 100) / 100;
                        } while (dataUrl.split(',')[1].length > MAX_B64 && quality > 0.40);
                    }
                    resolve({ name: buildName(fmt.ext), content: dataUrl.split(',')[1], type: fmt.mime });
                }
            } catch (err) {
                if (document.body.contains(iframe)) document.body.removeChild(iframe);
                console.error('Attachment conversion error:', err);
                resolve(null);
            }
        };
        iframe.srcdoc = html;
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
    // Check base64 char count directly — Vercel body limit is 4.5 MB total.
    // Base64 inflates by ~33%, so 3 MB of base64 chars ≈ 2.25 MB actual file.
    // Keeping the check at 3 MB base64 leaves headroom for the email body + headers.
    const MAX_B64_CHARS = 3 * 1024 * 1024; // 3 MB of base64 characters
    if (attachment.content && attachment.content.length > MAX_B64_CHARS) {
        const mb = (attachment.content.length / (1024 * 1024)).toFixed(1);
        showResult(resultElementId,
            `❌ Attachment is ~${mb} MB (base64) — too large for Vercel (4.5 MB total limit).<br>` +
            `Keep attachments under 2 MB actual file size. Try switching to <strong>HTML</strong> format or compress the file.`, 'error');
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

// ── Multi-country Name Banks ─────────────────────────────────────────────────
const _NAME_BANKS = {
    us: {
        first: ['James', 'John', 'Robert', 'Michael', 'William', 'David', 'Richard', 'Joseph', 'Thomas', 'Charles',
            'Mary', 'Patricia', 'Jennifer', 'Linda', 'Barbara', 'Elizabeth', 'Susan', 'Jessica', 'Sarah', 'Karen',
            'Emily', 'Amanda', 'Stephanie', 'Rebecca', 'Laura', 'Ashley', 'Megan'],
        last: ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez',
            'Wilson', 'Anderson', 'Taylor', 'Thomas', 'Moore', 'Jackson', 'Thompson', 'White', 'Harris', 'Martin'],
    },
    uk: {
        first: ['Oliver', 'Jack', 'Harry', 'George', 'Charlie', 'James', 'William', 'Thomas', 'Alfie', 'Freddie',
            'Olivia', 'Emily', 'Isla', 'Poppy', 'Ava', 'Isabella', 'Sophie', 'Grace', 'Lily', 'Amelia'],
        last: ['Smith', 'Jones', 'Williams', 'Taylor', 'Davies', 'Brown', 'Evans', 'Wilson', 'Thomas', 'Roberts',
            'Johnson', 'Walker', 'Wright', 'Thompson', 'White', 'Hall', 'Harris', 'Lewis', 'Clarke', 'Robinson'],
    },
    ca: {
        first: ['Liam', 'Noah', 'Oliver', 'Elijah', 'Aiden', 'Lucas', 'Ethan', 'Mason', 'Logan', 'Carter',
            'Emma', 'Olivia', 'Sophia', 'Ava', 'Charlotte', 'Isabella', 'Mia', 'Abigail', 'Harper', 'Evelyn'],
        last: ['Tremblay', 'Gagnon', 'Roy', 'Bouchard', 'Gauthier', 'Morin', 'Lavoie', 'Fortin', 'Campbell', 'MacDonald'],
    },
    au: {
        first: ['Jack', 'Oliver', 'William', 'Noah', 'Thomas', 'Archer', 'Mason', 'Henry', 'Cooper', 'Charlotte',
            'Olivia', 'Amelia', 'Emma', 'Ava', 'Mia', 'Isla', 'Sophie', 'Grace', 'Chloe', 'Ruby'],
        last: ['Smith', 'Jones', 'Williams', 'Brown', 'Wilson', 'Taylor', 'Johnson', 'White', 'Mitchell', 'Campbell'],
    },
    de: {
        first: ['Lukas', 'Leon', 'Jonas', 'Maximilian', 'Felix', 'Finn', 'Paul', 'Noah', 'Elias', 'Tim',
            'Emma', 'Mia', 'Hannah', 'Emilia', 'Sofia', 'Lena', 'Anna', 'Lea', 'Marie', 'Leonie'],
        last: ['Müller', 'Schmidt', 'Schneider', 'Fischer', 'Weber', 'Meyer', 'Wagner', 'Becker', 'Schulz', 'Koch'],
    },
    fr: {
        first: ['Gabriel', 'Raphael', 'Lucas', 'Leo', 'Hugo', 'Arthur', 'Louis', 'Tom', 'Nathan', 'Mathis',
            'Emma', 'Jade', 'Louise', 'Alice', 'Chloé', 'Inès', 'Léa', 'Manon', 'Camille', 'Lola'],
        last: ['Martin', 'Bernard', 'Thomas', 'Petit', 'Robert', 'Richard', 'Durand', 'Dubois', 'Moreau', 'Laurent'],
    },
    it: {
        first: ['Alessandro', 'Francesco', 'Lorenzo', 'Matteo', 'Andrea', 'Marco', 'Luca', 'Davide', 'Simone', 'Federico',
            'Sofia', 'Giulia', 'Martina', 'Sara', 'Valentina', 'Chiara', 'Alessia', 'Federica', 'Elena', 'Laura'],
        last: ['Rossi', 'Russo', 'Ferrari', 'Esposito', 'Bianchi', 'Romano', 'Colombo', 'Ricci', 'Marino', 'Greco'],
    },
    es: {
        first: ['Alejandro', 'Diego', 'Pablo', 'Carlos', 'Miguel', 'Javier', 'Luis', 'Antonio', 'Manuel', 'Jorge',
            'Lucia', 'Maria', 'Paula', 'Laura', 'Ana', 'Carmen', 'Isabel', 'Sofia', 'Elena', 'Marta'],
        last: ['Garcia', 'Martinez', 'Fernandez', 'Lopez', 'Sanchez', 'Perez', 'Gonzalez', 'Rodriguez', 'Hernandez', 'Jimenez'],
    },
    nl: {
        first: ['Daan', 'Sem', 'Finn', 'Jesse', 'Liam', 'Noah', 'Lucas', 'Milan', 'Tim', 'Bram',
            'Emma', 'Sophie', 'Julia', 'Anna', 'Lisa', 'Lotte', 'Laura', 'Sara', 'Nina', 'Amy'],
        last: ['De Jong', 'Jansen', 'De Vries', 'Van den Berg', 'Van Dijk', 'Bakker', 'Janssen', 'Visser', 'Smit', 'Meijer'],
    },
    br: {
        first: ['Gabriel', 'Lucas', 'Matheus', 'Pedro', 'Bruno', 'Rafael', 'Felipe', 'Guilherme', 'Vitor', 'Thiago',
            'Ana', 'Maria', 'Juliana', 'Amanda', 'Fernanda', 'Camila', 'Beatriz', 'Mariana', 'Patricia', 'Leticia'],
        last: ['Silva', 'Santos', 'Oliveira', 'Souza', 'Rodrigues', 'Ferreira', 'Alves', 'Pereira', 'Lima', 'Gomes'],
    },
    mx: {
        first: ['Carlos', 'Jose', 'Luis', 'Miguel', 'Juan', 'Francisco', 'Roberto', 'Fernando', 'Eduardo', 'Alejandro',
            'Maria', 'Ana', 'Laura', 'Alejandra', 'Sofia', 'Valeria', 'Paola', 'Karla', 'Monica', 'Claudia'],
        last: ['Hernandez', 'Garcia', 'Martinez', 'Lopez', 'Perez', 'Rodriguez', 'Sanchez', 'Ramirez', 'Torres', 'Flores'],
    },
    sg: {
        first: ['Wei', 'Jun', 'Jia', 'Hui', 'Ming', 'Kai', 'Ethan', 'Ryan', 'Aidan', 'Brandon',
            'Emily', 'Sophia', 'Chloe', 'Hannah', 'Priya', 'Jasmine', 'Sarah', 'Rachel', 'Michelle', 'Amanda'],
        last: ['Tan', 'Lim', 'Lee', 'Ng', 'Wong', 'Chan', 'Koh', 'Teo', 'Goh', 'Ong'],
    },
    nz: {
        first: ['Oliver', 'Jack', 'James', 'William', 'Thomas', 'Mason', 'Logan', 'Noah', 'Hunter', 'Liam',
            'Olivia', 'Charlotte', 'Isla', 'Mia', 'Ava', 'Sophie', 'Amelia', 'Grace', 'Emma', 'Harper'],
        last: ['Smith', 'Jones', 'Williams', 'Brown', 'Taylor', 'Wilson', 'Anderson', 'Thompson', 'Tane', 'Walker'],
    },
    se: {
        first: ['Liam', 'Noah', 'Oliver', 'William', 'Elias', 'Lucas', 'Alexander', 'Hugo', 'Oscar', 'Leo',
            'Emma', 'Olivia', 'Astrid', 'Maja', 'Alice', 'Ella', 'Vera', 'Ebba', 'Lina', 'Saga'],
        last: ['Andersson', 'Johansson', 'Karlsson', 'Nilsson', 'Eriksson', 'Larsson', 'Olsson', 'Persson', 'Svensson', 'Lindqvist'],
    },
    pl: {
        first: ['Jakub', 'Mateusz', 'Piotr', 'Michal', 'Pawel', 'Tomasz', 'Lukasz', 'Marcin', 'Bartosz', 'Adam',
            'Anna', 'Maria', 'Katarzyna', 'Magdalena', 'Agnieszka', 'Ewelina', 'Paulina', 'Natalia', 'Monika', 'Joanna'],
        last: ['Kowalski', 'Nowak', 'Wisniewski', 'Wojcik', 'Kowalczyk', 'Kaminski', 'Lewandowski', 'Zielinski', 'Szymanski', 'Wozniak'],
    },
    ae: {
        first: ['Mohammed', 'Ahmed', 'Ali', 'Omar', 'Hassan', 'Khalid', 'Ibrahim', 'Yusuf', 'Tariq', 'Samir',
            'Fatima', 'Aisha', 'Sara', 'Mariam', 'Nour', 'Layla', 'Hana', 'Dina', 'Rania', 'Yasmin'],
        last: ['Al-Rashid', 'Al-Maktoum', 'Al-Nahyan', 'Al-Mazrouei', 'Al-Shamsi', 'Al-Mansoori', 'Khalaf', 'Salem', 'Hamdan', 'Saeed'],
    },
    in: {
        first: ['Arjun', 'Rohan', 'Aditya', 'Rahul', 'Vikram', 'Amit', 'Saurabh', 'Kiran', 'Nikhil', 'Rajesh',
            'Priya', 'Anjali', 'Deepika', 'Neha', 'Sneha', 'Pooja', 'Swati', 'Kavya', 'Riya', 'Shreya'],
        last: ['Sharma', 'Patel', 'Singh', 'Kumar', 'Gupta', 'Mehta', 'Joshi', 'Chauhan', 'Rao', 'Nair'],
    },
    jp: {
        first: ['Haruto', 'Yuto', 'Sota', 'Yuma', 'Hayato', 'Kota', 'Ren', 'Ryuto', 'Kaito', 'Daiki',
            'Yui', 'Hana', 'Sakura', 'Aoi', 'Hina', 'Riko', 'Mia', 'Koharu', 'Akari', 'Nana'],
        last: ['Sato', 'Suzuki', 'Takahashi', 'Tanaka', 'Watanabe', 'Ito', 'Yamamoto', 'Nakamura', 'Kobayashi', 'Kato'],
    },
};
function _getNameBank(country) {
    if (country === 'random' || !_NAME_BANKS[country]) {
        const keys = Object.keys(_NAME_BANKS);
        return _NAME_BANKS[keys[Math.floor(Math.random() * keys.length)]];
    }
    return _NAME_BANKS[country];
}
function _randomNameFromCountry(country) {
    const bank = _getNameBank(country);
    return _rndOf(bank.first) + ' ' + _rndOf(bank.last);
}
function updateRandomNameExamples(ctx) {
    const countryEl = document.getElementById((ctx || 'bulk') + 'NameCountry');
    const country = countryEl ? countryEl.value : 'us';
    const examples = Array.from({ length: 4 }, () => _randomNameFromCountry(country)).join(', ');
    // Support ctx-specific IDs: 'singleRandomNameExamples' or legacy 'randomNameExamples' for bulk
    const exId = ctx === 'single' ? 'singleRandomNameExamples' : 'randomNameExamples';
    const ex = document.getElementById(exId);
    if (ex) ex.textContent = examples;
    const sel = document.getElementById((ctx || 'bulk') + 'CountrySelector');
    if (sel) sel.classList.add('visible');
}
// Toggle random sender name UI (updated: country support)
function toggleRandomSenderName(ctx) {
    const cb = document.getElementById(ctx + 'RandomSenderName');
    const row = document.getElementById(ctx + 'SenderNameRow');
    const prev = document.getElementById(ctx + 'RandomNamePreview');
    if (!cb) return;
    const isRandom = cb.checked;
    if (row) row.style.display = isRandom ? 'none' : 'flex';
    if (prev) prev.style.display = isRandom ? 'block' : 'none';
    const sel = document.getElementById(ctx + 'CountrySelector');
    if (isRandom && prev) {
        updateRandomNameExamples(ctx);
        if (sel) sel.classList.add('visible');
    } else {
        if (sel) sel.classList.remove('visible');
    }
}

// Show spam warning when HTML attachment format is selected
function onAttachFormatChange(ctx, el) {
    const warn = document.getElementById(ctx + 'AttachFormatWarn');
    if (warn) warn.style.display = (el.value === 'html') ? 'block' : 'none';
}

// Real-time subject spam keyword checker
// These are the #1 spam-flagged subjects used in phishing/bulk campaigns
const _SPAM_SUBJECT_WORDS = [
    'shipment', 'shipped', 'shipping', 'package', 'delivery', 'delivered',
    'order', 'invoice', 'receipt', 'billing', 'payment', 'charge',
    'confirm', 'confirmation', 'verify', 'verification', 'account',
    'urgent', 'important', 'action required', 'click here', 'click now',
    'free', 'winner', 'won', 'prize', 'congratulations', 'reward',
    'limited time', 'expires', 'offer', 'deal', 'discount', 'sale',
    'suspended', 'blocked', 'compromised', 'unusual activity',
    'act now', 'respond', 'reply', 'open immediately',
    'dear customer', 'dear user', 'dear member', 'hello dear',
    'bank', 'refund', 'claim', 'tax', 'irs', 'amazon', 'paypal', 'fedex', 'ups', 'dhl',
];
const _subjectWarnTimers = {};
function checkSubjectSpam(ctx, val) {
    const warn = document.getElementById(ctx + 'SubjectSpamWarn');
    if (!warn) return;
    const lower = val.toLowerCase();
    const hit = _SPAM_SUBJECT_WORDS.some(w => lower.includes(w));
    if (hit && val.length > 3) {
        warn.style.display = 'block';
        warn.style.opacity = '1';
        clearTimeout(_subjectWarnTimers[ctx]);
        // Auto-dismiss after 10 seconds with smooth fade out
        _subjectWarnTimers[ctx] = setTimeout(() => {
            warn.style.transition = 'opacity 0.6s ease';
            warn.style.opacity = '0';
            setTimeout(() => {
                warn.style.display = 'none';
                warn.style.opacity = '1';
                warn.style.transition = '';
            }, 650);
        }, 10000);
    } else {
        clearTimeout(_subjectWarnTimers[ctx]);
        warn.style.display = 'none';
    }
}


// ── Spam Score Checker ─────────────────────────────────────────────────────────────────────────
// Debounce timer for real-time analysis
let _scDebounceTimer = null;

/**
 * openSpamPanel(ctx) — open the panel and run analysis immediately
 */
function openSpamPanel(ctx) {
    const panel = document.getElementById('spamPanel_' + ctx);
    if (!panel) return;
    panel.style.display = 'block';
    _doSpamCheck(ctx);
}

/**
 * runSpamCheck(ctx) — called on input events (debounced 400ms)
 */
function runSpamCheck(ctx) {
    clearTimeout(_scDebounceTimer);
    _scDebounceTimer = setTimeout(() => _doSpamCheck(ctx), 400);
    // Also fire subject spam check for inline warning
    const subjEl = document.getElementById((ctx === 'single' ? 'singleSubject' : 'bulkSubject'));
    if (subjEl) checkSubjectSpam(ctx, subjEl.value);
}

function _doSpamCheck(ctx) {
    if (!window.analyzeSpam) return;
    const panel = document.getElementById('spamPanel_' + ctx);
    if (!panel || panel.style.display === 'none') return;

    const subjectId = ctx === 'single' ? 'singleSubject' : 'bulkSubject';
    const bodyId = ctx === 'single' ? 'singleHtml' : 'bulkHtml';
    const subject = (document.getElementById(subjectId) || {}).value || '';
    const body = (document.getElementById(bodyId) || {}).value || '';

    const { results, issues } = analyzeSpam(subject, body);
    _renderSpamPanel(ctx, results, issues);
}

function _renderSpamPanel(ctx, results, issues) {
    // ── Provider rows ────────────────────────────────────────────────────────
    const provContainer = document.getElementById('scProviders_' + ctx);
    if (!provContainer) return;

    provContainer.innerHTML = results.map(r => {
        const pct = r.score;
        const barColour = pct < (r.inbox || 35) ? '#22c55e'
            : pct < (r.promo || 65) ? '#f59e0b'
                : '#ef4444';
        return `
        <div class="sc-provider-row">
            <span class="sc-provider-name">${r.icon} ${r.name}</span>
            <div class="sc-bar-wrap">
                <div class="sc-bar-fill" style="width:${pct}%;background:${barColour};"></div>
            </div>
            <span class="sc-verdict" style="color:${r.colour};">
                ${r.vicon} ${r.verdict}<span class="sc-score-badge">${pct}/100</span>
            </span>
        </div>`;
    }).join('');

    // ── Issues list ──────────────────────────────────────────────────────────
    const issuesWrap = document.getElementById('scIssues_' + ctx);
    const issueList = document.getElementById('scIssueList_' + ctx);
    if (!issuesWrap || !issueList) return;

    if (issues.length === 0) {
        issuesWrap.style.display = 'none';
    } else {
        issuesWrap.style.display = 'block';
        issueList.innerHTML = issues.map(i => `
            <div class="sc-issue ${i.type}">
                <span class="sc-issue-dot"></span>
                <span>${i.msg}</span>
            </div>`).join('');
    }
}


// ── Body Mode Toggle (HTML / Plain Text) ─────────────────────────────────────
function setBodyMode(ctx, mode) {
    const htmlBtn = document.getElementById(ctx + 'ModeHtml');
    const textBtn = document.getElementById(ctx + 'ModeText');
    const bodyId = ctx === 'single' ? 'singleHtml' : 'bulkHtml';
    const badgeEl = document.querySelector('#' + bodyId + ' ~ .spintax-badge, .spintax-wrap .spintax-badge');
    const bodyEl = document.getElementById(bodyId);
    const label = document.querySelector('[for="' + bodyId + '"], label:has(+ div .spintax-wrap)');
    // Find the label above this form-group
    const fgLabel = bodyEl ? bodyEl.closest('.form-group') && bodyEl.closest('.form-group').querySelector('label') : null;
    if (htmlBtn) htmlBtn.classList.toggle('mode-active', mode === 'html');
    if (textBtn) textBtn.classList.toggle('mode-active', mode === 'text');
    if (!bodyEl) return;
    if (mode === 'html') {
        bodyEl.placeholder = '<h1>Hello!</h1><p>Your content here. Use {Option A|Option B} for spintax.</p>';
        if (fgLabel) fgLabel.textContent = ctx === 'single' ? 'HTML Body:' : 'HTML Template:';
    } else {
        bodyEl.placeholder = 'Type your plain text message here.\n\nUse {Hello|Hi|Hey} spintax for variation.\nUse $name, $email, $product etc. for personalisation.';
        if (fgLabel) fgLabel.textContent = ctx === 'single' ? 'Plain Text Body:' : 'Plain Text Template:';
    }
    // Store mode so sendEmail picks it up
    window['_bodyMode_' + ctx] = mode;
    // Re-run spam check
    runSpamCheck(ctx);
}
function getBodyMode(ctx) {
    return window['_bodyMode_' + ctx] || 'html';
}

// ── Spam Score Minimizer ──────────────────────────────────────────────────────
// Replaces known spam-triggering keywords with safer spintax alternatives
const _SPAM_FIXES = {
    'shipment delivered': '{Your item|Package} has {arrived|been received}',
    'shipment': '{package|parcel|item}',
    'shipped': '{sent|processed|dispatched}',
    'shipping': '{delivery|fulfilment|processing}',
    'delivery failed': 'delivery {update|notification|status}',
    'delivered': '{arrived|completed|received}',
    'order confirmation': '{request summary|purchase details}',
    'order info': '{request details|purchase information}',
    'invoice': '{document|statement|record}',
    'urgent': '{important|priority}',
    'action required': '{please review|your attention is needed}',
    'act now': '{see details|review now}',
    'click here': '{view details|learn more|open here}',
    'click now': '{see more|view now}',
    'free': '{complimentary|included|no extra cost}',
    'winner': '{selected recipient|valued member}',
    'prize': '{reward|benefit}',
    'congratulations': '{great news|thank you}',
    'limited time': '{for a short time|while available}',
    'expires': '{ends|closes}',
    'verify your account': 'confirm your {details|information}',
    'verify': '{confirm|review}',
    'account suspended': 'account {update|notification}',
    'suspended': '{paused|on hold}',
    'payment due': '{balance due|amount pending}',
    'payment': '{transaction|process}',
    'dear customer': '{Hello|Hi} {$name|there}',
    'dear user': '{Hello|Hi} {$name|there}',
};

function minimizeSpam(ctx) {
    const subjectId = ctx === 'single' ? 'singleSubject' : 'bulkSubject';
    const bodyId = ctx === 'single' ? 'singleHtml' : 'bulkHtml';
    const subjEl = document.getElementById(subjectId);
    const bodyEl = document.getElementById(bodyId);

    function applyFixes(text) {
        if (!text) return text;
        // Apply longest matches first to avoid partial replacements
        const entries = Object.entries(_SPAM_FIXES).sort((a, b) => b[0].length - a[0].length);
        for (const [word, repl] of entries) {
            const regex = new RegExp(word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi');
            text = text.replace(regex, repl);
        }
        return text;
    }

    let changed = false;
    if (subjEl && subjEl.value) {
        const fixed = applyFixes(subjEl.value);
        if (fixed !== subjEl.value) { subjEl.value = fixed; changed = true; }
    }
    if (bodyEl && bodyEl.value) {
        const fixed = applyFixes(bodyEl.value);
        if (fixed !== bodyEl.value) { bodyEl.value = fixed; changed = true; }
    }

    // Flash panel to confirm
    const panel = document.getElementById('spamPanel_' + ctx);
    if (panel && panel.style.display !== 'none') {
        panel.style.outline = '2px solid #10b981';
        setTimeout(() => { panel.style.outline = ''; }, 1200);
    }

    // Re-run spam check
    _doSpamCheck(ctx);
    if (changed) {
        // Show minimize success toast
        const toast = document.createElement('div');
        toast.textContent = '✅ Spam words replaced with safer alternatives!';
        Object.assign(toast.style, {
            position: 'fixed', bottom: '24px', right: '24px', zIndex: '9999',
            background: '#064e3b', border: '1px solid #10b981', color: '#6ee7b7',
            padding: '10px 18px', borderRadius: '8px', fontSize: '13px',
            fontWeight: '600', boxShadow: '0 8px 24px rgba(0,0,0,.4)',
            animation: 'scFadeIn .2s ease',
        });
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 3000);
    }
}

// ── Batch section visibility ───────────────────────────────────────────────
function syncBatchSection() {
    const methodEl = document.getElementById('bulkMethod');
    const section = document.getElementById('smtpBatchSection');
    if (!section || !methodEl) return;
    // Show batch settings for both SMTP and EC2 (both support account rotation)
    const m = methodEl.value;
    section.style.display = (m === 'smtp' || m === 'ec2') ? 'block' : 'none';
    // Update label to show which thing is rotating
    const titleEl = section.querySelector('.batch-section-title');
    if (titleEl) {
        if (m === 'ec2') {
            titleEl.innerHTML = '⚙️ EC2 Relay Batch Settings &nbsp;<span id="batchModeLabel" class="badge-mode">sequential</span>';
        } else {
            titleEl.innerHTML = '⚙️ SMTP Batch Settings &nbsp;<span id="batchModeLabel" class="badge-mode">sequential</span>';
        }
    }
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
    const field = document.getElementById(fieldId);
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
    try { localStorage.setItem(LIBRARY_KEY, JSON.stringify(lib)); } catch { }
}

function escHtml(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// Save subject or body to library
// listKey: 'subjectLib' | 'bodyLib'   listElId: id of the <div> to re-render
function saveToLibrary(fieldId, listKey, listElId) {
    const field = document.getElementById(fieldId);
    if (!field || !field.value.trim()) { alert('Field is empty'); return; }
    const lib = loadLibrary();
    const key = listKey === 'subjectLib' ? 'subjects' : 'bodies';
    const cap = key === 'subjects' ? 50 : 30;
    const val = field.value.trim();
    // Deduplicate
    if (lib[key].includes(val)) { alert('Already saved'); return; }
    lib[key].unshift(val);
    if (lib[key].length > cap) lib[key].pop();
    saveLibrary(lib);
    renderLibraryList(key, listElId, fieldId);
}

function renderLibraryList(key, listElId, fieldId) {
    const el = document.getElementById(listElId);
    if (!el) return;
    const lib = loadLibrary();
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
    const lib = loadLibrary();
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
    renderLibraryList('bodies', 'singleBodyList', 'singleHtml');
    renderLibraryList('subjects', 'bulkSubjectList', 'bulkSubject');
    renderLibraryList('bodies', 'bulkBodyList', 'bulkHtml');
}

// ══════════════════════════════════════════════════════════════════════════════
// ── SUBJECT POOL  (multiple subjects → random pick per email) ────────────────
// ══════════════════════════════════════════════════════════════════════════════

function addSubjectToPool(context) {
    const fieldId = context === 'single' ? 'singleSubject' : 'bulkSubject';
    const field = document.getElementById(fieldId);
    if (!field || !field.value.trim()) { alert('Subject field is empty'); return; }
    // Support pasting multiple lines at once
    const lines = field.value.trim().split('\n').map(l => l.trim()).filter(l => l);
    const pool = context === 'single' ? singleSubjectPool : bulkSubjectPool;
    lines.forEach(line => { if (!pool.includes(line)) pool.push(line); });
    renderSubjectPool(context);
}

function loadSubjectPoolFile(context, event) {
    const file = event.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = function (e) {
        const lines = e.target.result.trim().split('\n').map(l => l.trim()).filter(l => l);
        const pool = context === 'single' ? singleSubjectPool : bulkSubjectPool;
        lines.forEach(line => { if (!pool.includes(line)) pool.push(line); });
        renderSubjectPool(context);
    };
    reader.readAsText(file);
    event.target.value = '';
}

function renderSubjectPool(context) {
    const poolEl = document.getElementById(context + 'SubjectPool');
    const countEl = document.getElementById(context + 'SubjectCount');
    const pool = context === 'single' ? singleSubjectPool : bulkSubjectPool;
    if (countEl) countEl.textContent = pool.length;
    if (!poolEl) return;
    if (!pool.length) {
        poolEl.innerHTML = '<div class="library-empty">Add a subject or browse .txt file (one per line) — randomly picked per email</div>';
        return;
    }
    poolEl.innerHTML = pool.map((s, i) => `
        <div class="library-item">
            <span class="library-item-text" title="${escHtml(s)}">${escHtml(s.slice(0, 90))}${s.length > 90 ? '…' : ''}</span>
            <button class="library-item-del" onclick="removeSubjectFromPool('${context}',${i})">✕</button>
        </div>`).join('');
}

function removeSubjectFromPool(context, idx) {
    const pool = context === 'single' ? singleSubjectPool : bulkSubjectPool;
    pool.splice(idx, 1);
    renderSubjectPool(context);
}

function clearSubjectPool(context) {
    if (context === 'single') singleSubjectPool = [];
    else bulkSubjectPool = [];
    renderSubjectPool(context);
}

// 10 spam-free subject templates with spintax + placeholders
const SPAM_FREE_SUBJECTS = [
    '{Hi|Hello|Hey} {{name}}, Your {Exclusive|Special|VIP} {Offer|Deal|Invitation} is Ready',
    '{Important|Urgent|Action Required}: Account Update — {{unique_id}}',
    'Your {Order|Invoice|Receipt} #{{13_digit}} from {{company}} is {Confirmed|Ready|Processed}',
    '{Congratulations|Great News|You\'re Selected} — {Claim|Unlock|Access} Your {Reward|Gift|Bonus}',
    '{Don\'t Miss|Last Chance|Limited Time}: {Save 20%|Get 30% Off|Exclusive Discount} {Today|This Week|Ending Soon}',
    '{New|Latest|Exclusive} {Opportunity|Product|Service} Available at {{company}}',
    '{{random_name}} wants to {connect|collaborate|partner} with you — {{date}}',
    '{Monthly|Weekly|Quarterly} {Report|Summary|Newsletter} — {{company}} — {{date}}',
    '{Re:|Fwd:|Follow-up:} {Your Request|Our Conversation|Your Inquiry} #{{random_6}}',
    '{Reminder|Notice|Alert}: {Meeting|Appointment|Discussion} {Today|Tomorrow|Scheduled} at {{time}}'
];

function loadSpamFreeSubjectTemplates(context) {
    const pool = context === 'single' ? singleSubjectPool : bulkSubjectPool;
    SPAM_FREE_SUBJECTS.forEach(s => { if (!pool.includes(s)) pool.push(s); });
    renderSubjectPool(context);
    // Also set first template in the field
    const fieldId = context === 'single' ? 'singleSubject' : 'bulkSubject';
    const field = document.getElementById(fieldId);
    if (field && !field.value.trim()) field.value = SPAM_FREE_SUBJECTS[0];
    alert('✅ Loaded 10 spam-free subject templates into the pool!\nThey will be randomly rotated during sending.');
}

// ══════════════════════════════════════════════════════════════════════════════
// ── BODY POOL  (multiple HTML files → random pick per email, bulk only) ──────
// ══════════════════════════════════════════════════════════════════════════════

function loadBodyFiles(event) {
    const files = Array.from(event.target.files);
    if (!files.length) return;
    let loaded = 0;
    files.forEach(file => {
        const reader = new FileReader();
        reader.onload = function (e) {
            bodyPool.push({ id: _bodyPoolNextId++, name: file.name, content: e.target.result });
            loaded++;
            if (loaded === files.length) renderBodyPool();
        };
        reader.readAsText(file);
    });
    event.target.value = '';
}

function renderBodyPool() {
    const poolEl = document.getElementById('bodyPoolList');
    const countEl = document.getElementById('bodyPoolCount');
    if (countEl) countEl.textContent = bodyPool.length;
    if (!poolEl) return;
    if (!bodyPool.length) {
        poolEl.innerHTML = '<div class="library-empty">Browse HTML files — one will be randomly picked per email during bulk send</div>';
        return;
    }
    poolEl.innerHTML = bodyPool.map(b => `
        <div class="library-item">
            <span class="library-item-text">📄 ${escHtml(b.name)} <small style="color:#888;">(${Math.round(b.content.length / 1024 * 10) / 10} KB)</small></span>
            <button class="btn-xs" style="font-size:10px;background:#667eea;color:#fff;border:none;border-radius:3px;padding:2px 6px;cursor:pointer;margin-right:4px;" onclick="useBodyFromPool(${b.id})">Use</button>
            <button class="library-item-del" onclick="removeBodyFile(${b.id})">✕</button>
        </div>`).join('');
}

function removeBodyFile(id) {
    bodyPool = bodyPool.filter(b => b.id !== id);
    renderBodyPool();
}

function clearBodyPool() {
    bodyPool = [];
    renderBodyPool();
}

function useBodyFromPool(id) {
    const item = bodyPool.find(b => b.id === id);
    if (!item) return;
    const field = document.getElementById('bulkHtml');
    if (field) { field.value = item.content; alert(`✅ "${item.name}" loaded into the HTML body field.`); }
}

// ══════════════════════════════════════════════════════════════════════════════
// ── SPAM-FREE HTML BODY TEMPLATE ─────────────────────────────────────────────
// ══════════════════════════════════════════════════════════════════════════════

const SAMPLE_HTML_TEMPLATE = `<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;background:#f9f9f9;">
  <div style="background:#fff;padding:30px;border-radius:8px;border:1px solid #e0e0e0;">
    <h2 style="color:#333;margin-top:0;">{Exclusive Offer|Special Deal|Premium Opportunity} Just for You</h2>
    <p style="color:#555;line-height:1.6;">{Hi|Hello|Dear} {{name}},</p>
    <p style="color:#555;line-height:1.6;">
      {We are thrilled to|We're excited to|We'd like to} {inform|notify|let you know} that <strong>{{company}}</strong>
      has a {special|exclusive|limited} {offer|deal|opportunity} available {just for you|today|this week}.
    </p>
    <div style="background:#f0f4ff;padding:15px;border-radius:6px;margin:20px 0;border-left:4px solid #667eea;">
      <strong>Reference ID:</strong> {{13_digit}}<br>
      <strong>Date:</strong> {{date}}<br>
      <strong>Valid Until:</strong> {48 hours|72 hours|End of this week|This month only}
    </div>
    <p style="color:#555;line-height:1.6;">
      {To take advantage of|To claim|To access} this {offer|opportunity|deal},
      {simply reply to this email|reach out to our team|contact us today}.
    </p>
    <a href="#" style="display:inline-block;background:#667eea;color:#fff;padding:12px 24px;border-radius:6px;text-decoration:none;font-weight:bold;">
      {Get Started|Claim Now|Learn More|Take Action}
    </a>
    <p style="color:#888;font-size:12px;margin-top:30px;">
      {Best regards|Warm regards|Sincerely},<br>
      <strong>{{random_name}}</strong><br>
      {{company}}<br>
      <small>Ref: {{unique_id}} | {{date}}</small>
    </p>
  </div>
</div>`;

function loadSampleHtmlTemplate(fieldId) {
    const field = document.getElementById(fieldId);
    if (!field) return;
    if (field.value.trim() && !confirm('Replace current body with the sample template?')) return;
    field.value = SAMPLE_HTML_TEMPLATE;
    alert('✅ Sample template loaded!\nIt uses spintax {A|B|C} and placeholders {{name}}, {{company}}, {{date}}, etc.\nCustomize it as needed.');
}

// ══════════════════════════════════════════════════════════════════════════════
// ── HTML FILE CONVERTER (browse any .html → download in 12 formats) ──────────
// ══════════════════════════════════════════════════════════════════════════════

function loadHtmlConverterFile(context, event) {
    const file = event.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = function (e) {
        htmlConverterData[context] = { name: file.name, content: e.target.result };
        const nameEl = document.getElementById(context + 'ConverterFileName');
        const clearBtn = document.getElementById(context + 'ConverterClear');
        const barEl = document.getElementById(context + 'ConverterBar');
        if (nameEl) nameEl.textContent = '📄 ' + file.name;
        if (clearBtn) clearBtn.style.display = 'inline-block';
        if (barEl) barEl.style.display = 'flex';
    };
    reader.readAsText(file);
    event.target.value = '';
}

function clearConverterFile(context) {
    htmlConverterData[context] = null;
    const nameEl = document.getElementById(context + 'ConverterFileName');
    const clearBtn = document.getElementById(context + 'ConverterClear');
    const barEl = document.getElementById(context + 'ConverterBar');
    const statusEl = document.getElementById('exportStatus_' + context + 'Converter');
    if (nameEl) nameEl.textContent = '';
    if (clearBtn) clearBtn.style.display = 'none';
    if (barEl) barEl.style.display = 'none';
    if (statusEl) { statusEl.textContent = ''; statusEl.style.display = 'none'; }
}

async function exportHtmlFile(context, format) {
    const data = htmlConverterData[context];
    if (!data) { alert('Please browse an HTML file first.'); return; }
    // Reuse the existing exportBodyContent logic but with the converter file's content
    // Temporarily swap the field value, call export, then restore
    const statusId = 'exportStatus_' + context + 'Converter';
    const status = document.getElementById(statusId);
    function setStatus(msg) {
        if (status) { status.textContent = msg; status.style.display = msg ? 'block' : 'none'; }
    }
    function triggerDownload(blob, filename) {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a'); a.href = url; a.download = filename; a.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
    }
    const html = data.content;
    const baseName = data.name.replace(/\.(html|htm)$/i, '');
    setStatus('Converting…');
    try {
        if (format === 'txt') {
            triggerDownload(new Blob([htmlToPlainText(html)], { type: 'text/plain' }), baseName + '.txt');
        } else if (format === 'md') {
            triggerDownload(new Blob([htmlToMarkdown(html)], { type: 'text/markdown' }), baseName + '.md');
        } else if (format === 'rtf') {
            triggerDownload(new Blob([htmlToRtf(html)], { type: 'application/rtf' }), baseName + '.rtf');
        } else if (format === 'docx') {
            const wordHtml = `<html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:w="urn:schemas-microsoft-com:office:word" xmlns="http://www.w3.org/TR/REC-html40"><head><meta charset="utf-8"><meta name=ProgId content=Word.Document></head><body>${html}</body></html>`;
            triggerDownload(new Blob([wordHtml], { type: 'application/vnd.ms-word' }), baseName + '.doc');
        } else if (format === 'xlsx') {
            if (window.XLSX) {
                const doc = new DOMParser().parseFromString(html, 'text/html');
                const tables = doc.querySelectorAll('table');
                const wb = XLSX.utils.book_new();
                if (tables.length) {
                    tables.forEach((tbl, ti) => XLSX.utils.book_append_sheet(wb, XLSX.utils.table_to_sheet(tbl), `Sheet${ti + 1}`));
                } else {
                    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(htmlToPlainText(html).split('\n').map(l => [l])), 'Content');
                }
                triggerDownload(new Blob([XLSX.write(wb, { bookType: 'xlsx', type: 'array' })], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' }), baseName + '.xlsx');
            } else { setStatus('❌ SheetJS not loaded'); return; }
        } else if (format === 'pptx') {
            if (typeof PptxGenJS !== 'undefined') {
                const pptx = new PptxGenJS();
                const paras = htmlToPlainText(html).split('\n\n').filter(p => p.trim()).slice(0, 20);
                (paras.length ? paras : [htmlToPlainText(html)]).forEach(para => {
                    const slide = pptx.addSlide();
                    slide.addText(para.slice(0, 500), { x: 0.5, y: 0.5, w: 9, h: 5, fontSize: 16, wrap: true });
                });
                const buf = await pptx.stream();
                triggerDownload(new Blob([buf], { type: 'application/vnd.openxmlformats-officedocument.presentationml.presentation' }), baseName + '.pptx');
            } else { setStatus('❌ PptxGenJS not loaded'); return; }
        } else if (format === 'pdf') {
            await _exportViaCanvas(html, 'pdf', baseName + '.pdf', setStatus, triggerDownload); return;
        } else if (['png', 'jpeg', 'gif', 'webp', 'tiff'].includes(format)) {
            await _exportViaCanvas(html, format, baseName + '.' + format, setStatus, triggerDownload); return;
        }
        setStatus('✓ Downloaded ' + baseName + '.' + format);
        setTimeout(() => setStatus(''), 4000);
    } catch (err) {
        setStatus('❌ ' + err.message);
    }
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
        md = md.replace(/<h([1-6])[^>]*>([\s\S]*?)<\/h\1>/gi, (_, n, t) => '#'.repeat(parseInt(n)) + ' ' + t.replace(/<[^>]+>/g, '') + '\n');
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
        l.replace(/\\/g, '\\\\').replace(/\{/g, '\\{').replace(/\}/g, '\\}') + '\\par'
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
        const a = document.createElement('a');
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
                    const ws = XLSX.utils.aoa_to_sheet(rows);
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
                const pptx = new PptxGenJS();
                const text = htmlToPlainText(html);
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
        } else if (['png', 'jpeg', 'gif', 'webp', 'tiff'].includes(format)) {
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
                    const mimeMap = { png: 'image/png', jpeg: 'image/jpeg', gif: 'image/jpeg', webp: 'image/webp', tiff: 'image/png' };
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


// ══════════════════════════════════════════════════════════════════════════════
// ── DELIVERABILITY CHECKER ───────────────────────────────────────────────────
// ══════════════════════════════════════════════════════════════════════════════

function autoFillDomainFromSmtp() {
    if (smtpAccounts.length > 0) {
        const user = smtpAccounts[0].user || '';
        if (user.includes('@')) {
            document.getElementById('delivCheckDomain').value = user.split('@')[1];
        }
    } else {
        alert('No SMTP accounts configured. Add one in the SMTP Config tab first.');
    }
}

async function runDeliverabilityCheck() {
    const input = (document.getElementById('delivCheckDomain') || {}).value.trim();
    if (!input) {
        showResult('delivResult', '⚠️ Please enter a domain or SMTP email address', 'error');
        return;
    }

    const domain = input.includes('@') ? input.split('@')[1] : input;
    showResult('delivResult', `🔍 Checking ${domain}... (SPF, DKIM, DMARC, MX)`, 'info');
    document.getElementById('delivScoreCard').style.display = 'none';
    document.getElementById('delivChecks').style.display = 'none';

    try {
        const resp = await fetch('/api/deliverability', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'check_domain', domain, smtp_user: input })
        });
        const data = await resp.json();

        if (!data.success) {
            showResult('delivResult', `❌ ${data.error}`, 'error');
            return;
        }

        // Show score card
        const scoreCard = document.getElementById('delivScoreCard');
        const scoreCircle = document.getElementById('delivScoreCircle');
        const scoreLabel = document.getElementById('delivScoreLabel');
        const scoreSummary = document.getElementById('delivScoreSummary');
        scoreCard.style.display = 'block';

        const score = data.score || 0;
        let scoreColor, scoreText;
        if (score >= 80) { scoreColor = '#22c55e'; scoreText = 'Excellent'; }
        else if (score >= 60) { scoreColor = '#f59e0b'; scoreText = 'Needs Improvement'; }
        else if (score >= 40) { scoreColor = '#f97316'; scoreText = 'Poor'; }
        else { scoreColor = '#ef4444'; scoreText = 'Critical Issues'; }

        scoreCircle.style.border = `4px solid ${scoreColor}`;
        scoreCircle.style.color = scoreColor;
        scoreCircle.textContent = score;
        scoreLabel.style.color = scoreColor;
        scoreLabel.textContent = `Deliverability Score: ${scoreText}`;
        scoreSummary.textContent = `Domain: ${domain} — ${score}/100 points`;

        // Show check results
        const checksDiv = document.getElementById('delivChecks');
        checksDiv.style.display = 'block';

        const checksList = document.getElementById('delivChecksList');
        const checks = data.checks || {};
        let checksHtml = '';

        for (const [name, check] of Object.entries(checks)) {
            const label = name.toUpperCase();
            const sev = check.severity || 'warning';
            const icon = sev === 'ok' ? '✅' : sev === 'critical' ? '❌' : '⚠️';
            const color = sev === 'ok' ? '#22c55e' : sev === 'critical' ? '#ef4444' : '#f59e0b';
            const bg = sev === 'ok' ? 'rgba(34,197,94,0.08)' : sev === 'critical' ? 'rgba(239,68,68,0.08)' : 'rgba(245,158,11,0.08)';

            checksHtml += `
                <div style="padding:12px;margin:8px 0;border-radius:8px;background:${bg};border-left:3px solid ${color};">
                    <div style="font-weight:600;color:${color};">${icon} ${label}: ${check.status || 'UNKNOWN'}</div>
                    <div style="font-size:12px;color:#94a3b8;margin-top:4px;">${check.message || ''}</div>
                    ${check.record ? `<div style="font-size:11px;color:#64748b;margin-top:4px;font-family:monospace;word-break:break-all;">${check.record}</div>` : ''}
                    ${check.fix ? `<div style="font-size:12px;color:#60a5fa;margin-top:6px;white-space:pre-wrap;">💡 ${check.fix}</div>` : ''}
                </div>`;
        }
        checksList.innerHTML = checksHtml;

        // Show recommendations
        const recsDiv = document.getElementById('delivRecommendations');
        const recs = data.recommendations || [];
        let recsHtml = '';

        for (const rec of recs) {
            const sevColor = rec.severity === 'critical' ? '#ef4444' : rec.severity === 'warning' ? '#f59e0b' : rec.severity === 'ok' ? '#22c55e' : '#60a5fa';
            const sevIcon = rec.severity === 'critical' ? '🔴' : rec.severity === 'warning' ? '🟡' : rec.severity === 'ok' ? '🟢' : '🔵';
            recsHtml += `
                <div style="padding:12px;margin:8px 0;border-radius:8px;background:#0f172a;border-left:3px solid ${sevColor};">
                    <div style="font-weight:600;">${sevIcon} ${rec.title}</div>
                    ${rec.detail ? `<div style="font-size:12px;color:#94a3b8;margin-top:4px;white-space:pre-wrap;">${rec.detail}</div>` : ''}
                    ${rec.impact ? `<div style="font-size:11px;color:#64748b;margin-top:4px;">Impact: ${rec.impact}</div>` : ''}
                </div>`;
        }
        recsDiv.innerHTML = recsHtml;

        showResult('delivResult', `✅ Check complete for <strong>${domain}</strong> — Score: <strong style="color:${scoreColor};">${score}/100</strong>`, 'success');

    } catch (err) {
        showResult('delivResult', `❌ Check failed: ${err.message}`, 'error');
    }
}

// Checklist counter
document.addEventListener('change', function (e) {
    if (e.target.classList.contains('deliv-check')) {
        const all = document.querySelectorAll('.deliv-check');
        const checked = document.querySelectorAll('.deliv-check:checked');
        const countEl = document.getElementById('delivChecklistCount');
        if (countEl) countEl.textContent = `${checked.length}/${all.length} completed`;
    }
});

// ══════════════════════════════════════════════════════════════════════════════
// ── WARMUP TRACKING (daily send limits per account) ──────────────────────────
// ══════════════════════════════════════════════════════════════════════════════

const WARMUP_KEY = 'km_warmup_v1';

function getWarmupData() {
    try { return JSON.parse(localStorage.getItem(WARMUP_KEY) || '{}'); } catch { return {}; }
}

function saveWarmupData(data) {
    localStorage.setItem(WARMUP_KEY, JSON.stringify(data));
}

function recordSend(accountUser) {
    const today = new Date().toISOString().slice(0, 10);
    const data = getWarmupData();
    if (!data[accountUser]) data[accountUser] = {};
    if (!data[accountUser][today]) data[accountUser][today] = 0;
    data[accountUser][today]++;
    saveWarmupData(data);
    return data[accountUser][today];
}

function getTodaySendCount(accountUser) {
    const today = new Date().toISOString().slice(0, 10);
    const data = getWarmupData();
    return (data[accountUser] && data[accountUser][today]) || 0;
}

// ── safeFetchJson is defined earlier in this file ────────────────────────────
