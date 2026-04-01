import sys
sys.path.insert(0, 'api')

from email.charset import Charset as _Charset, QP as _QP
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.utils import formatdate, make_msgid
import base64

# ── Exact replica of v5.5 _build_msg ──────────────────────────────────────
def _build_msg(from_header, to_email, subject, html_body, attachment=None):
    plain = 'Hello plain text version'
    _qp = _Charset('utf-8')
    _qp.body_encoding = _QP
    text_part = MIMEText(plain, 'plain', _qp)
    html_part = MIMEText(html_body, 'html', _qp)
    del text_part['MIME-Version']
    del html_part['MIME-Version']
    if attachment:
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
    domain = 'gmail.com'
    msg['From'] = from_header
    msg['To'] = to_email
    msg['Subject'] = subject
    msg['Date'] = formatdate(localtime=True)
    msg['Message-ID'] = make_msgid(domain=domain)
    return msg

# ── Exact replica of v5.5 add_attachment_to_message ───────────────────────
def add_attachment(msg, attachment):
    raw_b64 = attachment['content']
    raw_b64 += '=' * (-len(raw_b64) % 4)
    file_data = base64.b64decode(raw_b64)
    mime_type = attachment.get('type', 'application/octet-stream')
    filename  = attachment.get('name', 'attachment')
    main_type, sub_type = mime_type.split('/', 1) if '/' in mime_type else ('application', 'octet-stream')
    part = MIMEBase(main_type, sub_type, name=filename)
    part.set_payload(file_data)
    encoders.encode_base64(part)
    del part['MIME-Version']
    part.add_header('Content-Disposition', 'attachment', filename=filename)
    msg.attach(part)

# ── Simulate real attachment ───────────────────────────────────────────────
fake_pdf  = base64.b64encode(b'%PDF-1.4 fake content').decode()
attachment = {'name': 'invoice.pdf', 'content': fake_pdf, 'type': 'application/pdf'}

msg = _build_msg('Sender <sender@gmail.com>', 'recv@gmail.com',
                 'Test Subject', '<h1>Hello</h1><p>Body text here.</p>', attachment)
add_attachment(msg, attachment)

raw = msg.as_string()
print('=== FULL RAW EMAIL ===')
print(raw)
print()
print('=== ANALYSIS ===')
mv  = raw.count('MIME-Version:')
qp  = raw.count('quoted-printable')
b64 = raw.count('base64')
html_ok = '<h1>Hello</h1>' in raw
print(f'MIME-Version count : {mv}   (PASS=1, FAIL>=2)')
print(f'QP encoded parts   : {qp}   (PASS=2, text+html)')
print(f'Base64 parts       : {b64}  (PASS=1, attachment only)')
print(f'HTML body readable : {html_ok}')
print()
if mv == 1 and qp == 2 and b64 == 1 and html_ok:
    print('>>> ALL PASS - MIME structure is RFC-compliant <<<')
else:
    print('>>> FAIL - MIME structure has issues <<<')
