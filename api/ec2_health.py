"""
EC2 Relay Health Check API
Verifies if EC2 instances have email relay server running
"""

import json
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        """Check health of EC2 relay servers"""
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            instances = data.get('instances', [])
            
            if not instances:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'success': False,
                    'error': 'No instances provided'
                }).encode())
                return
            
            # Check health of each instance
            results = []
            for instance in instances:
                instance_id = instance.get('instance_id')
                public_ip = instance.get('public_ip')
                
                if not public_ip or public_ip == 'N/A':
                    results.append({
                        'instance_id': instance_id,
                        'status': 'no_ip',
                        'healthy': False,
                        'message': 'Instance has no public IP'
                    })
                    continue
                
                # Try to reach health endpoint
                health_url = f'http://{public_ip}:8080/health'
                try:
                    req = urllib.request.Request(health_url, method='GET')
                    with urllib.request.urlopen(req, timeout=15) as response:
                        health_data = json.loads(response.read().decode('utf-8'))
                        
                        # Check for critical warnings (JetMailer Style - SMTP ports)
                        port587_status = health_data.get('port_587_outbound', 'unknown')
                        port465_status = health_data.get('port_465_outbound', 'unknown')
                        
                        # Determine if there are issues
                        has_warning = False
                        warning_messages = []
                        
                        if port587_status == 'blocked' and port465_status == 'blocked':
                            has_warning = True
                            warning_messages.append('⚠️ SMTP ports 587/465 blocked - check AWS security group')
                        
                        result_data = {
                            'instance_id': instance_id,
                            'public_ip': public_ip,
                            'status': 'healthy_with_warnings' if has_warning else 'healthy',
                            'healthy': True,
                            'relay_url': f'http://{public_ip}:8080/relay',
                            'method': health_data.get('method', 'Authenticated SMTP'),
                            'port_587_outbound': port587_status,
                            'port_465_outbound': port465_status,
                            'timestamp': health_data.get('timestamp'),
                            'info': 'JetMailer Style - No port 25 needed'
                        }
                        
                        if has_warning:
                            result_data['warnings'] = warning_messages
                        
                        results.append(result_data)
                except urllib.error.URLError as e:
                    error_msg = str(e)
                    help_text = 'Check: 1) Wait 10-15 min after creation for setup to complete, 2) Verify security group allows port 8080, 3) SSH and check: systemctl status email-relay, netstat -tlnp | grep 8080'
                    
                    results.append({
                        'instance_id': instance_id,
                        'public_ip': public_ip,
                        'status': 'unreachable',
                        'healthy': False,
                        'message': f'Cannot reach relay server - Connection failed',
                        'error_detail': error_msg,
                        'help': help_text
                    })
                except Exception as e:
                    results.append({
                        'instance_id': instance_id,
                        'public_ip': public_ip,
                        'status': 'error',
                        'healthy': False,
                        'message': str(e)
                    })
            
            # Calculate summary
            total = len(results)
            healthy_count = sum(1 for r in results if r.get('healthy'))
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            self.wfile.write(json.dumps({
                'success': True,
                'summary': {
                    'total': total,
                    'healthy': healthy_count,
                    'unhealthy': total - healthy_count
                },
                'instances': results
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
    
    def do_OPTIONS(self):
        """Handle CORS preflight"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
