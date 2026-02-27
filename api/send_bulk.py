"""
KINGMAILER v4.0 - Bulk Email Sending API
Features: CSV processing, SMTP/SES/EC2, Account Rotation, Spintax, Template Tags
"""

from http.server import BaseHTTPRequestHandler
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage
from email.utils import formatdate, formataddr, make_msgid
import boto3
import json
import csv
import io
import time
import random
import re
import struct
import uuid
import urllib.request
import urllib.error
from datetime import datetime
import string
import base64


# Spintax Processor
def process_spintax(text):
    """Process spintax syntax: {option1|option2|option3}
    IMPORTANT: only matches groups containing | so {{template_tags}} are never touched.
    """
    if not text:
        return text
    # (?<!\{) and (?!\}) prevent matching {{ or }} i.e. template tag braces.
    # [^{}]*\|[^{}]* ensures there is at least one pipe inside — real spintax only.
    pattern = r'(?<!\{)\{([^{}]*\|[^{}]*)\}(?!\})'
    def replace_fn(match):
        options = match.group(1).split('|')
        return random.choice(options).strip()
    max_iter = 10
    iteration = 0
    while re.search(pattern, text) and iteration < max_iter:
        text = re.sub(pattern, replace_fn, text)
        iteration += 1
    return text


# ─── Generator helpers ────────────────────────────────────────────────────────
_FIRST_NAMES = ['James','John','Robert','Michael','William','David','Richard','Joseph','Thomas','Charles',
                'Mary','Patricia','Jennifer','Linda','Elizabeth','Barbara','Susan','Jessica','Sarah','Karen']
_LAST_NAMES  = ['Smith','Johnson','Williams','Brown','Jones','Garcia','Miller','Davis','Rodriguez','Martinez',
                'Hernandez','Lopez','Gonzalez','Wilson','Anderson','Thomas','Taylor','Moore','Jackson','Martin']
_CO_PREFIX   = ['Tech','Global','Digital','Smart','Innovative','Advanced','Premier','Elite','Prime','Omega']
_CO_SUFFIX   = ['Solutions','Systems','Corporation','Industries','Group','Services','Technologies','Consulting','Enterprises','Partners']
_STREET_NAMES= ['Oak','Main','Pine','Maple','Cedar','Elm','Washington','Park','Lake','Hill']
_STREET_TYPES= ['St','Ave','Blvd','Dr','Ln','Rd','Way','Ct']
_CITIES      = ['New York','Los Angeles','Chicago','Houston','Phoenix','Philadelphia','San Antonio','San Diego','Dallas','Austin']
_STATES      = [('NY',10001),('CA',90001),('IL',60601),('TX',73301),('AZ',85001),
                ('PA',19101),('FL',33101),('OH',43001),('GA',30301),('NC',27601)]
_DOMAINS     = ['gmail.com','yahoo.com','outlook.com','hotmail.com','icloud.com','proton.me',
                'techmail.com','bizmail.net','fastmail.com','mailbox.org']
_URL_NAMES   = ['techgroup','innovatech','globalservices','smartsolutions','digitalcorp',
                'primeworks','elitepartners','advancedsys','omegacorp','primetech']

def gen_random_name():
    return f"{random.choice(_FIRST_NAMES)} {random.choice(_LAST_NAMES)}"

def gen_company():
    return f"{random.choice(_CO_PREFIX)} {random.choice(_CO_SUFFIX)}"

def gen_13_digit():
    ts = int(datetime.now().timestamp() * 1000)
    return str(ts * 1000 + random.randint(0, 999))[:13]

def gen_tracking_id():
    return 'TRK-' + ''.join(random.choices(string.digits, k=8))

def gen_invoice_number():
    return f"INV-{datetime.now().year}-{''.join(random.choices(string.digits, k=4))}"

def gen_phone():
    area = random.randint(200, 999)
    mid  = random.randint(200, 999)
    end  = random.randint(1000, 9999)
    return f"+1 ({area}) {mid}-{end}"

def gen_random_email():
    fn = random.choice(_FIRST_NAMES).lower()
    ln = random.choice(_LAST_NAMES).lower()
    dom = random.choice(_DOMAINS)
    sep = random.choice(['.', '_', ''])
    return f"{fn}{sep}{ln}@{dom}"

def gen_random_url():
    name = random.choice(_URL_NAMES)
    tld  = random.choice(['.com', '.net', '.org', '.io'])
    return f"https://www.{name}{tld}"

