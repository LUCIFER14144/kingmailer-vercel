"""
Quick test endpoint to verify placeholder replacement
"""
from http.server import BaseHTTPRequestHandler
import json
import re
import random
import string
from datetime import datetime

def process_spintax(text):
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

def replace_template_tags(text, recipient_email=''):
    if not text:
        return text
    
    def gen_random_name():
        first = ['James', 'John', 'Robert', 'Michael', 'William']
        last = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones']
        return f"{random.choice(first)} {random.choice(last)}"
    
    def gen_company():
        prefixes = ['Tech', 'Global', 'Digital', 'Smart', 'Innovative']
        suffixes = ['Solutions', 'Systems', 'Corporation', 'Industries', 'Group']
        return f"{random.choice(prefixes)} {random.choice(suffixes)}"
    
    def gen_13_digit():
        timestamp = int(datetime.now().timestamp() * 1000)
        random_suffix = random.randint(100, 999)
        id_str = f"{timestamp}{random_suffix}"
        return id_str[:13]
    
    replacements = {
        'random_name': gen_random_name(),
        'name': gen_random_name(),
        'company': gen_company(),
        'company_name': gen_company(),
        '13_digit': gen_13_digit(),
        'unique_id': gen_13_digit(),
        'date': datetime.now().strftime('%B %d, %Y'),
        'time': datetime.now().strftime('%I:%M %p'),
        'year': str(datetime.now().year),
        'random_6': ''.join(random.choices(string.ascii_letters + string.digits, k=6)),
        'random_8': ''.join(random.choices(string.ascii_letters + string.digits, k=8)),
        'recipient': recipient_email,
        'email': recipient_email
    }
    
    for tag, value in replacements.items():
        pattern = r'\{\{' + re.escape(tag) + r'\}\}'
        text = re.sub(pattern, str(value), text, flags=re.IGNORECASE)
    
    return text

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            subject = data.get('subject', '')
            html = data.get('html', '')
            to_email = data.get('to', 'test@example.com')
            
            # Process
            subject_original = subject
            html_original = html
            
            subject = process_spintax(subject)
            html = process_spintax(html)
            subject = replace_template_tags(subject, to_email)
            html = replace_template_tags(html, to_email)
            
            result = {
                'success': True,
                'original': {
                    'subject': subject_original,
                    'html': html_original[:200] + '...' if len(html_original) > 200 else html_original
                },
                'processed': {
                    'subject': subject,
                    'html': html[:200] + '...' if len(html) > 200 else html
                },
                'placeholders_found': {
                    'subject': len(re.findall(r'\{\{[^}]+\}\}', subject_original)),
                    'html': len(re.findall(r'\{\{[^}]+\}\}', html_original))
                },
                'placeholders_remaining': {
                    'subject': len(re.findall(r'\{\{[^}]+\}\}', subject)),
                    'html': len(re.findall(r'\{\{[^}]+\}\}', html))
                }
            }
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(result, indent=2).encode())
            
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
