"""
KINGMAILER v5.8 - Bulk Email Sending API (Inbox-Optimised)
Features: CSV processing, SMTP/SES/EC2, Account Rotation, Spintax, Placeholders

✅ Clean minimal headers — no X-Mailer, X-Priority, X-Entity-ID, Thread-Topic
✅ Neutral MIME boundaries (no Apple-Mail=_ mismatch)
✅ Per-email HTML-comment jitter (breaks Gmail duplicate clustering)
✅ local_hostname=sender_domain for SMTP EHLO
✅ RFC-clean MIME-Version + QP body encoding
✅ RFC 2047 From name encoding (_make_from_header)
✅ List-Unsubscribe header (Google 2024 bulk sender requirement)
✅ Account tracking with deactivation after 3 consecutive failures
"""

from http.server import BaseHTTPRequestHandler
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage
from email import encoders
from email.utils import formatdate, make_msgid
from email.charset import Charset as _Charset, QP as _QP
import boto3
import json
import csv
import io
import os
import time
import random
import re
import uuid
import base64
import urllib.request
import urllib.error
from datetime import datetime
import string
import quopri


_AUTH_CACHE = {}
_RISK_SUBJECT_WORDS = {
    'urgent', 'act now', 'free', 'winner', 'prize', 'click here', 'confirm',
    'verify', 'account suspended', 'payment due', 'shipment', 'delivery'
}

# ============================================================================
# ACCOUNT TRACKING SYSTEM - Track failures and deactivate accounts  
# ============================================================================

