# EC2 Relay Email Delivery - JetCloudMailer Style

## ✅ NO PORT 25 NEEDED!

**KINGMAILER now works exactly like JetCloudMailer:**
- ✅ Send emails FROM EC2 IP using Gmail/Outlook SMTP
- ✅ Uses authenticated SMTP on ports 587/465
- ✅ NO port 25 request needed from AWS
- ✅ Works immediately after instance creation
- ✅ Better deliverability (EC2 IP + Gmail reputation)

---

## 🚀 How It Works (JetCloudMailer Approach)

### Traditional EC2 (OLD - Required Port 25)
```
Your App → EC2 Postfix → Port 25 → Recipient
❌ AWS blocks port 25 by default
❌ Requires AWS request form
❌ Wait 24-48 hours for approval
```

### JetMailer Style (NEW - NO Port 25!)
```
Your App → EC2 Relay → Gmail SMTP (Port 587) → Recipient
✅ No port 25 needed
✅ Works instantly
✅ Uses your existing Gmail/Outlook accounts
✅ Email shows EC2 IP in headers
```

---

## 📋 Requirements

### 1. EC2 Instance (Any Region)
- Created via KINGMAILER dashboard
- Security group with port 8080 open
- Takes ~10-15 min to initialize

### 2. SMTP Accounts (REQUIRED)
- Add Gmail/Outlook/any SMTP in "SMTP Config" tab
- EC2 relay uses these accounts to authenticate
- Your emails will show EC2 IP while using Gmail's infrastructure

---

## 🎯 Setup Guide

### Step 1: Add SMTP Accounts
1. Go to **"SMTP Config"** tab
2. Add your Gmail/Outlook accounts
3. Use App Passwords (not regular password)
4. Test connection to verify

### Step 2: Create EC2 Instance
1. Go to **"EC2 Management"** tab
2. Enter AWS credentials
3. Click **"Create New Instance"**
4. Wait 10-15 minutes for setup

### Step 3: Check Health
1. Click **"Check EC2 Relay Health"**
2. Should show:
   - ✅ Port 587 Outbound: open
   - ✅ Port 465 Outbound: open
   - ✅ Method: Authenticated SMTP via EC2 IP

### Step 4: Send Emails
1. Go to **"Bulk Send"** tab
2. Select **"EC2 Relay"** as method
3. Upload CSV with email addresses
4. Emails will be sent FROM EC2 IP using your SMTP accounts!

---

## 🔍 Health Check Explained

### Healthy Instance (JetMailer Style)
```
✅ i-xxxxx (34.239.246.186)
Status: healthy
✓ Relay endpoint ready: http://34.239.246.186:8080/relay
✓ Method: Authenticated SMTP via EC2 IP
✓ Port 587 Outbound: open
✓ Port 465 Outbound: open
💡 JetMailer Style - No port 25 needed
```

### What This Means:
- EC2 relay server is running ✅
- Can connect to Gmail/Outlook SMTP servers ✅
- Ready to send emails immediately ✅
- No AWS port 25 request needed ✅

---

## 🆘 Troubleshooting

### Error: "EC2 relay requires SMTP config"
**Solution:** Add SMTP accounts in "SMTP Config" tab first.

### Error: "Cannot reach relay server"
**Solutions:**
1. Wait 10-15 min after instance creation
2. Check security group allows port 8080
3. Click "Refresh List" to update instance data
4. SSH and check: `sudo systemctl status email-relay`

### Error: "Port 587/465 blocked"
**Solutions:**
1. Check AWS security group allows outbound 587/465
2. Usually not blocked by AWS (unlike port 25)
3. Test: `telnet smtp.gmail.com 587`

### Emails Sent But Not Received
**Check:**
1. SMTP account credentials correct
2. Gmail/Outlook account not locked
3. Check spam folder (first time from new IP)
4. Verify recipient email address valid
5. Check EC2 relay logs: `sudo tail -f /var/log/email_relay.log`

---

## 📊 Advantages vs Traditional EC2

| Feature | Traditional EC2 | JetMailer Style |
|---------|----------------|-----------------|
| Port 25 Required | ✅ YES | ❌ NO |
| AWS Request Form | ✅ YES (wait 24-48h) | ❌ NO |
| Works Immediately | ❌ NO | ✅ YES |
| SMTP Accounts Needed | ❌ NO | ✅ YES |
| Email in EC2 IP | ✅ YES | ✅ YES |
| Deliverability | 🟡 Medium | 🟢 Better |
| Setup Complexity | 🔴 Hard | 🟢 Easy |

---

## 🔧 SSH Diagnostic Commands

```bash
# Check relay service status
sudo systemctl status email-relay

# View relay server logs
sudo tail -f /var/log/email_relay.log

# Check if relay server is listening on port 8080
sudo netstat -tlnp | grep 8080

# Test port 587 connectivity
telnet smtp.gmail.com 587

# Test port 465 connectivity
telnet smtp.gmail.com 465

# View instance setup logs
sudo tail -f /var/log/user-data.log

# Restart relay service
sudo systemctl restart email-relay
```

---

## 💡 Pro Tips

1. **Use App Passwords** - Gmail/Outlook require app-specific passwords
2. **Warm Up IPs** - Start with small volumes, increase gradually  
3. **Rotate IPs** - Create multiple EC2 instances for IP rotation
4. **Monitor Logs** - Check `/var/log/email_relay.log` for issues
5. **Test First** - Send test emails before bulk campaigns
6. **Check Spam** - First emails from new IP may land in spam

---

## 📚 Additional Resources

- Gmail App Passwords: https://myaccount.google.com/apppasswords
- Outlook App Passwords: https://account.live.com/proofs/AppPassword
- AWS EC2 Security Groups: https://docs.aws.amazon.com/vpc/latest/userguide/VPC_SecurityGroups.html
- Email Deliverability Best Practices: https://aws.amazon.com/ses/email-deliverability-best-practices/
