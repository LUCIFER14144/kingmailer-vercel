"""
Test endpoint for placeholder replacement
"""
from http.server import BaseHTTPRequestHandler
import json
import re
import random
import string
from datetime import datetime


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


def replace_template_tags(text, recipient_email=''):
    """Replace all template tags in text"""
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
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_POST(self):
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            test_text = data.get('text', '')
            recipient = data.get('recipient', 'test@example.com')
            
            # Process
            original = test_text
            processed = process_spintax(test_text)
            processed = replace_template_tags(processed, recipient)
            
            # Count replacements
            original_placeholders = len(re.findall(r'\{\{[^}]+\}\}', original))
            remaining_placeholders = len(re.findall(r'\{\{[^}]+\}\}', processed))
            replaced_count = original_placeholders - remaining_placeholders
            
            result = {
                'success': True,
                'original': original,
                'processed': processed,
                'stats': {
                    'original_placeholders': original_placeholders,
                    'remaining_placeholders': remaining_placeholders,
                    'replaced_count': replaced_count,
                    'all_replaced': remaining_placeholders == 0
                }
            }
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({
                'success': False,
                'error': str(e)
            }).encode())
