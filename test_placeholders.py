#!/usr/bin/env python3
"""
Test placeholder replacement locally
"""
import re
import random
import string
from datetime import datetime

def replace_template_tags(text, recipient_email='test@example.com'):
    """Replace all template tags in text"""
    if not text:
        return text
    
    def gen_random_name():
        first = ['James', 'John', 'Robert', 'Michael', 'William', 'Mary', 'Patricia', 'Jennifer', 'Linda', 'Elizabeth']
        last = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez']
        return f"{random.choice(first)} {random.choice(last)}"
    
    def gen_company():
        prefixes = ['Tech', 'Global', 'Digital', 'Smart', 'Innovative', 'Advanced', 'Premier', 'Elite']
        suffixes = ['Solutions', 'Systems', 'Corporation', 'Industries', 'Group', 'Services', 'Technologies']
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
    
    print(f"\n✓ Testing with {len(replacements)} placeholders")
    print(f"✓ Input text length: {len(text)}")
    
    for tag, value in replacements.items():
        pattern = r'\{\{' + re.escape(tag) + r'\}\}'
        count_before = len(re.findall(pattern, text, flags=re.IGNORECASE))
        text = re.sub(pattern, str(value), text, flags=re.IGNORECASE)
        if count_before > 0:
            print(f"  → Replaced {count_before}x {{{{{tag}}}}} with: {value}")
    
    return text

# Test cases
print("=" * 60)
print("PLACEHOLDER REPLACEMENT TEST")
print("=" * 60)

test_cases = [
    {
        'name': 'Simple subject line',
        'input': 'Hello {{name}} - Your ID is {{13_digit}}',
        'expected_tags': ['name', '13_digit']
    },
    {
        'name': 'HTML body with multiple tags',
        'input': '''
        <p>Dear {{name}},</p>
        <p>Your email is {{email}} and company is {{company}}</p>
        <p>Date: {{date}}, Time: {{time}}, Year: {{year}}</p>
        <p>Random codes: {{random_6}} and {{random_8}}</p>
        <p>Unique ID: {{unique_id}}</p>
        ''',
        'expected_tags': ['name', 'email', 'company', 'date', 'time', 'year', 'random_6', 'random_8', 'unique_id']
    },
    {
        'name': 'Case insensitive test',
        'input': 'Hello {{NAME}} and {{Email}} from {{COMPANY}}',
        'expected_tags': ['NAME', 'Email', 'COMPANY']
    },
    {
        'name': 'All tags test',
        'input': '{{email}} {{name}} {{company}} {{random_name}} {{13_digit}} {{unique_id}} {{date}} {{time}} {{year}} {{random_6}} {{random_8}} {{recipient}}',
        'expected_tags': ['email', 'name', 'company', 'random_name', '13_digit', 'unique_id', 'date', 'time', 'year', 'random_6', 'random_8', 'recipient']
    }
]

for i, test in enumerate(test_cases, 1):
    print(f"\n\nTest #{i}: {test['name']}")
    print("-" * 60)
    print(f"INPUT:\n{test['input']}")
    
    result = replace_template_tags(test['input'], 'test@example.com')
    
    print(f"\nOUTPUT:\n{result}")
    
    # Check if any placeholders remain
    remaining = re.findall(r'\{\{([^}]+)\}\}', result)
    if remaining:
        print(f"\n⚠️  WARNING: {len(remaining)} placeholders not replaced: {remaining}")
    else:
        print(f"\n✅ SUCCESS: All placeholders replaced!")

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)
