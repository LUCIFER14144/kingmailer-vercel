# EC2 Relay Email Delivery Troubleshooting

## 🚨 CRITICAL: AWS Port 25 Restrictions

### The Problem
**AWS blocks port 25 (SMTP) outbound by default on all EC2 instances to prevent spam.**

This means:
- ✅ Your relay server accepts emails (shows "sent")
- ✅ Postfix queues the emails
- ❌ AWS blocks delivery on port 25
- ❌ Emails never reach recipients

### How to Check If You're Affected

1. **Check Health Status:**
   - Click "Check EC2 Relay Health" in your dashboard
   - Look for: `Port 25 Outbound: blocked`
   - Look for: `⚠️ X emails stuck in queue`

2. **SSH to Your Instance:**
   ```bash
   # Check mail queue
   mailq
   
   # If you see queued emails, port 25 is blocked
   # If queue is empty but emails aren't arriving, check spam
   ```

---

## ✅ Solution 1: Request AWS to Unblock Port 25 (RECOMMENDED)

### Step 1: Submit AWS Request Form
1. Go to: https://aws.amazon.com/forms/ec2-email-limit-rdns-request
2. Fill out the form:
   - **Use Case:** Transactional email sending
   - **Elastic IP:** Your EC2 instance IP
   - **Reverse DNS:** `ec2-XX-XX-XX-XX.compute-1.amazonaws.com` (your instance hostname)
   - **Describe use case:** "Sending transactional emails via KINGMAILER platform"

### Step 2: Wait for Approval
- Typical approval time: 24-48 hours
- AWS will send confirmation email when approved

### Step 3: Test After Approval
```bash
# SSH to instance
ssh -i your-key.pem ec2-user@YOUR_IP

# Send test email
echo "Test" | mail -s "Test Email" your@email.com

# Check logs
sudo tail -f /var/log/maillog
```

---

## ✅ Solution 2: Use Amazon SES as SMTP Relay

If you can't wait for port 25 approval, configure Postfix to use Amazon SES:

### Step 1: Configure SES
1. Go to AWS SES Console: https://console.aws.amazon.com/ses/
2. Verify your sending domain or email
3. Create SMTP credentials
4. Note down: SMTP endpoint, username, password

### Step 2: Configure Postfix to Use SES (SSH Required)
```bash
# SSH to your EC2 instance
ssh -i your-key.pem ec2-user@YOUR_EC2_IP

# Install SASL authentication
sudo yum install -y cyrus-sasl-plain

# Create password file
sudo bash -c 'cat > /etc/postfix/sasl_passwd << EOF
[email-smtp.us-east-1.amazonaws.com]:587 YOUR_SMTP_USERNAME:YOUR_SMTP_PASSWORD
EOF'

# Secure the file
sudo postmap /etc/postfix/sasl_passwd
sudo chmod 600 /etc/postfix/sasl_passwd*

# Update Postfix config
sudo bash -c 'cat >> /etc/postfix/main.cf << EOF

# Amazon SES SMTP Relay
relayhost = [email-smtp.us-east-1.amazonaws.com]:587
smtp_sasl_auth_enable = yes
smtp_sasl_security_options = noanonymous
smtp_sasl_password_maps = hash:/etc/postfix/sasl_passwd
smtp_use_tls = yes
smtp_tls_security_level = encrypt
smtp_tls_note_starttls_offer = yes
EOF'

# Restart Postfix
sudo systemctl restart postfix

# Test
echo "Test via SES" | mail -s "Test Email" your@email.com
sudo tail -f /var/log/maillog
```

**Replace:**
- `email-smtp.us-east-1.amazonaws.com` with your SES region endpoint
- `YOUR_SMTP_USERNAME` with SES SMTP username
- `YOUR_SMTP_PASSWORD` with SES SMTP password

---

## 🔍 Diagnostic Commands

### Check Postfix Status
```bash
sudo systemctl status postfix
sudo systemctl status email-relay
```

### Check Mail Queue
```bash
mailq                    # Show queued emails
sudo postqueue -p        # Detailed queue
sudo postqueue -f        # Flush queue (force retry)
```

### Check Logs
```bash
sudo tail -f /var/log/maillog          # Postfix logs
sudo tail -f /var/log/email_relay.log  # Relay server logs
sudo tail -f /var/log/user-data.log    # Initial setup logs
```

### Test Port 25 Connectivity
```bash
# Test outbound port 25
telnet gmail-smtp-in.l.google.com 25

# If it hangs or times out = AWS is blocking port 25
# If you get a response = Port 25 is open
```

### Check Network
```bash
netstat -tlnp | grep 8080    # Relay server listening
netstat -tlnp | grep 25      # Postfix listening
```

---

## 📊 Understanding the Health Check

### Healthy Instance
```
✅ i-xxxxx (34.239.246.186)
Status: healthy
✓ Relay endpoint ready: http://34.239.246.186:8080/relay
✓ Postfix: Running
✓ Port 25 Outbound: open
✓ Mail Queue: Empty ✓
```

### Instance with AWS Port 25 Block
```
✅ i-xxxxx (34.239.246.186)
Status: healthy_with_warnings
✓ Relay endpoint ready: http://34.239.246.186:8080/relay
✓ Postfix: Running
✓ Port 25 Outbound: blocked
✓ Mail Queue: 15 emails queued ⚠️

⚠️ AWS is blocking port 25 outbound - emails will NOT be delivered!
➡️ Request removal: https://aws.amazon.com/forms/ec2-email-limit-rdns-request
```

---

## 🎯 Quick Fix Checklist

- [ ] Security group has port 8080 open inbound
- [ ] Health check shows "healthy"
- [ ] Port 25 outbound status = "open" (not "blocked")
- [ ] Mail queue is empty
- [ ] Test email sent and received successfully
- [ ] Check spam folder if not received
- [ ] Verify reverse DNS is set properly
- [ ] Consider SPF/DKIM records for better deliverability

---

## 🆘 Still Not Working?

1. **Check AWS Account:**
   - New AWS accounts often have stricter email restrictions
   - Trial/free tier accounts may have additional limits

2. **Check Recipient Email:**
   - Gmail/Outlook may mark EC2 emails as spam initially
   - Check spam/junk folders
   - Whitelist your EC2 IP

3. **Improve Email Reputation:**
   - Set up SPF record: `v=spf1 ip4:YOUR_EC2_IP ~all`
   - Configure DKIM signing
   - Set proper reverse DNS (PTR record)
   - Warm up IP by sending small volumes first

4. **Contact Support:**
   - AWS Support for port 25 issues
   - Check `/var/log/maillog` for specific error codes
   - Share error codes for troubleshooting

---

## 📚 Additional Resources

- AWS Port 25 Request Form: https://aws.amazon.com/forms/ec2-email-limit-rdns-request
- Amazon SES Setup: https://docs.aws.amazon.com/ses/latest/dg/send-email-smtp.html
- Postfix Configuration: http://www.postfix.org/documentation.html
- Email Deliverability Best Practices: https://aws.amazon.com/ses/email-deliverability-best-practices/
