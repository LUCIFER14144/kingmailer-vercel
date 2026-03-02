# 🚨 CRITICAL: DNS SETUP REQUIRED FOR INBOX DELIVERY 🚨

## ⚠️ WITHOUT THESE DNS RECORDS, YOUR EMAILS WILL ALWAYS GO TO SPAM! ⚠️

According to Gmail, Yahoo, and Outlook 2024+ sender requirements, **ALL emails without proper authentication (SPF/DKIM/DMARC) are automatically marked as spam**. The code fixes we've implemented are necessary but **NOT SUFFICIENT** - you MUST configure DNS records at your domain registrar.

---

## 📋 What You Need to Do

### Option 1: Using Gmail SMTP (Easiest - Already Has DKIM!)
If you're sending through Gmail's SMTP server (`smtp.gmail.com`):

✅ **Gmail automatically adds DKIM signatures** - you don't need to set up DKIM!  
✅ **Use your Gmail address as the From address** (e.g., yourname@gmail.com)  
✅ **Gmail's SPF is already set** for gmail.com domain

**You're mostly covered!** But you should still:
1. **Don't send too many emails too fast** - Gmail throttles bulk sending
2. **Start slow** - Send 10-20 emails/day, gradually increase over 2-4 weeks
3. **Avoid spam complaints** - If recipients mark your emails as spam, Gmail will block you

### Option 2: Using Custom Domain (Requires DNS Setup!)
If you're sending from your own domain (e.g., hello@yourdomain.com):

---

## 🔧 Step 1: Set Up SPF Record

**What is SPF?** SPF tells receiving servers which mail servers are allowed to send emails from your domain.

**Go to your domain registrar** (GoDaddy, Namecheap, Cloudflare, etc.) and add a **TXT record**:

```
Host/Name: @   (or leave blank, or "yourdomain.com" depending on your registrar)
Type: TXT
Value: v=spf1 a mx ~all
TTL: 3600 (or default)
```

**If you're also using Gmail/Google Workspace to send:**
```
Value: v=spf1 include:_spf.google.com a mx ~all
```

**If you're using AWS SES:**
```
Value: v=spf1 include:amazonses.com a mx ~all
```

**If you're using multiple services:**
```
Value: v=spf1 include:_spf.google.com include:amazonses.com a mx ~all
```

---

## 🔐 Step 2: Set Up DKIM Record

**What is DKIM?** DKIM cryptographically signs your emails so receiving servers can verify they're really from you.