def gen_address_parts():
    num   = random.randint(100, 9999)
    sname = random.choice(_STREET_NAMES)
    stype = random.choice(_STREET_TYPES)
    state, zipbase = random.choice(_STATES)
    city  = random.choice(_CITIES)
    zipcode = str(zipbase + random.randint(0, 99)).zfill(5)
    street = f"{num} {sname} {stype}."
    return street, city, state, zipcode, f"{street}, {city}, {state} {zipcode}"

def gen_recipient_name_parts(row_data, recipient_email):
    """Always generate a random name — only email comes from CSV."""
    first = random.choice(_FIRST_NAMES)
    last  = random.choice(_LAST_NAMES)
    return f"{first} {last}", first, last

# ── Reference-file tag generators (ported from working latest13) ──────────────
_PRODUCTS   = ['Premium Software License','Annual Membership Plan','Business Suite Pro',
               'Enterprise Cloud Package','Professional Toolkit','Digital Marketing Suite',
               'Security Firewall License','Data Analytics Platform','E-Commerce Plugin','CRM Solution']
_AMOUNTS    = ['$29.99','$49.99','$99.99','$149.99','$199.99','$249.99','$299.99',
               '$349.99','$399.99','$499.99','$599.99','$699.99','$799.99','$999.99']
_QUANTITIES = ['1','2','3','1','1','2','1','1','3','1']

_CO_US_PREFIX = ['Apex','Summit','Pinnacle','Horizon','Nexus','Vertex','Prime','Elite',
                 'Sterling','Vanguard','Crest','Zenith','Atlas','Titan','Beacon','Keystone',
                 'Frontier','Patriot','Liberty','Heritage','Prestige','Legacy','Triumph',
                 'Clarity','Synergy','Momentum','Catalyst','Velocity','Precision','Quantum']
_CO_US_MIDDLE = ['Solutions','Technologies','Enterprises','Industries','Services','Systems',
                 'Consulting','Partners','Associates','Ventures','Holdings','Capital',
                 'Resources','Dynamics','Innovations','Networks','Management','Development']
_CO_US_SUFFIX = ['LLC','Inc.','Corp.','Co.','Ltd.','Group','International']

def _gen_unique_id_bulk(pattern):
    """Generate IDs like 4-8-4, 5-6-5, 4-4-4-4, 8-8."""
    parts = [str(random.randint(0, 10**int(n)-1)).zfill(int(n)) for n in pattern.split('-')]
    return '-'.join(parts)

def _gen_rand_alphanum_bulk(n, alpha_only=False):
    chars = string.ascii_uppercase if alpha_only else string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=n))

def _gen_rnd_company_us():
    return f"{random.choice(_CO_US_PREFIX)} {random.choice(_CO_US_MIDDLE)} {random.choice(_CO_US_SUFFIX)}"

def _gen_sender_tag_bulk(sender_name):
    first = sender_name.split()[0] if sender_name else 'Support'
    patterns = [
        f"From {sender_name}", f"Team {sender_name}", f"Support {sender_name}",
        f"By {sender_name}", f"- {sender_name}", f"Message from {first}",
        f"Sent by {first}", f"{sender_name} Team", f"{sender_name} Support",
        f"Office of {first}", f"{first}'s Team", f"Via {sender_name}",
    ]
    return random.choice(patterns)