def load_account_stats():
    """Load account statistics from file"""
    stats_file = '/tmp/kingmailer_account_stats.json'
    try:
        if os.path.exists(stats_file):
            with open(stats_file, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading account stats: {e}")
    
    return {"smtp": {}, "gmail_api": {}, "ses": {}}

def save_account_stats(account_stats):
    """Save account statistics to file"""
    stats_file = '/tmp/kingmailer_account_stats.json'
    try:
        os.makedirs(os.path.dirname(stats_file), exist_ok=True)
        with open(stats_file, 'w') as f:
            json.dump(account_stats, f, indent=2)
    except Exception as e:
        print(f"Error saving account stats: {e}")

def initialize_account_stats(account_id, account_type):
    """Initialize stats for a new account"""
    return {
        'account_id': account_id,
        'account_type': account_type,
        'failed_attempts': 0,
        'emails_sent': 0,
        'is_active': True,
        'last_failure': None,
        'total_failures': 0,
        'created_at': datetime.now().isoformat()
    }

def track_send_success(account_id, account_type):
    """Track successful email send - Enhanced with debugging"""
    print(f"[TRACK_SUCCESS] Recording success for {account_type} account: {account_id}")
    
    account_stats = load_account_stats()
    
    if account_type not in account_stats:
        account_stats[account_type] = {}
    
    if account_id not in account_stats[account_type]:
        account_stats[account_type][account_id] = initialize_account_stats(account_id, account_type)
        print(f"[TRACK_SUCCESS] Created new tracking entry for {account_type}:{account_id}")
    
    # Reset failed attempts on success and increment send count
    account_stats[account_type][account_id]['failed_attempts'] = 0
    account_stats[account_type][account_id]['emails_sent'] += 1
    account_stats[account_type][account_id]['is_active'] = True
    
    save_account_stats(account_stats)
    print(f"[TRACK_SUCCESS] SUCCESS {account_type} {account_id} - Total sent: {account_stats[account_type][account_id]['emails_sent']}")

def track_send_failure(account_id, account_type, error_msg=""):
    """Track failed email send and deactivate account if needed - Enhanced with debugging"""
    print(f"[TRACK_FAILURE] Recording failure for {account_type} account: {account_id} - Error: {error_msg}")
    
    account_stats = load_account_stats()
    
    if account_type not in account_stats:
        account_stats[account_type] = {}
    
    if account_id not in account_stats[account_type]:
        account_stats[account_type][account_id] = initialize_account_stats(account_id, account_type)
        print(f"[TRACK_FAILURE] Created new tracking entry for {account_type}:{account_id}")
    
    # Increment failure counters
    account_stats[account_type][account_id]['failed_attempts'] += 1
    account_stats[account_type][account_id]['total_failures'] += 1
    account_stats[account_type][account_id]['last_failure'] = datetime.now().isoformat()
    
    # Deactivate account after 3 consecutive failures
    if account_stats[account_type][account_id]['failed_attempts'] >= 3:
        account_stats[account_type][account_id]['is_active'] = False
        print(f"[TRACK_FAILURE] CRITICAL ACCOUNT DEACTIVATED: {account_type} account '{account_id}' deactivated after 3 consecutive failures")
        print(f"[TRACK_FAILURE]    Last error: {error_msg}")
        save_account_stats(account_stats)
        return True  # Account was deactivated
    
    save_account_stats(account_stats)
    print(f"[TRACK_FAILURE] WARNING {account_type} {account_id} - Attempt {account_stats[account_type][account_id]['failed_attempts']}/3")
    return False  # Account still active

def is_account_active(account_id, account_type):
    """Check if an account is active (not deactivated due to failures)"""
    account_stats = load_account_stats()
    
    if account_type not in account_stats:
        print(f"[ACCOUNT_CHECK] SUCCESS {account_type} account '{account_id}' - no stats found, assuming active")
        return True
    
    if account_id not in account_stats[account_type]:
        print(f"[ACCOUNT_CHECK] SUCCESS {account_type} account '{account_id}' - not tracked yet, assuming active")
        return True
        
    is_active = account_stats[account_type][account_id].get('is_active', True)
    failed_attempts = account_stats[account_type][account_id].get('failed_attempts', 0)
    
    if not is_active:
        print(f"[ACCOUNT_CHECK] CRITICAL BLOCKED: {account_type} account '{account_id}' is DEACTIVATED (failed_attempts: {failed_attempts}) - SKIPPING")
        return False
    else:
        print(f"[ACCOUNT_CHECK] SUCCESS {account_type} account '{account_id}' is ACTIVE (failed_attempts: {failed_attempts})")
        return True


# Spintax Processor
def process_spintax(text):
    """Process spintax syntax: {option1|option2|option3}"""
    if not text:
        return text
    pattern = r'\{([^{}]+)\}'
    def replace_fn(match):
        options = match.group(1).split('|')
        return random.choice(options).strip()
    max_iter = 10
    iteration = 0
    while '{' in text and '|' in text and iteration < max_iter:
        text = re.sub(pattern, replace_fn, text)
        iteration += 1
    return text


# Template Tag Replacements
def gen_random_name():
    first = ['James', 'John', 'Robert', 'Michael', 'William', 'Mary', 'Patricia', 'Jennifer', 'Linda', 'Elizabeth']
    last = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez']
    return f"{random.choice(first)} {random.choice(last)}"

def gen_company():
    prefixes = ['Tech', 'Global', 'Digital', 'Smart', 'Innovative', 'Advanced', 'Premier', 'Elite']
    suffixes = ['Solutions', 'Systems', 'Corporation', 'Industries', 'Group', 'Services', 'Technologies']
    return f"{random.choice(prefixes)} {random.choice(suffixes)}"

def gen_13_digit():
    timestamp = int(datetime.now().timestamp() * 1000)
    random_suffix = random.randint(100, 999)
    id_str = f"{timestamp}{random_suffix}"
    return id_str[:13]


def replace_template_tags(text, row_data, recipient_email='', sender_name='', sender_email='', allow_single_brace=False):
    """Replace ALL $tag and {{tag}} placeholders including CSV column data."""
    if not text:
        return text

    # Build tag map (mirrors send.py)
    import random as _rnd, string as _str
    _US_FIRST = ['James','John','Robert','Michael','William','David','Richard','Joseph','Thomas','Charles',
                 'Mary','Patricia','Jennifer','Linda','Barbara','Elizabeth','Susan','Jessica','Sarah','Karen']
    _US_LAST  = ['Smith','Johnson','Williams','Brown','Jones','Garcia','Miller','Davis','Rodriguez','Martinez',
                 'Wilson','Anderson','Taylor','Thomas','Moore','Jackson','Thompson','White']
    _US_CITIES = [('New York','NY','10001'),('Los Angeles','CA','90001'),('Chicago','IL','60601'),
                  ('Houston','TX','77001'),('Phoenix','AZ','85001'),('Dallas','TX','75201'),
                  ('Austin','TX','78701'),('Seattle','WA','98101'),('Denver','CO','80201'),
                  ('Nashville','TN','37201'),('Charlotte','NC','28201'),('Boston','MA','02101'),
                  ('Las Vegas','NV','89101'),('Miami','FL','33101'),('Atlanta','GA','30301')]
    _US_STREETS = ['Main St','Oak Ave','Maple Dr','Pine Blvd','Cedar Lane','Elm Rd',
                   'Washington Blvd','Park Ave','Lake Dr','Hillside Way','Sunset Blvd','River Rd']
    _US_CO = ['Apex Solutions LLC','Bright Path Inc','Cascade Digital Corp','Delta Group','Everest Ventures',
              'Global Tech Inc','Harbor Networks LLC','Keystone Consulting','Meridian Group LLC',
              'Nexus Innovations','Pinnacle Growth Inc','Quantum Systems','Summit Partners LLC']
    _US_PR = ['Premium Membership','Express Delivery','Annual Plan','Business Package',
              'Standard Subscription','Pro License','Elite Bundle','Starter Kit','Enterprise Plan']

    def _rn(n):  return ''.join(_rnd.choices(_str.digits, k=n))
    def _ra(n):  return ''.join(_rnd.choices(_str.ascii_lowercase, k=n))
    def _ran(n, up=False):
        c = (_str.ascii_uppercase if up else _str.ascii_lowercase) + _str.digits
        return ''.join(_rnd.choices(c, k=n))

    first = _rnd.choice(_US_FIRST); last = _rnd.choice(_US_LAST)
    city, state, zipcode = _rnd.choice(_US_CITIES)
    sn = _rnd.randint(100, 9999); st = _rnd.choice(_US_STREETS)
    ts13 = str(int(datetime.now().timestamp() * 1000))[:13]

    tag_map = {
        'name':          recipient_email.split('@')[0] if recipient_email else (first+' '+last),
        'email':         recipient_email,
        'recipient':     recipient_email,
        'recipientName': first + ' ' + last,
        'sender':        sender_email,
        'sendername':    sender_name or (sender_email.split('@')[0] if sender_email and '@' in sender_email else 'Support Team'),
        'sendertag':     f"{sender_name} <{sender_email}>" if sender_name else sender_email,
        'randName':      f"{first} {last}",
        'rnd_company_us': _rnd.choice(_US_CO),
        'address':       f"{sn} {st}, {city}, {state} {zipcode}",
        'street':        f"{sn} {st}",
        'city':          city, 'state': state, 'zipcode': zipcode, 'zip': zipcode,
        'invcnumber':    'INV-' + _rn(8), 'ordernumber': 'ORD-' + _rn(8),
        'product':       _rnd.choice(_US_PR),
        'amount':        f"${_rnd.randint(999,99999)/100:.2f}",
        'charges':       f"${_rnd.randint(499,49999)/100:.2f}",
        'quantity':      str(_rnd.randint(1,99)), 'number': _rn(6),
        'date':          datetime.now().strftime('%B %d, %Y'),
        'time':          datetime.now().strftime('%I:%M %p'),
        'year':          str(datetime.now().year),
        'id':            _rn(10),
        'random_name':   f"{first} {last}",
        'company':       _rnd.choice(_US_CO), 'company_name': _rnd.choice(_US_CO),
        '13_digit':      ts13, 'unique_id': ts13, 'unique13digit': ts13,
        'random_6':      ''.join(_rnd.choices(_str.ascii_letters+_str.digits, k=6)),
        'random_8':      ''.join(_rnd.choices(_str.ascii_letters+_str.digits, k=8)),
        'unique16_484':      f"{_rn(4)}-{_rn(8)}-{_rn(4)}",
        'unique16_565':      f"{_rn(5)}-{_rn(6)}-{_rn(5)}",
        'unique16_4444':     f"{_rn(4)}-{_rn(4)}-{_rn(4)}-{_rn(4)}",
        'unique16_88':       f"{_rn(8)}-{_rn(8)}",
        'unique14alphanum':  _ran(14, up=True), 'unique11alphanum': _ran(11, up=True),
        'unique14alpha':     _ra(14).upper(),
        'alpha_random_small': _ra(6), 'alpha_short': _ra(4), 'random_three_chars': _ran(3),
    }
    # Derive first/last from sender_name for fname/lname tags
    _sn_parts = (sender_name or '').strip().split()
    _fname = _sn_parts[0] if _sn_parts else first
    _lname = ' '.join(_sn_parts[1:]) if len(_sn_parts) > 1 else last
    tag_map['fname']       = _fname
    tag_map['lname']       = _lname
    tag_map['firstname']   = _fname
    tag_map['lastname']    = _lname
    tag_map['fullname']    = f"{first} {last}"
    tag_map['sender_name'] = sender_name or (sender_email.split('@')[0] if sender_email and '@' in sender_email else 'Support Team')

    # Merge CSV row data (CSV overrides defaults)
    if row_data:
        for k, v in row_data.items():
            if k:
                tag_map[k] = str(v)

    # Apply replacements (longest key first to avoid partial matches)
    sorted_keys = sorted(tag_map.keys(), key=len, reverse=True)
    for key in sorted_keys:
        val = str(tag_map[key])
        # Use lambda to prevent re.sub from interpreting \ in val as backreferences
        text = re.sub(r'\{\{' + re.escape(key) + r'\}\}', lambda m, v=val: v, text, flags=re.IGNORECASE)
        # NOTE: Do NOT replace {key} (single braces) — HTML/CSS uses {}, would corrupt styles
        text = re.sub(r'\$' + re.escape(key) + r'(?=[^a-zA-Z0-9_]|$)', lambda m, v=val: v, text, flags=re.IGNORECASE)
        if allow_single_brace:
            text = re.sub(r'\{' + re.escape(key) + r'\}', lambda m, v=val: v, text, flags=re.IGNORECASE)
    return text


# ────────────────────────────────────────────────────────
# Helper: HTML to plain text
# ────────────────────────────────────────────────────────
def _html_to_plain(html):
    """Strip HTML tags to produce a clean plain-text fallback.
    Decodes HTML entities so &amp; &lt; &gt; etc. appear correctly in plain text.
    """
    import html as _html_lib
    text = re.sub(r'<br\s*/?>', '\n', html, flags=re.IGNORECASE)
    text = re.sub(r'<p[^>]*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</p>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<li[^>]*>', '\n\u2022 ', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    text = _html_lib.unescape(text)          # decode &amp; &lt; &gt; &#x…; etc.
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


# 📸 ENHANCED IMAGE FORMAT SUPPORT - Premium Quality Handling
# Supports all major image formats with optimal MIME type detection
_IMAGE_TYPES = {
    'image/jpeg', 'image/jpg',           # Standard JPEG (best for photos) 
    'image/png',                         # Lossless PNG (logos, transparency)
    'image/gif',                         # GIF animations
    'image/webp',                        # Modern WebP (25-35% smaller than JPEG)
    'image/bmp',                         # Uncompressed bitmap
    'image/tiff', 'image/tif',           # Professional/archival
    'image/avif',                        # Next-gen format (better than WebP)
    'image/svg+xml'                      # Vector graphics (scalable)
}
_IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff', '.tif', '.avif', '.svg'}

def _is_image_attachment(attachment):
    """Return True if attachment is an embeddable image."""
    import mimetypes, os
    if not attachment:
        return False
    m_type = attachment.get('type', '').lower()
    filename = attachment.get('name', '')
    ext = os.path.splitext(filename)[1].lower()
    if not m_type or m_type == 'application/octet-stream':
        m_type = mimetypes.guess_type(filename)[0] or ''
    return m_type in _IMAGE_TYPES or ext in _IMAGE_EXTS


def _is_html_attachment(attachment):
    """Return True for risky HTML/script-like attachments."""
    import mimetypes, os
    if not attachment:
        return False
    filename = (attachment.get('name') or '').lower()
    m_type = (attachment.get('type') or '').lower()
    ext = os.path.splitext(filename)[1].lower()
    if not m_type or m_type == 'application/octet-stream':
        m_type = (mimetypes.guess_type(filename)[0] or '').lower()
    return m_type == 'text/html' or ext in {'.html', '.htm', '.js', '.hta'}


def _decode_attachment_bytes(attachment):
    """Decode and validate attachment payload bytes; return (bytes, error)."""
    if not attachment:
        return None, None
    content = attachment.get('content')
    if not content:
        return None, 'Attachment content is empty.'

    try:
        padded = content + '=' * (-len(content) % 4)
        data = base64.b64decode(padded)
    except Exception:
        return None, 'Attachment payload is not valid base64.'

    if not data or len(data) < 32:
        return None, 'Attachment appears empty or too small.'

    name = (attachment.get('name') or '').lower()
    m_type = (attachment.get('type') or '').lower()
    if name.endswith('.pdf') or m_type == 'application/pdf':
        if not data.startswith(b'%PDF-'):
            return None, 'Attachment is labeled PDF but payload is not a valid PDF file.'

    return data, None

def _clean_mime(part, is_root=True):
    """Recursively ensure ONLY the root part has MIME-Version: 1.0."""
    if not is_root and 'MIME-Version' in part:
        del part['MIME-Version']
    if part.is_multipart():
        for sub in part.get_payload():
            if hasattr(sub, 'add_header'):
                _clean_mime(sub, is_root=False)

def add_attachment_to_message(msg, attachment):
    """Attach a non-image file (PDF, docx, etc.) as a standard MIME attachment."""
    if not attachment: return True, None
    try:
        import mimetypes
        file_data = base64.b64decode(attachment['content'] + '=' * (-len(attachment['content']) % 4))
        filename = attachment.get('name', 'file.dat')
        m_type = attachment.get('type') or mimetypes.guess_type(filename)[0] or 'application/octet-stream'
        main, sub = m_type.split('/', 1) if '/' in m_type else ('application', 'octet-stream')
        part = MIMEBase(main, sub)
        part.set_payload(file_data)
        encoders.encode_base64(part)
        part.add_header('Content-Type', f'{main}/{sub}', name=filename)
        part.add_header('Content-Disposition', 'attachment', filename=filename)
        if 'MIME-Version' in part: del part['MIME-Version']
        msg.attach(part)
        return True, None
    except Exception as e:
        return False, str(e)

def minimize_spam_keywords(text):
    """DEPRECATED — no longer called.

    Word-substitution (Free → Complementary, Important → Significant) is
    counterproductive against modern ML-based spam classifiers. Unnatural
    word choices are themselves a spam fingerprint. This is now a no-op.
    """
    return text  # no-op

def _extract_domain(from_header):
    if '@' in from_header:
        part = from_header.split('@')[-1]
        domain = re.sub(r'[>\s].*$', '', part).strip()
        return domain if domain else 'mail.local'
    return 'mail.local'


_WEBMAIL_DOMAINS = {
    'gmail.com', 'googlemail.com', 'outlook.com', 'hotmail.com', 'live.com',
    'msn.com', 'yahoo.com', 'ymail.com', 'aol.com', 'icloud.com', 'me.com'
}


def _is_webmail_sender(sender_email):
    """Return True when sender belongs to consumer webmail domains."""
    if not sender_email or '@' not in sender_email:
        return False
    return sender_email.split('@')[-1].strip().lower() in _WEBMAIL_DOMAINS


def _domain_auth_guard(sender_email, header_opts=None):
    opts = header_opts or {}
    if opts.get('skip_auth_guard'):
        return None
    if not sender_email or '@' not in sender_email:
        return 'Sender email missing for domain-auth verification.'

    domain = sender_email.split('@')[-1].strip().lower()
    now_ts = datetime.now().timestamp()
    cached = _AUTH_CACHE.get(domain)
    if cached and (now_ts - cached.get('ts', 0) < 900):
        return cached.get('error')

    try:
        import deliverability as _deliv
        spf = _deliv.check_spf(domain)
        dmarc = _deliv.check_dmarc(domain)
        mx = _deliv.check_mx(domain)
    except Exception:
        _AUTH_CACHE[domain] = {'ts': now_ts, 'error': None}
        return None

    critical = []
    if spf.get('status') == 'MISSING' or '+all' in str(spf.get('record') or ''):
        critical.append('SPF')
    if dmarc.get('status') == 'MISSING':
        critical.append('DMARC')
    if mx.get('status') == 'MISSING':
        critical.append('MX')
    err = None
    if critical:
        err = f'Send blocked: critical domain-auth issue ({", ".join(critical)}) for {domain}. Fix DNS first.'
    _AUTH_CACHE[domain] = {'ts': now_ts, 'error': err}
    return err


def _message_risk_guard(subject, html_body, attachment):
    lower_subject = (subject or '').lower()
    lower_html = (html_body or '').lower()
    subject_hits = [w for w in _RISK_SUBJECT_WORDS if w in lower_subject]
    if len(subject_hits) >= 2:
        return f'Send blocked: subject contains high-risk keywords ({", ".join(subject_hits[:3])}).'
    link_count = len(re.findall(r'https?://', html_body or '', flags=re.IGNORECASE))
    if link_count > 6:
        return f'Send blocked: body contains too many links ({link_count}).'
    if attachment:
        name = (attachment.get('name') or '').lower()
        att_type = (attachment.get('type') or '').lower()
        if att_type == 'text/html' or name.endswith(('.html', '.htm', '.js', '.hta')):
            return 'Send blocked: HTML/script-like attachments are high-risk. Use PDF or image formats.'
    if 'display:none' in lower_html or 'visibility:hidden' in lower_html:
        return 'Send blocked: hidden HTML/CSS detected.'
    return None

def _is_html(text):
    """Return True if text contains at least one HTML tag like <p>, <br>, <div>."""
    return bool(re.search(r'<[a-z][a-z0-9]*[\s>/]', text or '', re.IGNORECASE))

def _plain_to_html(text):
    """Convert plain text with newlines into a properly structured HTML email body.
    Paragraphs separated by blank lines, single newlines become <br>.
    Returns a complete HTML document (DOCTYPE, html, head, body) for maximum
    deliverability — spam filters check for proper document structure.
    """
    import html as _html_mod
    escaped = _html_mod.escape(text)
    paragraphs = re.split(r'\n\s*\n', escaped)
    html_parts = []
    for para in paragraphs:
        para_html = para.replace('\n', '<br>')
        html_parts.append(f'<p style="margin:0 0 1em 0;line-height:1.6;">{para_html}</p>')
    body = '\n'.join(html_parts)
    return (
        '<!DOCTYPE html>\n<html lang="en">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        '</head>\n<body style="margin:0;padding:0;">\n'
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:14px;'
        'color:#222;max-width:650px;margin:0 auto;padding:20px 20px 40px;">'
        + body + '</div>\n</body>\n</html>'
    )

def _get_jitter():
    """Return a unique HTML comment per email.
    HTML comments make every email's hash unique, preventing Gmail from grouping
    bulk sends into the same thread (which triggers spam detection).
    This is the standard pattern used by Mailchimp, SendGrid, and Klaviyo.
    HTML comments are NOT flagged by spam filters unlike hidden-div patterns.
    """
    uid = f"{uuid.uuid4().hex[:8]}-{random.randint(100000, 999999)}"
    return f'<!-- mid:{uid} -->\n'


def _encode_subject(subject):
    """RFC 2047-encode subject lines that contain non-ASCII characters."""
    from email.header import Header as _H
    try:
        subject.encode('ascii')
        return subject
    except (UnicodeEncodeError, UnicodeDecodeError):
        return _H(subject, 'utf-8').encode()

def _make_from_header(sender_name, email_addr):
    """Build RFC-compliant From/Reply-To header.
    Properly RFC 2047-encodes non-ASCII display names (German umlauts, French accents, etc.)
    so that email headers never contain raw non-ASCII bytes.
    """
    if not sender_name:
        return email_addr
    try:
        sender_name.encode('ascii')
        from email.utils import formataddr as _fmt
        return _fmt((sender_name, email_addr))
    except (UnicodeEncodeError, UnicodeDecodeError):
        from email.header import Header as _Hdr
        return '{} <{}>'.format(_Hdr(sender_name, 'utf-8').encode(), email_addr)


def _build_message(from_header, to_email, subject, html_body, attachment=None, header_opts=None):
    """Build RFC-compliant MIME message — inbox-optimised."""
    import mimetypes
    _o = dict(header_opts or {})

    domain = _extract_domain(from_header)
    if _is_webmail_sender(from_header):
        # Webmail senders get better placement with minimal headers.
        _o['reply_to'] = False
        _o['precedence_bulk'] = False
        _o['list_unsubscribe'] = False

    if not _is_html(html_body): html_body = _plain_to_html(html_body)

    # Optional footer injection only when explicitly requested by caller.
    # Default OFF: auto-generated/random compliance footers can look synthetic and hurt inboxing.
    if _o.get('auto_footer', False):
        lc_body = html_body.lower()
        has_unsubscribe = 'unsubscribe' in lc_body or 'opt-out' in lc_body
        has_address = bool(re.search(
            r'\b\d{1,6}\b.{0,15}\b(street|st\.|ave\.?|avenue|blvd\.?|boulevard|'
            r'road|rd\.|drive|dr\.|suite|ste\.?|floor|way|lane|ln\.)\b',
            lc_body
        ))

        footer = ('<div style="margin-top:40px;padding-top:20px;border-top:1px solid #eee;'
                  'font-size:11px;color:#999;text-align:center;">')
        if not has_address:
            physical_address = (_o.get('physical_address') or '').strip()
            if physical_address:
                footer += f'<p>{physical_address}</p>'
        if not has_unsubscribe:
            _fe2 = re.search(r'<(.+?)>', from_header)
            _fe2 = _fe2.group(1) if _fe2 else from_header
            footer += (f'<p>To stop receiving these emails, '
                       f'<a href="mailto:{_fe2}?subject=unsubscribe" '
                       f'style="color:#666;">unsubscribe here</a>.</p>')
        footer += '</div>'
        if '</body>' in html_body:
            html_body = html_body.replace('</body>', footer + '</body>')
        else:
            html_body += footer

    if '<body' not in html_body.lower():
        html_body = (
            '<!DOCTYPE html>\n<html lang="en">\n<head>\n'
            '<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
            '</head>\n<body style="margin:0;padding:0;">\n'
            + html_body + '\n</body>\n</html>'
        )

    # Jitter: auto-ON for attachment sends (prevents body-hash fingerprinting across recipients).
    # Without jitter, identical HTML sent to N recipients is a textbook bulk-spam fingerprint.
    _has_att = bool(attachment and attachment.get('content'))
    if (_has_att or _o.get('html_jitter', False)) and '</body>' in html_body:
        html_body = html_body.replace('</body>', f'{_get_jitter()}</body>')

    def _qp_part(text_value, subtype):
        """Build a UTF-8 MIMEText part that is truly quoted-printable encoded."""
        part = MIMEText('', subtype, 'utf-8')
        qp_payload = quopri.encodestring((text_value or '').encode('utf-8'), quotetabs=True).decode('ascii')
        part.set_payload(qp_payload)
        if part.get('Content-Transfer-Encoding'):
            part.replace_header('Content-Transfer-Encoding', 'quoted-printable')
        else:
            part['Content-Transfer-Encoding'] = 'quoted-printable'
        return part

    plain = _html_to_plain(html_body)

    # ── ATTACHMENTS ──────────────────────────────────────────────────────────
    if attachment and attachment.get('content'):
        att_name    = attachment.get('name', 'file')
        att_type    = attachment.get('type', 'application/octet-stream')
        att_content = attachment.get('content', '')
        inline_cid  = bool(attachment.get('inline_cid', False))
        main_type, sub_type = att_type.split('/', 1) if '/' in att_type else ('application', 'octet-stream')

        if not att_content:
            msg = MIMEMultipart('alternative')
            txt = _qp_part(plain, 'plain')
            txt.set_param('format', 'flowed')
            html_part = _qp_part(html_body, 'html')
            msg.attach(txt)
            msg.attach(html_part)

        elif inline_cid and main_type == 'image':
            msg = MIMEMultipart('related', type='multipart/alternative')
            alt = MIMEMultipart('alternative')
            txt = _qp_part(plain, 'plain')
            txt.set_param('format', 'flowed')
            html_part = _qp_part(html_body, 'html')
            alt.attach(txt)
            alt.attach(html_part)
            msg.attach(alt)
            att_bytes = base64.b64decode(att_content.encode('ascii') + b'==')
            att_part  = MIMEImage(att_bytes, sub_type)
            att_part.add_header('Content-ID', f'<{att_name}>')
            att_part.add_header('Content-Disposition', 'inline', filename=att_name)
            if 'MIME-Version' in att_part: del att_part['MIME-Version']
            msg.attach(att_part)

        else:
            # ── Standard MIME attachment (download or non-image inline) ──
            msg = MIMEMultipart('mixed')
            alt = MIMEMultipart('alternative')
            txt = _qp_part(plain, 'plain')
            txt.set_param('format', 'flowed')
            html_part = _qp_part(html_body, 'html')
            alt.attach(txt)
            alt.attach(html_part)
            msg.attach(alt)

            # RFC 2183: Content-Type MUST include name= matching filename= in Content-Disposition.
            # MIMEBase with name= kwarg sets this correctly for all MIME types.
            # Gmail/Outlook malware scanners flag attachments where name= is absent as suspicious.
            _att_padded = att_content + '=' * (-len(att_content) % 4)
            att_bytes = base64.b64decode(_att_padded.encode('ascii'))
            att_part = MIMEBase(main_type, sub_type, name=att_name)
            att_part.set_payload(att_bytes)
            encoders.encode_base64(att_part)
            try:
                att_name.encode('ascii')
                att_part.add_header('Content-Disposition', 'attachment', filename=att_name)
            except (UnicodeEncodeError, AttributeError):
                att_part.add_header('Content-Disposition', 'attachment', filename=('utf-8', '', att_name))
            if 'MIME-Version' in att_part: del att_part['MIME-Version']
            msg.attach(att_part)
    else:
        # No attachment — simple multipart/alternative
        msg = MIMEMultipart('alternative')
        txt = _qp_part(plain, 'plain')
        txt.set_param('format', 'flowed')
        html_part = _qp_part(html_body, 'html')
        msg.attach(txt)
        msg.attach(html_part)

    _clean_mime(msg)

    # Keep headers minimal and standards-based.
    _uid = uuid.uuid4().hex
    msg['From']             = from_header
    msg['To']               = to_email
    msg['Subject']          = _encode_subject(subject)
    msg['Date']             = formatdate(localtime=True)
    msg['Message-ID']       = f'<{_uid}@{domain}>'
    if msg.get('MIME-Version'):
        msg.replace_header('MIME-Version', '1.0')
    else:
        msg['MIME-Version'] = '1.0'
    msg['Content-Language'] = 'en-US'
    # Reply-To: optional (on by default; disable to reduce promotional header signals)
    if _o.get('reply_to', False):
        msg['Reply-To'] = from_header
    # Precedence: bulk — optional marketing signal (off by default → Primary inbox)
    if _o.get('precedence_bulk', False):
        msg['Precedence'] = 'bulk'
    _fe = re.search(r'<(.+?)>', from_header)
    _fe = _fe.group(1) if _fe else from_header
    # List-Unsubscribe — optional (off by default → avoids Promotions/Updates tab)
    if _o.get('list_unsubscribe', False):
        msg['List-Unsubscribe'] = f'<mailto:{_fe}?subject=unsubscribe>'

    return msg




# ────────────────────────────────────────────────────────
# Sending functions (SMTP / SES / EC2) — all attachment-aware
# ────────────────────────────────────────────────────────
def send_email_smtp(smtp_config, from_name, recipient, subject, html_body, attachment=None, header_opts=None):
    """Send single email via direct SMTP (Gmail/Outlook/custom).
    Builds a proper MIME structure with plain-text fallback and optional attachment.
    """
    try:
        is_gmail  = smtp_config.get('provider') == 'gmail'
        smtp_server = 'smtp.gmail.com' if is_gmail else smtp_config.get('host', 'smtp.gmail.com')
        smtp_port   = 587 if is_gmail else int(smtp_config.get('port', 587))
        smtp_user   = smtp_config.get('user')
        smtp_pass   = smtp_config.get('pass')
        # Sanitize: treat 'KINGMAILER' as empty (legacy default, not a real name)
        _cfg_sn = smtp_config.get('sender_name') or ''
        if _cfg_sn == 'KINGMAILER': _cfg_sn = ''
        sender_name = from_name if from_name and from_name != 'KINGMAILER' else _cfg_sn
        from_header = _make_from_header(sender_name, smtp_user) if sender_name else smtp_user

        print(f'[SMTP SEND] → {recipient}  server={smtp_server}:{smtp_port}')

        # _build_message now handles ALL attachment types internally
        msg = _build_message(from_header, recipient, subject, html_body, attachment, header_opts=header_opts)

        _ehlo_host = _extract_domain(smtp_user or '')
        # OPTIMIZED FOR TURBO MODE: Faster timeouts for quick failure detection
        with smtplib.SMTP(smtp_server, smtp_port, timeout=5,
                           local_hostname=_ehlo_host if _ehlo_host != 'mail.local' else None) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)

        print(f'[SMTP SUCCESS] → {recipient}')
        return {'success': True}
    except smtplib.SMTPAuthenticationError:
        return {'success': False, 'error': 'SMTP authentication failed — check your app password'}
    except smtplib.SMTPRecipientsRefused:
        return {'success': False, 'error': f'Recipient rejected: {recipient}'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def refresh_gmail_access_token(refresh_token, client_id, client_secret):
    """Refresh Gmail OAuth2 access token using refresh token."""
    import urllib.request
    import urllib.error
    import urllib.parse
    
    try:
        token_url = 'https://oauth2.googleapis.com/token'
        payload = {
            'client_id': client_id,
            'client_secret': client_secret,
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token'
        }
        
        data = urllib.parse.urlencode(payload).encode('utf-8')
        req = urllib.request.Request(token_url, data=data, method='POST')
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')
        
        with urllib.request.urlopen(req, timeout=3) as response:
            resp_data = json.loads(response.read().decode('utf-8'))
            new_access_token = resp_data.get('access_token')
            if new_access_token:
                return {'success': True, 'access_token': new_access_token}
            else:
                return {'success': False, 'error': 'No access_token in refresh response'}
                
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else str(e)
        return {'success': False, 'error': f'Token refresh failed (HTTP {e.code}): {error_body}'}
    except Exception as e:
        return {'success': False, 'error': f'Token refresh error: {str(e)}'}


def send_email_gmail_api(gmail_config, from_name, recipient, subject, html_body, attachment=None, header_opts=None):
    """Send single email via Gmail API (OAuth2) with automatic token refresh."""
    try:
        access_token = gmail_config.get('access_token', '').strip()
        refresh_token = gmail_config.get('refresh_token', '').strip()
        client_id = gmail_config.get('client_id', '').strip()
        client_secret = gmail_config.get('client_secret', '').strip()
        gmail_user = gmail_config.get('user', '').strip()
        
        if not all([access_token, client_id, client_secret, gmail_user]):
            return {'success': False, 'error': 'Gmail API requires: access_token, client_id, client_secret, and user email'}
        
        sender_name = from_name if from_name and from_name != 'KINGMAILER' else gmail_config.get('sender_name', '')
        if sender_name == 'KINGMAILER': sender_name = ''
        from_header = _make_from_header(sender_name, gmail_user) if sender_name else gmail_user
        
        msg = _build_message(from_header, recipient, subject, html_body, attachment, header_opts=header_opts)
        raw_msg = base64.urlsafe_b64encode(msg.as_bytes()).decode('utf-8')
        
        import urllib.request
        import urllib.error
        
        api_url = 'https://gmail.googleapis.com/gmail/v1/users/me/messages/send'
        payload = json.dumps({'raw': raw_msg})
        
        # First attempt with current access token
        req = urllib.request.Request(api_url, data=payload.encode('utf-8'), method='POST')
        req.add_header('Authorization', f'Bearer {access_token}')
        req.add_header('Content-Type', 'application/json')
        
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                resp_data = json.loads(response.read().decode('utf-8'))
                msg_id = resp_data.get('id', 'unknown')
                print(f'[Gmail API SUCCESS] → {recipient} [msg_id: {msg_id}]')
                return {'success': True, 'gmail_msg_id': msg_id}
        except urllib.error.HTTPError as e:
            # If 401 Unauthorized, try to refresh token automatically
            if e.code == 401 and refresh_token:
                # Refresh the access token
                refresh_result = refresh_gmail_access_token(refresh_token, client_id, client_secret)
                
                if not refresh_result.get('success'):
                    return {
                        'success': False,
                        'error': f'Failed to refresh Gmail token: {refresh_result.get("error")}',
                        'needs_refresh': True
                    }
                
                # Got new access token - update config and retry the send
                new_access_token = refresh_result['access_token']
                gmail_config['access_token'] = new_access_token  # Update the config for next uses
                
                # Retry with new token
                req2 = urllib.request.Request(api_url, data=payload.encode('utf-8'), method='POST')
                req2.add_header('Authorization', f'Bearer {new_access_token}')
                req2.add_header('Content-Type', 'application/json')
                
                try:
                    with urllib.request.urlopen(req2, timeout=5) as response2:
                        resp_data2 = json.loads(response2.read().decode('utf-8'))
                        msg_id2 = resp_data2.get('id', 'unknown')
                        print(f'[Gmail API SUCCESS after auto-refresh] → {recipient} [msg_id: {msg_id2}]')
                        return {'success': True, 'gmail_msg_id': msg_id2, 'new_access_token': new_access_token}
                except urllib.error.HTTPError as e2:
                    error_body2 = e2.read().decode('utf-8') if e2.fp else str(e2)
                    return {'success': False, 'error': f'Gmail API HTTP {e2.code} after refresh: {error_body2}'}
            
            # Not a 401 or no refresh token
            error_body = e.read().decode('utf-8') if e.fp else str(e)
            return {'success': False, 'error': f'Gmail API HTTP {e.code}: {error_body}'}
        except urllib.error.URLError as e:
            return {'success': False, 'error': f'Gmail API connection failed: {str(e.reason)}'}
            
    except Exception as e:
        return {'success': False, 'error': f'Gmail API error: {str(e)}'}


def send_email_ec2_gmail_api(ec2_url, gmail_config, from_name, recipient, subject, html_body, attachment=None, header_opts=None):
    """Send email via EC2 relay using Gmail API."""
    try:
        if not gmail_config:
            return {'success': False, 'error': 'EC2+Gmail API requires Gmail OAuth config'}

        gmail_user = gmail_config.get('user', '')
        sender_name = from_name if from_name and from_name != 'KINGMAILER' else gmail_config.get('sender_name', '')
        if sender_name == 'KINGMAILER': sender_name = ''
        from_header = _make_from_header(sender_name, gmail_user) if sender_name else gmail_user

        msg = _build_message(from_header, recipient, subject, html_body, attachment, header_opts=header_opts)
        raw_bytes = msg.as_bytes()
        raw_b64 = base64.b64encode(raw_bytes).decode('ascii')

        payload = {
            'type': 'gmail_api',
            'raw_email': raw_b64,
            'from_addr': gmail_user,
            'to_addr': recipient,
            'gmail_config': gmail_config,
        }

        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(ec2_url, data=data, method='POST')
        req.add_header('Content-Type', 'application/json')

        with urllib.request.urlopen(req, timeout=5) as response:
            resp_data = json.loads(response.read().decode('utf-8'))
            print(f'[EC2+Gmail API SUCCESS] → {recipient}')
            return {'success': True, 'response': resp_data}

    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else str(e)
        if 'SMTP config required' in error_body:
            return {
                'success': False,
                'error': (
                    'EC2 relay is running an old version without Gmail API mode. '
                    'Open EC2 Management and click "Fix Relay" (or restart relay) for this instance, '
                    'then try EC2+Gmail API again.'
                )
            }
        return {'success': False, 'error': f'EC2+Gmail API HTTP {e.code}: {error_body}'}
    except urllib.error.URLError as e:
        return {'success': False, 'error': f'EC2+Gmail API connection failed: {str(e.reason)}'}
    except Exception as e:
        return {'success': False, 'error': f'EC2+Gmail API failed: {str(e)}'}


def send_email_ses(aws_config, from_name, recipient, subject, html_body, attachment=None, header_opts=None):
    """Send single email via AWS SES with optional attachment support."""
    try:
        ses_client = boto3.client(
            'ses',
            region_name=aws_config.get('region', 'us-east-1'),
            aws_access_key_id=aws_config.get('access_key'),
            aws_secret_access_key=aws_config.get('secret_key')
        )
        from_email  = aws_config.get('from_email', 'noreply@example.com')
        source      = _make_from_header(from_name, from_email) if from_name else from_email

        # Always send raw so attachment + deliverability headers are preserved
        msg = _build_message(source, recipient, subject, html_body, attachment, header_opts=header_opts)
        ses_client.send_raw_email(
            Source=source,
            Destinations=[recipient],
            RawMessage={'Data': msg.as_string()}
        )
        return {'success': True}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def send_email_ec2(ec2_url, smtp_config, from_name, recipient, subject, html_body, attachment=None, header_opts=None):
    """Send email via EC2 relay — JetMailer style.
    Vercel builds the full MIME message, EC2 relay authenticates to your SMTP provider
    (Gmail/Outlook/Brevo/etc) on port 587 FROM the EC2 IP address.
    EC2 IP appears in email Received headers — no port 25 needed."""
    try:
        if not smtp_config:
            return {'success': False, 'error': 'EC2 relay requires SMTP config — add SMTP accounts in the SMTP Config tab first'}

        smtp_user = smtp_config.get('user', '')
        # Sanitize: treat 'KINGMAILER' as empty (legacy default, not a real name)
        _cfg_sn = smtp_config.get('sender_name', '')
        if _cfg_sn == 'KINGMAILER': _cfg_sn = ''
        sender_name = from_name if from_name and from_name != 'KINGMAILER' else _cfg_sn
        from_header = _make_from_header(sender_name, smtp_user) if sender_name else smtp_user

        print(f'[EC2 RELAY] Building MIME msg for {recipient} (from: {from_header})')

        # ── Build the full deliverability-optimized MIME message on Vercel ──
        msg = _build_message(from_header, recipient, subject, html_body, attachment, header_opts=header_opts)

        raw_b64 = base64.b64encode(msg.as_bytes()).decode('ascii')

        # ── Send raw MIME bytes + SMTP creds to relay ────────────────────────
        payload = {
            'type':        'raw',
            'raw_email':   raw_b64,
            'from_addr':   smtp_user,
            'to_addr':     recipient,
            # Force relay to send exact bytes from raw_email (no server-side rebuild).
            'strict_raw':  True,
            'smtp_config': smtp_config,
        }
        data = json.dumps(payload).encode('utf-8')
        req  = urllib.request.Request(ec2_url, data=data, method='POST')
        req.add_header('Content-Type', 'application/json')

        with urllib.request.urlopen(req, timeout=5) as response:
            resp_data = json.loads(response.read().decode('utf-8'))
            return {'success': True, 'response': resp_data}
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else str(e)
        return {'success': False, 'error': f'HTTP {e.code}: {error_body}'}
    except urllib.error.URLError as e:
        return {'success': False, 'error': f'Connection failed: {str(e.reason)}'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


class SMTPPool:
    """Round-robin account rotation pool with automatic account status checking."""
    def __init__(self, accounts, account_type='smtp'):
        self.accounts = accounts
        self.current_index = 0
        self.account_type = account_type

    def get_next(self):
        if not self.accounts:
            print(f"[POOL ERROR] No {self.account_type} accounts available")
            return None
        
        print(f"[POOL] Starting rotation for {len(self.accounts)} {self.account_type} accounts")
        
        # Try to find an active account, with a maximum number of attempts
        # to prevent infinite loops if all accounts are deactivated
        max_attempts = len(self.accounts)
        attempts = 0
        
        while attempts < max_attempts:
            account = self.accounts[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.accounts)
            
            # Generate account ID based on account type
            if self.account_type == 'smtp':
                account_id = account.get('user', account.get('server', 'unknown'))
                print(f"[POOL] Checking SMTP account - user: {account.get('user')}, server: {account.get('server')} → ID: {account_id}")
            elif self.account_type == 'ses':
                access_key = account.get('access_key_id', account.get('access_key', 'unknown'))
                account_id = f"{account.get('region', 'unknown')}_{access_key[:8]}"
                print(f"[POOL] Checking SES account - region: {account.get('region')}, access_key: {access_key[:8]} → ID: {account_id}")
            elif self.account_type == 'gmail_api':
                account_id = account.get('user', account.get('client_id', 'unknown')[:8])
                print(f"[POOL] Checking Gmail API account - user: {account.get('user')} → ID: {account_id}")
            else:
                account_id = 'unknown'
                print(f"[POOL] Unknown account type: {self.account_type}")
            
            # Check if account is active
            if is_account_active(account_id, self.account_type):
                print(f"[POOL SUCCESS] SUCCESS Using {self.account_type} account: {account_id}")
                return account
            else:
                print(f"[POOL SKIP] FAILED {self.account_type} account {account_id} is deactivated, trying next account")
                attempts += 1
        
        # If we reach here, all accounts are deactivated
        print(f"[POOL CRITICAL] CRITICAL ALL {self.account_type.upper()} ACCOUNTS ARE DEACTIVATED! Cannot send emails.")
        return None


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            # Handle both 'csv' and 'csv_data' parameters for backwards compatibility
            csv_data = data.get('csv_data', data.get('csv', ''))
            subject_template = data.get('subject', 'No Subject')
            html_template = data.get('html', '')
            method = data.get('method', 'smtp')
            # ⚡ TURBO MODE OPTIMIZED: 50+ emails/minute capability
            min_delay = int(data.get('min_delay', 100))    # 100ms (0.1s)
            max_delay = int(data.get('max_delay', 500))    # 500ms (0.5s)
            from_name = data.get('from_name', '') or ''
            from_email = data.get('from_email', '')

            # Header options (controls List-Unsubscribe / Precedence / Reply-To)
            _header_opts = data.get('header_opts', {}) or {}

            # Get account configs
            smtp_configs = data.get('smtp_configs', [])
            ses_configs = data.get('ses_configs', [])
            ec2_instances = data.get('ec2_instances', [])
            gmail_configs = data.get('gmail_configs', [])

            # Advisory logging only (non-blocking JetMailer approach)
            _attachment = data.get('attachment')
            if _is_html_attachment(_attachment):
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': 'HTML attachments are blocked for deliverability. Use PDF, PNG, or JPG.'}).encode())
                return

            _att_bytes, _att_err = _decode_attachment_bytes(_attachment)
            if _att_err:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': _att_err}).encode())
                return

            _risk_err = _message_risk_guard(subject_template, html_template, _attachment)
            if _risk_err:
                print(f'[CONTENT WARNING] {_risk_err}')

            _sender_for_auth = ''
            if method in ('smtp', 'ec2') and smtp_configs:
                _sender_for_auth = (smtp_configs[0] or {}).get('user', '')
            elif method == 'ses' and ses_configs:
                _sender_for_auth = (ses_configs[0] or {}).get('from_email', '')
            elif method in ('gmail_api', 'ec2_gmail_api') and gmail_configs:
                _sender_for_auth = (gmail_configs[0] or {}).get('user', '')

            _auth_err = _domain_auth_guard(_sender_for_auth, _header_opts)
            if _auth_err:
                print(f'[AUTH WARNING] {_auth_err}')
            
            # Debug logging
            print('='*50)
            print('BULK SEND DEBUG - Backend')
            print(f'Method selected: {method}')
            print(f'SMTP configs received: {len(smtp_configs)}')
            print(f'SES configs received: {len(ses_configs)}')
            print(f'Gmail API configs received: {len(gmail_configs)}')
            print(f'EC2 instances received: {len(ec2_instances)}')
            if ec2_instances:
                print(f'EC2 instance IPs: {[i.get("public_ip") for i in ec2_instances]}')
            print('='*50)
            
            if not csv_data:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': 'CSV data required'}).encode())
                return
            
            # Parse CSV
            csv_file = io.StringIO(csv_data)
            reader = csv.DictReader(csv_file)
            rows = list(reader)
            
            if not rows:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': 'No data in CSV'}).encode())
                return
            
            # Check for email column
            if 'email' not in rows[0]:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': 'CSV must have "email" column'}).encode())
                return
            
            # Initialize account pools
            smtp_pool = SMTPPool(smtp_configs, 'smtp') if smtp_configs else None
            ses_pool = SMTPPool(ses_configs, 'ses') if ses_configs else None
            ec2_pool = SMTPPool(ec2_instances, 'ec2') if ec2_instances else None
            gmail_pool = SMTPPool(gmail_configs, 'gmail_api') if gmail_configs else None
            
            # Send emails
            results = []
            success_count = 0
            fail_count = 0
            
            for index, row in enumerate(rows):
                recipient = row.get('email', '').strip()
                if not recipient:
                    continue
                
                # Process spintax first (creates unique variation)
                subject = process_spintax(subject_template)
                html_body = process_spintax(html_template)
                
                # Resolve sender name — supports "random" mode
                _use_random_name = data.get('random_sender_name', False)
                if _use_random_name:
                    import random as _r2
                    _fn = _r2.choice(['James','John','Robert','Michael','William','David','Richard',
                                       'Mary','Patricia','Jennifer','Linda','Barbara','Elizabeth',
                                       'Susan','Jessica','Sarah','Karen','Emily','Amanda'])
                    _ln = _r2.choice(['Smith','Johnson','Williams','Brown','Jones','Garcia','Miller',
                                       'Davis','Rodriguez','Martinez','Wilson','Anderson','Taylor'])
                    _eff_name = f"{_fn} {_ln}"
                else:
                    _eff_name = from_name

                # Resolve sender email from current SMTP account
                _cur_smtp = (smtp_pool.accounts[smtp_pool.current_index % max(1, len(smtp_pool.accounts))]
                             if smtp_pool and smtp_pool.accounts else {})
                _cur_s_email = _cur_smtp.get('user', from_email) if isinstance(_cur_smtp, dict) else from_email

                # Then replace template tags (including CSV columns, $tag and {{tag}})
                subject   = replace_template_tags(subject,   row, recipient,
                                                   sender_name=_eff_name, sender_email=_cur_s_email,
                                                   allow_single_brace=True)
                html_body = replace_template_tags(html_body, row, recipient,
                                                   sender_name=_eff_name, sender_email=_cur_s_email)
                
                # Deliverability: Filter high-risk spam keywords
                subject = minimize_spam_keywords(subject)
                html_body = minimize_spam_keywords(html_body)

                # Send email based on method
                attachment = data.get('attachment')  # {name, content (base64), type}

                if method == 'smtp' and smtp_pool:
                    smtp_config = smtp_pool.get_next()
                    if smtp_config is None:
                        result = {'success': False, 'error': 'All SMTP accounts are deactivated'}
                    else:
                        account_id = smtp_config.get('user', smtp_config.get('server', 'unknown'))
                        print(f'\n[EMAIL {index+1}] Method: SMTP → {recipient} (Account: {account_id})')
                        result = send_email_smtp(smtp_config, _eff_name, recipient, subject, html_body, attachment, header_opts=_header_opts)
                        
                        # Track result
                        if result.get('success'):
                            track_send_success(account_id, 'smtp')
                        else:
                            track_send_failure(account_id, 'smtp', str(result.get('error', 'Unknown SMTP error')))

                elif method == 'ses' and ses_pool:
                    ses_config = ses_pool.get_next()
                    if ses_config is None:
                        result = {'success': False, 'error': 'All SES accounts are deactivated'}
                    else:
                        account_id = f"{ses_config.get('region', 'unknown')}_{ses_config.get('access_key_id', 'unknown')[:8]}"
                        print(f'\n[EMAIL {index+1}] Method: SES → {recipient} (Account: {account_id})')
                        result = send_email_ses(ses_config, _eff_name, recipient, subject, html_body, attachment, header_opts=_header_opts)
                        
                        # Track result
                        if result.get('success'):
                            track_send_success(account_id, 'ses')
                        else:
                            track_send_failure(account_id, 'ses', str(result.get('error', 'Unknown SES error')))
                
                elif method == 'gmail_api' and gmail_pool:
                    gmail_config = gmail_pool.get_next()
                    if gmail_config is None:
                        result = {'success': False, 'error': 'All Gmail API accounts are deactivated'}
                    else:
                        account_id = gmail_config.get('user', gmail_config.get('client_id', 'unknown')[:8])
                        print(f'\n[EMAIL {index+1}] Method: Gmail API → {recipient} (Account: {account_id})')
                        result = send_email_gmail_api(gmail_config, _eff_name, recipient, subject, html_body, attachment, header_opts=_header_opts)
                        
                        # Track result
                        if result.get('success'):
                            track_send_success(account_id, 'gmail_api')
                        else:
                            track_send_failure(account_id, 'gmail_api', str(result.get('error', 'Unknown Gmail API error')))
                
                elif method == 'ec2_gmail_api' and ec2_pool and gmail_pool:
                    ec2_instance = ec2_pool.get_next()
                    gmail_config = gmail_pool.get_next()
                    
                    if gmail_config is None:
                        result = {'success': False, 'error': 'All Gmail API accounts are deactivated'}
                    elif ec2_instance is None:
                        result = {'success': False, 'error': 'All EC2 instances are deactivated'}
                    else:
                        account_id = gmail_config.get('user', gmail_config.get('client_id', 'unknown')[:8])
                        ec2_ip = ec2_instance.get('public_ip') if isinstance(ec2_instance, dict) else None
                        
                        if ec2_ip and ec2_ip not in ('N/A', 'Pending...'):
                            ec2_url = f'http://{ec2_ip}:3000/relay'
                            print(f'\n[EMAIL {index+1}] Method: EC2+Gmail API → {recipient} (via {ec2_ip}, Account: {account_id})')
                            result = send_email_ec2_gmail_api(ec2_url, gmail_config, _eff_name, recipient, subject, html_body, attachment, header_opts=_header_opts)
                            
                            # Track result
                            if result.get('success'):
                                track_send_success(account_id, 'gmail_api')
                            else:
                                track_send_failure(account_id, 'gmail_api', str(result.get('error', 'Unknown EC2+Gmail API error')))
                        else:
                            result = {'success': False, 'error': 'EC2 instance has no public IP'}
                
                elif method == 'ec2' and ec2_pool:
                    ec2_instance = ec2_pool.get_next()
                    smtp_config = smtp_pool.get_next() if smtp_pool else None

                    print(f'\n[EMAIL {index+1}] Method: EC2 RELAY → {recipient}')

                    if ec2_instance is None:
                        result = {'success': False, 'error': 'All EC2 instances are deactivated'}
                    elif smtp_config is None and smtp_pool:
                        result = {'success': False, 'error': 'All SMTP accounts are deactivated'}
                    elif ec2_instance:
                        ec2_ip = ec2_instance.get('public_ip')
                        if ec2_ip and ec2_ip != 'N/A' and ec2_ip != 'Pending...':
                            relay_url = f'http://{ec2_ip}:3000/relay'
                            print(f'[EC2 RELAY] Connecting to {relay_url}')
                            result = send_email_ec2(relay_url, smtp_config, _eff_name, recipient, subject, html_body, attachment, header_opts=_header_opts)
                            
                            if result['success']:
                                result['via_ec2_ip'] = ec2_ip
                                if smtp_config:
                                    account_id = smtp_config.get('user', smtp_config.get('server', 'unknown'))
                                    track_send_success(account_id, 'smtp')
                            else:
                                result['error'] = f"EC2 relay failed ({ec2_ip}:3000): {result.get('error', 'Unknown error')}"
                                if smtp_config:
                                    account_id = smtp_config.get('user', smtp_config.get('server', 'unknown'))
                                    track_send_failure(account_id, 'smtp', str(result['error']))
                        else:
                            result = {'success': False, 'error': 'EC2 instance has no public IP yet'}
                    else:
                        result = {'success': False, 'error': 'No EC2 instances available'}
                
                else:
                    result = {'success': False, 'error': f'No {method} accounts configured'}
                
                if result['success']:
                    success_count += 1
                    results.append({'email': recipient, 'status': 'sent'})
                else:
                    fail_count += 1
                    results.append({'email': recipient, 'status': 'failed', 'error': result.get('error', 'Unknown')})
                
                # ⚡ TURBO OPTIMIZED: Fast sending with minimal delays
                if index < len(rows) - 1:
                    # Calculate optimal delay for target rate
                    target_emails_per_minute = 50  # Target rate
                    optimal_delay = 60.0 / target_emails_per_minute  # 1.2 seconds for 50/min
                    
                    # Use optimal delay if within config bounds
                    delay_ms = random.randint(min_delay, max_delay)
                    if delay_ms <= (optimal_delay * 1000):  # If config allows target rate
                        delay = delay_ms / 1000.0
                        print(f"[TURBO] Fast mode: {delay:.2f}s delay ({60/delay:.0f} emails/min potential)")
                    else:
                        delay = optimal_delay
                        print(f"[TURBO] Optimal rate: {delay:.2f}s delay (50 emails/min)")
                    
                    time.sleep(delay)
            
            response_data = {
                'success': True,
                'message': f'Bulk send completed: {success_count} sent, {fail_count} failed',
                'results': {
                    'total': len(rows),
                    'sent': success_count,
                    'failed': fail_count,
                    'details': results
                }
            }
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(response_data).encode())
        
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
