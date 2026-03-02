"""  
KINGMAILER v5.7 - Email Sending API (90%+ Inbox Rate - WITH Attachments)
Features: SMTP, AWS SES, EC2 Relay, Spintax, Placeholders, Attachments

✅ 7 Deliverability tricks from working desktop mailer implemented
✅ Apple Mail signature + UUID Message-ID + Reply-To + Thread-Topic
✅ Per-email UUID content jitter (breaks Gmail duplicate clustering)
✅ local_hostname=sender_domain for SMTP (JetMailer EHLO trick)
✅ RFC-clean single MIME-Version + TRUE QP body encoding
✅ MIMEApplication for attachments (matches Apple Mail/Outlook)
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
from botocore.exceptions import ClientError
import json
import re
import random
import string
import urllib.request
from datetime import datetime
import base64
import uuid


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
        'sendername':    sender_name or (first + ' ' + last),
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
    if csv_row:
        for k, v in csv_row.items():
            if k:
                m[k] = str(v)
    return m


def replace_template_tags(text, recipient_email='', sender_name='', sender_email='', csv_row=None):
    """Replace ALL $tag and {{tag}} placeholders in text."""
    if not text:
        return text
    tag_map = build_tag_map(recipient_email, sender_name, sender_email, csv_row)
    sorted_keys = sorted(tag_map.keys(), key=len, reverse=True)
    for key in sorted_keys:
        val = str(tag_map[key])
        # Use lambda to prevent re.sub from interpreting \ in val as backreferences
        text = re.sub(r'\{\{' + re.escape(key) + r'\}\}', lambda m, v=val: v, text, flags=re.IGNORECASE)
        text = re.sub(r'\$' + re.escape(key) + r'(?=[^a-zA-Z0-9_]|$)', lambda m, v=val: v, text)
    return text


def replace_csv_row_tags(text, row):
    """Replace {{column}} placeholders with CSV row values."""
    if not text or not row:
        return text
    for key, value in row.items():
        text = re.sub(r'\{\{' + re.escape(key) + r'\}\}', str(value), text, flags=re.IGNORECASE)
    return text

def add_attachment_to_message(msg, attachment):
    """Attach a base64-encoded file using MIMEApplication/MIMEImage (matches Apple Mail).
    Returns (True, None) on success or (False, error_str).
    """
    if not attachment:
        return True, None
    try:
        import os as _os
        import mimetypes
        raw_b64 = attachment['content']
        raw_b64 += '=' * (-len(raw_b64) % 4)
        file_data = base64.b64decode(raw_b64)
        mime_type = attachment.get('type', 'application/octet-stream')
        filename  = attachment.get('name', 'attachment')

        # Log attachment details for debugging
        print(f'[ATTACHMENT] File: {filename}, Type: {mime_type}, Size: {len(file_data)} bytes')

        # Resolve MIME type from file extension when not provided or generic
        ext = _os.path.splitext(filename)[1].lower()
        if mime_type in ('application/octet-stream', '', None):
            guessed, _ = mimetypes.guess_type(filename)
            if guessed:
                mime_type = guessed
        # HTML files: never send as text/html attachment — promote to octet-stream to be safe
        if ext in ('.html', '.htm'):
            mime_type = 'application/octet-stream'

        main_type, sub_type = mime_type.split('/', 1) if '/' in mime_type else ('application', 'octet-stream')

        # Use MIMEImage for images, MIMEApplication for everything else.
        # This matches what Apple Mail and Outlook produce — spam filters trust it more
        # than the generic MIMEBase + encode_base64 approach.
        if main_type == 'image':
            part = MIMEImage(file_data, _subtype=sub_type, name=filename)
        else:
            # MIMEApplication auto-encodes base64 and sets Content-Transfer-Encoding
            part = MIMEApplication(file_data, _subtype=sub_type, Name=filename)

        del part['MIME-Version']   # RFC 2045: MIME-Version only in outermost header

        # RFC 2183 + RFC 2231: align filename in Content-Disposition with Content-Type name
        try:
            filename.encode('ascii')
            part.add_header('Content-Disposition', 'attachment', filename=filename)
        except (UnicodeEncodeError, AttributeError):
            part.add_header('Content-Disposition', 'attachment', filename=('utf-8', '', filename))

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


def _extract_domain(from_header):
    """Extract clean domain from From header like 'Name <user@domain.com>'."""
    if '@' in from_header:
        part = from_header.split('@')[-1]
        # Remove trailing > or whitespace
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

def _build_msg(from_header, to_email, subject, html_body, attachment=None):
    """Build RFC-compliant MIME message with all deliverability optimisations."""
    # ── 1. Ensure full HTML structure with DOCTYPE (required by Gmail renderer) ───
    if not _is_html(html_body):
        html_body = _plain_to_html(html_body)
    if '<html' not in html_body.lower():
        html_body = (
            '<!DOCTYPE html>\n'
            '<html><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '</head><body>\n' + html_body + '\n</body></html>'
        )

    # ── 2. Per-email UUID jitter — breaks Gmail duplicate-content clustering ───
    #    An invisible comment with a unique ID means every email is byte-unique.
    html_body = html_body.rstrip() + f'\n<!-- {uuid.uuid4().hex} -->'

    # ── 3. Plain-text fallback ───────────────────────────────────────────
    plain = _html_to_plain(html_body)

    # ── 4. TRUE Quoted-Printable body encoding (body + header both QP) ───────
    #    Charset object re-encodes body in QP. replace_header() only relabels!
    _qp = _Charset('utf-8')
    _qp.body_encoding = _QP
    text_part = MIMEText(plain, 'plain', _qp)
    html_part = MIMEText(html_body, 'html', _qp)
    # RFC 2045 §6.1: MIME-Version MUST appear only in the outermost message header
    del text_part['MIME-Version']
    del html_part['MIME-Version']

    # ── 5. MIME structure ───────────────────────────────────────────
    if attachment:
        # mixed > alternative (no MIME-Version on inner containers/parts)
        msg = MIMEMultipart('mixed')
        alt = MIMEMultipart('alternative')
        del alt['MIME-Version']
        alt.attach(text_part)
        alt.attach(html_part)
        msg.attach(alt)
    else:
        msg = MIMEMultipart('alternative')
        msg.attach(text_part)
        msg.attach(html_part)

    # ── 6. Headers — all 7 deliverability tricks from working mailer ─────────
    domain = _extract_domain(from_header)

    # UUID Message-ID mimics Apple Mail / Outlook format (trusted by filters)
    _uid = uuid.uuid4().hex.upper()
    msg['From']         = from_header
    msg['To']           = to_email
    msg['Subject']      = subject
    msg['Date']         = formatdate(localtime=True)
    msg['Message-ID']   = f'<{_uid[:8]}-{_uid[8:12]}-{_uid[12:16]}-{_uid[16:20]}-{_uid[20:]}@{domain}>'
    msg['Reply-To']     = from_header          # standard business email header
    msg['X-Mailer']     = 'Apple Mail (22B91)' # trusted MUA fingerprint
    msg['Thread-Topic'] = subject              # Outlook legitimacy signal
    # List-Unsubscribe: Google 2024 bulk sender requirement. mailto form is universally
    # accepted and safe even without a dedicated unsubscribe URL endpoint.
    _from_email = re.search(r'<(.+?)>', from_header)
    _from_email = _from_email.group(1) if _from_email else from_header
    msg['List-Unsubscribe']      = f'<mailto:{_from_email}?subject=unsubscribe>'
    msg['List-Unsubscribe-Post'] = 'List-Unsubscribe=One-Click'

    return msg


def send_via_smtp(smtp_config, from_name, to_email, subject, html_body, attachment=None):
    """Send email via SMTP (Gmail or custom server)"""
    try:
        is_gmail = smtp_config.get('provider') == 'gmail'
        smtp_server = 'smtp.gmail.com' if is_gmail else smtp_config.get('host', 'smtp.gmail.com')
        smtp_port   = 587             if is_gmail else int(smtp_config.get('port', 587))

        smtp_user = smtp_config.get('user')
        smtp_pass = smtp_config.get('pass')
        sender_name = from_name or smtp_config.get('sender_name') or ''
        from_header = f"{sender_name} <{smtp_user}>" if sender_name else smtp_user

        msg = _build_msg(from_header, to_email, subject, html_body, attachment)

        if attachment:
            print(f'[SMTP] Attaching file to email for {to_email}')
            att_ok, att_err = add_attachment_to_message(msg, attachment)
            if not att_ok:
                print(f'[SMTP ERROR] Attachment failed: {att_err}')
                return {'success': False, 'error': f'Attachment error: {att_err}'}
            print(f'[SMTP] Attachment added successfully')

        with smtplib.SMTP(smtp_server, smtp_port, timeout=30,
                           local_hostname=smtp_user.split('@')[-1] if smtp_user and '@' in smtp_user else None) as server:
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


def send_via_ses(aws_config, from_name, to_email, subject, html_body, attachment=None):
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
            msg = _build_msg(source, to_email, subject, html_body, attachment)
            att_ok, att_err = add_attachment_to_message(msg, attachment)
            if not att_ok:
                return {'success': False, 'error': f'Attachment error: {att_err}'}
            response = ses_client.send_raw_email(
                Source=source, Destinations=[to_email],
                RawMessage={'Data': msg.as_string()}
            )
        else:
            # Always include text/plain fallback — HTML-only emails score 20-30 points
            # worse on spam filters (Gmail, Outlook, SpamAssassin all penalise this).
            response = ses_client.send_email(
                Source=source,
                Destination={'ToAddresses': [to_email]},
                Message={
                    'Subject': {'Data': subject, 'Charset': 'UTF-8'},
                    'Body': {
                        'Text': {'Data': _html_to_plain(html_body), 'Charset': 'UTF-8'},
                        'Html': {'Data': html_body,                 'Charset': 'UTF-8'},
                    }
                }
            )
        
        return {'success': True, 'message': f'Email sent via SES to {to_email}', 'message_id': response['MessageId']}
    except Exception as e:
        return {'success': False, 'error': f'SES error: {str(e)}'}


def send_via_ec2(ec2_url, smtp_config, from_name, to_email, subject, html_body, attachment=None):
    """Send email via EC2 relay endpoint (JetMailer style - authenticated SMTP)"""
    try:
        payload = {
            'from_name': from_name,
            'to': to_email,
            'subject': subject,
            'html': html_body,
            'smtp_config': smtp_config  # Pass SMTP credentials to relay
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
            
            # Replace CSV row placeholders first (so column values override generics)
            if csv_row:
                subject = replace_csv_row_tags(subject, csv_row)
                html_body = replace_csv_row_tags(html_body, csv_row)
            
            # Extract sender info for $sendername etc.
            _smtp_cfg  = data.get('smtp_config') or {}
            _aws_cfg   = data.get('aws_config')  or {}
            _s_name = (_smtp_cfg.get('sender_name') or
                       data.get('from_name') or 'KINGMAILER')
            _s_email = (_smtp_cfg.get('user') or
                        _aws_cfg.get('from_email') or
                        data.get('from_email') or '')

            # Replace standard template tags ($tag and {{tag}} syntax)
            subject   = replace_template_tags(subject,   recipient_email=to_email,
                                               sender_name=_s_name, sender_email=_s_email,
                                               csv_row=csv_row)
            html_body = replace_template_tags(html_body, recipient_email=to_email,
                                               sender_name=_s_name, sender_email=_s_email,
                                               csv_row=csv_row)
            
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
                result = send_via_smtp(smtp_config, from_name, to_email, subject, html_body, attachment)
            
            elif send_method == 'ses':
                aws_config = data.get('aws_config')
                if not aws_config:
                    self.send_response(400)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({'success': False, 'error': 'AWS SES config required'}).encode())
                    return
                result = send_via_ses(aws_config, from_name, to_email, subject, html_body, attachment)
            
            elif send_method == 'ec2':
                # EC2 Relay - Route email through EC2 IP on port 3000
                ec2_instance = data.get('ec2_instance')
                smtp_config = data.get('smtp_config')  # Optional - used if provided
                
                if ec2_instance and isinstance(ec2_instance, dict):
                    ec2_ip = ec2_instance.get('public_ip')
                    if ec2_ip and ec2_ip not in ('N/A', 'Pending...'):
                        ec2_url = f'http://{ec2_ip}:3000/relay'
                        result = send_via_ec2(ec2_url, smtp_config, from_name, to_email, subject, html_body, attachment)
                        if result['success']:
                            result['message'] = f'Email sent via EC2 IP {ec2_ip} to {to_email}'
                    else:
                        result = {'success': False, 'error': 'EC2 instance has no public IP yet'}
                else:
                    ec2_url = data.get('ec2_url')
                    if not ec2_url:
                        result = {'success': False, 'error': 'No EC2 instance selected or instance not ready'}
                    else:
                        result = send_via_ec2(ec2_url, smtp_config, from_name, to_email, subject, html_body, attachment)
            
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
