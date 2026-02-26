# KINGMAILER v4.0 - Troubleshooting Guide

## Common Issues & Solutions

### 1. Gmail SMTP Shows EC2/AWS IP in Email Headers

**Problem:** When using "Gmail SMTP" method, emails show EC2 or AWS IP addresses in headers instead of Gmail's IP.

**Diagnosis:**
- Open browser console (F12) and look for debug logs:
  ```
  ======= BULK SEND DEBUG =======
  Selected method: smtp
  Method will send from: Gmail IP
  ```
- Check backend logs in Vercel deployment for:
  ```
  [SMTP SERVER] smtp.gmail.com:587
  [EXPECTED IP] Gmail servers (NOT EC2, NOT Vercel)
  ```

**Possible Causes:**
1. **Wrong method selected**: You may have accidentally selected "EC2 Relay" instead of "Gmail SMTP"
2. **Vercel infrastructure**: Vercel serverless functions run on AWS, but this should NOT affect Gmail SMTP sends
3. **Email headers misread**: Check for "Received:" header - Gmail SMTP should show:
   ```
   Received: from mail-<xxx>-gmail.google.com
   ```
   NOT:
   ```
   Received: from ec2-xxx.compute-1.amazonaws.com
   ```

**Solution:**
1. Verify dropdown selection shows: **"Gmail SMTP (Gmail IP - With Account Rotation)"**
2. Clear browser cache and reload
3. Check console logs to confirm method is "smtp"
4. Send a test email and inspect FULL headers (in Gmail: Show Original)

---

### 2. EC2 Relay Method Fails

**Problem:** Selected "EC2 Relay" but getting errors.

**Common Error Messages:**

#### "No running EC2 instances available"
**Cause:** Instances are still initializing (in "pending" state)

**Solution:**
- EC2 instances take 2-3 minutes to fully start
- Dashboard now shows instance state with color:
  - 🟢 **RUNNING** = Ready to use
  - 🟠 **PENDING** = Still initializing (auto-refreshes every 30s)
- Wait for state to change to "RUNNING" before sending
- Manual refresh: Click "Refresh Instances" button in EC2 tab

#### "Verify security group allows port 8080"
**Cause:** Port 8080 is not open in AWS security group

**Solution:**
- Port 8080 is REQUIRED for EC2 relay HTTP API (NOT your application port)
- Port 3000 or any other port is IRRELEVANT to email relay
- Security group should allow:
  - Port 8080 (relay HTTP API) ✅ REQUIRED
  - Port 587 (SMTP with STARTTLS) ✅ REQUIRED
  - Port 465 (SMTPS SSL) ✅ REQUIRED  
  - Port 22 (SSH for management) ✅ REQUIRED
  - Port 25 (NOT used in JetMailer style)
  - Port 3000 (NOT needed for email relay)

**Check Security Group:**
```bash
# In AWS Console > EC2 > Security Groups > kingmailer-sg-xxx
Inbound Rules:
- SSH (22) from 0.0.0.0/0
- Custom TCP (587) from 0.0.0.0/0
- Custom TCP (465) from 0.0.0.0/0
- Custom TCP (8080) from 0.0.0.0/0
```

#### "EC2 relay requires SMTP accounts (like JetMailer)"
**Cause:** EC2 relay uses JetMailer-style architecture - it authenticates with Gmail/Outlook and routes through EC2 IP

**Solution:**
1. Add at least one Gmail SMTP account in "SMTP Config" tab
2. EC2 relay will use these credentials but send from EC2 IP
3. This is how JetMailer works - authenticated SMTP through EC2 IP

---

### 3. Port Confusion: 3000 vs 8080

**Your ports:**
- **Port 3000**: Your local/testing port (IGNORE for production email relay)
- **Port 8080**: EC2 relay server HTTP API (REQUIRED for EC2 relay method)
- **Port 587/465**: Gmail/Outlook SMTP ports (REQUIRED for authenticated SMTP)

**What each port does:**
- **8080**: JetMailer-style relay server on EC2 accepts HTTP POST requests with email data
- **587**: Gmail SMTP with STARTTLS (direct or via EC2 relay)
- **465**: Gmail SMTPS with SSL (alternative to 587)

**Important:** Your application runs on Vercel (serverless), NOT on EC2. The EC2 instance is ONLY for email relay.

---

### 4. AWS Credentials Not Saving

**Problem:** AWS credentials seem lost after page reload.

