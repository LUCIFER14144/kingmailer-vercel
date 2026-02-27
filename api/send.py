"""
KINGMAILER v4.0 - Enhanced Email Sending API
Features: SMTP, AWS SES, EC2 Relay, Spintax, Template Tags
"""

from http.server import BaseHTTPRequestHandler
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage
from email.utils import formatdate, formataddr, make_msgid
import boto3
from botocore.exceptions import ClientError
import json
import re
import random
import string
import struct
import uuid
import urllib.request
from datetime import datetime
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

def _gen_random_name():
    return f"{random.choice(_FIRST_NAMES)} {random.choice(_LAST_NAMES)}"

def _gen_company():
    return f"{random.choice(_CO_PREFIX)} {random.choice(_CO_SUFFIX)}"

def _gen_13_digit():
    ts = int(datetime.now().timestamp() * 1000)
    return str(ts * 1000 + random.randint(0, 999))[:13]

def _gen_phone():
    area = random.randint(200, 999)
    mid  = random.randint(200, 999)
    end  = random.randint(1000, 9999)
    return f"+1 ({area}) {mid}-{end}"

def _gen_random_email():
    fn  = random.choice(_FIRST_NAMES).lower()
    ln  = random.choice(_LAST_NAMES).lower()
    dom = random.choice(_DOMAINS)
    sep = random.choice(['.','_',''])
    return f"{fn}{sep}{ln}@{dom}"

def _gen_address_parts():
    num   = random.randint(100, 9999)
    sname = random.choice(_STREET_NAMES)
    stype = random.choice(_STREET_TYPES)
    state, zipbase = random.choice(_STATES)
    city  = random.choice(_CITIES)
    zipcode = str(zipbase + random.randint(0, 99)).zfill(5)
    street = f"{num} {sname} {stype}."
    return street, city, state, zipcode, f"{street}, {city}, {state} {zipcode}"

def _gen_recipient_name_parts(csv_row, recipient_email):
    """Always generate a random name — only email comes from CSV."""
    first = random.choice(_FIRST_NAMES)
    last  = random.choice(_LAST_NAMES)
    return f"{first} {last}", first, last

# ── Reference-file tag generators (ported from working latest13) ──────────────
_PRODUCTS  = ['Premium Software License','Annual Membership Plan','Business Suite Pro',
              'Enterprise Cloud Package','Professional Toolkit','Digital Marketing Suite',
              'Security Firewall License','Data Analytics Platform','E-Commerce Plugin','CRM Solution']
_AMOUNTS   = ['$29.99','$49.99','$99.99','$149.99','$199.99','$249.99','$299.99',
              '$349.99','$399.99','$499.99','$599.99','$699.99','$799.99','$999.99']
_QUANTITIES= ['1','2','3','1','1','2','1','1','3','1']
_NUMBERS   = [str(random.randint(100000,999999)) for _ in range(20)]

_CO_US_PREFIX = ['Apex','Summit','Pinnacle','Horizon','Nexus','Vertex','Prime','Elite',
                 'Sterling','Vanguard','Crest','Zenith','Atlas','Titan','Beacon','Keystone',
                 'Frontier','Patriot','Liberty','Heritage','Prestige','Legacy','Triumph',
                 'Clarity','Synergy','Momentum','Catalyst','Velocity','Precision','Quantum']
_CO_US_MIDDLE = ['Solutions','Technologies','Enterprises','Industries','Services','Systems',
                 'Consulting','Partners','Associates','Ventures','Holdings','Capital',
                 'Resources','Dynamics','Innovations','Networks','Management','Development']
_CO_US_SUFFIX = ['LLC','Inc.','Corp.','Co.','Ltd.','Group','International']

def _gen_unique_id(pattern):
    """Generate IDs like 4-8-4, 5-6-5, 4-4-4-4, 8-8 from digit groups."""
    parts = [str(random.randint(0, 10**int(n)-1)).zfill(int(n)) for n in pattern.split('-')]
    return '-'.join(parts)

