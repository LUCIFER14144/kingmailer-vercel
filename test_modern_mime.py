"""
Test Python modern EmailMessage API vs legacy MIME* classes
The modern API was designed specifically to produce RFC-compliant output
without the MIME-Version sub-part pollution and other issues in legacy classes.
"""
import base64
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

fake_pdf = base64.b64encode(b'%PDF-1.4 test content').decode()
html_body = '<h1>Hello World</h1><p>This is a test email with an attachment.</p>'
plain_body = 'Hello World\n\nThis is a test email with an attachment.'

# ── Build using EmailMessage (modern Python 3.6+ API) ─────────────────────
msg = EmailMessage()
msg['From']       = 'Sender <sender@gmail.com>'
msg['To']         = 'recipient@gmail.com'
msg['Subject']    = 'Test Email With Attachment'
msg['Date']       = formatdate(localtime=True)
msg['Message-ID'] = make_msgid(domain='gmail.com')

# Set plain text content first
msg.set_content(plain_body)
# Add HTML as alternative
msg.add_alternative(html_body, subtype='html')
# Add attachment
pdf_bytes = base64.b64decode(fake_pdf + '=' * (-len(fake_pdf) % 4))
msg.add_attachment(pdf_bytes, maintype='application', subtype='pdf', filename='invoice.pdf')

raw = msg.as_string()
print('=== EmailMessage OUTPUT ===')
print(raw)
print()
print('=== ANALYSIS ===')
mv  = raw.count('MIME-Version:')
qp  = raw.count('quoted-printable')
b64 = raw.count('base64')
html_ok = 'Hello World' in raw and '<h1>' in raw

print(f'MIME-Version count : {mv}   (must be 1)')
print(f'QP encoded parts   : {qp}')
print(f'Base64 parts       : {b64}')
print(f'HTML body readable : {html_ok}')
print()
if mv == 1:
    print('>>> MIME-Version: PASS <<<')
else:
    print(f'>>> MIME-Version: FAIL ({mv} copies) <<<')
