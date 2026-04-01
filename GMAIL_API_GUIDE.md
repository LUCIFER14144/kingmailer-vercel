# Gmail API Integration Guide

## Overview

This feature adds **Gmail API** support as an alternative to SMTP, allowing you to send emails even when SMTP ports (465, 587) are blocked. It includes both direct Gmail API sending and EC2 relay support for IP reputation benefits.

## Why Gmail API?

✅ **No Port Blocking** - Works over HTTPS (port 443), never blocked  
✅ **Higher Limits** - 2000 emails/day vs 500 for SMTP (with proper warmup)  
✅ **Better Authentication** - OAuth2 tokens instead of app passwords  
✅ **EC2 IP Support** - Can route through EC2 relay for clean IP reputation  

## Setup Steps

### 1. Get Google Cloud OAuth2 Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Create a new project or select existing
3. Enable **Gmail API**:
   - Navigate to "APIs & Services" > "Library"
   - Search for "Gmail API"
   - Click "Enable"
4. Create OAuth 2.0 credentials:
   - Go to "Credentials" > "Create Credentials" > "OAuth client ID"
   - Application type: **Desktop app**
   - Name it (e.g., "KingMailer Gmail API")
   - Download the JSON file

### 2. Get Access & Refresh Tokens

**Method A: Using OAuth2 Playground (Easiest)**

