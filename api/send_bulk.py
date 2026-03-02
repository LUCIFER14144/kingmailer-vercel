"""
KINGMAILER v4.2 - Bulk Email Sending API
Inbox Fix: Minimal spam-clean headers, proper MIME structure, RFC 2231 attachment filenames
"""

from http.server import BaseHTTPRequestHandler
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.utils import formatdate, make_msgid
import boto3
import json, csv, io, os, time, random, re, uuid, base64, urllib.request, urllib.error, string
from datetime import datetime

def process_spintax(text):
    if not text: return text
    pattern = r'\{([^{}]+)\}'
    def replace_fn(match):
        options = match.group(1).split('|')
        return random.choice(options).strip()
    max_iter = 10; iteration = 0
    while '{' in text and '|' in text and iteration < max_iter:
        text = re.sub(pattern, replace_fn, text); iteration += 1
    return text

def replace_template_tags(text, row_data, recipient_email='', sender_name='', sender_email=''):
    if not text: return text
    import random as _rnd, string as _str
    _US_FIRST = ['James','John','Robert','Michael','William','David','Richard','Joseph','Thomas','Charles','Mary','Patricia','Jennifer','Linda','Barbara','Elizabeth','Susan','Jessica','Sarah','Karen']
    _US_LAST  = ['Smith','Johnson','Williams','Brown','Jones','Garcia','Miller','Davis','Rodriguez','Martinez','Wilson','Anderson','Taylor','Thomas','Moore','Jackson','Thompson','White']
    _US_CITIES = [('New York','NY','10001'),('Los Angeles','CA','90001'),('Chicago','IL','60601'),('Houston','TX','77001'),('Phoenix','AZ','85001'),('Dallas','TX','75201'),('Austin','TX','78701'),('Seattle','WA','98101'),('Denver','CO','80201'),('Nashville','TN','37201'),('Charlotte','NC','28201'),('Boston','MA','02101'),('Las Vegas','NV','89101'),('Miami','FL','33101'),('Atlanta','GA','30301')]
    _US_STREETS = ['Main St','Oak Ave','Maple Dr','Pine Blvd','Cedar Lane','Elm Rd','Washington Blvd','Park Ave','Lake Dr','Hillside Way','Sunset Blvd','River Rd']
    _US_CO = ['Apex Solutions LLC','Bright Path Inc','Cascade Digital Corp','Delta Group','Everest Ventures','Global Tech Inc','Harbor Networks LLC','Keystone Consulting','Meridian Group LLC','Nexus Innovations','Pinnacle Growth Inc','Quantum Systems','Summit Partners LLC']
    _US_PR = ['Premium Membership','Express Delivery','Annual Plan','Business Package','Standard Subscription','Pro License','Elite Bundle','Starter Kit','Enterprise Plan']
    def _rn(n): return ''.join(_rnd.choices(_str.digits, k=n))
    def _ra(n): return ''.join(_rnd.choices(_str.ascii_lowercase, k=n))
    def _ran(n, up=False):
        c = (_str.ascii_uppercase if up else _str.ascii_lowercase) + _str.digits
        return ''.join(_rnd.choices(c, k=n))
    first = _rnd.choice(_US_FIRST); last = _rnd.choice(_US_LAST)
    city, state, zipcode = _rnd.choice(_US_CITIES)
    sn = _rnd.randint(100,9999); st = _rnd.choice(_US_STREETS)
    ts13 = str(int(datetime.now().timestamp()*1000))[:13]
    tag_map = {
        'name': recipient_email.split('@')[0] if recipient_email else (first+' '+last),
        'email': recipient_email, 'recipient': recipient_email,
        'recipientName': first+' '+last, 'sender': sender_email,
        'sendername': sender_name or (first+' '+last),
        'sendertag': f"{sender_name} <{sender_email}>" if sender_name else sender_email,
        'randName': f"{first} {last}", 'rnd_company_us': _rnd.choice(_US_CO),
        'address': f"{sn} {st}, {city}, {state} {zipcode}",
        'street': f"{sn} {st}", 'city': city, 'state': state, 'zipcode': zipcode, 'zip': zipcode,
        'invcnumber': 'INV-'+_rn(8), 'ordernumber': 'ORD-'+_rn(8),
        'product': _rnd.choice(_US_PR),
        'amount': f"${_rnd.randint(999,99999)/100:.2f}",
        'charges': f"${_rnd.randint(499,49999)/100:.2f}",
        'quantity': str(_rnd.randint(1,99)), 'number': _rn(6),
        'date': datetime.now().strftime('%B %d, %Y'), 'time': datetime.now().strftime('%I:%M %p'),
        'year': str(datetime.now().year), 'id': _rn(10),
        'random_name': f"{first} {last}", 'company': _rnd.choice(_US_CO), 'company_name': _rnd.choice(_US_CO),
        '13_digit': ts13, 'unique_id': ts13, 'unique13digit': ts13,
        'random_6': ''.join(_rnd.choices(_str.ascii_letters+_str.digits,k=6)),
        'random_8': ''.join(_rnd.choices(_str.ascii_letters+_str.digits,k=8)),
        'unique16_484': f"{_rn(4)}-{_rn(8)}-{_rn(4)}",
        'unique16_565': f"{_rn(5)}-{_rn(6)}-{_rn(5)}",
        'unique16_4444': f"{_rn(4)}-{_rn(4)}-{_rn(4)}-{_rn(4)}",
        'unique16_88': f"{_rn(8)}-{_rn(8)}",
        'unique14alphanum': _ran(14,up=True), 'unique11alphanum': _ran(11,up=True),
        'unique14alpha': _ra(14).upper(),
        'alpha_random_small': _ra(6), 'alpha_short': _ra(4), 'random_three_chars': _ran(3),
    }
    if row_data:
        for k, v in row_data.items():
            if k: tag_map[k] = str(v)
    sorted_keys = sorted(tag_map.keys(), key=len, reverse=True)
    for key in sorted_keys:
        val = str(tag_map[key])
        text = re.sub(r'\{\{'+re.escape(key)+r'\}\}', lambda m,v=val: v, text, flags=re.IGNORECASE)
        text = re.sub(r'\$'+re.escape(key)+r'(?=[^a-zA-Z0-9_]|$)', lambda m,v=val: v, text)
    return text