### For AWS SES:
1. Go to [AWS SES Console](https://console.aws.amazon.com/ses/)
2. Click **Verified identities** → Select your domain
3. Click **DKIM authentication** tab
4. Click **Create DKIM keys**
5. AWS will show you 3 CNAME records - **add all 3 to your DNS**

Example records:
```
Host: abc123._domainkey.yourdomain.com
Type: CNAME
Value: abc123.dkim.amazonses.com
TTL: 3600

(Repeat for all 3 DKIM CNAME records)
```

### For Google Workspace:
1. Go to [Google Admin Console](https://admin.google.com/)
2. Navigate to **Apps** → **Google Workspace** → **Gmail** → **Authenticate email**
3. Click **Generate new record**
4. Copy the TXT record and add it to your DNS:
```
Host: google._domainkey
Type: TXT
Value: (long value provided by Google)
TTL: 3600
```

### For other SMTP providers:
Check with your email provider for DKIM setup instructions. Most providers have a "DKIM Setup" or "Email Authentication" section.

---

## 🛡️ Step 3: Set Up DMARC Record

**What is DMARC?** DMARC tells receiving servers what to do with emails that fail SPF or DKIM checks.

**Add this TXT record to your DNS:**

```
Host: _dmarc
Type: TXT
Value: v=DMARC1; p=quarantine; pct=100; rua=mailto:dmarc@yourdomain.com
TTL: 3600
```

**Change `dmarc@yourdomain.com` to your actual email address** where you want to receive DMARC reports.

**Policy options:**
- `p=none` - Don't reject emails, just send reports (use this to test)
- `p=quarantine` - Send failed emails to spam (recommended for production)
- `p=reject` - Reject failed emails completely (strictest, use after testing)

---

## 🔍 Step 4: Set Up Reverse DNS (PTR Record) - For Custom SMTP Only

**What is PTR?** PTR record (reverse DNS) maps your sending IP address back to your domain name.

**⚠️ You CAN'T do this yourself** - you need to contact your hosting provider or VPS provider:

1. Find your sending server's IP address
2. Contact your hosting provider (AWS, DigitalOcean, Linode, etc.)
3. Request a **PTR record** pointing your IP to `mail.yourdomain.com`

Example:
```
IP: 123.45.67.89
PTR Record: 123.45.67.89 → mail.yourdomain.com
```

**Gmail/Outlook requirement:** The PTR record hostname MUST have an A record pointing back to the same IP.

---

## ✅ Step 5: Verify Your Setup

### Check DNS Propagation (wait 24-48 hours after adding records):
- [MXToolbox](https://mxtoolbox.com/SuperTool.aspx) - Check SPF, DKIM, DMARC
- [Google Admin Toolbox](https://toolbox.googleapps.com/apps/checkmx/) - Verify all records

### Send Test Email:
1. Send an email to [check-auth@verifier.port25.com](mailto:check-auth@verifier.port25.com)
2. You'll receive an automated reply showing your authentication status
3. **All checks should be GREEN** (SPF: PASS, DKIM: PASS, DMARC: PASS)

### Check Spam Score:
Send a test email to [mail-tester.com](https://www.mail-tester.com/) - aim for **9/10 or higher**

---

## 📊 Step 6: Warm Up Your Domain (VERY IMPORTANT!)

Even with perfect DNS setup, if you suddenly send 1000 emails from a new domain/IP, **they will go to spam**. You MUST warm up your sender reputation:

**Week 1:** Send 10-20 emails/day to engaged recipients (people who will open/reply)  
**Week 2:** Send 50-100 emails/day  
**Week 3:** Send 200-300 emails/day  
**Week 4:** Send 500-1000 emails/day  
**Week 5+:** Gradually increase to your target volume

**Tips:**
- Send to people who know you first (they'll open/reply)
- Avoid sudden volume spikes
- Monitor bounce rate (keep below 5%)
- Monitor spam complaint rate (keep below 0.1%)

---

## 🚫 Common Mistakes That WILL Cause Spam

1. **Sending from domain A using SMTP server B** - SPF will fail!
   - ❌ BAD: From: hello@mydomain.com via smtp.randomserver.com
   - ✅ GOOD: From: hello@mydomain.com via mail.mydomain.com (with SPF record)

2. **No DKIM signing** - 80% of emails without DKIM go to spam

3. **No warm-up period** - Sending 1000 emails immediately from a new domain

4. **Using someone else's SMTP without permission** - You'll get blacklisted

5. **Shared IP with bad reputation** - Check your IP on [MXToolbox Blacklist Check](https://mxtoolbox.com/blacklists.aspx)

---

## 📞 Need Help?

**If you're using Gmail SMTP:**
- Just make sure you're using your Gmail address as From address
- Enable 2FA and create an [App Password](https://myaccount.google.com/apppasswords)
- Stay within [Gmail sending limits](https://support.google.com/a/answer/166852)

**If you're using AWS SES:**
- [AWS SES DKIM Setup Guide](https://docs.aws.amazon.com/ses/latest/dg/send-email-authentication-dkim.html)
- [AWS SES Reputation Dashboard](https://console.aws.amazon.com/ses/) - Monitor bounce/complaint rates

**If you're using a custom SMTP server:**
- Contact your hosting provider for PTR record setup
- Use [DKIM Core](https://dkimcore.org/tools/) to generate DKIM keys
- Test everything with [MXToolbox](https://mxtoolbox.com/)

**Still going to spam?**
1. Check [Google Postmaster Tools](https://postmaster.google.com/) - See your domain reputation
2. Check [Microsoft SNDS](https://sendersupport.olc.protection.outlook.com/snds/) - See your IP reputation
3. Verify your IP isn't blacklisted: [MXToolbox Blacklist Check](https://mxtoolbox.com/blacklists.aspx)
4. Send test to [mail-tester.com](https://www.mail-tester.com/) and fix all issues shown

---

## 🎯 Summary Checklist

Before sending bulk emails, verify:

- [ ] SPF record is published (TXT record at @)
- [ ] DKIM is enabled (3 CNAME records for SES, or TXT for Google)
- [ ] DMARC record is published (TXT record at _dmarc)
- [ ] PTR record is set (if using custom SMTP server)
- [ ] Test email passes all checks at check-auth@verifier.port25.com
- [ ] Mail-tester.com score is 9/10 or higher
- [ ] IP is not blacklisted (check MXToolbox)
- [ ] Starting with low volume (10-20 emails/day) to warm up

**THIS IS NOT OPTIONAL - WITHOUT THESE DNS RECORDS, NO CODE FIX WILL WORK!**
