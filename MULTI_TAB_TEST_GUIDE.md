# 🧪 Test Guide: Multi-Tab Login Feature

## ✅ Quick Test Instructions

Follow these steps to verify that you can login to **3 tabs** with **3 device option**:

---

### 📋 Prerequisites

1. You need an account with `max_devices: 3` (or higher)
2. Default accounts:
   - Username: `admin` / Password: `admin123` (default max_devices: 1)
   - Username: `demo` / Password: `demo` (default max_devices: 1)
   - Username: `user` / Password: `password` (default max_devices: 1)

**IMPORTANT:** First, create a test user with 3 device slots!

---

### 🔧 Step 1: Create User with 3 Device Slots

1. Go to: https://kingmailer-vercel.vercel.app/login.html
2. Login as `admin` (password: `admin123`)
3. Click **Admin** button in top-right
4. In "Create New User" section, enter:
   ```
   Username: testuser
   Password: test123
   Role: user
   Max Devices: 3  ← IMPORTANT: Set to 3!
   ```
5. Click **Create User**
6. Verify success message
7. Logout

---

### 🎯 Step 2: Test Multi-Tab Login

#### Tab 1:
1. Open https://kingmailer-vercel.vercel.app/login.html
2. Login with:
   - Username: `testuser`
   - Password: `test123`
3. ✅ You should see the dashboard
4. Notice the username in top-right shows: `testuser`

#### Tab 2 (New Tab):
1. Open a **NEW TAB** (Ctrl+T)
2. Go to: https://kingmailer-vercel.vercel.app/login.html
3. Login with **same credentials**:
   - Username: `testuser`
   - Password: `test123`
4. ✅ You should see the dashboard again
5. Notice: Both tabs are logged in simultaneously!

#### Tab 3 (Third Tab):
1. Open **another NEW TAB** (Ctrl+T)
2. Go to: https://kingmailer-vercel.vercel.app/login.html
3. Login with **same credentials**:
   - Username: `testuser`
   - Password: `test123`  
4. ✅ You should see the dashboard
5. Notice: **All 3 tabs** are logged in at the same time!

#### Tab 4 (Device Limit Test):
1. Open **4th NEW TAB** (Ctrl+T)
2. Go to: https://kingmailer-vercel.vercel.app/login.html
3. Try to login with same credentials
4. ❌ Expected result: **"Device limit reached. Max 3 allowed."**

---

### ✅ Expected Results Summary

| Action | Expected Result |
|--------|----------------|
| Login Tab 1 | ✅ Success |
| Login Tab 2 (same account) | ✅ Success (2/3 devices) |
| Login Tab 3 (same account) | ✅ Success (3/3 devices) |
| Login Tab 4 (same account) | ❌ Error: "Device limit reached" |

---

### 🔍 Verify Session Isolation

#### Test A: Independent Sessions
1. In **Tab 1**: Check top-right → Shows `testuser`
2. In **Tab 2**: Check top-right → Shows `testuser`
3. In **Tab 3**: Check top-right → Shows `testuser`
4. ✅ Each tab maintains its own session

#### Test B: Logout Isolation
1. In **Tab 1**: Click **Logout** button
2. **Tab 1**: Should redirect to login page
3. **Tab 2**: Should still be logged in (check it!)
4. **Tab 3**: Should still be logged in (check it!)
5. ✅ Logging out one tab doesn't affect others

#### Test C: Close Tab Behavior
1. **Close Tab 2** (X button)
2. **Tab 3**: Should still be logged in
3. **Open new Tab**: Go to site → Should ask for login
4. ✅ Closing tab releases that device slot

---

### 🎮 Advanced Test: Multiple Different Accounts

If you have 3 different accounts, you can login to each in separate tabs:

#### Tab 1:
- Username: `testuser1`
- Password: `password1`

#### Tab 2:
- Username: `testuser2`
- Password: `password2`

#### Tab 3:
- Username: `testuser3`
- Password: `password3`

✅ All 3 tabs operate completely independently with different users!

---

### 🔄 Daily Reset Test

Device slots automatically reset daily:

1. Login in 3 tabs (use all 3 slots)
2. Wait until next day (or ask admin to manually reset)
3. Old HWIDs are cleared automatically
4. You can login fresh with 3 new tabs

**Admin Manual Reset:**
1. Login as `admin`
2. Go to Admin Panel
3. Find user in table
4. Click **Reset Devices** button
5. All device slots freed immediately

---

### 📊 Visual Checklist

Copy and fill this out during testing:

```
□ Created user with max_devices: 3
□ Tab 1 login: SUCCESS
□ Tab 2 login: SUCCESS (same account)
□ Tab 3 login: SUCCESS (same account)
□ Tab 4 login: BLOCKED (device limit)
□ Tab 1 shows correct username
□ Tab 2 shows correct username  
□ Tab 3 shows correct username
□ Logout Tab 1: Other tabs still logged in
□ Close Tab 2: Tab 3 still logged in
□ Can login in new tab after closing old one
```

---

### 🐛 Troubleshooting

**Issue: Can't login in new tab**
```
Cause: Device limit reached (3 slots used)
Solution: 
  1. Close one existing logged-in tab
  2. Or logout from one existing tab
  3. Or wait for daily reset (midnight)
  4. Or ask admin to reset devices
```

**Issue: Page shows login even though I logged in**
```
Cause: Page didn't refresh after login
Solution: Refresh the page (F5)
```

**Issue: All tabs log out when I logout one**
```
Cause: Browser cache issue
Solution: 
  1. Clear browser cache
  2. Hard refresh (Ctrl+F5)
  3. Try incognito mode
```

**Issue: Error "HWID required for login"**
```
Cause: Browser doesn't support sessionStorage
Solution: Update browser or use Chrome/Edge/Firefox
```

---

### 📸 Screenshot Evidence

When testing, take screenshots of:
1. Tab 1 showing dashboard with username
2. Tab 2 showing dashboard with username
3. Tab 3 showing dashboard with username
4. Tab 4 showing "Device limit reached" error

---

### ✨ Success Criteria

Your test is successful if you can:
✅ Open 3 different browser tabs
✅ Login to all 3 tabs simultaneously  
✅ Each tab shows dashboard (not kicked out)
✅ Each tab operates independently
✅ 4th tab is blocked with device limit error
✅ Logging out one tab doesn't affect others

---

## 🎉 Congratulations!

If all tests pass, your **Multi-Tab Login** feature is working perfectly!

You can now:
- Manage 3 email accounts in parallel
- Test different configs side-by-side
- Share account with team (up to 3 devices)
- Work more efficiently with isolated sessions

**Deployment:** https://kingmailer-vercel.vercel.app
**Status:** ✅ Live & Tested

