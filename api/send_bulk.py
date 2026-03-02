"""  
KINGMAILER v4.2 - Bulk Email Sending API
Features: CSV processing, SMTP/SES/EC2, Account Rotation, Spintax, Placeholders
"""

from http.server import BaseHTTPRequestHandler
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
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
        text = re.sub(r'\$' + re.escape(key) + r'(?=[^a-zA-Z0-9_]|$)', lambda m, v=val: v, text)
    return text


# ────────────────────────────────────────────────────────
# Helper: HTML to plain text
# ────────────────────────────────────────────────────────
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


# ────────────────────────────────────────────────────────
# Helper: attachment base64 → MIME part
# ────────────────────────────────────────────────────────
def add_attachment_to_message(msg, attachment):
    """Attach a base64-encoded file with proper RFC-compliant MIME headers.
    Returns (True, None) on success or (False, error_str).
    """
    if not attachment:
        return True, None
    try:
        import os as _os
        raw_b64 = attachment['content']
        raw_b64 += '=' * (-len(raw_b64) % 4)
        file_data = base64.b64decode(raw_b64)
        mime_type = attachment.get('type', 'application/octet-stream')
        filename  = attachment.get('name', 'attachment')
        
        # Log attachment details for debugging
        print(f'[ATTACHMENT] File: {filename}, Type: {mime_type}, Size: {len(file_data)} bytes')

        # Extension → proper MIME type map
        _EXT_MAP = {
            '.pdf':  'application/pdf',
            '.txt':  'text/plain',
            '.png':  'image/png',
            '.jpg':  'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif':  'image/gif',
            '.webp': 'image/webp',
            '.tiff': 'image/tiff',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.doc':  'application/msword',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.xls':  'application/vnd.ms-excel',
            '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            # HTML/HTM: treat as octet-stream to prevent inline rendering & spam triggers
            '.html': 'application/octet-stream',
            '.htm':  'application/octet-stream',
        }
        ext = _os.path.splitext(filename)[1].lower()
        if mime_type in ('application/octet-stream', '') and ext in _EXT_MAP:
            mime_type = _EXT_MAP[ext]

        main_type, sub_type = mime_type.split('/', 1) if '/' in mime_type else ('application', 'octet-stream')

        # RFC 2183: name= in Content-Type AND filename= in Content-Disposition must both
        # be present and match. Gmail/Outlook malware scanners flag attachments that
        # have Content-Disposition filename= but no Content-Type name= as suspicious/malformed.
        part = MIMEBase(main_type, sub_type, name=filename)
        part.set_payload(file_data)
        encoders.encode_base64(part)

        # RFC 2231 filename encoding: handles non-ASCII filenames correctly.
        # Falls back to plain ASCII for simple filenames.
        try:
            filename.encode('ascii')
            part.add_header('Content-Disposition', 'attachment', filename=filename)
        except (UnicodeEncodeError, AttributeError):
            part.add_header('Content-Disposition', 'attachment', filename=('utf-8', '', filename))

        msg.attach(part)
        return True, None
    except Exception as e:
        return False, str(e)

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
    """
    import html as _html_mod
    # Escape HTML entities first
    escaped = _html_mod.escape(text)
    # Split on blank lines → paragraphs
    paragraphs = re.split(r'\n\s*\n', escaped)
    html_parts = []
    for para in paragraphs:
        # Single newlines within a paragraph → <br>
        para_html = para.replace('\n', '<br>')
        html_parts.append(f'<p style="margin:0 0 1em 0;line-height:1.6;">{para_html}</p>')
    body = '\n'.join(html_parts)
    return (
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:14px;'
        'color:#222;max-width:650px;margin:0 auto;padding:20px;">'
        + body + '</div>'
    )

def _build_message(from_header, to_email, subject, html_body, attachment=None):
    """Build RFC-compliant MIME message. Auto-converts plain text to proper HTML."""
    if not _is_html(html_body):
        html_body = _plain_to_html(html_body)
    
    # When attachment is present, add filler text to improve text-to-attachment ratio
    if attachment:
        html_body += ('<br><br><p style="color:#666;font-size:11px;line-height:1.4;">'
                      'This message contains an attachment for your review. '
                      'Please ensure you have the necessary software to view the attached file. '
                      'If you have any questions or concerns, feel free to reply to this email.</p>')
    
    plain = _html_to_plain(html_body)

    # multipart/alternative: plain text MUST be first (RFC 2046)
    alt = MIMEMultipart('alternative')
    alt.attach(MIMEText(plain, 'plain', 'utf-8'))

    # HTML part — natively use utf-8 charset which handles encoding properly
    html_part = MIMEText(html_body, 'html', 'utf-8')
    alt.attach(html_part)

    # Always use multipart/mixed for consistent MIME structure
    msg = MIMEMultipart('mixed')
    msg.attach(alt)

    domain = _extract_domain(from_header)

    msg['From']              = from_header
    msg['To']                = to_email
    msg['Subject']           = subject
    msg['Date']              = formatdate(localtime=True)
    msg['Message-ID']        = make_msgid(domain=domain)
    msg['Reply-To']          = from_header
    # List-Unsubscribe required by Gmail/Yahoo 2024+ sender policy
    msg['List-Unsubscribe']  = f'<mailto:{from_header}?subject=unsubscribe>'
    msg['List-Unsubscribe-Post'] = 'List-Unsubscribe=One-Click'
    return msg




# ────────────────────────────────────────────────────────
# Sending functions (SMTP / SES / EC2) — all attachment-aware
# ────────────────────────────────────────────────────────
def send_email_smtp(smtp_config, from_name, recipient, subject, html_body, attachment=None):
    """Send single email via direct SMTP (Gmail/Outlook/custom).
    Builds a proper MIME structure with plain-text fallback and optional attachment.
    """
    try:
        is_gmail  = smtp_config.get('provider') == 'gmail'
        smtp_server = 'smtp.gmail.com' if is_gmail else smtp_config.get('host', 'smtp.gmail.com')
        smtp_port   = 587 if is_gmail else int(smtp_config.get('port', 587))
        smtp_user   = smtp_config.get('user')
        smtp_pass   = smtp_config.get('pass')
        sender_name = from_name or smtp_config.get('sender_name') or ''
        from_header = f"{sender_name} <{smtp_user}>" if sender_name else smtp_user

        print(f'[SMTP SEND] → {recipient}  server={smtp_server}:{smtp_port}')

        # Build proper MIME message (plain + html + optional attachment)
        msg = _build_message(from_header, recipient, subject, html_body, attachment)
        if attachment:
            print(f'[BULK-SMTP] Attaching file for {recipient}')
            ok, err = add_attachment_to_message(msg, attachment)
            if not ok:
                print(f'[BULK-SMTP ERROR] Attachment failed: {err}')
                return {'success': False, 'error': f'Attachment error: {err}'}
            print(f'[BULK-SMTP] Attachment added successfully')

        with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as server:
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


def send_email_ses(aws_config, from_name, recipient, subject, html_body, attachment=None):
    """Send single email via AWS SES with optional attachment support."""
    try:
        ses_client = boto3.client(
            'ses',
            region_name=aws_config.get('region', 'us-east-1'),
            aws_access_key_id=aws_config.get('access_key'),
            aws_secret_access_key=aws_config.get('secret_key')
        )
        from_email  = aws_config.get('from_email', 'noreply@example.com')
        source      = f"{from_name} <{from_email}>" if from_name else from_email

        if attachment:
            # Must use send_raw_email when there is an attachment
            msg = _build_message(source, recipient, subject, html_body, attachment)
            ok, err = add_attachment_to_message(msg, attachment)
            if not ok:
                return {'success': False, 'error': f'Attachment error: {err}'}
            ses_client.send_raw_email(
                Source=source,
                Destinations=[recipient],
                RawMessage={'Data': msg.as_string()}
            )
        else:
            ses_client.send_email(
                Source=source,
                Destination={'ToAddresses': [recipient]},
                Message={
                    'Subject': {'Data': subject, 'Charset': 'UTF-8'},
                    'Body': {
                        'Text': {'Data': _html_to_plain(html_body), 'Charset': 'UTF-8'},
                        'Html': {'Data': html_body, 'Charset': 'UTF-8'}
                    }
                }
            )
        return {'success': True}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def send_email_ec2(ec2_url, smtp_config, from_name, recipient, subject, html_body, attachment=None):
    """Send email via EC2 relay server with optional attachment."""
    try:
        print(f'[EC2 RELAY] Sending to {recipient} via {ec2_url}')
        payload = {
            'from_name': from_name,
            'to':        recipient,
            'subject':   subject,
            'html':      html_body,
            'smtp_config': smtp_config,
        }
        if attachment:
            payload['attachment'] = attachment

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
            from_name = data.get('from_name', 'KINGMAILER')
            from_email = data.get('from_email', '')
            
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
                
                # Send email based on method
                attachment = data.get('attachment')  # {name, content (base64), type}

                if method == 'smtp' and smtp_pool:
                    smtp_config = smtp_pool.get_next()
                    print(f'\n[EMAIL {index+1}] Method: SMTP → {recipient}')
                    result = send_email_smtp(smtp_config, _eff_name, recipient, subject, html_body, attachment)

                elif method == 'ses' and ses_pool:
                    ses_config = ses_pool.get_next()
                    print(f'\n[EMAIL {index+1}] Method: SES → {recipient}')
                    result = send_email_ses(ses_config, _eff_name, recipient, subject, html_body, attachment)
                
                elif method == 'ec2' and ec2_pool:
                    ec2_instance = ec2_pool.get_next()
                    smtp_config  = smtp_pool.get_next() if smtp_pool else None

                    print(f'\n[EMAIL {index+1}] Method: EC2 RELAY → {recipient}')

                    if ec2_instance:
                        ec2_ip = ec2_instance.get('public_ip')
                        if ec2_ip and ec2_ip != 'N/A' and ec2_ip != 'Pending...':
                            relay_url = f'http://{ec2_ip}:3000/relay'
                            print(f'[EC2 RELAY] Connecting to {relay_url}')
                            result = send_email_ec2(relay_url, smtp_config, _eff_name, recipient, subject, html_body, attachment)
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
