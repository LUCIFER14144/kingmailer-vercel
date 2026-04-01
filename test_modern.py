from email.message import EmailMessage
import base64

msg = EmailMessage()
msg['Subject'] = "Test"
msg['From'] = "sender@gmail.com"
msg['To'] = "recv@gmail.com"
msg.set_content("Hello plain")
msg.add_alternative("<h1>Hello html</h1>", subtype='html')

# Add attachment
fake_pdf = b'%PDF-1.4 fake content'
msg.add_attachment(fake_pdf, maintype='application', subtype='pdf', filename='invoice.pdf')

raw = msg.as_string()
print('=== MODERN RAW OUTPUT ===')
print(raw)
print('==================')
mv_count = raw.count('MIME-Version:')
print(f'MIME-Version count: {mv_count}')
