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
                state = instance.get('state', 'unknown')
                launch_time = instance.get('launch_time', '')
                
                if not public_ip or public_ip == 'N/A' or public_ip == 'Pending...':
                    results.append({
                        'instance_id': instance_id,
                        'status': 'no_ip',
                        'healthy': False,
                        'message': '⏳ Waiting for public IP assignment...',
                        'help': 'Refresh instances list in 30 seconds'
                    })
                    continue
                
                # Calculate instance age in minutes (if launch_time available)
                instance_age_min = None
                if launch_time:
                    try:
                        from datetime import datetime
                        # Parse ISO format: 2024-03-03T12:34:56.000Z
                        if 'T' in launch_time:
                            lt = datetime.fromisoformat(launch_time.replace('Z', '+00:00'))
                            age_seconds = (datetime.now(lt.tzinfo) - lt).total_seconds()
                            instance_age_min = int(age_seconds / 60)
                    except Exception:
                        pass
                
                # Try to reach health endpoint
                health_url = f'http://{public_ip}:3000/health'
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
                            'relay_url': f'http://{public_ip}:3000/relay',
                            'method': health_data.get('method', 'Authenticated SMTP'),
                            'port_587_outbound': port587_status,
                            'port_465_outbound': port465_status,
                            'timestamp': health_data.get('timestamp'),
                            'info': '✅ Relay server is running and ready'
                        }
                        
                        if has_warning:
                            result_data['warnings'] = warning_messages
                        
                        results.append(result_data)
                except urllib.error.URLError as e:
                    error_msg = str(e)
                    
                    # Smart guidance based on instance age
                    if instance_age_min is not None:
                        if instance_age_min < 3:
                            help_text = f'⏳ Instance is only {instance_age_min} min old. Setup takes 2-4 minutes. Wait 2 more minutes then check health again.'
                            needs_action = False
                        elif instance_age_min < 8:
                            help_text = f'⏳ Instance is {instance_age_min} min old. Almost ready. Try checking health again in 1 minute.'
                            needs_action = False
                        else:
                            help_text = f'❌ Instance is {instance_age_min} min old but relay not responding. Click "Restart Relay" button to fix it automatically via SSM.'
                            needs_action = True
                    else:
                        help_text = 'If instance was just created, wait 3-5 min. If >10 min old, use "Restart Relay" button to auto-fix.'
                        needs_action = None
                    
                    result_obj = {
                        'instance_id': instance_id,
                        'public_ip': public_ip,
                        'status': 'unreachable',
                        'healthy': False,
                        'message': f'Cannot reach relay server on port 3000',
                        'error_detail': error_msg,
                        'help': help_text,
                        'instance_age_minutes': instance_age_min
                    }
                    
                    if needs_action:
                        result_obj['needs_restart'] = True
                    
                    results.append(result_obj)
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