def _gen_rand_alphanum(n, alpha_only=False):
    chars = string.ascii_uppercase if alpha_only else string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=n))

def _gen_rnd_company_us():
    return f"{random.choice(_CO_US_PREFIX)} {random.choice(_CO_US_MIDDLE)} {random.choice(_CO_US_SUFFIX)}"

def _gen_sender_tag(sender_name):
    """Create sender-tag variation using the actual sender name."""
    first = sender_name.split()[0] if sender_name else 'Support'
    patterns = [
        f"From {sender_name}", f"Team {sender_name}", f"Support {sender_name}",
        f"By {sender_name}", f"- {sender_name}", f"Message from {first}",
        f"Sent by {first}", f"{sender_name} Team", f"{sender_name} Support",
        f"Office of {first}", f"{first}'s Team", f"Via {sender_name}",
    ]
    return random.choice(patterns)


# Template Tag Replacements
def replace_template_tags(text, recipient_email='', from_name='', from_email=''):
    """Replace all standard template tags in text."""
    if not text:
        return text
    return _apply_tag_replacements(text, {}, recipient_email, from_name, from_email)


def _apply_tag_replacements(text, csv_row, recipient_email='', from_name='', from_email=''):
    """Core tag replacement used by both single-send and bulk-send paths."""
    if not text:
        return text

    full_name, first_name, last_name = _gen_recipient_name_parts(csv_row, recipient_email)
    recipient_company = _gen_company()  # always auto-generated
    formal_name = f"{random.choice(['Mr.','Ms.','Dr.'])} {full_name}"

    addr_street, addr_city, addr_state, addr_zip, addr_full = _gen_address_parts()
    sender_name_val    = from_name or _gen_random_name()
    sender_email_val   = from_email or recipient_email
    sender_company_val = _gen_company()
    sent_from_city     = random.choice(_CITIES)
    sent_from_state    = random.choice([s for s, _ in _STATES])

    rnd_name = _gen_random_name()
    _invcnumber = _gen_rand_alphanum(12)
    _ordernumber = _gen_rand_alphanum(14)
    _id = _gen_rand_alphanum(14)
    _sender_tag = _gen_sender_tag(sender_name_val)

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
        'unique_id':          _gen_13_digit(),
        '13_digit':           _gen_13_digit(),
        'tracking_id':        'TRK-' + ''.join(random.choices(string.digits, k=8)),
        'invoice_number':     f"INV-{datetime.now().year}-{''.join(random.choices(string.digits, k=4))}",
        # Random strings
        'random_6':           ''.join(random.choices(string.ascii_letters + string.digits, k=6)),
        'random_8':           ''.join(random.choices(string.ascii_letters + string.digits, k=8)),
        'random_upper_10':    ''.join(random.choices(string.ascii_uppercase, k=10)),
        'random_lower_12':    ''.join(random.choices(string.ascii_lowercase, k=12)),
        'random_alphanum_16': ''.join(random.choices(string.ascii_letters + string.digits, k=16)),
        # People & companies (all randomly generated)
        'random_name':    rnd_name,
        'name':           full_name,
        'random_company': _gen_company(),
        'company':        recipient_company,
        'company_name':   recipient_company,
        # Contact
        'random_phone':    _gen_phone(),
        'random_email':    _gen_random_email(),
        'random_url':      'https://www.' + random.choice(_URL_NAMES) + random.choice(['.com','.net','.org','.io']),
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
    # ($sendertag before $sendername before $sender, $zipcode before $zip, etc.)
    dollar_tags = [
        # Recipient / name
        ('$recipientName',    full_name),
        ('$recipient_first',  first_name),
        ('$recipient_last',   last_name),
        ('$recipient',        recipient_email),
        ('$name',             full_name),
        ('$email',            recipient_email),
        # Sender (most-specific first)
        ('$sendername',       sender_name_val),
        ('$sendertag',        _sender_tag),
        ('$sender',           sender_name_val),
        # IDs
        ('$unique16_4444',    _gen_unique_id('4-4-4-4')),
        ('$unique16_484',     _gen_unique_id('4-8-4')),
        ('$unique16_565',     _gen_unique_id('5-6-5')),
        ('$unique16_88',      _gen_unique_id('8-8')),
        ('$unique14alphanum', _gen_rand_alphanum(14)),
        ('$unique14alpha',    _gen_rand_alphanum(14, alpha_only=True)),
        ('$unique11alphanum', _gen_rand_alphanum(11)),
        ('$unique13digit',    _gen_13_digit()),
        ('$invcnumber',       _invcnumber),
        ('$ordernumber',      _ordernumber),
        ('$id',               _id),
        # Product / commerce
        ('$product',          random.choice(_PRODUCTS)),
        ('$charges',          random.choice(_AMOUNTS)),
        ('$amount',           random.choice(_AMOUNTS)),
        ('$quantity',         random.choice(_QUANTITIES)),
        ('$number',           str(random.randint(100000, 999999))),
        # Address (most-specific first)
        ('$zipcode',          addr_zip),
        ('$zip',              addr_zip),
        ('$address',          addr_full),
        ('$street',           addr_street),
        ('$state',            addr_state),
        ('$city',             addr_city),
        # Custom
        ('$alpha_random_small', ''.join(random.choices(string.ascii_lowercase, k=6))),
        ('$rnd_company_us',     _gen_rnd_company_us()),
        ('$random_three_chars', ''.join(random.choices(string.ascii_uppercase, k=3))),
        ('$alpha_short',        ''.join(random.choices(string.ascii_lowercase, k=3))),
        ('$randName',           rnd_name),
        # Date
        ('$date',             datetime.now().strftime('%m/%d/%Y')),
    ]
    for tag, value in dollar_tags:
        text = text.replace(tag, str(value))

    return text


