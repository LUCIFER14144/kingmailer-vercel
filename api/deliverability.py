"""
KINGMAILER - Deliverability Diagnostic API
Checks SPF, DKIM, DMARC, MX records, blacklists, and provides
actionable recommendations for improving inbox placement.
"""

from http.server import BaseHTTPRequestHandler
import json
import socket
import re


def _dns_txt(domain):
    """Fetch TXT records using low-level DNS over UDP (no external libs needed)."""
    records = []
    try:
        # Use socket to resolve via system DNS
        import struct
        # Build DNS query for TXT records
        tid = 0x1234
        flags = 0x0100  # standard query, recursion desired
        qname = b''
        for part in domain.encode().split(b'.'):
            qname += bytes([len(part)]) + part
        qname += b'\x00'
        query = struct.pack('>HHHHHH', tid, flags, 1, 0, 0, 0) + qname + struct.pack('>HH', 16, 1)  # TXT, IN

        # Try system DNS resolver
        try:
            dns_server = '8.8.8.8'  # Google Public DNS
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(5)
            sock.sendto(query, (dns_server, 53))
            data, _ = sock.recvfrom(4096)
            sock.close()

            # Parse response
            if len(data) > 12:
                ancount = struct.unpack('>H', data[6:8])[0]
                offset = 12
                # Skip question section
                while data[offset] != 0:
                    offset += data[offset] + 1
                offset += 5  # null byte + QTYPE + QCLASS

                for _ in range(ancount):
                    # Skip name (may be compressed)
                    if data[offset] & 0xC0 == 0xC0:
                        offset += 2
                    else:
                        while data[offset] != 0:
                            offset += data[offset] + 1
                        offset += 1
                    rtype = struct.unpack('>H', data[offset:offset+2])[0]
                    rdlen = struct.unpack('>H', data[offset+8:offset+10])[0]
                    offset += 10
                    if rtype == 16:  # TXT
                        txt = b''
                        pos = offset
                        end = offset + rdlen
                        while pos < end:
                            slen = data[pos]
                            txt += data[pos+1:pos+1+slen]
                            pos += 1 + slen
                        records.append(txt.decode('utf-8', errors='replace'))
                    offset += rdlen
        except Exception:
            pass
    except Exception:
        pass
    return records


def _dns_mx(domain):
    """Check if domain has MX records using socket."""
    try:
        import struct
        tid = 0x5678
        flags = 0x0100
        qname = b''
        for part in domain.encode().split(b'.'):
            qname += bytes([len(part)]) + part
        qname += b'\x00'
        query = struct.pack('>HHHHHH', tid, flags, 1, 0, 0, 0) + qname + struct.pack('>HH', 15, 1)  # MX, IN

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(5)
        sock.sendto(query, ('8.8.8.8', 53))
        data, _ = sock.recvfrom(4096)
        sock.close()

        ancount = struct.unpack('>H', data[6:8])[0]
        return ancount > 0
    except Exception:
        return None  # Unknown


def check_spf(domain):
    """Check SPF record for a domain."""
    txt_records = _dns_txt(domain)
    spf_records = [r for r in txt_records if r.startswith('v=spf1')]

    if not spf_records:
        return {
            'status': 'MISSING',
            'record': None,
            'message': f'No SPF record found for {domain}. Emails WILL fail SPF checks.',
            'fix': f'Add this TXT record to your DNS:\n  v=spf1 include:_spf.google.com ~all\n\nIf using other providers, add their includes too.',
            'severity': 'critical'
        }

    spf = spf_records[0]
    issues = []

    if spf.endswith('-all'):
        policy = 'hard fail (-all) — strict, good'
    elif spf.endswith('~all'):
        policy = 'soft fail (~all) — recommended'
    elif spf.endswith('?all'):
        policy = 'neutral (?all) — weak, should be ~all'
        issues.append('Change ?all to ~all for better protection')
    elif spf.endswith('+all'):
        policy = 'pass all (+all) — DANGEROUS, allows anyone to send as you!'
        issues.append('CRITICAL: Change +all to ~all immediately. +all means ANY server can send as your domain.')
    else:
        policy = 'no all mechanism — incomplete'
        issues.append('SPF record should end with -all or ~all')

    # Check for common includes
    has_google = 'google.com' in spf or '_spf.google.com' in spf
    has_outlook = 'outlook.com' in spf or 'microsoft.com' in spf

    return {
        'status': 'PASS' if not issues else 'WARN',
        'record': spf,
        'policy': policy,
        'includes_google': has_google,
        'includes_microsoft': has_outlook,
        'issues': issues,
        'message': f'SPF record found: {spf}',
        'severity': 'ok' if not issues else 'warning'
    }


