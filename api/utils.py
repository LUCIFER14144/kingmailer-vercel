"""
KINGMAILER v4.0 - Utility Functions
Spintax, template tags, and helper functions
"""

import re
import random
import string
from datetime import datetime


def process_spintax(text):
    """
    Process spintax syntax: {option1|option2|option3}
    Recursively processes nested spintax
    """
    if not text:
        return text
    
    # Find all spintax patterns
    pattern = r'\{([^{}]+)\}'
    
    def replace_spintax(match):
        options = match.group(1).split('|')
        return random.choice(options).strip()
    
    # Keep processing until no more spintax found
    max_iterations = 10
    iteration = 0
    
    while '{' in text and '|' in text and iteration < max_iterations:
        text = re.sub(pattern, replace_spintax, text)
        iteration += 1
    
    return text


def generate_13_digit():
    """Generate unique 13-digit ID like original script"""
    timestamp = int(datetime.now().timestamp() * 1000)
    random_suffix = random.randint(100, 999)
    id_str = f"{timestamp}{random_suffix}"
    return id_str[:13]


def generate_random_string(length=10, char_type='alphanumeric'):
    """Generate random string"""
    if char_type == 'alphanumeric':
        chars = string.ascii_letters + string.digits
    elif char_type == 'alpha':
        chars = string.ascii_letters
    elif char_type == 'numeric':
        chars = string.digits
    elif char_type == 'hex':
        chars = string.hexdigits.lower()
    else:
        chars = string.ascii_letters + string.digits
    
    return ''.join(random.choice(chars) for _ in range(length))


def generate_usa_address():
    """Generate random USA address"""
    street_names = ['Oak', 'Main', 'Pine', 'Maple', 'Cedar', 'Elm', 'Washington', 'Park', 'Lake', 'Hill']
    street_types = ['St', 'Ave', 'Blvd', 'Dr', 'Ln', 'Rd', 'Way', 'Ct']
    cities = ['New York', 'Los Angeles', 'Chicago', 'Houston', 'Phoenix', 'Philadelphia', 'San Antonio', 'San Diego', 'Dallas', 'Austin']
    states = ['NY', 'CA', 'IL', 'TX', 'AZ', 'PA', 'FL', 'OH', 'GA', 'NC']
    
    street_number = random.randint(100, 9999)
    street_name = random.choice(street_names)
    street_type = random.choice(street_types)
    city = random.choice(cities)
    state = random.choice(states)
    zipcode = random.randint(10000, 99999)
    
    return f"{street_number} {street_name} {street_type}, {city}, {state} {zipcode}"


def generate_company_name():
    """Generate random company name"""
    prefixes = ['Tech', 'Global', 'Digital', 'Smart', 'Innovative', 'Advanced', 'Premier', 'Elite', 'Prime', 'Omega']
    suffixes = ['Solutions', 'Systems', 'Corporation', 'Industries', 'Group', 'Services', 'Technologies', 'Consulting', 'Enterprises', 'Partners']
    
    return f"{random.choice(prefixes)} {random.choice(suffixes)}"


def generate_random_name():
    """Generate random person name"""
    first_names = ['James', 'John', 'Robert', 'Michael', 'William', 'David', 'Richard', 'Joseph', 'Thomas', 'Charles',
                   'Mary', 'Patricia', 'Jennifer', 'Linda', 'Elizabeth', 'Barbara', 'Susan', 'Jessica', 'Sarah', 'Karen']
    last_names = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez',
                  'Hernandez', 'Lopez', 'Gonzalez', 'Wilson', 'Anderson', 'Thomas', 'Taylor', 'Moore', 'Jackson', 'Martin']
    
    return f"{random.choice(first_names)} {random.choice(last_names)}"


def replace_template_tags(text, recipient_email=''):
    """
    Replace all template tags in text
    Supports both {{tag}} and {tag} syntax
    """
    if not text:
        return text
    
    # Define tag replacements
    replacements = {
        'random_name': generate_random_name(),
        'company': generate_company_name(),
        'company_name': generate_company_name(),
        'usa_address': generate_usa_address(),
        'address': generate_usa_address(),
        '13_digit': generate_13_digit(),
        'unique_id': generate_13_digit(),
        'date': datetime.now().strftime('%B %d, %Y'),
        'time': datetime.now().strftime('%I:%M %p'),
        'year': str(datetime.now().year),
        'month': datetime.now().strftime('%B'),
        'day': str(datetime.now().day),
        'random_6': generate_random_string(6, 'alphanumeric'),
        'random_8': generate_random_string(8, 'alphanumeric'),
        'random_10': generate_random_string(10, 'alphanumeric'),
        'hex_8': generate_random_string(8, 'hex'),
        'alpha_10': generate_random_string(10, 'alpha'),
        'numeric_6': generate_random_string(6, 'numeric'),
        'recipient': recipient_email,
        'email': recipient_email
    }
    
    # Replace {{tag}} format
    for tag, value in replacements.items():
        text = re.sub(r'\{\{' + tag + r'\}\}', str(value), text, flags=re.IGNORECASE)
    
    # Replace {tag} format (if not spintax)
    for tag, value in replacements.items():
        # Only replace if not part of spintax (no | nearby)
        pattern = r'\{' + tag + r'(?!\|)(?![^}]*\|)\}'
        text = re.sub(pattern, str(value), text, flags=re.IGNORECASE)
    
    return text


def rotate_from_list(items, index=None):
    """
    Rotate through a list of items
    Returns next item based on index
    """
    if not items:
        return None
    
    if index is None:
        return random.choice(items)
    
    return items[index % len(items)]
