# 🚀 KINGMAILER v4.0 - Vercel Deployment Guide

## Quick Deploy

### Option 1: Deploy with Vercel CLI (Recommended)

```bash
# Install Vercel CLI globally
npm install -g vercel

# Navigate to project directory
cd kingmailer-vercel

# Login to Vercel
vercel login

# Deploy (it will ask a few questions)
vercel

# For production deployment
vercel --prod
```

### Option 2: Deploy via GitHub

1. **Push to GitHub:**
```bash
git init
git add .
git commit -m "Initial commit - KINGMAILER v4.0"
git remote add origin https://github.com/YOUR_USERNAME/kingmailer-vercel.git
git push -u origin main
```

2. **Import to Vercel:**
   - Go to https://vercel.com/new
   - Import your GitHub repository
   - Click "Deploy"

3. **Done!** Your app will be live at `https://your-project.vercel.app`

## Configuration

### Environment Variables (Optional)

If you want to set default SMTP credentials, add these in Vercel Dashboard:

- `GMAIL_USER` - Your Gmail address
- `GMAIL_APP_PASSWORD` - Gmail App Password

## Post-Deployment

### 1. Test SMTP on Vercel

After deployment, visit your dashboard and:

1. Go to "SMTP Config" tab
2. Add your Gmail credentials
3. Click "Test Connection"
4. You should see ✅ Success!

### 2. Verify SMTP Ports Work

Run this test to confirm SMTP ports are accessible:

```bash
curl -X POST https://your-project.vercel.app/api/test_smtp \
  -H "Content-Type: application/json" \
  -d '{
    "type": "smtp",
    "smtp_config": {
      "provider": "gmail",
      "user": "your.email@gmail.com",
      "pass": "your-app-password"
    }
  }'
```

Expected response:
```json
{
  "success": true,
  "message": "✓ SMTP connection successful to smtp.gmail.com:587"
}
```

## Gmail App Password Setup

1. Enable 2-Factor Authentication on your Gmail account
2. Go to https://myaccount.google.com/apppasswords
3. Select "Mail" and "Other (Custom name)"
4. Name it "KingMailer"
5. Copy the 16-character password
6. Use this password (NOT your regular Gmail password)

## Troubleshooting

### "Authentication failed" error:
- Make sure you're using an App Password, not your regular Gmail password
- Verify 2FA is enabled on your Gmail account
- Check that you copied the App Password correctly (no spaces)

### "Module not found" error:
- Make sure `requirements.txt` is in the root directory
- Vercel should automatically install dependencies

### Connection timeout:
- This shouldn't happen on Vercel! (Unlike Railway/Render)
- If it does, check your SMTP server address and port

## Custom Domain

To use your own domain:

1. Go to Vercel Dashboard → Your Project → Settings → Domains
2. Add your domain (e.g., `mail.yourdomain.com`)
3. Update DNS records as instructed
4. Wait for DNS propagation (usually 5-10 minutes)

## Scaling

Vercel Serverless Functions have these limits:

- **Free Tier:** 100GB bandwidth, 100 hours function execution
- **Pro Tier:** Unlimited bandwidth, 1000 hours function execution

For high-volume sending (10,000+ emails/day), consider:
- Upgrading to Vercel Pro
- Using AWS SES (supports millions of emails)
- Splitting across multiple SMTP accounts

## Security Best Practices

1. **Never commit credentials** - Use environment variables
2. **Use App Passwords** - Not your main Gmail password
3. **Rotate keys regularly** - Change SMTP passwords monthly
4. **Monitor sending** - Watch for unusual activity
5. **Rate limiting** - Use delays between emails (already implemented)

## Support

Issues? Check:
- [Vercel Documentation](https://vercel.com/docs)
- [GitHub Issues](https://github.com/LUCIFER14144/kingmailer-vercel/issues)

---

**Happy emailing! 👑**
