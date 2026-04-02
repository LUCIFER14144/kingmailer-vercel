# 🔐 Multi-Tab Login Support

## ✅ Feature Implemented

KINGMAILER now supports **multiple device logins in separate browser tabs**!

### 🎯 What This Means

If your account has `max_devices: 3`, you can now:
- Open **3 different browser tabs**
- Login with **3 different accounts** (or same account 3 times)
- Each tab operates **independently**
- Each tab has its **own session**

### 🔧 Technical Changes

**Before (localStorage):**
```javascript
// Shared across ALL tabs
localStorage.setItem('kingmailer_session', token);
localStorage.setItem('kingmailer_user', username);
localStorage.setItem('kingmailer_hwid', hwid);
```
❌ Problem: All tabs shared the same session
❌ Result: Only 1 login possible per browser

**After (sessionStorage):**
```javascript
// Unique to EACH tab
sessionStorage.setItem('kingmailer_session', token);
sessionStorage.setItem('kingmailer_user', username);
sessionStorage.setItem('kingmailer_hwid', hwid);
```
✅ Solution: Each tab has its own session
✅ Result: Multiple logins possible (up to max_devices limit)

### 📊 How It Works

#### 1. Device Limit System
Each user account has a `max_devices` setting:
```json
{
  "username": "user1",
  "max_devices": 3,
  "active_hwids": []
}
```

#### 2. HWID Generation (Per Tab)
Each browser tab generates its own unique HWID:
```javascript
// Old: hwid = 'browser_abc123456'  (shared)
// New: hwid = 'tab_xyz789012'      (per tab)
```

#### 3. Login Flow
```
Tab 1: Login as user1 → HWID: tab_abc123 → Active HWIDs: [tab_abc123]
Tab 2: Login as user1 → HWID: tab_def456 → Active HWIDs: [tab_abc123, tab_def456]
Tab 3: Login as user1 → HWID: tab_ghi789 → Active HWIDs: [tab_abc123, tab_def456, tab_ghi789]
Tab 4: Login as user1 → ❌ ERROR: "Device limit reached. Max 3 allowed."
```

### 🎮 Usage Examples

#### Example 1: Multiple Accounts
```
Tab 1: Login as "sender1@gmail.com"
Tab 2: Login as "sender2@gmail.com"
Tab 3: Login as "sender3@gmail.com"
→ Send emails from 3 different accounts simultaneously
```

#### Example 2: Same Account, Multiple Tabs
```
Tab 1: Login as "admin"
Tab 2: Login as "admin" (counts as 2nd device)
Tab 3: Login as "admin" (counts as 3rd device)
→ Monitor different sections of dashboard
```

#### Example 3: Testing Multiple Configs
```
Tab 1: Login → Test SMTP config
Tab 2: Login → Test Gmail API
Tab 3: Login → Test AWS SES
→ Compare results side-by-side
```

### 🔄 Session Isolation

Each tab maintains:
- ✅ **Independent authentication**
- ✅ **Separate HWID**
- ✅ **Unique session token**
- ✅ **Isolated user data**

Closing a tab automatically logs out **only that tab**:
```
Close Tab 1 → Tab 2 and Tab 3 remain logged in
Close Tab 2 → Tab 3 remains logged in
Close Tab 3 → All sessions closed
```

### 🔄 Daily HWID Reset

The system automatically resets all HWIDs daily:
```python
# In api/auth.py
today_str = datetime.now().strftime('%Y-%m-%d')
if last_reset != today_str:
    for u in users.values():
        u["active_hwids"] = []  # Clear all HWIDs
```

This means:
- All device slots refresh every 24 hours
- Old HWIDs are automatically removed
- No manual cleanup needed

### 📝 Files Modified

| File | Change | Purpose |
|------|--------|---------|
| `public/login.html` | localStorage → sessionStorage | Per-tab HWID generation |
| `public/index.html` | localStorage → sessionStorage | Per-tab session checking |
| `public/admin.html` | localStorage → sessionStorage | Per-tab admin access |

### ⚙️ Admin Configuration

Admins can set device limits when creating users:

```javascript
// Create user with 3 device slots
POST /api/users
{
  "username": "poweruser",
  "password": "secure123",
  "max_devices": 3  // Allow 3 simultaneous logins
}
```

Default: `max_devices: 1`

### 🚀 Testing the Feature

#### Test 1: Open Multiple Tabs
1. Open Tab 1 → https://kingmailer-vercel.vercel.app
2. Login with account that has `max_devices: 3`
3. Open Tab 2 → Login with same account
4. Open Tab 3 → Login with same account
5. ✅ All 3 tabs should be logged in simultaneously

#### Test 2: Device Limit
1. With 3 tabs already logged in
2. Open Tab 4 → Try to login
3. ❌ Should see: "Device limit reached. Max 3 allowed."

#### Test 3: Session Isolation
1. Tab 1: Login as user1
2. Tab 2: Login as user2
3. Tab 1 should still show user1 (not replaced by user2)
4. Each tab operates independently

#### Test 4: Logout Isolation
1. Tab 1: Login as user1
2. Tab 2: Login as user1
3. Tab 1: Click logout
4. Tab 1: Redirected to login page
5. Tab 2: Should still be logged in

### 🔒 Security Notes

- Each tab has unique HWID (prevents cross-tab interference)
- Sessions are tab-isolated (closing tab = auto-logout)
- Device limits enforced server-side (cannot be bypassed)
- Daily reset prevents HWID accumulation
- Admin can manually reset HWIDs if needed

### 🐛 Troubleshooting

**Issue: "Device limit reached" but no tabs open**
- Solution: Daily reset will clear at midnight, or ask admin to reset HWIDs

**Issue: Tab shows "Login" even though I just logged in**
- Solution: Refresh the page (sessionStorage loads on page load)

**Issue: Can't login in new tab**
- Cause: Device limit reached
- Solution: Close one existing tab, or increase `max_devices`

### 📊 Comparison

| Feature | Before (localStorage) | After (sessionStorage) |
|---------|---------------------|----------------------|
| Multi-tab login | ❌ No | ✅ Yes |
| Session isolation | ❌ Shared | ✅ Isolated |
| Device counting | ⚠️ Inaccurate | ✅ Accurate |
| Tab independence | ❌ No | ✅ Yes |
| Logout behavior | ⚠️ All tabs | ✅ Per tab |

### 🎉 Benefits

1. **Parallel Testing:** Test multiple configs simultaneously
2. **Multi-Account:** Manage multiple email accounts at once
3. **Team Collaboration:** Share account with team (up to device limit)
4. **Workflow Flexibility:** Different tabs for different tasks
5. **True Device Tracking:** Accurate device count per user

---

**Version:** KINGMAILER v4.1+
**Status:** ✅ Production Ready
**Deployment:** Live on Vercel

