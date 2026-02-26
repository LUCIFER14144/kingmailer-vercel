# KINGMAILER v4.0 - NEW FEATURES ADDED

## 🎉 Major Update - All Missing Features Implemented!

### Deployment URL: https://kingmailer-vercel.vercel.app

---

## 🔐 1. LOGIN SYSTEM (User Requested)

### Features:
- **Login Page**: `/login.html` with beautiful dark theme
- **Session Management**: Uses localStorage for user sessions
- **Quick Access**: Demo mode for testing without authentication
- **Auto-redirect**: Redirects to login if not authenticated

### Default Credentials:
```
Username: admin | Password: admin123
Username: demo  | Password: demo
Username: user  | Password: password
```

### How to Add Users:
Edit `api/login.py` and add to the USERS dictionary:
```python
USERS = {
    'newuser': hashlib.sha256('newpassword'.encode()).hexdigest()
}
```

---

## 🖥️ 2. EC2 RELAY SUPPORT (User Requested - "every email should be sent from ec2 ip")

### Features:
- **Full EC2 Integration**: Send all emails through EC2 relay endpoints
- **Connection Testing**: Test EC2 relay before adding
- **Multiple Relays**: Add and manage multiple EC2 endpoints
- **Auto-rotation**: Bulk sending rotates between EC2 relays
- **Priority Option**: EC2 marked as "Recommended" in send methods

### How It Works:
1. Add EC2 relay endpoint URL (e.g., `http://your-ec2-ip:2525/send`)
2. System routes all emails through your EC2 server
3. Your EC2 server uses its own IP for sending
4. Bypasses all platform restrictions

### API Endpoints:
- `POST /api/ec2_relay` - Add/test EC2 relay
- `GET /api/ec2_relay` - List all relays
- `DELETE /api/ec2_relay` - Remove relay

---

## 🔄 3. SPINTAX PROCESSING

### What is Spintax?
Spintax creates unique variations of text by randomly selecting from options.

### Syntax:
```
{option1|option2|option3}
```

### Examples:
```
Subject: {Hello|Hi|Greetings} {{name}}!
Result: "Hello John!" or "Hi John!" or "Greetings John!"

Body: This is {great|awesome|amazing}!
Result: "This is great!" or "This is awesome!" or "This is amazing!"

Nested: {Hello {there|friend}|Hi}
Result: "Hello there" or "Hello friend" or "Hi"
```

### How to Use:
Just include spintax in your subject or body templates. The system automatically processes it for each email, creating unique content.

---

## 🏷️ 4. ADVANCED TEMPLATE TAGS

### Available Tags:
```
{{random_name}}      → John Smith, Mary Johnson, etc.
{{company}}          → Tech Solutions, Global Industries, etc.
{{company_name}}     → Same as {{company}}
{{13_digit}}         → Unique 13-digit ID (timestamp-based)
{{unique_id}}        → Same as {{13_digit}}
{{date}}             → February 25, 2026
{{time}}             → 03:45 PM
{{year}}             → 2026
{{random_6}}         → 6-char alphanumeric (aB3xY9)
{{random_8}}         → 8-char alphanumeric
{{random_10}}        → 10-char alphanumeric
{{recipient}}        → Recipient's email address
{{email}}            → Recipient's email address

CSV Column Tags:
{{name}}             → From CSV 'name' column
{{company}}          → From CSV 'company' column
{{any_column}}       → Any column name from your CSV
```

### Examples:
```html
<h1>Hi {{name}}!</h1>
<p>Your unique ID is: {{13_digit}}</p>
<p>Sent from {{company_name}} on {{date}}</p>
```

---

## 📋 5. SUBJECT/BODY ROTATION

### Features:
- **Load Multiple Subjects**: Upload or paste multiple subject lines
- **Load Multiple Bodies**: Upload or paste multiple email bodies
- **Auto-rotation**: System rotates through subjects/bodies for each send
- **API Management**: Add/remove subjects/bodies programmatically

### API Endpoints:
```
POST /api/rotation
{
  "type": "subject",
  "items": ["Subject 1", "Subject 2", "Subject 3"]
}

POST /api/rotation
{
  "type": "body",
  "items": ["<h1>Body 1</h1>", "<h1>Body 2</h1>"]
}

DELETE /api/rotation
{
  "type": "all"  // or "subject" or "body"
}
```

---

## 🎯 6. ENHANCED SENDING FEATURES

### Single Email:
- Supports SMTP, AWS SES, EC2 Relay
- Automatic spintax processing
- Template tag replacement
- Custom from names

### Bulk Sending:
- CSV-based with unlimited columns
- All CSV columns available as template tags
- Account rotation (SMTP/SES/EC2)
- Random delays between sends (anti-spam)
- Spintax + Template tags on every email
- Real-time progress tracking

### Example CSV:
```csv
email,name,company,position
john@example.com,John Smith,Acme Corp,CEO
jane@example.com,Jane Doe,Tech Inc,CTO
```

### Example Template:
```
Subject: {Hello|Hi} {{name}} from {{company}}!

Body:
<h1>{Greetings|Hello|Hi} {{name}}!</h1>
<p>We noticed you work at {{company}} as {{position}}.</p>
<p>Your unique tracking code: {{13_digit}}</p>
<p>Date: {{date}}</p>
```

**Result**: Each email is unique with different greeting, processed spintax, and personalized data!

