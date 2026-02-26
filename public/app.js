/**
 * KINGMAILER v4.0 - Frontend JavaScript
 * Handles all dashboard interactions and API calls
 */

// Global state
let smtpAccounts = [];
let sesAccounts = [];
let ec2Relays = [];

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    initTabs();
    loadAccounts();
    loadEc2Relays();
    
    // Show/hide custom SMTP fields
    document.getElementById('smtpProvider').addEventListener('change', function() {
        const customFields = document.getElementById('customSmtpFields');
        customFields.style.display = this.value === 'custom' ? 'block' : 'none';
    });
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
            ec2Relays = data.accounts.ec2_relays || [];
            
            renderSmtpAccounts();
            renderSesAccounts();
            renderEc2Relays();
        }
    } catch (error) {
        console.error('Failed to load accounts:', error);
    }
}

async function loadEc2Relays() {
    try {
        const response = await fetch('/api/ec2_relay');
        const data = await response.json();
        
        if (data.success) {
            ec2Relays = data.relays || [];
            renderEc2Relays();
        }
    } catch (error) {
        console.error('Failed to load EC2 relays:', error);
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

// EC2 Functions
async function testEc2Relay() {
    const url = document.getElementById('ec2Url').value;
    
    if (!url) {
        showResult('ec2Result', 'Please enter relay URL', 'error');
        return;
    }
    
    showResult('ec2Result', '🔄 Testing EC2 relay connection...', 'info');
    
    try {
        const response = await fetch('/api/ec2_relay', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                action: 'test',
                url: url
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showResult('ec2Result', `✅ ${data.message || 'Connection successful'}`, 'success');
        } else {
            showResult('ec2Result', `❌ ${data.error}`, 'error');
        }
    } catch (error) {
        showResult('ec2Result', `❌ Connection failed: ${error.message}`, 'error');
    }
}

async function addEc2Relay() {
    const url = document.getElementById('ec2Url').value;
    const label = document.getElementById('ec2Label').value || url;
    
    if (!url) {
        showResult('ec2Result', 'Please enter relay URL', 'error');
        return;
    }
    
    try {
        const response = await fetch('/api/ec2_relay', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                action: 'add',
                url: url,
                label: label
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showResult('ec2Result', '✅ EC2 relay added successfully!', 'success');
            loadEc2Relays();
            
            // Clear form
            document.getElementById('ec2Url').value = '';
            document.getElementById('ec2Label').value = '';
        } else {
            showResult('ec2Result', `❌ ${data.error}`, 'error');
        }
    } catch (error) {
        showResult('ec2Result', `❌ Failed to add relay: ${error.message}`, 'error');
    }
}

function renderEc2Relays() {
    const container = document.getElementById('ec2RelaysList');
    
    if (ec2Relays.length === 0) {
        container.innerHTML = '<p class="no-accounts">No EC2 relays added yet</p>';
        return;
    }
    
    container.innerHTML = ec2Relays.map(relay => `
        <div class="account-card">
            <div class="account-info">
                <strong>${relay.label}</strong><br>
                <small>${relay.url}</small>
            </div>
            <button class="btn btn-danger" onclick="deleteAccount('ec2', ${relay.id})">Delete</button>
        </div>
    `).join('');
}

// Delete account
async function deleteAccount(type, id) {
    if (!confirm('Are you sure you want to delete this account?')) {
        return;
    }
    
    try {
        // Use different endpoint for EC2 relays
        const endpoint = (type === 'ec2') ? '/api/ec2_relay' : '/api/accounts';
        
        const response = await fetch(endpoint, {
            method: 'DELETE',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ type, id })
        });
        
        const data = await response.json();
        
        if (data.success) {
            if (type === 'ec2') {
                loadEc2Relays();
            } else {
                loadAccounts();
            }
        }
    } catch (error) {
        console.error('Failed to delete account:', error);
    }
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
        if (ec2Relays.length === 0) {
            showResult('singleResult', 'Please add an EC2 relay first', 'error');
            return;
        }
        config.ec2_url = ec2Relays[0].url;
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
    const csv = document.getElementById('bulkCsv').value;
    const subject = document.getElementById('bulkSubject').value;
    const html = document.getElementById('bulkHtml').value;
    const method = document.getElementById('bulkMethod').value;
    const minDelay = document.getElementById('bulkMinDelay').value;
    const maxDelay = document.getElementById('bulkMaxDelay').value;
    
    if (!csv || !subject || !html) {
        showResult('bulkResult', 'Please fill in all fields', 'error');
        return;
    }
    
    // Get config based on method
    let config = {};
    
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
        if (ec2Relays.length === 0) {
            showResult('bulkResult', 'Please add at least one EC2 relay first', 'error');
            return;
        }
        config.ec2_configs = ec2Relays;
    }
    
    showResult('bulkResult', '🔄 Starting bulk send... This may take a while.', 'info');
    
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
        
        if (data.success) {
            showResult('bulkResult', 
                `✅ Bulk send complete!<br>
                Total: ${data.results.total}<br>
                Sent: ${data.results.sent}<br>
                Failed: ${data.results.failed}<br>
                Skipped: ${data.results.skipped.length}`, 
                'success'
            );
        } else {
            showResult('bulkResult', `❌ ${data.error}`, 'error');
        }
    } catch (error) {
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