def _html_to_plain(html):
    text = re.sub(r'<br\s*/?>', '\n', html, flags=re.IGNORECASE)
    text = re.sub(r'<p[^>]*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</p>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<li[^>]*>', '\n- ', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def add_attachment_to_message(msg, attachment):
    if not attachment: return True, None
    try:
        import os as _os
        raw_b64 = attachment['content'] + '=' * (-len(attachment['content']) % 4)
        file_data = base64.b64decode(raw_b64)
        mime_type = attachment.get('type', 'application/octet-stream')
        filename  = attachment.get('name', 'attachment')
        _EXT_MAP = {
            '.pdf':'application/pdf','.txt':'text/plain','.png':'image/png',
            '.jpg':'image/jpeg','.jpeg':'image/jpeg','.gif':'image/gif',
            '.webp':'image/webp','.tiff':'image/tiff',
            '.docx':'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.doc':'application/msword',
            '.xlsx':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.xls':'application/vnd.ms-excel',
            '.pptx':'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            '.html':'application/octet-stream','.htm':'application/octet-stream',
        }
        ext = _os.path.splitext(filename)[1].lower()
        if mime_type in ('application/octet-stream', '') and ext in _EXT_MAP:
            mime_type = _EXT_MAP[ext]
        main_type, sub_type = mime_type.split('/',1) if '/' in mime_type else ('application','octet-stream')
        part = MIMEBase(main_type, sub_type)
        part.set_payload(file_data)
        encoders.encode_base64(part)
        try:
            filename.encode('ascii')
            part.add_header('Content-Disposition', 'attachment', filename=filename)
        except UnicodeEncodeError:
            part.add_header('Content-Disposition', 'attachment', filename=('utf-8','',filename))
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
    return bool(re.search(r'<[a-z][a-z0-9]*[\s>/]', text or '', re.IGNORECASE))

def _plain_to_html(text):
    import html as _html_mod
    escaped = _html_mod.escape(text)
    paragraphs = re.split(r'\n\s*\n', escaped)
    html_parts = [f'<p style="margin:0 0 1em 0;line-height:1.6;">{p.replace(chr(10), "<br>")}</p>' for p in paragraphs]
    body = '\n'.join(html_parts)
    return '<div style="font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#222;max-width:650px;margin:0 auto;padding:20px;">' + body + '</div>'

def _build_message(from_header, to_email, subject, html_body, attachment=None):
    if not _is_html(html_body):
        html_body = _plain_to_html(html_body)
    plain = _html_to_plain(html_body)
    alt = MIMEMultipart('alternative')
    alt.attach(MIMEText(plain, 'plain', 'utf-8'))
    alt.attach(MIMEText(html_body, 'html', 'utf-8'))
    if attachment:
        msg = MIMEMultipart('mixed')
        msg.attach(alt)
    else:
        msg = alt
    domain = _extract_domain(from_header)
    msg['From']       = from_header
    msg['To']         = to_email
    msg['Subject']    = subject
    msg['Date']       = formatdate(localtime=True)
    msg['Message-ID'] = make_msgid(domain=domain)
    msg['Reply-To']   = from_header
    msg['X-Mailer']   = 'KINGMAILER'
    return msg

def send_email_smtp(smtp_config, from_name, recipient, subject, html_body, attachment=None):
    try:
        is_gmail    = smtp_config.get('provider') == 'gmail'
        smtp_server = 'smtp.gmail.com' if is_gmail else smtp_config.get('host', 'smtp.gmail.com')
        smtp_port   = 587 if is_gmail else int(smtp_config.get('port', 587))
        smtp_user   = smtp_config.get('user')
        smtp_pass   = smtp_config.get('pass')
        sender_name = from_name or smtp_config.get('sender_name') or ''
        from_header = f"{sender_name} <{smtp_user}>" if sender_name else smtp_user
        msg = _build_message(from_header, recipient, subject, html_body, attachment)
        if attachment:
            ok, err = add_attachment_to_message(msg, attachment)
            if not ok: return {'success': False, 'error': f'Attachment error: {err}'}
        with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as server:
            server.ehlo(); server.starttls(); server.ehlo()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        return {'success': True}
    except smtplib.SMTPAuthenticationError:
        return {'success': False, 'error': 'SMTP authentication failed'}
    except smtplib.SMTPRecipientsRefused:
        return {'success': False, 'error': f'Recipient rejected: {recipient}'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def send_email_ses(aws_config, from_name, recipient, subject, html_body, attachment=None):
    try:
        ses_client = boto3.client('ses',
            region_name=aws_config.get('region','us-east-1'),
            aws_access_key_id=aws_config.get('access_key'),
            aws_secret_access_key=aws_config.get('secret_key'))
        from_email = aws_config.get('from_email', 'noreply@example.com')
        source     = f"{from_name} <{from_email}>" if from_name else from_email
        if attachment:
            msg = _build_message(source, recipient, subject, html_body, attachment)
            ok, err = add_attachment_to_message(msg, attachment)
            if not ok: return {'success': False, 'error': f'Attachment error: {err}'}
            ses_client.send_raw_email(Source=source, Destinations=[recipient], RawMessage={'Data': msg.as_string()})
        else:
            ses_client.send_email(Source=source,
                Destination={'ToAddresses': [recipient]},
                Message={'Subject': {'Data': subject, 'Charset': 'UTF-8'},
                    'Body': {'Text': {'Data': _html_to_plain(html_body), 'Charset': 'UTF-8'},
                             'Html': {'Data': html_body, 'Charset': 'UTF-8'}}})
        return {'success': True}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def send_email_ec2(ec2_url, smtp_config, from_name, recipient, subject, html_body, attachment=None):
    try:
        payload = {'from_name': from_name, 'to': recipient, 'subject': subject, 'html': html_body, 'smtp_config': smtp_config}
        if attachment: payload['attachment'] = attachment
        data = json.dumps(payload).encode('utf-8')
        req  = urllib.request.Request(ec2_url, data=data, method='POST')
        req.add_header('Content-Type', 'application/json')
        with urllib.request.urlopen(req, timeout=30) as response:
            return {'success': True, 'response': json.loads(response.read().decode('utf-8'))}
    except urllib.error.HTTPError as e:
        return {'success': False, 'error': f'HTTP {e.code}: {e.read().decode("utf-8") if e.fp else str(e)}'}
    except urllib.error.URLError as e:
        return {'success': False, 'error': f'Connection failed: {str(e.reason)}'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

class SMTPPool:
    def __init__(self, accounts): self.accounts = accounts; self.current_index = 0
    def get_next(self):
        if not self.accounts: return None
        account = self.accounts[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.accounts)
        return account

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            csv_data         = data.get('csv_data', data.get('csv', ''))
            subject_template = data.get('subject', 'No Subject')
            html_template    = data.get('html', '')
            method           = data.get('method', 'smtp')
            min_delay        = int(data.get('min_delay', 2000))
            max_delay        = int(data.get('max_delay', 5000))
            from_name        = data.get('from_name', 'KINGMAILER')
            from_email       = data.get('from_email', '')
            smtp_configs  = data.get('smtp_configs', [])
            ses_configs   = data.get('ses_configs', [])
            ec2_instances = data.get('ec2_instances', [])
            if not csv_data:
                self._json(400, {'success': False, 'error': 'CSV data required'}); return
            rows = list(csv.DictReader(io.StringIO(csv_data)))
            if not rows:
                self._json(400, {'success': False, 'error': 'No data in CSV'}); return
            if 'email' not in rows[0]:
                self._json(400, {'success': False, 'error': 'CSV must have "email" column'}); return
            smtp_pool = SMTPPool(smtp_configs) if smtp_configs else None
            ses_pool  = SMTPPool(ses_configs)  if ses_configs  else None
            ec2_pool  = SMTPPool(ec2_instances) if ec2_instances else None
            results = []; success_count = 0; fail_count = 0
            for index, row in enumerate(rows):
                recipient = row.get('email', '').strip()
                if not recipient: continue
                subject   = process_spintax(subject_template)
                html_body = process_spintax(html_template)
                _use_random_name = data.get('random_sender_name', False)
                if _use_random_name:
                    _fn = random.choice(['James','John','Robert','Michael','William','David','Richard','Mary','Patricia','Jennifer','Linda','Barbara','Elizabeth','Susan','Jessica','Sarah','Karen','Emily','Amanda'])
                    _ln = random.choice(['Smith','Johnson','Williams','Brown','Jones','Garcia','Miller','Davis','Rodriguez','Martinez','Wilson','Anderson','Taylor'])
                    _eff_name = f"{_fn} {_ln}"
                else:
                    _eff_name = from_name
                _cur_smtp    = (smtp_pool.accounts[smtp_pool.current_index % max(1,len(smtp_pool.accounts))] if smtp_pool and smtp_pool.accounts else {})
                _cur_s_email = _cur_smtp.get('user', from_email) if isinstance(_cur_smtp, dict) else from_email
                subject   = replace_template_tags(subject,   row, recipient, sender_name=_eff_name, sender_email=_cur_s_email)
                html_body = replace_template_tags(html_body, row, recipient, sender_name=_eff_name, sender_email=_cur_s_email)
                attachment = data.get('attachment')
                if method == 'smtp' and smtp_pool:
                    result = send_email_smtp(smtp_pool.get_next(), _eff_name, recipient, subject, html_body, attachment)
                elif method == 'ses' and ses_pool:
                    result = send_email_ses(ses_pool.get_next(), _eff_name, recipient, subject, html_body, attachment)
                elif method == 'ec2' and ec2_pool:
                    ec2_instance = ec2_pool.get_next()
                    smtp_config  = smtp_pool.get_next() if smtp_pool else None
                    if ec2_instance:
                        ec2_ip = ec2_instance.get('public_ip')
                        if ec2_ip and ec2_ip not in ('N/A', 'Pending...'):
                            result = send_email_ec2(f'http://{ec2_ip}:3000/relay', smtp_config, _eff_name, recipient, subject, html_body, attachment)
                        else:
                            result = {'success': False, 'error': 'EC2 instance has no public IP yet'}
                    else:
                        result = {'success': False, 'error': 'No EC2 instances available'}
                else:
                    result = {'success': False, 'error': f'No {method} accounts configured'}
                if result['success']:
                    success_count += 1; results.append({'email': recipient, 'status': 'sent'})
                else:
                    fail_count += 1; results.append({'email': recipient, 'status': 'failed', 'error': result.get('error','Unknown')})
                if index < len(rows) - 1:
                    time.sleep(random.randint(min_delay, max_delay) / 1000.0)
            self._json(200, {'success': True,
                'message': f'Bulk send completed: {success_count} sent, {fail_count} failed',
                'results': {'total': len(rows), 'sent': success_count, 'failed': fail_count, 'details': results}})
        except Exception as e:
            self._json(500, {'success': False, 'error': str(e)})

    def _json(self, status, payload):
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()