import sys
import base64
sys.path.insert(0, 'api')
from send_bulk import _build_message, add_attachment_to_message

fake_pdf = base64.b64encode(b'%PDF-1.4 fake content').decode()
attachment = {'name': 'invoice.pdf', 'content': fake_pdf, 'type': 'application/pdf'}

msg = _build_message('Sender <sender@gmail.com>', 'recv@gmail.com', 'Test Subject', '<h1>Hello</h1>', attachment=attachment)
add_attachment_to_message(msg, attachment)

print(msg.as_string())