def add_attachment_to_message(msg, attachment):
    """Attach a base64-encoded file to a MIME message.
    Uses MIMEApplication/MIMEImage (correct classes, trusted by spam filters).
    Returns (True, None) on success or (False, error_str) on failure."""
    if not attachment:
        return True, None
    try:
        raw_b64 = attachment['content']
        raw_b64 += '=' * (-len(raw_b64) % 4)
        file_data = base64.b64decode(raw_b64)
        filename  = attachment.get('name', 'attachment')
        mime_type = attachment.get('type', '')

        # Infer MIME type from filename extension if not provided or too generic
        if not mime_type or mime_type in ('application/octet-stream', 'binary/octet-stream'):
            ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
            mime_map = {
                'pdf':  'application/pdf',
                'png':  'image/png',
                'jpg':  'image/jpeg',
                'jpeg': 'image/jpeg',
                'gif':  'image/gif',
                'webp': 'image/webp',
                'doc':  'application/msword',
                'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'xls':  'application/vnd.ms-excel',
                'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'ppt':  'application/vnd.ms-powerpoint',
                'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
                'zip':  'application/zip',
                'txt':  'text/plain',
                'html': 'text/html',
                'htm':  'text/html',
                'csv':  'text/csv',
            }
            mime_type = mime_map.get(ext, 'application/pdf')

        main_type, sub_type = mime_type.split('/', 1) if '/' in mime_type else ('application', 'pdf')

        # Use MIMEImage for images, MIMEApplication for everything else.
        # MIMEApplication already calls Encoders.encode_base64 internally —
        # DO NOT call set_charset(None) after it, that deletes the CTE header.
        if main_type == 'image':
            part = MIMEImage(file_data, _subtype=sub_type)
        else:
            part = MIMEApplication(file_data, _subtype=sub_type)
            # MIMEApplication has already set Content-Transfer-Encoding: base64.
            # Leaving it alone produces the cleanest, most trusted MIME structure.

        # RFC 2183 Content-Disposition — include standard date metadata so the
        # attachment looks like it came from a real email client.
        now_rfc = formatdate(localtime=True)
        part.add_header(
            'Content-Disposition', 'attachment',
            filename=filename,
            **{'creation-date': now_rfc, 'modification-date': now_rfc, 'read-date': now_rfc}
        )
        # Unique per-message attachment ID (mirrors real MUA behaviour)
        part['X-Attachment-Id'] = uuid.uuid4().hex
        msg.attach(part)
        return True, None
    except Exception as e:
        return False, str(e)


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