1. Go to [OAuth2 Playground](https://developers.google.com/oauthplayground)
2. Click the gear icon (⚙️) in top-right
3. Check "Use your own OAuth credentials"
4. Enter your Client ID and Client Secret
5. In Step 1, find "Gmail API v1" and select:
   - `https://www.googleapis.com/auth/gmail.send`
6. Click "Authorize APIs"
7. Sign in with your Gmail account
8. In Step 2, click "Exchange authorization code for tokens"
9. Copy the **access_token** and **refresh_token**

**Method B: Using gcloud CLI**

```bash
gcloud auth application-default login --scopes=https://www.googleapis.com/auth/gmail.send
```

Then get tokens from `~/.config/gcloud/application_default_credentials.json`

### 3. Add Gmail API Account in KingMailer

1. Open KingMailer web interface
2. Click **"Gmail API"** tab
3. Fill in the form:
   - **Email**: Your Gmail address (e.g., youremail@gmail.com)
   - **Access Token**: From OAuth2 playground (starts with `ya29.`)
   - **Refresh Token**: From OAuth2 playground (starts with `1//`)
   - **Client ID**: From credentials JSON (ends with `.apps.googleusercontent.com`)
   - **Client Secret**: From credentials JSON
   - **Sender Name**: Display name for emails (optional)
4. Click **"Test Connection"** to verify
5. If successful, click **"Add Gmail API Account"**

### 4. Send Emails

**Single Email:**
1. Go to "Single Email" section
2. Select method: **"Gmail API (OAuth2)"** or **"EC2 Relay + Gmail API"**
3. Fill in recipient, subject, body
4. Click "Send Single Email"

**Bulk Email:**
1. Go to "Bulk Email" section
2. Select method: **"Gmail API (OAuth2)"** or **"EC2 Relay + Gmail API"**
3. Upload CSV or paste email list
4. Configure subject, body, delays
5. Click "Start Bulk Send"

## Testing Before Deployment

Before deploying to production, test the integration:

```bash
cd "c:\Users\Eliza\Desktop\online blaster - Copy\kingmailer-vercel"

# Edit test_gmail_api.py with your credentials
notepad test_gmail_api.py

# Run the test
python test_gmail_api.py
```

Expected output:
```
✅ Direct Gmail API: PASS
✅ EC2 + Gmail API: PASS (if EC2 configured)
🎉 Gmail API integration is working!
```

## Token Refresh

Access tokens expire after 1 hour. KingMailer automatically:
- Detects HTTP 401 errors
- Returns `needs_refresh: true` flag
- Frontend prompts you to refresh token

**To refresh manually:**
1. Go back to OAuth2 Playground
2. Click "Refresh access token" button
3. Copy new access_token
4. Update in KingMailer Gmail API settings

**For production:** Consider implementing automatic token refresh using the refresh_token (requires backend token storage).

## Send Methods

### 1. Gmail API (Direct)
- Sends directly from Gmail via HTTPS
- Uses your Gmail account reputation
- Good for personal/verified accounts
- No EC2 required

### 2. EC2 Relay + Gmail API
- Routes Gmail API request through EC2 instance
- Email appears to come from **EC2's clean IP**
- Best deliverability for bulk sending
- Requires running EC2 instance

## Account Rotation

For bulk sending with multiple Gmail accounts:
1. Add multiple Gmail API accounts
2. KingMailer automatically rotates every 50 emails (configurable via batch size)
3. Rotation log shows: `🔄 Gmail API rotated → email@gmail.com (account 2/5)`

## Limits & Best Practices

| Account Type | Daily Limit | Recommended Warmup |
|--------------|-------------|-------------------|
| Free Gmail | 500 emails/day | Start with 20-50/day |
| Google Workspace | 2000 emails/day | Start with 100-200/day |

**Best Practices:**
- Use **real sender names** (not generic ones)
- Add delays: 2-5 seconds between emails
- Warm up gradually: increase by 20% every 3 days
- Monitor Gmail "Sent" folder for bounces
- Don't send to purchased lists (violates Gmail ToS)
- Use EC2 relay for untrusted recipient lists

## Troubleshooting

### Error: "Access token expired"
**Solution:** Refresh token in OAuth2 Playground, update in UI

### Error: "Invalid credentials"
**Solution:** Double-check Client ID, Client Secret match the downloaded JSON

### Error: "Daily sending quota exceeded"
**Solution:** Wait 24 hours or upgrade to Google Workspace

### Error: "User rate limit exceeded"
**Solution:** Increase delays between emails (use 5-10 seconds)

### Error: "Insufficient permission"
**Solution:** Re-authorize with scope `https://www.googleapis.com/auth/gmail.send`

### Error: "EC2 relay timeout"
**Solution:** Verify EC2 instance is running and relay server is listening on port 3000

## Security Notes

⚠️ **Access tokens expire in 1 hour** - use refresh_token for long-term access  
⚠️ **Store credentials securely** - never commit tokens to Git  
⚠️ **Use different accounts** for testing vs production  
⚠️ **Revoke access** in Google account settings if compromised  

## Architecture

```
┌─────────────┐
│  Frontend   │
│  (Browser)  │
└──────┬──────┘
       │ POST /api/send
       │ { method: 'gmail_api', gmail_config: {...}, ... }
       ▼
┌─────────────────┐
│  Vercel Backend │
│   (send.py)     │
└──────┬──────────┘
       │
       ├───────────────────────────────────┐
       │                                   │
       ▼ Direct Gmail API                  ▼ EC2 Relay
┌──────────────────┐              ┌──────────────────┐
│ Gmail API Server │              │  EC2 Instance    │
│ (Google)         │              │  (Node.js relay) │
└──────────────────┘              └────────┬─────────┘
                                           │
                                           ▼
                                  ┌──────────────────┐
                                  │ Gmail API Server │
                                  │ (via EC2 IP)     │
                                  └──────────────────┘
```

## Deployment

Once testing is successful:

```bash
cd "c:\Users\Eliza\Desktop\online blaster - Copy\kingmailer-vercel"
vercel --prod --yes
```

New production URL: `https://kingmailer-vercel-mds-projects-f21afbac.vercel.app`

## Support

For issues:
1. Check browser console (F12) for JavaScript errors
2. Check Vercel function logs for backend errors
3. Verify OAuth2 credentials are correct
4. Test with a single email before bulk sending

## Related Files

- **Backend**: `api/send.py`, `api/send_bulk.py`
- **Frontend**: `public/index.html`, `public/app.js`
- **Test**: `test_gmail_api.py`
- **Docs**: This file

---

Built with ❤️ for reliable email delivery
