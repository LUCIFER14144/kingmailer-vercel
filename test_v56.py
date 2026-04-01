"""v5.6 MIME structure verification"""
import base64, uuid
from email.charset import Charset as _Charset, QP as _QP
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.utils import formatdate

def _extract_domain(from_header):
    import re
    m = re.search(r'@([\w.-]+)', from_header)
    return m.group(1) if m else 'gmail.com'

def _html_to_plain(html):
    import re
    text = re.sub(r'<[^>]+>', '', html)
    return text.strip()

html_body = '<h1>Hello World</h1><p>Marketing body text here with links.</p>'

# ── Replicate v5.6 _build_msg ──────────────────────────────────────────────
from_header = 'Test Sender <test@gmail.com>'
to_email = 'recipient@gmail.com'
subject = 'Test Email With Attachment'

if '<html' not in html_body.lower():
    html_body = (
        '<!DOCTYPE html>\n'
        '<html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '</head><body>\n' + html_body + '\n</body></html>'
    )
html_body = html_body.rstrip() + f'\n<!-- {uuid.uuid4().hex} -->'
plain = _html_to_plain(html_body)

_qp = _Charset('utf-8')
_qp.body_encoding = _QP
text_part = MIMEText(plain, 'plain', _qp)
html_part = MIMEText(html_body, 'html', _qp)
del text_part['MIME-Version']
del html_part['MIME-Version']

fake_pdf = base64.b64encode(b'%PDF-1.4 test content').decode()
attachment = {'name': 'invoice.pdf', 'content': fake_pdf, 'type': 'application/pdf'}

msg = MIMEMultipart('mixed')
alt = MIMEMultipart('alternative')
del alt['MIME-Version']
alt.attach(text_part)
alt.attach(html_part)
msg.attach(alt)

raw_b64 = attachment['content']
raw_b64 += '=' * (-len(raw_b64) % 4)
file_data = base64.b64decode(raw_b64)
part = MIMEBase('application', 'pdf', name='invoice.pdf')
part.set_payload(file_data)
encoders.encode_base64(part)
del part['MIME-Version']
part.add_header('Content-Disposition', 'attachment', filename='invoice.pdf')
msg.attach(part)

domain = _extract_domain(from_header)
_uid = uuid.uuid4().hex.upper()
msg['From']         = from_header
msg['To']           = to_email
msg['Subject']      = subject
msg['Date']         = formatdate(localtime=True)
msg['Message-ID']   = f'<{_uid[:8]}-{_uid[8:12]}-{_uid[12:16]}-{_uid[16:20]}-{_uid[20:]}@{domain}>'
msg['Reply-To']     = from_header
msg['X-Mailer']     = 'Apple Mail (22B91)'
msg['Thread-Topic'] = subject

raw = msg.as_string()
print('=== FULL RAW EMAIL (v5.6) ===')
print(raw)
print()

mv  = raw.count('MIME-Version:')
qp  = raw.count('quoted-printable')
b64 = raw.count('base64')
html_ok = '<h1>Hello World</h1>' in raw
uuid_ok = '<!-- ' in raw
reply_to_ok = 'Reply-To' in raw
xmailer_ok = 'Apple Mail' in raw
msgid_ok = 'Message-ID' in raw and '@gmail.com>' in raw

print('=== ANALYSIS ===')
print(f'MIME-Version count : {mv}   {"PASS" if mv==1 else "FAIL"}')
print(f'QP encoded parts   : {qp}   {"PASS" if qp==2 else "FAIL"}')
print(f'Base64 (attach)    : {b64}  {"PASS" if b64==1 else "FAIL"}')
print(f'HTML body readable : {html_ok}  {"PASS" if html_ok else "FAIL"}')
print(f'UUID jitter        : {uuid_ok}  {"PASS" if uuid_ok else "FAIL"}')
print(f'Reply-To header    : {reply_to_ok}  {"PASS" if reply_to_ok else "FAIL"}')
print(f'X-Mailer header    : {xmailer_ok}  {"PASS" if xmailer_ok else "FAIL"}')
print(f'UUID Message-ID    : {msgid_ok}  {"PASS" if msgid_ok else "FAIL"}')
print()
if all([mv==1, qp==2, b64==1, html_ok, uuid_ok, reply_to_ok, xmailer_ok, msgid_ok]):
    print('>>> ALL 8 CHECKS PASS — READY TO DEPLOY <<<')
else:
    print('>>> SOME CHECKS FAILED <<<')