def _build_msg(from_header, to_email, subject, html_body, attachment=None, include_unsubscribe=False):
    """Build a high-deliverability MIME message modelled on the techniques from
    the reference desktop mailer (working latest13).  Techniques used:
    - Apple Mail X-Mailer + iPhone User-Agent  (trusted MUA identity)
    - UUID-style Message-ID matching real client format
    - Reply-To header
    - Thread-Topic + Thread-Index (Outlook legitimacy signals)
    - Zero-width subject jitter (byte-unique, breaks duplicate clustering)
    - HTML wrapped with DOCTYPE + UTF-8 charset meta
    - HTML part encoded as base64 (masks HTML structure from simple filters)
    - Unique HTML comment UUID per email (byte-unique body)
    - Mobile signature 'Sent from my iPhone'
    - Non-breaking space jitter in plain-text part
    - include_unsubscribe only for real campaign sends
    """
    # ── Extract sender domain ──────────────────────────────────────────────
    sender_domain = from_header.split('@')[-1].rstrip('>') if '@' in from_header else 'mail.com'

    # ── Subject: inject invisible zero-width jitter ───────────────────────
    # Makes every email byte-unique at the subject level, preventing
    # Gmail's 'duplicate subject' spam clustering.
    _zwsp_pool = ['\u200c', '\u200d', '\u200b']
    subject_noise = ''.join(random.choices(_zwsp_pool, k=random.randint(3, 8)))
    jittered_subject = subject + subject_noise

    # ── UUID-format Message-ID (matches real Apple Mail format) ──────────
    uid = uuid.uuid4().hex.upper()
    msg_id = f'<{uid[:8]}-{uid[8:12]}-{uid[12:16]}-{uid[16:20]}-{uid[20:]}@{sender_domain}>'

    # ── Thread-Index (Outlook legitimacy header) ──────────────────────────
    try:
        _ti = base64.b64encode(
            struct.pack('>Q', int(__import__('time').time() * 10000000 + 116444736000000000))[:6]
            + bytes([random.randint(0, 255) for _ in range(10)])
        ).decode()
    except Exception:
        _ti = ''

    # ── Build plain-text with mobile sig + jitter ─────────────────────────
    _jitter = ''.join(random.choices([' ', '\u00A0'], k=random.randint(5, 10)))
    plain = _html_to_plain(html_body) + '\n\nSent from my iPhone' + _jitter

    # ── Build HTML with DOCTYPE wrap + unique comment + mobile sig ────────
    _html_uuid = uuid.uuid4().hex
    if '<html' in html_body.lower():
        # Already has html tag — inject comment before </body>
        if '</body>' in html_body.lower():
            html_wrapped = re.sub(
                r'</body>',
                f'<!-- {_html_uuid} --></body>',
                html_body, flags=re.IGNORECASE
            )
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

    # ── MIME structure ────────────────────────────────────────────────────
    # multipart/mixed  (outer, always — broad client compat)
    #   └─ multipart/alternative
    #        ├─ text/plain
    #        └─ text/html  (base64 encoded to mask HTML from simple filters)
    msg = MIMEMultipart('mixed')
    alt = MIMEMultipart('alternative')

    plain_part = MIMEText(plain, 'plain', 'utf-8')
    alt.attach(plain_part)

    html_part = MIMEText(html_wrapped, 'html', 'utf-8')
    # Force base64 on the HTML part — masks markup structure from simple
    # pattern-matching spam filters (same technique as reference mailer)
    html_part.replace_header('Content-Transfer-Encoding', 'base64')
    alt.attach(html_part)

    msg.attach(alt)

    # ── Headers ───────────────────────────────────────────────────────────
    msg['From']       = from_header
    msg['To']         = to_email
    msg['Subject']    = jittered_subject
    msg['Date']       = formatdate(localtime=True)
    msg['Message-ID'] = msg_id
    msg['Reply-To']   = from_header
    
    # Return-Path for proper bounce handling (required by many filters)
    sender_email = from_header.split('<')[-1].rstrip('>') if '<' in from_header else from_header
    msg['Return-Path'] = sender_email

    # REMOVED: X-Mailer, User-Agent, Thread-Index, Thread-Topic
    # Reference file comment: "REMOVED to look more natural and avoid spam flags"
    # Over-identifying as specific clients triggers spam filters

    # Only add bulk/unsubscribe headers for real campaign sends
    if include_unsubscribe:
        msg['List-Unsubscribe']      = f'<mailto:unsubscribe@{sender_domain}?subject=unsubscribe>'
        msg['List-Unsubscribe-Post'] = 'List-Unsubscribe=One-Click'
        msg['Precedence']            = 'bulk'

    return msg


