# KINGMAILER v4.0 - Vercel Edition

**Full-featured email marketing platform with SMTP support on Vercel!**

## ✨ Features

- ✅ **Gmail SMTP** - Works perfectly on Vercel Serverless Functions
- ✅ **AWS SES** - Professional email sending
- ✅ **EC2 Relay** - Route through your own server
- ✅ **Bulk Sending** - CSV upload with template replacement
- ✅ **Multi-Account** - Add unlimited SMTP accounts
- ✅ **Smart Rotation** - Automatic account rotation & failover
- ✅ **Template Tags** - Personalize emails with {{name}}, {{email}}, etc.

## 🚀 Deploy to Vercel

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/LUCIFER14144/kingmailer-vercel)

### Manual Deployment:

```bash
# Install Vercel CLI
npm i -g vercel

# Deploy
vercel
```

## ⚙️ Configuration

### Gmail SMTP Setup:

1. Enable 2FA on your Gmail account
2. Generate App Password: https://myaccount.google.com/apppasswords
3. Add credentials in SMTP Config tab

### AWS SES Setup:

1. Get AWS Access Keys from IAM Console
2. Verify your sender email in SES
3. Add credentials in AWS SES tab

### EC2 Relay Setup:

1. Deploy relay server on your EC2 instance
2. Configure security group (allow port 2525)
3. Add endpoint URL in dashboard

## 📁 Project Structure

```
kingmailer-vercel/
├── api/                    # Serverless Functions
│   ├── send.py             # Single email sending
│   ├── send_bulk.py        # Bulk CSV sending
│   ├── test_smtp.py        # SMTP connection testing
│   └── accounts.py         # Account management
├── public/                 # Frontend
│   ├── index.html          # Dashboard
│   ├── app.js              # JavaScript
│   └── style.css           # Styling
├── vercel.json             # Vercel configuration
└── requirements.txt        # Python dependencies
```

## 🔧 Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally with Vercel CLI
vercel dev
```

## 🌐 Why Vercel?

**SMTP ports work perfectly!** Unlike Railway/Render, Vercel Serverless Functions run on AWS Lambda with full network access including SMTP ports 587/465/25.

## 📝 License

MIT License - Free for personal and commercial use

---

**Created by LUCIFER14144** | [GitHub](https://github.com/LUCIFER14144)