def check_dmarc(domain):
    """Check DMARC record."""
    dmarc_domain = f'_dmarc.{domain}'
    txt_records = _dns_txt(dmarc_domain)
    dmarc_records = [r for r in txt_records if r.startswith('v=DMARC1')]

    if not dmarc_records:
        return {
            'status': 'MISSING',
            'record': None,
            'message': f'No DMARC record found for {domain}.',
            'fix': f'Add this TXT record to your DNS:\n  Host: _dmarc.{domain}\n  Value: v=DMARC1; p=none; rua=mailto:dmarc@{domain}\n\nStart with p=none for monitoring, then move to p=quarantine.',
            'severity': 'critical'
        }

    dmarc = dmarc_records[0]
    issues = []

    # Parse policy
    policy_match = re.search(r'p=(\w+)', dmarc)
    policy = policy_match.group(1) if policy_match else 'unknown'

    if policy == 'none':
        issues.append('p=none only monitors, does not protect. Move to p=quarantine after testing.')
    elif policy == 'reject':
        pass  # Best policy
    elif policy == 'quarantine':
        pass  # Good policy

    # Check for rua (aggregate reports)
    has_rua = 'rua=' in dmarc

    return {
        'status': 'PASS' if not issues else 'WARN',
        'record': dmarc,
        'policy': policy,
        'has_reporting': has_rua,
        'issues': issues,
        'message': f'DMARC record found: {dmarc}',
        'severity': 'ok' if policy in ('quarantine', 'reject') else 'warning'
    }


def check_dkim(domain):
    """Check common DKIM selector records."""
    selectors = ['google', 'default', 'selector1', 'selector2', 'k1', 'dkim', 's1', 's2']
    found = []

    for sel in selectors:
        dkim_domain = f'{sel}._domainkey.{domain}'
        txt_records = _dns_txt(dkim_domain)
        dkim_records = [r for r in txt_records if 'DKIM' in r.upper() or 'p=' in r]
        if dkim_records:
            found.append({'selector': sel, 'record': dkim_records[0][:100] + '...' if len(dkim_records[0]) > 100 else dkim_records[0]})

    if not found:
        return {
            'status': 'UNKNOWN',
            'selectors_checked': selectors,
            'found': [],
            'message': f'No DKIM records found for common selectors on {domain}. This does NOT necessarily mean DKIM is not set up — your provider may use a different selector.',
            'fix': 'For Gmail: DKIM is automatically handled when sending through smtp.gmail.com.\nFor custom domains: Check your email provider\'s DKIM setup guide.',
            'severity': 'warning'
        }

    return {
        'status': 'PASS',
        'found': found,
        'message': f'Found DKIM records for selectors: {", ".join(f["selector"] for f in found)}',
        'severity': 'ok'
    }


def check_mx(domain):
    """Check MX records."""
    has_mx = _dns_mx(domain)
    if has_mx is None:
        return {'status': 'UNKNOWN', 'message': 'Could not check MX records', 'severity': 'warning'}
    if has_mx:
        return {'status': 'PASS', 'message': f'MX records found for {domain}', 'severity': 'ok'}
    return {
        'status': 'MISSING',
        'message': f'No MX records for {domain} — replies to this domain will bounce',
        'severity': 'critical',
        'fix': 'Add MX records pointing to your email provider'
    }


def check_blacklist(ip_or_domain):
    """Check common DNS blacklists."""
    # Can only check IPs
    try:
        ip = socket.gethostbyname(ip_or_domain) if not re.match(r'^\d+\.\d+\.\d+\.\d+$', ip_or_domain) else ip_or_domain
    except Exception:
        return {'status': 'UNKNOWN', 'message': 'Could not resolve IP', 'severity': 'warning'}

    # Reverse the IP for DNSBL queries
    parts = ip.split('.')
    reversed_ip = '.'.join(parts[::-1])

    blacklists = [
        'zen.spamhaus.org',
        'bl.spamcop.net',
        'b.barracudacentral.org',
        'dnsbl.sorbs.net',
    ]

    listed_on = []
    clean_on = []

    for bl in blacklists:
        query = f'{reversed_ip}.{bl}'
        try:
            socket.setdefaulttimeout(3)
            socket.gethostbyname(query)
            listed_on.append(bl)
        except socket.gaierror:
            clean_on.append(bl)
        except Exception:
            pass

    if listed_on:
        return {
            'status': 'LISTED',
            'ip': ip,
            'listed_on': listed_on,
            'clean_on': clean_on,
            'message': f'IP {ip} is LISTED on: {", ".join(listed_on)}',
            'fix': 'Your sending IP is blacklisted. Request delisting from each blacklist provider. This is the #1 cause of 0% inbox rate.',
            'severity': 'critical'
        }

    return {
        'status': 'CLEAN',
        'ip': ip,
        'clean_on': clean_on,
        'message': f'IP {ip} is clean on {len(clean_on)} checked blacklists',
        'severity': 'ok'
    }