def send_via_smtp(smtp_config, from_name, to_email, subject, html_body, attachment=None, include_unsubscribe=False):
    """Send email via SMTP (Gmail or custom server)"""
    try:
        is_gmail = smtp_config.get('provider') == 'gmail'
        smtp_server = 'smtp.gmail.com' if is_gmail else smtp_config.get('host', 'smtp.gmail.com')
        smtp_port   = 587             if is_gmail else int(smtp_config.get('port', 587))

        smtp_user = smtp_config.get('user')
        smtp_pass = smtp_config.get('pass')
        sender_name = smtp_config.get('sender_name') or from_name
        from_header = f"{sender_name} <{smtp_user}>" if sender_name else smtp_user

        msg = _build_msg(from_header, to_email, subject, html_body, attachment, include_unsubscribe)

        if attachment:
            att_ok, att_err = add_attachment_to_message(msg, attachment)
            if not att_ok:
                return {'success': False, 'error': f'Attachment error: {att_err}'}

        with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)

        return {'success': True, 'message': f'Email sent via SMTP to {to_email}'}

    except smtplib.SMTPAuthenticationError:
        return {'success': False, 'error': 'SMTP authentication failed — check your Gmail app password'}
    except smtplib.SMTPRecipientsRefused:
        return {'success': False, 'error': f'Recipient address rejected: {to_email}'}
    except Exception as e:
        return {'success': False, 'error': f'SMTP error: {str(e)}'}


def send_via_ses(aws_config, from_name, to_email, subject, html_body, attachment=None, include_unsubscribe=False):
    """Send email via AWS SES"""
    try:
        ses_client = boto3.client(
            'ses',
            region_name=aws_config.get('region', 'us-east-1'),
            aws_access_key_id=aws_config.get('access_key'),
            aws_secret_access_key=aws_config.get('secret_key')
        )
        
        from_email = aws_config.get('from_email', 'noreply@example.com')
        source = f"{from_name} <{from_email}>" if from_name else from_email

        if attachment:
            msg = _build_msg(source, to_email, subject, html_body, attachment, include_unsubscribe)
            att_ok, att_err = add_attachment_to_message(msg, attachment)
            if not att_ok:
                return {'success': False, 'error': f'Attachment error: {att_err}'}
            response = ses_client.send_raw_email(
                Source=source, Destinations=[to_email],
                RawMessage={'Data': msg.as_string()}
            )
        else:
            # Use send_raw_email even without attachments so we get multipart/alternative
            msg = _build_msg(source, to_email, subject, html_body, attachment=None, include_unsubscribe=include_unsubscribe)
            response = ses_client.send_raw_email(
                Source=source,
                Destinations=[to_email],
                RawMessage={'Data': msg.as_string()}
            )
        
        return {'success': True, 'message': f'Email sent via SES to {to_email}', 'message_id': response['MessageId']}
    except Exception as e:
        return {'success': False, 'error': f'SES error: {str(e)}'}


