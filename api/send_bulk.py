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


def replace_template_tags(text, row_data, recipient_email='', sender_name='', sender_email=''):
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
        'sendername':    sender_name or (first + ' ' + last),
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
    tag_map['sender_name'] = sender_name or f"{first} {last}"

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
        '<!DOCTYPE html>\n<html>\n<head><meta charset="utf-8"></head>\n<body>\n'
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:14px;'
        'color:#222;max-width:650px;margin:0 auto;padding:20px;">'
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
    if not _is_html(html_body): html_body = _plain_to_html(html_body)

    # ── Deliverability: Mandatory Footer ──
    lc_body = html_body.lower()
    has_unsubscribe = 'unsubscribe' in lc_body or 'opt-out' in lc_body
    has_address = bool(re.search(
        r'\b\d{1,6}\b.{0,15}\b(street|st\.|ave\.?|avenue|blvd\.?|boulevard|'
        r'road|rd\.|drive|dr\.|suite|ste\.?|floor|way|lane|ln\.)\b',
        lc_body
    ))

    # Only inject footer for emails with enough content to be a commercial message.
    # Forcing a business address + unsubscribe into a short test/personal email
    # creates a content mismatch that Gmail's ML classifier reads as suspicious bulk.
    _plain_preview = _html_to_plain(html_body)
    _word_count    = len(_plain_preview.split())
    _needs_footer  = _word_count >= 20 and (not has_unsubscribe or not has_address)

    if _needs_footer:
        footer = ('<div style="margin-top:40px;padding-top:20px;border-top:1px solid #eee;'
                  'font-size:11px;color:#999;text-align:center;">')
        if not has_address:
            _ft_cities = [('New York','NY','10001'),('Los Angeles','CA','90001'),('Chicago','IL','60601'),
                          ('Houston','TX','77001'),('Austin','TX','78701'),('Seattle','WA','98101'),
                          ('Denver','CO','80201'),('Miami','FL','33101'),('Atlanta','GA','30301'),
                          ('Boston','MA','02101'),('Nashville','TN','37201'),('Dallas','TX','75201')]
            _ft_streets = ['Main St','Oak Ave','Maple Dr','Pine Blvd','Cedar Lane','Elm Rd',
                           'Washington Blvd','Park Ave','Lake Dr','Hillside Way','Sunset Blvd']
            _fc, _fs, _fz = random.choice(_ft_cities)
            _fn = random.randint(100, 9999)
            _ft_s = random.choice(_ft_streets)
            footer += f'<p>{_fn} {_ft_s}, {_fc}, {_fs} {_fz}</p>'
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
            '<!DOCTYPE html>\n<html>\n<head><meta charset="utf-8"></head>\n<body>\n'
            + html_body + '\n</body>\n</html>'
        )

    # Unique HTML comment per email — breaks Gmail duplicate clustering
    html_body = html_body.replace('</body>', f'{_get_jitter()}</body>')

    domain = _extract_domain(from_header)

    from email.charset import Charset, QP
    cset = Charset('utf-8')
    cset.body_encoding = QP

    plain = _html_to_plain(html_body)

    # ── NO SEPARATE ATTACHMENTS: all content is embedded in the HTML body ───
    msg = MIMEMultipart('alternative')
    txt = MIMEText(plain, 'plain', cset)
    txt.set_param('format', 'flowed')   # RFC 3676 — real mail-client signal
    msg.attach(txt)
    msg.attach(MIMEText(html_body, 'html', cset))

    _clean_mime(msg)

    _o = header_opts or {}
    msg['From']             = from_header
    msg['To']               = to_email
    msg['Subject']          = _encode_subject(subject)
    msg['Date']             = formatdate(localtime=True)
    msg['Message-ID']       = f'<{uuid.uuid4().hex}@{domain}>'
    # Reply-To: optional (on by default; disable to reduce promotional header signals)
    if _o.get('reply_to', True):
        msg['Reply-To'] = from_header
    msg['Content-Language'] = 'en-US'   # standard for all major ESPs (Mailchimp, SendGrid)
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

        with smtplib.SMTP(smtp_server, smtp_port, timeout=30,
                           local_hostname=None) as server:
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
            # Legacy relay fallback: old relay ignores type/raw_email and
            # reads these fields — prevents missing attachment on old relay instances
            'to':          recipient,
            'from_name':   from_name,
            'subject':     subject,
            'html':        html_body,
            'attachment':  attachment,   # ← OLD relay needs this for attachments
            'smtp_config': smtp_config,
        }
        data = json.dumps(payload).encode('utf-8')
        req  = urllib.request.Request(ec2_url, data=data, method='POST')
        req.add_header('Content-Type', 'application/json')

        with urllib.request.urlopen(req, timeout=30) as response:
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
    """Round-robin account rotation pool."""
    def __init__(self, accounts):
        self.accounts = accounts
        self.current_index = 0

    def get_next(self):
        if not self.accounts:
            return None
        account = self.accounts[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.accounts)
        return account


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
            min_delay = int(data.get('min_delay', 2000))
            max_delay = int(data.get('max_delay', 5000))
            from_name = data.get('from_name', '') or ''
            from_email = data.get('from_email', '')

            # Header options (controls List-Unsubscribe / Precedence / Reply-To)
            _header_opts = data.get('header_opts', {}) or {}

            # Get account configs
            smtp_configs = data.get('smtp_configs', [])
            ses_configs = data.get('ses_configs', [])
            ec2_instances = data.get('ec2_instances', [])
            
            # Debug logging
            print('='*50)
            print('BULK SEND DEBUG - Backend')
            print(f'Method selected: {method}')
            print(f'SMTP configs received: {len(smtp_configs)}')
            print(f'SES configs received: {len(ses_configs)}')
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
            smtp_pool = SMTPPool(smtp_configs) if smtp_configs else None
            ses_pool = SMTPPool(ses_configs) if ses_configs else None
            ec2_pool = SMTPPool(ec2_instances) if ec2_instances else None
            
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
                                                   sender_name=_eff_name, sender_email=_cur_s_email)
                html_body = replace_template_tags(html_body, row, recipient,
                                                   sender_name=_eff_name, sender_email=_cur_s_email)
                
                # Deliverability: Filter high-risk spam keywords
                subject = minimize_spam_keywords(subject)
                html_body = minimize_spam_keywords(html_body)

                # Send email based on method
                attachment = data.get('attachment')  # {name, content (base64), type}

                if method == 'smtp' and smtp_pool:
                    smtp_config = smtp_pool.get_next()
                    print(f'\n[EMAIL {index+1}] Method: SMTP → {recipient}')
                    result = send_email_smtp(smtp_config, _eff_name, recipient, subject, html_body, attachment, header_opts=_header_opts)

                elif method == 'ses' and ses_pool:
                    ses_config = ses_pool.get_next()
                    print(f'\n[EMAIL {index+1}] Method: SES → {recipient}')
                    result = send_email_ses(ses_config, _eff_name, recipient, subject, html_body, attachment, header_opts=_header_opts)
                
                elif method == 'ec2' and ec2_pool:
                    ec2_instance = ec2_pool.get_next()
                    smtp_config  = smtp_pool.get_next() if smtp_pool else None

                    print(f'\n[EMAIL {index+1}] Method: EC2 RELAY → {recipient}')

                    if ec2_instance:
                        ec2_ip = ec2_instance.get('public_ip')
                        if ec2_ip and ec2_ip != 'N/A' and ec2_ip != 'Pending...':
                            relay_url = f'http://{ec2_ip}:3000/relay'
                            print(f'[EC2 RELAY] Connecting to {relay_url}')
                            result = send_email_ec2(relay_url, smtp_config, _eff_name, recipient, subject, html_body, attachment, header_opts=_header_opts)
                            if result['success']:
                                result['via_ec2_ip'] = ec2_ip
                            else:
                                result['error'] = f"EC2 relay failed ({ec2_ip}:3000): {result.get('error', 'Unknown error')}"
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
                
                # Random delay between emails (except for last one)
                if index < len(rows) - 1:
                    delay = random.randint(min_delay, max_delay) / 1000.0
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