---

## 🆕 NEW API ENDPOINTS

### Login
- `POST /api/login` - Authenticate user

### EC2 Relay
- `POST /api/ec2_relay` - Add or test EC2 relay
- `GET /api/ec2_relay` - List all EC2 relays
- `DELETE /api/ec2_relay` - Remove EC2 relay

### Rotation
- `POST /api/rotation` - Add subjects/bodies
- `GET /api/rotation` - Get all subjects/bodies
- `DELETE /api/rotation` - Clear subjects/bodies

### Enhanced Send APIs
- `POST /api/send` - Single email (now with spintax + templates + EC2)
- `POST /api/send_bulk` - Bulk sending (now with all features)

---

## 📊 COMPARISON: Before vs After

### Before:
- ❌ No login system
- ❌ No EC2 support
- ❌ No spintax
- ❌ Limited template tags ({{name}}, {{email}} only)
- ❌ No subject/body rotation
- ❌ Basic SMTP + SES only

### After:
- ✅ Full login system with session management
- ✅ Complete EC2 relay integration
- ✅ Full spintax processing  
- ✅ 15+ advanced template tags
- ✅ Subject/body rotation API
- ✅ SMTP + SES + EC2 with auto-rotation
- ✅ Unique content for every email
- ✅ CSV column mapping
- ✅ Anti-spam delays
- ✅ Professional sender features

---

## 🚀 USAGE GUIDE

### Setting Up EC2 Relay (Recommended):

1. **Login** to dashboard with your credentials
2. Go to **EC2 Relay** tab
3. Enter your EC2 relay endpoint URL: `http://your-ec2-ip:2525/send`
4. Click **Test Connection** to verify
5. Click **Add Relay** to save
6. When sending emails, select "EC2 Relay" as the method

### Sending with Spintax + Templates:

```
Subject: {Hi|Hello|Greetings} {{name}}! {Special|Exclusive} offer for {{company}}

Body:
<h1>{Hi|Hello} {{name}}!</h1>
<p>We at {{company_name}} have a {special|unique|exclusive} opportunity.</p>
<p>Your tracking ID: {{13_digit}}</p>
<p>Date: {{date}}</p>
```

**Every email will be unique!**

### Bulk Sending with EC2:

1. Prepare CSV with email column + any custom columns
2. Create subject/body templates using {{column_name}} tags
3. Add spintax for variations: {option1|option2}
4. Select "EC2 Relay (Recommended)" as send method
5. Set delays (2000-5000ms recommended)
6. Click "Start Bulk Sending"

**Result**: Each email sent from your EC2 IP with unique content!

---

## 🔧 TECHNICAL DETAILS

### Backend (Python):
- `api/login.py` - Authentication system
- `api/ec2_relay.py` - EC2 relay management
- `api/rotation.py` - Subject/body rotation
- `api/utils.py` - Spintax + template tag processing
- `api/send.py` - Enhanced single email sending
- `api/send_bulk.py` - Enhanced bulk sending

### Frontend (JavaScript):
- `public/login.html` - Login page
- `public/index.html` - Dashboard (with session check)
- `public/app.js` - EC2 integration + updated API calls

---

## 📝 NOTES

### EC2 Relay Endpoint Requirements:
Your EC2 relay endpoint should accept POST requests with:
```json
{
  "from_name": "Sender Name",
  "from_email": "sender@domain.com",
  "to": "recipient@example.com",
  "subject": "Email Subject",
  "html": "<h1>HTML Content</h1>"
}
```

### Session Storage:
- Sessions stored in browser localStorage
- Logout clears session
- Sessions persist across page refreshes
- No server-side session management (stateless)

### In-Memory Storage Limitation:
- EC2 relays, subjects/bodies stored in memory
- Resets on Vercel serverless function restart
- For production: Connect to database (MongoDB, PostgreSQL, etc.)

---

## 🎯 COMPARISON WITH ORIGINAL SCRIPT

### Features from Original Script Now Added:
✅ Login system (lines 220-355 in original)  
✅ EC2 relay support (lines 3388-4444 in original)  
✅ Spintax processing (lines 2448-2467 in original)  
✅ Advanced template tags (lines 2372-2741 in original)  
✅ Subject/body rotation (lines 7257-7376 in original)  
✅ Account rotation (lines 5839-5883 in original)  
✅ Smart delays (lines 5670-5676 in original)  

### Still Missing (Advanced Features):
- HTML to PDF conversion (requires external libraries)
- Proxy/SOCKS support (complex in serverless)
- Gmail OAuth API (vs SMTP - more complex setup)
- Pause/Resume controls (requires websockets/stateful backend)

---

## 🔒 SECURITY NOTES

1. **Change Default Passwords!** 
   Edit `api/login.py` to add your own users with secure passwords

2. **Use HTTPS Only**
   Vercel provides HTTPS automatically

3. **EC2 Endpoint Security**
   Ensure your EC2 relay endpoint uses authentication/API keys

4. **Session Management**
   Current implementation uses localStorage (client-side)
   For production: Implement JWT tokens with server-side validation

---

## 📱 SUPPORT

- GitHub: https://github.com/LUCIFER14144/kingmailer-vercel
- Live Demo: https://kingmailer-vercel.vercel.app
- Login: demo / demo

---

**Created by LUCIFER14144**  
**KINGMAILER v4.0 - Enterprise Edition**