def _html_to_plain(html):
    """Strip HTML tags to produce a plain-text fallback."""
    text = re.sub(r'<br\s*/?>', '\n', html, flags=re.IGNORECASE)
    text = re.sub(r'<p[^>]*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</p>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<li[^>]*>', '\n• ', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def replace_template_tags(text, row_data, recipient_email='', from_name='', from_email=''):
    """Replace all template tags including CSV column data and recipient-derived tags."""
    if not text:
        return text

    # ── 1. CSV column placeholders first (highest priority) ──────────────────
    for key, value in row_data.items():
        escaped = re.escape(key)
        text = re.sub(r'\{\{' + escaped + r'\}\}', str(value), text, flags=re.IGNORECASE)
        # Only match single-brace if NOT part of spintax (no pipe nearby)
        text = re.sub(r'(?<!\{)\{' + escaped + r'\}(?!\})', str(value), text, flags=re.IGNORECASE)

    # ── 2. Recipient-derived tags (all auto-generated — only email comes from CSV) ─
    full_name, first_name, last_name = gen_recipient_name_parts(row_data, recipient_email)
    recipient_company = gen_company()
    titles = ['Mr.', 'Ms.', 'Dr.']
    formal_name = f"{random.choice(titles)} {full_name}"

    # ── 3. Address parts ──────────────────────────────────────────────────────
    addr_street, addr_city, addr_state, addr_zip, addr_full = gen_address_parts()

    # ── 4. Sender tags ───────────────────────────────────────────────────────
    sender_name_val    = from_name or gen_random_name()
    sender_email_val   = from_email or recipient_email
    sender_company_val = row_data.get('sender_company', gen_company())
    sent_from_city     = random.choice(_CITIES)
    sent_from_state    = random.choice([s for s, _ in _STATES])

    # ── 5. Full replacements map ──────────────────────────────────────────────
    rnd_name = gen_random_name()
    replacements = {
        # Recipient
        'recipient':           recipient_email,
        'recipient_name':      full_name,
        'recipient_first':     first_name,
        'recipient_last':      last_name,
        'recipient_formal':    formal_name,
        'recipient_company':   recipient_company,
        'email':               recipient_email,
        # Date & time
        'date':   datetime.now().strftime('%B %d, %Y'),
        'time':   datetime.now().strftime('%I:%M %p'),
        'year':   str(datetime.now().year),
        'month':  datetime.now().strftime('%B'),
        'day':    str(datetime.now().day),
        # IDs
        'unique_id':          gen_13_digit(),
        '13_digit':           gen_13_digit(),
        'tracking_id':        gen_tracking_id(),
        'invoice_number':     gen_invoice_number(),
        # Random strings
        'random_6':           ''.join(random.choices(string.ascii_letters + string.digits, k=6)),
        'random_8':           ''.join(random.choices(string.ascii_letters + string.digits, k=8)),
        'random_upper_10':    ''.join(random.choices(string.ascii_uppercase, k=10)),
        'random_lower_12':    ''.join(random.choices(string.ascii_lowercase, k=12)),
        'random_alphanum_16': ''.join(random.choices(string.ascii_letters + string.digits, k=16)),
        # People & companies (all randomly generated)
        'random_name':    rnd_name,
        'name':           full_name,
        'random_company': gen_company(),
        'company':        recipient_company,
        'company_name':   recipient_company,
        # Contact
        'random_phone':    gen_phone(),
        'random_email':    gen_random_email(),
        'random_url':      gen_random_url(),
        # Numbers
        'random_percent':  f"{random.randint(1, 99)}%",
        'random_currency': f"${random.randint(100, 9999):,}.{random.randint(0,99):02d}",
        # Address
        'address_street': addr_street,
        'address_city':   addr_city,
        'address_state':  addr_state,
        'address_zip':    addr_zip,
        'address_full':   addr_full,
        'usa_address':    addr_full,
        'address':        addr_full,
        # Sender
        'sender_name':    sender_name_val,
        'sender_email':   sender_email_val,
        'sender_company': sender_company_val,
        'sent_from':      f"Sent from {sent_from_city}, {sent_from_state}",
    }

    for tag, value in replacements.items():
        text = re.sub(r'\{\{' + re.escape(tag) + r'\}\}', str(value), text, flags=re.IGNORECASE)

    # ── Dollar-sign style placeholders (reference-file compatible: $name, $invcnumber, etc.) ────────
    # Order: longest/most-specific first to avoid substring collisions
    _invcnumber  = _gen_rand_alphanum_bulk(12)
    _ordernumber = _gen_rand_alphanum_bulk(14)
    _sender_tag  = _gen_sender_tag_bulk(sender_name_val)
    dollar_tags = [
        ('$recipientName',    full_name),
        ('$recipient_first',  first_name),
        ('$recipient_last',   last_name),
        ('$recipient',        recipient_email),
        ('$name',             full_name),
        ('$email',            recipient_email),
        ('$sendername',       sender_name_val),
        ('$sendertag',        _sender_tag),
        ('$sender',           sender_name_val),
        ('$unique16_4444',    _gen_unique_id_bulk('4-4-4-4')),
        ('$unique16_484',     _gen_unique_id_bulk('4-8-4')),
        ('$unique16_565',     _gen_unique_id_bulk('5-6-5')),
        ('$unique16_88',      _gen_unique_id_bulk('8-8')),
        ('$unique14alphanum', _gen_rand_alphanum_bulk(14)),
        ('$unique14alpha',    _gen_rand_alphanum_bulk(14, alpha_only=True)),
        ('$unique11alphanum', _gen_rand_alphanum_bulk(11)),
        ('$unique13digit',    gen_13_digit()),
        ('$invcnumber',       _invcnumber),
        ('$ordernumber',      _ordernumber),
        ('$id',               _gen_rand_alphanum_bulk(14)),
        ('$product',          random.choice(_PRODUCTS)),
        ('$charges',          random.choice(_AMOUNTS)),
        ('$amount',           random.choice(_AMOUNTS)),
        ('$quantity',         random.choice(_QUANTITIES)),
        ('$number',           str(random.randint(100000, 999999))),
        ('$zipcode',          addr_zip),
        ('$zip',              addr_zip),
        ('$address',          addr_full),
        ('$street',           addr_street),
        ('$state',            addr_state),
        ('$city',             addr_city),
        ('$alpha_random_small', ''.join(random.choices(string.ascii_lowercase, k=6))),
        ('$rnd_company_us',     _gen_rnd_company_us()),
        ('$random_three_chars', ''.join(random.choices(string.ascii_uppercase, k=3))),
        ('$alpha_short',        ''.join(random.choices(string.ascii_lowercase, k=3))),
        ('$randName',           rnd_name),
        ('$date',               datetime.now().strftime('%m/%d/%Y')),
    ]
    for tag, value in dollar_tags:
        text = text.replace(tag, str(value))

    return text


def _build_bulk_msg(from_header, smtp_user, recipient, subject, html_body, include_unsubscribe=True):
    """
    Build a high-deliverability MIME message for bulk sending using the same
    techniques as the reference mailer (Apple Mail identity, UUID Message-ID,
    subject jitter, base64 HTML encoding, mobile signature, Thread-Index).
    include_unsubscribe=True adds List-Unsubscribe + Precedence:bulk headers.
    """
    sender_domain = smtp_user.split('@')[-1] if smtp_user and '@' in smtp_user else 'mail.com'

    # ── Subject zero-width jitter ─────────────────────────────────────────────
    _zwsp = ['\u200c', '\u200d', '\u200b']
    jittered_subject = subject + ''.join(random.choices(_zwsp, k=random.randint(3, 8)))

    # ── UUID-style Message-ID ────────────────────────────────────────────────
    uid = uuid.uuid4().hex.upper()
    msg_id = f'<{uid[:8]}-{uid[8:12]}-{uid[12:16]}-{uid[16:20]}-{uid[20:]}@{sender_domain}>'

    # ── Thread-Index ─────────────────────────────────────────────────────────
    try:
        _ti = base64.b64encode(
            struct.pack('>Q', int(__import__('time').time() * 10000000 + 116444736000000000))[:6]
            + bytes([random.randint(0, 255) for _ in range(10)])
        ).decode()
    except Exception:
        _ti = ''

    # ── Plain-text with jitter + mobile sig ────────────────────────────────
    _jitter = ''.join(random.choices([' ', '\u00A0'], k=random.randint(5, 10)))
    plain_text = _html_to_plain(html_body) + '\n\nSent from my iPhone' + _jitter

    # ── HTML wrap with DOCTYPE + unique UUID comment ──────────────────────────
    _html_uuid = uuid.uuid4().hex
    if '<html' in html_body.lower():
        if '</body>' in html_body.lower():
            html_wrapped = re.sub(r'</body>', f'<!-- {_html_uuid} --></body>', html_body, flags=re.IGNORECASE)
        else:
            html_wrapped = html_body + f'<!-- {_html_uuid} -->'
    else:
        html_wrapped = (
            '<!DOCTYPE html>\n'
            '<html><head><meta charset="utf-8"></head><body>'
            + html_body.replace('\n', '<br>')
            + f'<!-- {_html_uuid} -->'
            '</body></html>'
        )

    # ── MIME structure: mixed > alternative > plain + html(base64) ──────────────
    msg = MIMEMultipart('mixed')
    alt = MIMEMultipart('alternative')
    alt.attach(MIMEText(plain_text, 'plain', 'utf-8'))
    html_part = MIMEText(html_wrapped, 'html', 'utf-8')
    html_part.replace_header('Content-Transfer-Encoding', 'base64')
    alt.attach(html_part)
    msg.attach(alt)

    # ── Headers ────────────────────────────────────────────────────────────
    msg['From']       = from_header
    msg['To']         = recipient
    msg['Subject']    = jittered_subject
    msg['Date']       = formatdate(localtime=True)
    msg['Message-ID'] = msg_id
    msg['Reply-To']   = from_header
    
    # Return-Path for proper bounce handling
    sender_email = from_header.split('<')[-1].rstrip('>') if '<' in from_header else from_header
    msg['Return-Path'] = sender_email

    # REMOVED: X-Mailer, User-Agent, Thread headers (spam trigger)

    if include_unsubscribe:
        msg['List-Unsubscribe']      = f'<mailto:unsubscribe@{sender_domain}?subject=unsubscribe>'
        msg['List-Unsubscribe-Post'] = 'List-Unsubscribe=One-Click'
        msg['Precedence']            = 'bulk'

    return msg


def _add_bulk_attachment(msg, attachment, plain_text, html_body):
    """Add attachment, converting msg from alternative to mixed structure."""
    # If msg is multipart/alternative (no attachment yet), convert to mixed
    if msg.get_content_subtype() == 'alternative':
        # Save all parts from the alternative message
        old_parts = list(msg.get_payload())
        # Save headers
        headers = {k: v for k, v in msg.items()}
        # Clear the message
        for part in old_parts:
            msg.get_payload().remove(part)
        # Convert to mixed
        msg.set_type('multipart/mixed')
        # Create new alternative part and move old parts into it
        alt = MIMEMultipart('alternative')
        for part in old_parts:
            alt.attach(part)
        # Attach alternative to the now-mixed message
        msg.attach(alt)
    
    # Now add the attachment to the mixed message
    filename  = attachment.get('name', 'attachment')
    mime_type = attachment.get('type', '')
    if not mime_type or mime_type in ('application/octet-stream', 'binary/octet-stream'):
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        mime_map = {
            'pdf':'application/pdf','png':'image/png','jpg':'image/jpeg',
            'jpeg':'image/jpeg','gif':'image/gif','webp':'image/webp',
            'doc':'application/msword',
            'docx':'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'xls':'application/vnd.ms-excel',
            'xlsx':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'ppt':'application/vnd.ms-powerpoint',
            'pptx':'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            'zip':'application/zip','txt':'text/plain','csv':'text/csv'
        }
        mime_type = mime_map.get(ext, 'application/pdf')
    main_type, sub_type = mime_type.split('/', 1) if '/' in mime_type else ('application', 'pdf')
    raw = attachment['content'] + '=' * (-len(attachment['content']) % 4)
    file_data = base64.b64decode(raw)
    
    if main_type == 'image':
        part = MIMEImage(file_data, _subtype=sub_type)
    else:
        part = MIMEApplication(file_data, _subtype=sub_type)
    
    now_rfc = formatdate(localtime=True)
    part.add_header(
        'Content-Disposition', 'attachment',
        filename=filename,
        **{'creation-date': now_rfc, 'modification-date': now_rfc, 'read-date': now_rfc}
    )
    part['X-Attachment-Id'] = uuid.uuid4().hex
    msg.attach(part)
    return msg


def send_email_smtp(smtp_config, from_name, recipient, subject, html_body, ec2_ip=None, include_unsubscribe=True, attachment=None):
    """
    Send a fully RFC-compliant bulk email via SMTP.
    Multipart/alternative (plain + HTML), proper headers, EHLO handshake.
    Supports optional attachment with correct MIME typing.
    """
    try:
        is_gmail = smtp_config.get('provider') == 'gmail'
        smtp_server = 'smtp.gmail.com' if is_gmail else smtp_config.get('host', 'smtp.gmail.com')
        smtp_port   = 587             if is_gmail else int(smtp_config.get('port', 587))
        smtp_user   = smtp_config.get('user')
        smtp_pass   = smtp_config.get('pass')

        print(f'[SMTP SEND] → {recipient}')
        print(f'[SMTP SERVER] {smtp_server}:{smtp_port}')

        sender_name = smtp_config.get('sender_name') or from_name
        from_header = f"{sender_name} <{smtp_user}>" if sender_name else smtp_user

        msg = _build_bulk_msg(from_header, smtp_user, recipient, subject, html_body, include_unsubscribe)
        if attachment:
            plain_text = _html_to_plain(html_body)
            msg = _add_bulk_attachment(msg, attachment, plain_text, html_body)

        with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)

        print(f'[SMTP SUCCESS] Email sent to {recipient} via {smtp_server}')
        return {'success': True}
    except smtplib.SMTPAuthenticationError:
        return {'success': False, 'error': 'SMTP authentication failed — check your app password'}
    except smtplib.SMTPRecipientsRefused:
        return {'success': False, 'error': f'Recipient address rejected: {recipient}'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def send_email_ses(aws_config, from_name, recipient, subject, html_body, include_unsubscribe=True):
    """Send bulk email via AWS SES using raw MIME for multipart/alternative + proper headers."""
    try:
        ses_client = boto3.client(
            'ses',
            region_name=aws_config.get('region', 'us-east-1'),
            aws_access_key_id=aws_config.get('access_key'),
            aws_secret_access_key=aws_config.get('secret_key')
        )

        from_email = aws_config.get('from_email', 'noreply@example.com')
        source = f"{from_name} <{from_email}>" if from_name else from_email
        smtp_user = from_email

        msg = _build_bulk_msg(source, smtp_user, recipient, subject, html_body, include_unsubscribe)

        ses_client.send_raw_email(
            Source=source,
            Destinations=[recipient],
            RawMessage={'Data': msg.as_string()}
        )

        return {'success': True}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def send_email_ec2(ec2_url, smtp_config, from_name, recipient, subject, html_body, include_unsubscribe=True, attachment=None):
    """Send email via EC2 relay (JetMailer style - authenticated SMTP through EC2 IP)"""
    try:
        print(f'[EC2 RELAY] Sending to {recipient} via {ec2_url}')
        print(f'[EC2 RELAY] SMTP credentials: {smtp_config.get("user") if smtp_config else "none"}')

        # Include plain-text so the EC2 relay can build multipart/alternative
        plain_text = _html_to_plain(html_body)

        payload = {
            'from_name': from_name,
            'to': recipient,
            'subject': subject,
            'html': html_body,
            'plain': plain_text,          # plain-text alternative for relay
            'smtp_config': smtp_config,   # Pass SMTP credentials to relay
            'include_unsubscribe': include_unsubscribe,
        }
        if attachment:
            payload['attachment'] = attachment
        
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(ec2_url, data=data, method='POST')
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
        return {'success': False, 'error': f'Unexpected error: {str(e)}'}


class SMTPPool:
    """Round-robin SMTP account rotation"""
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
            from_name = data.get('from_name', 'KINGMAILER')
            from_email = data.get('from_email', '')
            include_unsubscribe = data.get('include_unsubscribe', True)
            attachment = data.get('attachment')  # {name, type, content (base64)}
            
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
                
                # Then replace template tags (including CSV columns)
                subject   = replace_template_tags(subject,   row, recipient, from_name, from_email)
                html_body = replace_template_tags(html_body, row, recipient, from_name, from_email)
                
                # Send email based on method
                if method == 'smtp' and smtp_pool:
                    smtp_config = smtp_pool.get_next()
                    print(f'\\n[EMAIL {index+1}] Method: SMTP → {recipient}')
                    result = send_email_smtp(smtp_config, from_name, recipient, subject, html_body, include_unsubscribe=include_unsubscribe, attachment=attachment)
                
                elif method == 'ses' and ses_pool:
                    ses_config = ses_pool.get_next()  
                    print(f'\\n[EMAIL {index+1}] Method: SES → {recipient}')
                    result = send_email_ses(ses_config, from_name, recipient, subject, html_body, include_unsubscribe=include_unsubscribe)
                
                elif method == 'ec2' and ec2_pool:
                    # EC2 Relay - Route email through EC2 IP
                    # EC2 instance runs relay server on port 3000
                    ec2_instance = ec2_pool.get_next()  # type: ignore
                    smtp_config = smtp_pool.get_next() if smtp_pool else None
                    
                    print(f'\n[EMAIL {index+1}] Method: EC2 RELAY → {recipient}')
                    
                    if ec2_instance:
                        ec2_ip = ec2_instance.get('public_ip')  # type: ignore
                        if ec2_ip and ec2_ip != 'N/A' and ec2_ip != 'Pending...':
                            # Send via EC2 relay on port 3000 (user's open port)
                            relay_url = f'http://{ec2_ip}:3000/relay'
                            print(f'[EC2 RELAY] Connecting to {relay_url}')
                            result = send_email_ec2(relay_url, smtp_config, from_name, recipient, subject, html_body, include_unsubscribe=include_unsubscribe, attachment=attachment)
                            if result['success']:
                                result['via_ec2_ip'] = ec2_ip
                            else:
                                result['error'] = f"EC2 relay failed ({ec2_ip}:3000): {result.get('error', 'Unknown error')}"
                        else:
                            result = {'success': False, 'error': f'EC2 instance has no public IP yet'}
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