**Check:**
1. Open browser console and check localStorage:
   ```javascript
   localStorage.getItem('aws_credentials')
   ```
2. Should show JSON with access_key, secret_key, region, etc.

**Troubleshooting:**
- Private/Incognito mode may block localStorage
- Browser extensions might clear storage
- Check for success message: "✅ AWS credentials saved successfully!"

**Solution:**
- Use regular browser window (not incognito)
- Disable conflicting extensions
- After saving, refresh EC2 tab to load instances

---

### 5. EC2 Instances Created But Not Used

**Problem:** Dashboard shows EC2 instances with IP, but emails don't use them.

**Diagnosis Steps:**
1. Check instance state - must be "RUNNING" (not "pending")
2. Verify method selected is "EC2 Relay" (not "Gmail SMTP")
3. Open console and check:
   ```
   Available EC2 instances: 1
   EC2 instances - Running: 1, Pending: 0
   ```

**Common Mistake:**
- Selecting "Gmail SMTP" method but expecting EC2 IP to be used
- "Gmail SMTP" = Gmail servers (Gmail IP)
- "EC2 Relay" = Your EC2 server (EC2 IP)

---

### 6. Health Check Failures

**Problem:** EC2 instances created but health check fails.

**Wait Time:**
- EC2 instance creation: ~1 minute
- Relay server startup: ~2-3 minutes
- Total ready time: ~3-5 minutes

**Check Health:**
1. Go to EC2 tab
2. Instance shows "RUNNING" state
3. Wait 3-5 minutes after creation
4. Try sending test email

**Manual Health Check:**
```bash
# SSH into EC2 instance
ssh -i your-key.pem ec2-user@<PUBLIC_IP>

# Check relay server status
sudo systemctl status email-relay

# Check logs
sudo journalctl -u email-relay -f

# Test health endpoint
curl http://localhost:8080/health
```

---

## How to Read Email Headers

**Gmail SMTP Method:**
```
Received: from mail-sor-f41.google.com ([64.233.174.41])
```
✅ Good - Gmail IP

**EC2 Relay Method:**
```
Received: from ec2-98-80-186-32.compute-1.amazonaws.com ([98.80.186.32])
```
✅ Good - Your EC2 IP

**Unexpected (Problem):**
```
Received: from 169.254.0.145 (ec2-98-80-186-32...)
```
❌ Bad - Internal AWS IP (shouldn't happen with correct method)

**How to Check Headers in Gmail:**
1. Open email
2. Click three dots (...)
3. Click "Show Original"
4. Look for first "Received:" line (bottom to top)

---

## Debug Mode

All fixes include extensive debug logging. To see what's happening:

### Frontend (Browser Console F12):
```
======= BULK SEND DEBUG =======
Selected method: smtp
Available EC2 instances: 1
Available SMTP accounts: 2
Method will send from: Gmail IP
==============================
```

### Backend (Vercel Logs):
```
==================================================
BULK SEND DEBUG - Backend
Method selected: smtp
SMTP configs received: 2
EC2 instances received: 0
==================================================

[EMAIL 1] Method: SMTP → test@example.com
[SMTP SEND] → test@example.com
[SMTP SERVER] smtp.gmail.com:587
[EXPECTED IP] Gmail servers (NOT EC2, NOT Vercel)
[SMTP SUCCESS] Email sent to test@example.com via smtp.gmail.com
```

---

## Still Stuck?

If you're still having issues after trying these solutions:

1. **Clear all data and start fresh:**
   - Clear localStorage: `localStorage.clear()`
   - Reload page
   - Re-add AWS credentials
   - Re-add SMTP accounts
   - Refresh EC2 instances

2. **Provide these details:**
   - Console logs (browser F12 and Vercel deployment logs)
   - Email headers (Show Original in Gmail)
   - Screenshots of:
     - Send method dropdown selection
     - EC2 instances list with states
     - SMTP accounts configured
     - Error messages

3. **Test in isolation:**
   - Test Gmail SMTP with ONE account and ONE recipient
   - Test EC2 relay after confirming instance state is "RUNNING"
   - Check Vercel function logs for detailed debugging output

---

## Contact & Support

- Platform: https://kingmailer-vercel.vercel.app
- Version: KINGMAILER v4.0 (JetMailer Style)
- Architecture: Vercel Serverless + AWS EC2 Relay
- Email Methods: SMTP (Direct) | EC2 Relay (JetMailer Style) | AWS SES