def generate_recommendations(spf, dkim, dmarc, mx):
    """Generate prioritized actionable recommendations."""
    recs = []
    score = 100

    # Critical issues
    if spf.get('status') == 'MISSING':
        recs.append({'priority': 1, 'severity': 'critical', 'title': 'Add SPF Record', 'detail': spf.get('fix', ''), 'impact': 'Without SPF, all major providers will flag your emails as suspicious.'})
        score -= 30

    if dmarc.get('status') == 'MISSING':
        recs.append({'priority': 2, 'severity': 'critical', 'title': 'Add DMARC Record', 'detail': dmarc.get('fix', ''), 'impact': 'Google requires DMARC for bulk senders (>5000/day). Without it, emails go to spam.'})
        score -= 25

    if mx.get('status') == 'MISSING':
        recs.append({'priority': 3, 'severity': 'critical', 'title': 'Add MX Records', 'detail': mx.get('fix', ''), 'impact': 'Without MX records, your domain looks fake to spam filters.'})
        score -= 15

    # Warnings
    if dkim.get('status') == 'UNKNOWN':
        recs.append({'priority': 4, 'severity': 'warning', 'title': 'Verify DKIM Setup', 'detail': dkim.get('fix', ''), 'impact': 'DKIM proves your emails are not tampered with. It significantly improves trust.'})
        score -= 10

    if spf.get('status') == 'WARN':
        for issue in spf.get('issues', []):
            recs.append({'priority': 5, 'severity': 'warning', 'title': 'Fix SPF Issue', 'detail': issue, 'impact': 'Minor SPF issues can reduce deliverability.'})
            score -= 5

    if dmarc.get('status') == 'WARN':
        for issue in dmarc.get('issues', []):
            recs.append({'priority': 6, 'severity': 'info', 'title': 'Improve DMARC', 'detail': issue, 'impact': 'Strengthening DMARC improves long-term reputation.'})
            score -= 5

    # General best practices
    if not recs:
        recs.append({'priority': 10, 'severity': 'ok', 'title': 'DNS Looks Good!', 'detail': 'All critical DNS records are in place. Focus on content quality and sending patterns.', 'impact': ''})

    return {'score': max(0, score), 'recommendations': sorted(recs, key=lambda r: r['priority'])}


def run_full_check(domain, smtp_user=None):
    """Run all deliverability checks for a domain."""
    result = {
        'domain': domain,
        'smtp_user': smtp_user,
        'checks': {}
    }

    # Run checks
    result['checks']['spf'] = check_spf(domain)
    result['checks']['dkim'] = check_dkim(domain)
    result['checks']['dmarc'] = check_dmarc(domain)
    result['checks']['mx'] = check_mx(domain)

    # Generate recommendations
    rec = generate_recommendations(
        result['checks']['spf'],
        result['checks']['dkim'],
        result['checks']['dmarc'],
        result['checks']['mx']
    )
    result['score'] = rec['score']
    result['recommendations'] = rec['recommendations']

    # Add warmup guide
    result['warmup_guide'] = {
        'day_1_3': '50 emails/day — send to engaged contacts only',
        'day_4_7': '100 emails/day — monitor bounce rate (<2%)',
        'day_8_14': '250 emails/day — check spam complaints (<0.1%)',
        'day_15_21': '500 emails/day — maintain consistent volume',
        'day_22_30': '1000 emails/day — can increase if metrics are good',
        'rules': [
            'STOP immediately if bounce rate exceeds 2%',
            'STOP immediately if spam complaint rate exceeds 0.1%',
            'Always include working unsubscribe link',
            'Never send to purchased/scraped email lists',
            'Monitor Google Postmaster Tools daily',
        ]
    }

    return result


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))

            action = data.get('action', 'check_domain')

            if action == 'check_domain':
                domain = data.get('domain', '').strip()
                smtp_user = data.get('smtp_user', '')

                if not domain:
                    # Try to extract from smtp_user
                    if smtp_user and '@' in smtp_user:
                        domain = smtp_user.split('@')[-1]
                    else:
                        self.send_response(400)
                        self.send_header('Content-type', 'application/json')
                        self.send_header('Access-Control-Allow-Origin', '*')
                        self.end_headers()
                        self.wfile.write(json.dumps({
                            'success': False,
                            'error': 'Domain or SMTP user email required'
                        }).encode())
                        return

                result = run_full_check(domain, smtp_user)
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'success': True,
                    **result
                }).encode())

            elif action == 'check_blacklist':
                target = data.get('ip', data.get('domain', ''))
                if not target:
                    self.send_response(400)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        'success': False,
                        'error': 'IP or domain required'
                    }).encode())
                    return

                result = check_blacklist(target)
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'success': True,
                    **result
                }).encode())

            elif action == 'validate_email':
                email = data.get('email', '').strip()
                if not email or '@' not in email:
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        'success': True,
                        'valid': False,
                        'reason': 'Invalid email format'
                    }).encode())
                    return

                domain = email.split('@')[-1]
                has_mx = _dns_mx(domain)

                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'success': True,
                    'valid': has_mx is not False,
                    'has_mx': has_mx,
                    'domain': domain,
                    'reason': 'OK' if has_mx else f'Domain {domain} has no MX records — emails will bounce'
                }).encode())

            else:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'success': False,
                    'error': f'Unknown action: {action}'
                }).encode())

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({
                'success': False,
                'error': str(e)
            }).encode())

    def do_GET(self):
        """GET returns a simple status."""
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps({
            'success': True,
            'message': 'Deliverability checker API. POST with {action: "check_domain", domain: "example.com"}'
        }).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
