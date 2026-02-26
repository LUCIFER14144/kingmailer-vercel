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

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    initTabs();
    loadAccounts();
    loadEc2Credentials(); // Load saved credentials first
    loadEc2Instances();
    
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
                <small>${acc.user} (${acc.provider})</small>
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

function renderEc2Instances(instances) {
    const container = document.getElementById('ec2InstancesList');
    
    if (!instances || instances.length === 0) {
        container.innerHTML = '<p class="no-accounts">No EC2 instances found</p>';
        return;
    }
    
    container.innerHTML = instances.map(instance => `
        <div class="account-card">
            <div class="account-info">
                <strong>Instance: ${instance.instance_id}</strong><br>
                <small>
                    IP: ${instance.public_ip || 'Pending...'}<br>
                    Region: ${instance.region}<br>
                    State: ${instance.state}<br>
                    Created: ${instance.created_at}
                </small>
            </div>
            <button class="btn btn-danger" onclick="terminateEc2Instance('${instance.instance_id}')">Terminate</button>
        </div>
    `).join('');
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
        infoBox.innerHTML = '<strong>⭐ EC2 Relay Mode:</strong> Sends emails using Gmail SMTP through your EC2 instance. Combines Gmail authentication with EC2 IP routing for better deliverability. <span style="color: #00ff9d;">Requires both EC2 instances AND Gmail SMTP configured!</span>';
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
            showResult('singleResult', 'No running EC2 instances available', 'error');
            return;
        }
        config.ec2_instance = runningInstance;
        
        // Include SMTP config for Gmail via EC2 relay
        if (smtpAccounts.length > 0) {
            config.smtp_config = smtpAccounts[0];
        }
    }
    
    showResult('singleResult', '🔄 Sending email...', 'info');
    
    try {
        const response = await fetch('/api/send', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                to: to,
                subject: subject,
                html: html,
                method: method,
                ...config
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showResult('singleResult', `✅ ${data.message}`, 'success');
        } else {
            showResult('singleResult', `❌ ${data.error}`, 'error');
        }
    } catch (error) {
        showResult('singleResult', `❌ Send failed: ${error.message}`, 'error');
    }
}

// Send bulk emails
async function sendBulkEmails() {
    let csv = document.getElementById('bulkCsv').value.trim();
    const subject = document.getElementById('bulkSubject').value;
    const html = document.getElementById('bulkHtml').value;
    const method = document.getElementById('bulkMethod').value;
    const minDelay = document.getElementById('bulkMinDelay').value;
    const maxDelay = document.getElementById('bulkMaxDelay').value;
    
    if (!csv || !subject || !html) {
        showResult('bulkResult', 'Please fill in all fields', 'error');
        return;
    }
    
    // Convert simple format to CSV if needed
    if (inputMode === 'simple') {
        const emails = csv.split('\n').filter(line => line.trim() && line.includes('@'));
        csv = 'email\n' + emails.join('\n');
    }
    
    // Get config based on method
    let config = {};
    
    console.log('Bulk send method:', method);
    console.log('Available EC2 instances:', ec2Instances.length);
    console.log('Available SMTP accounts:', smtpAccounts.length);
    
    if (method === 'smtp') {
        if (smtpAccounts.length === 0) {
            showResult('bulkResult', 'Please add at least one SMTP account first', 'error');
            return;
        }
        config.smtp_configs = smtpAccounts;
    } else if (method === 'ses') {
        if (sesAccounts.length === 0) {
            showResult('bulkResult', 'Please add an AWS SES account first', 'error');
            return;
        }
        config.aws_config = sesAccounts[0];
    } else if (method === 'ec2') {
        if (ec2Instances.length === 0) {
            showResult('bulkResult', 'Please create at least one EC2 instance first', 'error');
            return;
        }
        // Get all running instances
        const runningInstances = ec2Instances.filter(i => i.state === 'running');
        if (runningInstances.length === 0) {
            showResult('bulkResult', 'No running EC2 instances available', 'error');
            return;
        }
        config.ec2_instances = runningInstances;
        
        // Include SMTP configs for Gmail via EC2 relay
        if (smtpAccounts.length > 0) {
            config.smtp_configs = smtpAccounts;
        }
    }
    
    // Update stats before sending
    updateBulkStats();
    bulkSendingActive = true;
    
    const methodNames = {
        'smtp': 'Gmail SMTP',
        'ec2': 'EC2 Relay',
        'ses': 'AWS SES'
    };
    
    showResult('bulkResult', `🔄 Starting bulk send via ${methodNames[method]}... This may take a while.`, 'info');
    
    try {
        const response = await fetch('/api/send_bulk', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                csv_data: csv,
                subject: subject,
                html: html,
                method: method,
                min_delay: minDelay,
                max_delay: maxDelay,
                ...config
            })
        });
        
        const data = await response.json();
        
        bulkSendingActive = false;
        
        if (data.success) {
            updateBulkProgress(data.results.sent, data.results.failed, data.results.total);
            
            let resultMessage = `✅ Bulk send complete via ${methodNames[method]}!<br>
                Total: ${data.results.total}<br>
                Sent: ${data.results.sent}<br>
                Failed: ${data.results.failed}`;
            
            if (data.results.skipped && data.results.skipped.length > 0) {
                resultMessage += `<br>Skipped: ${data.results.skipped.length}`;
            }
            
            if (method === 'ec2' && config.ec2_instances && config.ec2_instances[0]) {
                resultMessage += `<br><br>🚀 Sent from EC2 IP: ${config.ec2_instances[0].public_ip}`;
            }
            
            showResult('bulkResult', resultMessage, 'success');
        } else {
            showResult('bulkResult', `❌ ${data.error}`, 'error');
        }
    } catch (error) {
        bulkSendingActive = false;
        showResult('bulkResult', `❌ Bulk send failed: ${error.message}`, 'error');
    }
}

// Utility: Show result message
function showResult(elementId, message, type) {
    const element = document.getElementById(elementId);
    element.innerHTML = message;
    element.className = `result-box ${type}`;
    element.style.display = 'block';
}
