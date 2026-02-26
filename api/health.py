"""
KINGMAILER v4.0 - Health Check Endpoint
Vercel Serverless Function for deployment verification
"""

from flask import Flask, jsonify
import sys

app = Flask(__name__)

@app.route('/api/health', methods=['GET'])
def health_check():
    """Simple health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'KINGMAILER v4.0',
        'platform': 'Vercel Serverless',
        'python_version': sys.version,
        'features': {
            'smtp': True,
            'ses': True,
            'ec2_relay': True,
            'bulk_sending': True,
            'account_rotation': True
        },
        'message': '✅ SMTP works on Vercel!'
    }), 200

# Vercel serverless handler
def handler(request):
    with app.request_context(request.environ):
        return app.full_dispatch_request()
