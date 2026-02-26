# 🚀 KINGMAILER v4.0 - Quick Start Guide

## What You Got

**A complete email marketing platform with THESE working features:**

✅ **Gmail SMTP** - Works perfectly on Vercel (unlike Railway/Render!)  
✅ **AWS SES** - Professional email delivery  
✅ **EC2 Relay** - Use your own server  
✅ **Bulk Sending** - CSV upload with {{template}} tags  
✅ **Multi-Account Rotation** - Automatic switching between accounts  
✅ **Smart Delays** - Anti-spam protection built-in  
✅ **Beautiful Dashboard** - Modern, responsive UI  

## 📁 Project Structure

```
kingmailer-vercel/
├── api/                        # Backend API (Vercel Serverless Functions)
│   ├── send.py                 # Single email sending
│   ├── send_bulk.py            # Bulk CSV sending
│   ├── test_smtp.py            # Test SMTP/SES/EC2 connections
│   └── accounts.py             # Account management
├── public/                     # Frontend
│   ├── index.html              # Main dashboard
│   ├── app.js                  # JavaScript logic
│   └── style.css               # Styling
├── vercel.json                 # Vercel configuration
├── requirements.txt            # Python dependencies
├── package.json                # NPM configuration
├── DEPLOYMENT.md               # Deployment guide
└── README.md                   # Project info
```

## 🎯 Deploy Now (2 Minutes)

### Step 1: Install Vercel CLI
```bash
npm install -g vercel
```

### Step 2: Deploy
```bash
cd kingmailer-vercel
vercel login
vercel --prod
```

### Step 3: Visit Your Live Site!
Vercel will give you a URL like: `https://kingmailer-xxx.vercel.app`

## 🔧 Local Testing

Want to test locally first?

```bash
# Install Vercel CLI
npm install -g vercel

# Run local dev server
vercel dev
```

Then open: http://localhost:3000

## 📧 Setup Gmail SMTP

1. **Enable 2FA on Gmail:**
   - Go to Google Account Settings → Security → 2-Step Verification

2. **Generate App Password:**
   - Visit: https://myaccount.google.com/apppasswords
   - Select "Mail" and "Other"
   - Name it "KingMailer"
   - Copy the 16-character password

3. **Add to Dashboard:**
   - Open your deployed app
   - Go to "SMTP Config" tab
   - Provider: Gmail
   - Email: your.email@gmail.com
   - Password: paste the 16-character App Password
   - Click "Test Connection" → Should see ✅ Success!

## 🎓 How It Works

### Single Email:
1. Go to "Single Email" tab
2. Fill in recipient, subject, and HTML body
3. Select "Gmail SMTP"
4. Click "Send Email"

### Bulk Sending:
1. Go to "Bulk Sending" tab
2. Paste CSV data (must have 'email' column)
3. Use {{tags}} in subject/body templates
4. Set delays (2000-5000ms recommended)
5. Click "Start Bulk Sending"

**Example CSV:**
```csv
email,name,company
john@example.com,John Smith,ACME Corp
jane@example.com,Jane Doe,Tech Inc
```

**Example Template:**
```html
<h1>Hi {{name}}!</h1>
<p>Special offer from {{company}}...</p>
```

## 🌐 Why Vercel Works (And Railway Doesn't)

| Platform | SMTP Ports | Why |
|----------|-----------|-----|
| **Vercel** | ✅ Open | Serverless functions run on AWS Lambda with full network access |
| Railway | ❌ Blocked | Container platform blocks SMTP to prevent spam |
| Render Free | ❌ Blocked | Disabled SMTP since late 2023 |
| Heroku | ❌ Blocked | All SMTP ports firewalled |

**Your Titan-Ail-Mailer works because it's also on Vercel!**

## 🔥 Features Comparison

| Feature | KINGMAILER v4.0 | Titan-Ail-Mailer |
|---------|----------------|------------------|
| Gmail SMTP | ✅ | ✅ |
| Custom SMTP | ✅ | ✅ |
| AWS SES | ✅ | ❌ |
| EC2 Relay | ✅ | ❌ |
| Bulk Sending | ✅ | ✅ |
| Multi-Account Rotation | ✅ | ✅ |
| Template Tags | ✅ | ✅ |
| PDF Attachments | ⏳ Coming | ✅ |
| Account Management | ✅ | ✅ |

## 📊 Sending Limits

### Gmail SMTP:
- **Free Gmail:** 500 emails/day per account
- **Google Workspace:** 2000 emails/day per account
- **Tip:** Add multiple accounts for rotation!

### AWS SES:
- **Sandbox:** 200 emails/day
- **Production:** 50,000+ emails/day (request limit increase)
- **Cost:** $0.10 per 1,000 emails

## ⚡ Pro Tips

1. **Multi-Account Rotation:**
   - Add 5 Gmail accounts = 2,500 emails/day
   - Rotation happens automatically in bulk send

2. **Smart Delays:**
   - Use 2000-5000ms delays to avoid spam filters
   - Randomization is built-in

3. **Template Testing:**
   - Test with single email first
   - Then use same template for bulk

4. **AWS SES Setup:**
   - Better deliverability than Gmail
   - Must verify domain/email first
   - Requires moving out of sandbox

## 🐛 Troubleshooting

### "SMTP Authentication Failed"
- Using App Password, not regular Gmail password?
- 2FA enabled on Gmail?
- Check for typos in credentials

### "Connection Timeout"
- Should NOT happen on Vercel!
- Check SMTP server address if using custom

### "Module Not Found"
- Make sure requirements.txt is present
- Redeploy: `vercel --prod --force`

## 🎁 What's Different from Railway Version?

**Old (Railway):**
- ❌ SMTP ports blocked
- ✅ Gmail API workaround (complex OAuth)
- ❌ Required Google Cloud Console setup
- ❌ Token management headaches

**New (Vercel):**
- ✅ Direct SMTP works perfectly
- ✅ No OAuth needed
- ✅ Simple username/password
- ✅ Works exactly like your local machine

## 📚 Next Steps

1. **Deploy to Vercel** (see DEPLOYMENT.md)
2. **Add Gmail accounts** (see guide above)
3. **Test single email**
4. **Run bulk campaign**
5. **Monitor results**

## 🤝 Support

Need help?
- Check DEPLOYMENT.md for deployment issues
- Test SMTP with "Test Connection" button
- Use delays to avoid Gmail rate limits

---

**Made with 👑 by LUCIFER14144**

**Now go send some emails! 🚀**
