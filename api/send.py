"""
KINGMAILER v5.8 - Email Sending API (Inbox-Optimised)
Features: SMTP, AWS SES, EC2 Relay, Spintax, Placeholders, Attachments

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
from botocore.exceptions import ClientError
import json
import re
import random
import string
import urllib.request
import urllib.error
from datetime import datetime
import base64
import uuid
import quopri
import os


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
    """Track successful email send"""
    account_stats = load_account_stats()
    
    if account_type not in account_stats:
        account_stats[account_type] = {}
    
    if account_id not in account_stats[account_type]:
        account_stats[account_type][account_id] = initialize_account_stats(account_id, account_type)
    
    # Reset failed attempts on success and increment send count
    account_stats[account_type][account_id]['failed_attempts'] = 0
    account_stats[account_type][account_id]['emails_sent'] += 1
    account_stats[account_type][account_id]['is_active'] = True
    
    save_account_stats(account_stats)
    print(f"✅ SUCCESS TRACKED: {account_type} {account_id} - Total sent: {account_stats[account_type][account_id]['emails_sent']}")

def track_send_failure(account_id, account_type, error_msg=""):
    """Track failed email send and deactivate account if needed"""
    account_stats = load_account_stats()
    
    if account_type not in account_stats:
        account_stats[account_type] = {}
    
    if account_id not in account_stats[account_type]:
        account_stats[account_type][account_id] = initialize_account_stats(account_id, account_type)
    
    # Increment failure counters
    account_stats[account_type][account_id]['failed_attempts'] += 1
    account_stats[account_type][account_id]['total_failures'] += 1
    account_stats[account_type][account_id]['last_failure'] = datetime.now().isoformat()
    
    # Deactivate account after 3 consecutive failures
    if account_stats[account_type][account_id]['failed_attempts'] >= 3:
        account_stats[account_type][account_id]['is_active'] = False
        print(f"🚨 ACCOUNT DEACTIVATED: {account_type} account '{account_id}' deactivated after 3 consecutive failures")
        print(f"   Last error: {error_msg}")
        save_account_stats(account_stats)
        return True  # Account was deactivated
    
    save_account_stats(account_stats)
    print(f"⚠️ FAILURE TRACKED: {account_type} {account_id} - Attempt {account_stats[account_type][account_id]['failed_attempts']}/3")
    return False  # Account still active

def is_account_active(account_id, account_type):
    """Check if an account is active (not deactivated due to failures)"""
    account_stats = load_account_stats()
    
    if account_type not in account_stats:
        print(f"[ACCOUNT_CHECK] ✅ {account_type} account '{account_id}' - no stats found, assuming active")
        return True
    
    if account_id not in account_stats[account_type]:
        print(f"[ACCOUNT_CHECK] ✅ {account_type} account '{account_id}' - not tracked yet, assuming active")
        return True
        
    is_active = account_stats[account_type][account_id].get('is_active', True)
    failed_attempts = account_stats[account_type][account_id].get('failed_attempts', 0)
    
    if not is_active:
        print(f"[ACCOUNT_CHECK] 🚨 BLOCKED: {account_type} account '{account_id}' is DEACTIVATED (failed_attempts: {failed_attempts}) - REJECTING SEND")
        return False
    else:
        print(f"[ACCOUNT_CHECK] ✅ {account_type} account '{account_id}' is ACTIVE (failed_attempts: {failed_attempts})")
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


# ── Placeholder data pools ──────────────────────────────────────────────────
_US_FIRST = ['James','John','Robert','Michael','William','David','Richard','Joseph','Thomas','Charles',
             'Mary','Patricia','Jennifer','Linda','Barbara','Elizabeth','Susan','Jessica','Sarah','Karen',
             'Emily','Amanda','Stephanie','Rebecca','Laura','Sharon','Cynthia','Dorothy','Amy','Anna']
_US_LAST  = ['Smith','Johnson','Williams','Brown','Jones','Garcia','Miller','Davis','Rodriguez','Martinez',
             'Wilson','Anderson','Taylor','Thomas','Hernandez','Moore','Martin','Jackson','Thompson','White']
_US_CITIES = [
    ('New York','NY','10001'),('Los Angeles','CA','90001'),('Chicago','IL','60601'),
    ('Houston','TX','77001'),('Phoenix','AZ','85001'),('Philadelphia','PA','19101'),
    ('San Antonio','TX','78201'),('San Diego','CA','92101'),('Dallas','TX','75201'),
    ('Austin','TX','78701'),('Seattle','WA','98101'),('Denver','CO','80201'),
    ('Nashville','TN','37201'),('Charlotte','NC','28201'),('Boston','MA','02101'),
    ('Las Vegas','NV','89101'),('Miami','FL','33101'),('Atlanta','GA','30301'),
    ('Portland','OR','97201'),('Detroit','MI','48201'),
]
_US_STREETS   = ['Main St','Oak Ave','Maple Dr','Pine Blvd','Cedar Lane','Elm Rd',
                 'Washington Blvd','Park Ave','Lake Dr','Hillside Way','Sunset Blvd',
                 'River Rd','Forest Ave','Valley Dr','Summit Rd']
_US_COMPANIES = ['Apex Solutions LLC','Bright Path Inc','Cascade Digital Corp','Delta Group',
                 'Everest Ventures','Frontier Services Co','Global Tech Inc','Harbor Networks LLC',
                 'Inland Systems Corp','Jade Analytics','Keystone Consulting','Lighthouse Media',
                 'Meridian Group LLC','Nexus Innovations','Oakwood Industries','Pinnacle Growth Inc',
                 'Quantum Systems','Ridgeline Corp','Summit Partners LLC','Trident Enterprises']
_US_PRODUCTS  = ['Premium Membership','Express Delivery','Annual Plan','Business Package',
                 'Standard Subscription','Pro License','Elite Bundle','Starter Kit',
                 'Enterprise Plan','Monthly Service','Digital Package','Advanced Suite']


def _rnd_num(n):
    return ''.join(random.choices(string.digits, k=n))
def _rnd_alpha(n):
    return ''.join(random.choices(string.ascii_lowercase, k=n))
def _rnd_alphanum(n, upper=False):
    pool = (string.ascii_uppercase if upper else string.ascii_lowercase) + string.digits
    return ''.join(random.choices(pool, k=n))


def build_tag_map(recipient_email='', sender_name='', sender_email='', csv_row=None):
    """Build a fresh mapping of all $tag and {{tag}} placeholder values."""
    first = random.choice(_US_FIRST)
    last  = random.choice(_US_LAST)
    city, state, zipcode = random.choice(_US_CITIES)
    sn = random.randint(100, 9999)
    st = random.choice(_US_STREETS)
    ts13 = str(int(datetime.now().timestamp() * 1000))[:13]
    m = {
        'name':          recipient_email.split('@')[0] if recipient_email else (first+' '+last),
        'email':         recipient_email,
        'recipient':     recipient_email,
        'recipientName': first + ' ' + last,
        'sender':        sender_email,
        'sendername':    sender_name or (sender_email.split('@')[0] if sender_email and '@' in sender_email else 'Support Team'),
        'sendertag':     f"{sender_name} <{sender_email}>" if sender_name else sender_email,
        'randName':      f"{first} {last}",
        'rnd_company_us': random.choice(_US_COMPANIES),
        'address':       f"{sn} {st}, {city}, {state} {zipcode}",
        'street':        f"{sn} {st}",
        'city':          city,
        'state':         state,
        'zipcode':       zipcode,
        'zip':           zipcode,
        'invcnumber':    'INV-' + _rnd_num(8),
        'ordernumber':   'ORD-' + _rnd_num(8),
        'product':       random.choice(_US_PRODUCTS),
        'amount':        f"${random.randint(999, 99999)/100:.2f}",
        'charges':       f"${random.randint(499, 49999)/100:.2f}",
        'quantity':      str(random.randint(1, 99)),
        'number':        _rnd_num(6),
        'date':          datetime.now().strftime('%B %d, %Y'),
        'time':          datetime.now().strftime('%I:%M %p'),
        'year':          str(datetime.now().year),
        'id':            _rnd_num(10),
        'random_name':   f"{first} {last}",
        'company':       random.choice(_US_COMPANIES),
        'company_name':  random.choice(_US_COMPANIES),
        '13_digit':      ts13,
        'unique_id':     ts13,
        'unique13digit': ts13,
        'random_6':      ''.join(random.choices(string.ascii_letters + string.digits, k=6)),
        'random_8':      ''.join(random.choices(string.ascii_letters + string.digits, k=8)),
        'unique16_484':      f"{_rnd_num(4)}-{_rnd_num(8)}-{_rnd_num(4)}",
        'unique16_565':      f"{_rnd_num(5)}-{_rnd_num(6)}-{_rnd_num(5)}",
        'unique16_4444':     f"{_rnd_num(4)}-{_rnd_num(4)}-{_rnd_num(4)}-{_rnd_num(4)}",
        'unique16_88':       f"{_rnd_num(8)}-{_rnd_num(8)}",
        'unique14alphanum':  _rnd_alphanum(14, upper=True),
        'unique11alphanum':  _rnd_alphanum(11, upper=True),
        'unique14alpha':     _rnd_alpha(14).upper(),
        'alpha_random_small': _rnd_alpha(6),
        'alpha_short':        _rnd_alpha(4),
        'random_three_chars': _rnd_alphanum(3),
    }
    # Derive first/last from sender_name for fname/lname tags
    _sn_parts = (sender_name or '').strip().split()
    _fname = _sn_parts[0] if _sn_parts else first
    _lname = ' '.join(_sn_parts[1:]) if len(_sn_parts) > 1 else last
    m['fname']       = _fname
    m['lname']       = _lname
    m['firstname']   = _fname
    m['lastname']    = _lname
    m['fullname']    = f"{first} {last}"
    m['sender_name'] = sender_name or (sender_email.split('@')[0] if sender_email and '@' in sender_email else 'Support Team')
    if csv_row:
        for k, v in csv_row.items():
            if k:
                m[k] = str(v)
    return m


def replace_template_tags(text, recipient_email='', sender_name='', sender_email='', csv_row=None, allow_single_brace=False):
    """Replace ALL $tag and {{tag}} placeholders in text."""
    if not text:
        return text
    tag_map = build_tag_map(recipient_email, sender_name, sender_email, csv_row)
    sorted_keys = sorted(tag_map.keys(), key=len, reverse=True)
    for key in sorted_keys:
        val = str(tag_map[key])
        # Use lambda to prevent re.sub from interpreting \ in val as backreferences
        text = re.sub(r'\{\{' + re.escape(key) + r'\}\}', lambda m, v=val: v, text, flags=re.IGNORECASE)
        text = re.sub(r'\$' + re.escape(key) + r'(?=[^a-zA-Z0-9_]|$)', lambda m, v=val: v, text, flags=re.IGNORECASE)
        if allow_single_brace:
            text = re.sub(r'\{' + re.escape(key) + r'\}', lambda m, v=val: v, text, flags=re.IGNORECASE)
    return text


def replace_csv_row_tags(text, row):
    """Replace {{column}} placeholders with CSV row values."""
    if not text or not row:
        return text
    for key, value in row.items():
        text = re.sub(r'\{\{' + re.escape(key) + r'\}\}', str(value), text, flags=re.IGNORECASE)
    return text

def _clean_mime(part, is_root=True):
    """Recursively ensure ONLY the root part has MIME-Version: 1.0.
    Standard mail clients (Apple Mail, Gmail) only set this once.
    """
    if not is_root and 'MIME-Version' in part:
        del part['MIME-Version']
    if part.is_multipart():
        for sub in part.get_payload():
            if hasattr(sub, 'add_header'):
                _clean_mime(sub, is_root=False)

# Image MIME types that can be embedded inline
_IMAGE_TYPES = {'image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp', 'image/bmp', 'image/tiff'}
_IMAGE_EXTS  = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff', '.tif'}

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


def minimize_spam_keywords(text):
    """DEPRECATED — no longer called.

    Word-substitution approaches (Free → Complementary, Important → Significant) are
    counterproductive against modern ML-based spam classifiers (Gmail, Outlook, SpamAssassin).
    Unnatural word choices are themselves a spam fingerprint — the filter detects that you
    are trying to evade it. This function is kept only so existing call-sites don't crash;
    it is a no-op and will be fully removed in the next major version.
    """
    return text  # no-op

def _extract_domain(from_header):
    """Extract clean domain from From header like 'Name <user@domain.com>'."""
    if '@' in from_header:
        part = from_header.split('@')[-1]
        # Remove trailing > or whitespace
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
    """Block sending when critical SPF/DMARC/MX issues exist."""
    opts = header_opts or {}
    if opts.get('skip_auth_guard'):
        return None

    if not sender_email or '@' not in sender_email:
        return 'Sender email missing for domain-auth verification.'

    domain = sender_email.split('@')[-1].strip().lower()
    if not domain:
        return 'Invalid sender domain for domain-auth verification.'

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
        # If checker is unavailable, do not hard-fail; allow send and rely on frontend guard.
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
    """Block high-risk content/attachment patterns."""
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
    return '<!-- mid:' + uid + ' -->\n'


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
        # ASCII name — use formataddr to correctly quote special chars (commas, quotes…)
        from email.utils import formataddr as _fmt
        return _fmt((sender_name, email_addr))
    except (UnicodeEncodeError, UnicodeDecodeError):
        # Non-ASCII name: RFC 2047 encoded-word format
        from email.header import Header as _Hdr
        return '{} <{}>'.format(_Hdr(sender_name, 'utf-8').encode(), email_addr)


def _build_msg(from_header, to_email, subject, html_body, attachment=None, header_opts=None):
    """Build RFC-compliant MIME message — inbox-optimised."""
    import mimetypes
    _o = dict(header_opts or {})
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

    # Ensure proper HTML document structure
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

    domain = _extract_domain(from_header)
    if _is_webmail_sender(from_header):
        # Webmail senders get better placement with minimal headers.
        _o['reply_to'] = False
        _o['precedence_bulk'] = False
        _o['list_unsubscribe'] = False
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
            # ── CID inline image: multipart/related so <img src="cid:filename"> resolves ──
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

    # ── Headers: clean minimal set — every extra header is a potential spam signal ──
    # DELIBERATELY OMITTED (spam triggers):
    #   X-Mailer          — fake client identity detected by all major filters
    #   X-Entity-ID       — non-standard, automated-bulk-sender fingerprint
    #   X-Msg-Ref         — non-standard, automated-bulk-sender fingerprint
    #   Thread-Topic      — Outlook MAPI-only header, contradicts any other X-Mailer
    #   Thread-Index      — same as Thread-Topic
    #   Importance/X-Priority — bulk-mail markers, push to Promotions/Spam
    # Keep headers minimal and standards-based.
    _uid = uuid.uuid4().hex
    msg['From']       = from_header
    msg['To']         = to_email
    msg['Subject']    = _encode_subject(subject)
    msg['Date']       = formatdate(localtime=True)
    msg['Message-ID'] = f'<{_uid}@{domain}>'
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


def send_via_smtp(smtp_config, from_name, to_email, subject, html_body, attachment=None, header_opts=None):
    """Send email via SMTP (Gmail or custom server)"""
    try:
        is_gmail = smtp_config.get('provider') == 'gmail'
        smtp_server = 'smtp.gmail.com' if is_gmail else smtp_config.get('host', 'smtp.gmail.com')
        smtp_port   = 587             if is_gmail else int(smtp_config.get('port', 587))

        smtp_user = smtp_config.get('user')
        smtp_pass = smtp_config.get('pass')
        # Sanitize: treat 'KINGMAILER' as empty (legacy default, not a real name)
        _cfg_sn = smtp_config.get('sender_name') or ''
        if _cfg_sn == 'KINGMAILER': _cfg_sn = ''
        sender_name = from_name if from_name and from_name != 'KINGMAILER' else _cfg_sn
        from_header = _make_from_header(sender_name, smtp_user) if sender_name else smtp_user

        # _build_msg handles ALL attachment types (image + non-image) internally
        msg = _build_msg(from_header, to_email, subject, html_body, attachment, header_opts=header_opts)

        _ehlo_host = _extract_domain(smtp_user or '')
        with smtplib.SMTP(smtp_server, smtp_port, timeout=30,
                           local_hostname=_ehlo_host if _ehlo_host != 'mail.local' else None) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)

        return {'success': True, 'message': f'Email sent via SMTP to {to_email}', 'from_name': sender_name or smtp_user}

    except smtplib.SMTPAuthenticationError:
        return {'success': False, 'error': 'SMTP authentication failed — check your Gmail app password'}
    except smtplib.SMTPRecipientsRefused:
        return {'success': False, 'error': f'Recipient address rejected: {to_email}'}
    except Exception as e:
        return {'success': False, 'error': f'SMTP error: {str(e)}'}


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
        
        with urllib.request.urlopen(req, timeout=10) as response:
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


def send_via_gmail_api(gmail_config, from_name, to_email, subject, html_body, attachment=None, header_opts=None):
    """Send email via Gmail API (OAuth2) with automatic token refresh."""
    try:
        # Gmail API requires OAuth2 credentials
        access_token = gmail_config.get('access_token', '').strip()
        refresh_token = gmail_config.get('refresh_token', '').strip()
        client_id = gmail_config.get('client_id', '').strip()
        client_secret = gmail_config.get('client_secret', '').strip()
        gmail_user = gmail_config.get('user', '').strip()
        
        if not all([access_token, client_id, client_secret, gmail_user]):
            return {'success': False, 'error': 'Gmail API requires: access_token, client_id, client_secret, and user email'}
        
        # Build MIME message
        sender_name = from_name if from_name and from_name != 'KINGMAILER' else gmail_config.get('sender_name', '')
        if sender_name == 'KINGMAILER': sender_name = ''
        from_header = _make_from_header(sender_name, gmail_user) if sender_name else gmail_user
        msg = _build_msg(from_header, to_email, subject, html_body, attachment, header_opts=header_opts)
        
        # Encode message for Gmail API
        raw_msg = base64.urlsafe_b64encode(msg.as_bytes()).decode('utf-8')
        
        # Make direct HTTP request to Gmail API (no library needed)
        import urllib.request
        import urllib.error
        
        api_url = 'https://gmail.googleapis.com/gmail/v1/users/me/messages/send'
        payload = json.dumps({'raw': raw_msg})
        
        # First attempt with current access token
        req = urllib.request.Request(api_url, data=payload.encode('utf-8'), method='POST')
        req.add_header('Authorization', f'Bearer {access_token}')
        req.add_header('Content-Type', 'application/json')
        
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                resp_data = json.loads(response.read().decode('utf-8'))
                msg_id = resp_data.get('id', 'unknown')
                return {
                    'success': True,
                    'message': f'Email sent via Gmail API to {to_email}',
                    'gmail_msg_id': msg_id,
                    'from_name': sender_name or gmail_user
                }
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
                
                # Got new access token - retry the send
                new_access_token = refresh_result['access_token']
                
                # Retry with new token
                req2 = urllib.request.Request(api_url, data=payload.encode('utf-8'), method='POST')
                req2.add_header('Authorization', f'Bearer {new_access_token}')
                req2.add_header('Content-Type', 'application/json')
                
                try:
                    with urllib.request.urlopen(req2, timeout=30) as response2:
                        resp_data2 = json.loads(response2.read().decode('utf-8'))
                        msg_id2 = resp_data2.get('id', 'unknown')
                        return {
                            'success': True,
                            'message': f'Email sent via Gmail API to {to_email} (token auto-refreshed)',
                            'gmail_msg_id': msg_id2,
                            'from_name': sender_name or gmail_user,
                            'new_access_token': new_access_token  # Return to frontend for storage update
                        }
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


def send_via_ses(aws_config, from_name, to_email, subject, html_body, attachment=None, header_opts=None):
    """Send email via AWS SES"""
    try:
        ses_client = boto3.client(
            'ses',
            region_name=aws_config.get('region', 'us-east-1'),
            aws_access_key_id=aws_config.get('access_key'),
            aws_secret_access_key=aws_config.get('secret_key')
        )
        
        from_email = aws_config.get('from_email', 'noreply@example.com')
        source = _make_from_header(from_name, from_email) if from_name else from_email

        # Always use raw send path so attachment + deliverability headers are preserved
        msg = _build_msg(source, to_email, subject, html_body, attachment, header_opts=header_opts)
        response = ses_client.send_raw_email(
            Source=source, Destinations=[to_email],
            RawMessage={'Data': msg.as_string()}
        )
        
        from_n = from_name or from_email
        return {'success': True, 'message': f'Email sent via SES to {to_email}', 'from_name': from_n, 'message_id': response['MessageId']}
    except Exception as e:
        return {'success': False, 'error': f'SES error: {str(e)}'}


def send_via_ec2(ec2_url, smtp_config, from_name, to_email, subject, html_body, attachment=None, header_opts=None):
    """Send email via EC2 relay — JetMailer style.
    Vercel builds the full MIME message, EC2 relay authenticates to your SMTP provider
    (Gmail/Outlook/Brevo/etc) on port 587 FROM the EC2 IP address.
    This means the EC2 IP appears in email Received headers — no port 25 needed."""
    try:
        if not smtp_config:
            return {'success': False, 'error': 'EC2 relay requires SMTP config — add SMTP accounts in the SMTP Config tab first'}

        smtp_user = smtp_config.get('user', '')
        # Sanitize: treat 'KINGMAILER' as empty (legacy default, not a real name)
        _cfg_sn = smtp_config.get('sender_name', '')
        if _cfg_sn == 'KINGMAILER': _cfg_sn = ''
        sender_name = from_name if from_name and from_name != 'KINGMAILER' else _cfg_sn
        from_header = _make_from_header(sender_name, smtp_user) if sender_name else smtp_user

        # ── Build the fully deliverability-optimized MIME message on Vercel ────────
        msg = _build_msg(from_header, to_email, subject, html_body, attachment, header_opts=header_opts)

        # Serialize full message to bytes and base64-encode for JSON transport
        raw_bytes = msg.as_bytes()
        raw_b64   = base64.b64encode(raw_bytes).decode('ascii')

        # ── Send raw email + SMTP creds to relay ─────────────────────────────────
        payload = {
            'type':        'raw',               # relay authenticates with smtp_config
            'raw_email':   raw_b64,             # base64-encoded complete MIME message
            'from_addr':   smtp_user,           # SMTP envelope From
            'to_addr':     to_email,            # SMTP envelope To
            # Force relay to send exact bytes from raw_email (no server-side rebuild).
            'strict_raw':  True,
            'smtp_config': smtp_config,         # SMTP credentials relay uses to authenticate
        }

        data = json.dumps(payload).encode('utf-8')
        req  = urllib.request.Request(ec2_url, data=data, method='POST')
        req.add_header('Content-Type', 'application/json')

        with urllib.request.urlopen(req, timeout=30) as response:
            resp_data = json.loads(response.read().decode('utf-8'))
            return {'success': True, 'response': resp_data, 'from_name': sender_name or smtp_user}

    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else str(e)
        return {'success': False, 'error': f'HTTP {e.code}: {error_body}'}
    except urllib.error.URLError as e:
        return {'success': False, 'error': f'Connection failed: {str(e.reason)}'}
    except Exception as e:
        return {'success': False, 'error': f'EC2 relay failed: {str(e)}'}


def send_via_ec2_gmail_api(ec2_url, gmail_config, from_name, to_email, subject, html_body, attachment=None, header_opts=None):
    """Send email via EC2 relay using Gmail API (EC2 IP + Gmail OAuth)."""
    try:
        if not gmail_config:
            return {'success': False, 'error': 'EC2+Gmail API requires Gmail OAuth config'}

        gmail_user = gmail_config.get('user', '')
        sender_name = from_name if from_name and from_name != 'KINGMAILER' else gmail_config.get('sender_name', '')
        if sender_name == 'KINGMAILER': sender_name = ''
        from_header = _make_from_header(sender_name, gmail_user) if sender_name else gmail_user

        # Build MIME message
        msg = _build_msg(from_header, to_email, subject, html_body, attachment, header_opts=header_opts)
        raw_bytes = msg.as_bytes()
        raw_b64 = base64.b64encode(raw_bytes).decode('ascii')

        # Send to EC2 relay with gmail_api mode
        payload = {
            'type': 'gmail_api',              # relay will use Gmail API
            'raw_email': raw_b64,  
            'from_addr': gmail_user,
            'to_addr': to_email,
            'gmail_config': gmail_config,     # OAuth credentials for EC2 to use
        }

        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(ec2_url, data=data, method='POST')
        req.add_header('Content-Type', 'application/json')

        with urllib.request.urlopen(req, timeout=30) as response:
            resp_data = json.loads(response.read().decode('utf-8'))
            return {'success': True, 'response': resp_data, 'from_name': sender_name or gmail_user}

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


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            to_email = data.get('to', '').strip()
            subject = data.get('subject', 'No Subject')
            html_body = data.get('html', '')
            from_name = data.get('from_name', '') or ''
            from_email = data.get('from_email', '')
            send_method = data.get('method', 'smtp')
            csv_row = data.get('csv_row', {})
            attachment = data.get('attachment')  # {name, content (base64), type}
            
            if not to_email:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': 'Recipient email required'}).encode())
                return
            
            # Basic email validation
            if not re.match(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$', to_email):
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': f'Invalid email format: {to_email}'}).encode())
                return
            
            # Process spintax in subject and body
            subject = process_spintax(subject)
            html_body = process_spintax(html_body)
            
            # Replace CSV row placeholders first (so column values override generics)
            if csv_row:
                subject = replace_csv_row_tags(subject, csv_row)
                html_body = replace_csv_row_tags(html_body, csv_row)
            
            # Extract sender info for $sendername etc.
            _smtp_cfg  = data.get('smtp_config') or {}
            _aws_cfg   = data.get('aws_config')  or {}
            # from_name from frontend takes priority (it's the random/manual name)
            # Only fall back to smtp_config.sender_name if from_name is missing/empty/KINGMAILER
            _raw_from = data.get('from_name', '')
            _cfg_name = _smtp_cfg.get('sender_name', '')
            if _cfg_name == 'KINGMAILER': _cfg_name = ''  # legacy default, treat as empty
            _s_name = (_raw_from if _raw_from and _raw_from != 'KINGMAILER'
                       else _cfg_name
                       or _smtp_cfg.get('user', '')
                       or _aws_cfg.get('from_email', '')
                       or '')
            _s_email = (_smtp_cfg.get('user') or
                        _aws_cfg.get('from_email') or
                        data.get('from_email') or '')

            # Header options (controls List-Unsubscribe / Precedence / Reply-To)
            _header_opts = data.get('header_opts', {}) or {}

            # Advisory logging only (non-blocking JetMailer approach)
            _auth_err = _domain_auth_guard(_s_email, _header_opts)
            if _auth_err:
                print(f'[AUTH WARNING] {_auth_err}')

            _risk_err = _message_risk_guard(subject, html_body, attachment)
            if _risk_err:
                print(f'[CONTENT WARNING] {_risk_err}')

            # Replace standard template tags ($tag and {{tag}} syntax)
            subject   = replace_template_tags(subject,   recipient_email=to_email,
                                               sender_name=_s_name, sender_email=_s_email,
                                               csv_row=csv_row, allow_single_brace=True)
            html_body = replace_template_tags(html_body, recipient_email=to_email,
                                               sender_name=_s_name, sender_email=_s_email,
                                               csv_row=csv_row)

            if _is_html_attachment(attachment):
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': 'HTML attachments are blocked for deliverability. Use PDF, PNG, or JPG.'}).encode())
                return

            _att_bytes, _att_err = _decode_attachment_bytes(attachment)
            if _att_err:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': _att_err}).encode())
                return
            
            # Minimize Spam Trigger words
            subject = minimize_spam_keywords(subject)
            html_body = minimize_spam_keywords(html_body)
            
            # Route to appropriate sending method
            if send_method == 'smtp' or send_method == 'gmail':
                smtp_config = data.get('smtp_config')
                if not smtp_config:
                    self.send_response(400)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({'success': False, 'error': 'SMTP config required'}).encode())
                    return
                
                # Check if SMTP account is active before attempting to send  
                account_id = smtp_config.get('user', smtp_config.get('username', smtp_config.get('server', 'unknown')))
                if not is_account_active(account_id, 'smtp'):
                    self.send_response(400)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        'success': False, 
                        'error': f'SMTP account "{account_id}" is deactivated due to previous failures. Please check Account Stats to reactivate.'
                    }).encode())
                    return
                
                result = send_via_smtp(smtp_config, from_name, to_email, subject, html_body, attachment, header_opts=_header_opts)
                
                # Track success or failure
                if result.get('success'):
                    track_send_success(account_id, 'smtp')
                else:
                    track_send_failure(account_id, 'smtp', result.get('error', 'Unknown SMTP error'))
            
            elif send_method == 'ses':
                aws_config = data.get('aws_config')
                if not aws_config:
                    self.send_response(400)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({'success': False, 'error': 'AWS SES config required'}).encode())
                    return
                
                # Check if SES account is active before attempting to send
                account_id = f"{aws_config.get('region', 'unknown')}_{aws_config.get('access_key', aws_config.get('access_key_id', 'unknown'))[:8]}"
                if not is_account_active(account_id, 'ses'):
                    self.send_response(400)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        'success': False, 
                        'error': f'SES account "{account_id}" is deactivated due to previous failures. Please check Account Stats to reactivate.'
                    }).encode())
                    return
                
                result = send_via_ses(aws_config, from_name, to_email, subject, html_body, attachment, header_opts=_header_opts)
                
                # Track success or failure
                if result.get('success'):
                    track_send_success(account_id, 'ses')
                else:
                    track_send_failure(account_id, 'ses', result.get('error', 'Unknown SES error'))
            
            elif send_method == 'gmail_api':
                # Direct Gmail API send (no EC2 relay)
                gmail_config = data.get('gmail_config')
                if not gmail_config:
                    self.send_response(400)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({'success': False, 'error': 'Gmail API config required (access_token, client_id, client_secret, user)'}).encode())
                    return
                
                # Check if Gmail API account is active before attempting to send
                account_id = gmail_config.get('user', gmail_config.get('client_id', 'unknown')[:8])
                if not is_account_active(account_id, 'gmail_api'):
                    self.send_response(400)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        'success': False, 
                        'error': f'Gmail API account "{account_id}" is deactivated due to previous failures. Please check Account Stats to reactivate.'
                    }).encode())
                    return
                
                result = send_via_gmail_api(gmail_config, from_name, to_email, subject, html_body, attachment, header_opts=_header_opts)
                
                # Track success or failure
                if result.get('success'):
                    track_send_success(account_id, 'gmail_api')
                else:
                    track_send_failure(account_id, 'gmail_api', result.get('error', 'Unknown Gmail API error'))
            
            elif send_method == 'ec2_gmail_api':
                # Gmail API send via EC2 relay (benefits from EC2 IP reputation)
                ec2_instance = data.get('ec2_instance')
                gmail_config = data.get('gmail_config')
                
                if not gmail_config:
                    self.send_response(400)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({'success': False, 'error': 'Gmail API config required'}).encode())
                    return
                
                if ec2_instance and isinstance(ec2_instance, dict):
                    ec2_ip = ec2_instance.get('public_ip')
                    if ec2_ip and ec2_ip not in ('N/A', 'Pending...'):
                        ec2_url = f'http://{ec2_ip}:3000/relay'
                        result = send_via_ec2_gmail_api(ec2_url, gmail_config, from_name, to_email, subject, html_body, attachment, header_opts=_header_opts)
                        if result['success']:
                            result['message'] = f'Email sent via EC2 IP {ec2_ip} using Gmail API to {to_email}'
                    else:
                        result = {'success': False, 'error': 'EC2 instance has no public IP yet'}
                else:
                    ec2_url = data.get('ec2_url')
                    if not ec2_url:
                        result = {'success': False, 'error': 'No EC2 instance selected or instance not ready'}
                    else:
                        result = send_via_ec2_gmail_api(ec2_url, gmail_config, from_name, to_email, subject, html_body, attachment, header_opts=_header_opts)
            
            elif send_method == 'ec2':
                # EC2 Relay - Route email through EC2 IP on port 3000
                ec2_instance = data.get('ec2_instance')
                smtp_config = data.get('smtp_config')  # Optional - used if provided
                
                if ec2_instance and isinstance(ec2_instance, dict):
                    ec2_ip = ec2_instance.get('public_ip')
                    if ec2_ip and ec2_ip not in ('N/A', 'Pending...'):
                        ec2_url = f'http://{ec2_ip}:3000/relay'
                        result = send_via_ec2(ec2_url, smtp_config, from_name, to_email, subject, html_body, attachment, header_opts=_header_opts)
                        if result['success']:
                            result['message'] = f'Email sent via EC2 IP {ec2_ip} to {to_email}'
                    else:
                        result = {'success': False, 'error': 'EC2 instance has no public IP yet'}
                else:
                    ec2_url = data.get('ec2_url')
                    if not ec2_url:
                        result = {'success': False, 'error': 'No EC2 instance selected or instance not ready'}
                    else:
                        result = send_via_ec2(ec2_url, smtp_config, from_name, to_email, subject, html_body, attachment, header_opts=_header_opts)
            
            else:
                result = {'success': False, 'error': f'Unknown send method: {send_method}'}
            
            status_code = 200 if result['success'] else 400
            self.send_response(status_code)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
        
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
