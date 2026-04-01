from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

msg = MIMEMultipart('mixed')
alt = MIMEMultipart('alternative')
text = MIMEText("hello plain", 'plain', 'utf-8')
html = MIMEText("<h1>hello</h1>", 'html', 'utf-8')

alt.attach(text)
alt.attach(html)
msg.attach(alt)

part = MIMEApplication(b"pdf data", "pdf")
msg.attach(part)

# RECURSIVE DELETE
def clean_mime(part, is_root=True):
    if not is_root:
        if 'MIME-Version' in part:
            del part['MIME-Version']
    if part.is_multipart():
        for sub in part.get_payload():
            clean_mime(sub, is_root=False)

clean_mime(msg)

raw = msg.as_string()
print('=== CLEANED RAW OUTPUT ===')
print(raw)
print('==================')
mv_count = raw.count('MIME-Version:')
print(f'MIME-Version count: {mv_count}')