def send_via_ec2(ec2_url, smtp_config, from_name, to_email, subject, html_body, attachment=None, include_unsubscribe=False):
    """Send email via EC2 relay endpoint (JetMailer style - authenticated SMTP)"""
    try:
        payload = {
            'from_name': from_name,
            'to': to_email,
            'subject': subject,
            'html': html_body,
            'plain': _html_to_plain(html_body),  # proper plain-text for relay
            'smtp_config': smtp_config,
            'include_unsubscribe': include_unsubscribe,
        }
        if attachment:
            payload['attachment'] = attachment
        
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(ec2_url, data=data, method='POST')
        req.add_header('Content-Type', 'application/json')
        req.add_header('User-Agent', 'KINGMAILER/4.0')
        
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            return {
                'success': True,
                'message': f'Email sent via EC2 to {to_email}',
                'details': result
            }
    
    except Exception as e:
        return {'success': False, 'error': f'EC2 relay failed: {str(e)}'}


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            to_email = data.get('to', '').strip()
            subject = data.get('subject', 'No Subject')
            html_body = data.get('html', '')
            from_name = data.get('from_name', 'KINGMAILER')
            from_email = data.get('from_email', '')
            send_method = data.get('method', 'smtp')
            csv_row = data.get('csv_row', {})
            attachment = data.get('attachment')  # {name, content (base64), type}
            # Default False so single test emails never get Precedence:bulk or List-Unsubscribe
            # (those headers + an attachment = near-certain spam flag)
            include_unsubscribe = data.get('include_unsubscribe', False)
            
            if not to_email:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': 'Recipient email required'}).encode())
                return
            
            # Process spintax in subject and body
            subject = process_spintax(subject)
            html_body = process_spintax(html_body)
            
            # Replace all template tags including CSV row columns and recipient/sender tags
            subject   = _apply_tag_replacements(subject,   csv_row or {}, to_email, from_name, from_email)
            html_body = _apply_tag_replacements(html_body, csv_row or {}, to_email, from_name, from_email)
            
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
                result = send_via_smtp(smtp_config, from_name, to_email, subject, html_body, attachment, include_unsubscribe)
            
            elif send_method == 'ses':
                aws_config = data.get('aws_config')
                if not aws_config:
                    self.send_response(400)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({'success': False, 'error': 'AWS SES config required'}).encode())
                    return
                result = send_via_ses(aws_config, from_name, to_email, subject, html_body, attachment, include_unsubscribe)
            
            elif send_method == 'ec2':
                # EC2 Relay - Route email through EC2 IP on port 3000
                ec2_instance = data.get('ec2_instance')
                smtp_config = data.get('smtp_config')  # Optional - used if provided
                
                if ec2_instance and isinstance(ec2_instance, dict):
                    ec2_ip = ec2_instance.get('public_ip')
                    if ec2_ip and ec2_ip not in ('N/A', 'Pending...'):
                        ec2_url = f'http://{ec2_ip}:3000/relay'
                        result = send_via_ec2(ec2_url, smtp_config, from_name, to_email, subject, html_body, attachment, include_unsubscribe)
                        if result['success']:
                            result['message'] = f'Email sent via EC2 IP {ec2_ip} to {to_email}'
                    else:
                        result = {'success': False, 'error': 'EC2 instance has no public IP yet'}
                else:
                    ec2_url = data.get('ec2_url')
                    if not ec2_url:
                        result = {'success': False, 'error': 'No EC2 instance selected or instance not ready'}
                    else:
                        result = send_via_ec2(ec2_url, smtp_config, from_name, to_email, subject, html_body, attachment, include_unsubscribe)
            
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
