#!/usr/bin/env python3
"""
Flask Web Server for Card Drop Monitor
Serves the dashboard and provides API endpoints
"""

from flask import Flask, jsonify, send_file, request
from flask_cors import CORS
import sqlite3
import json
from datetime import datetime
import threading
import time
from card_drop_monitor import CardDropMonitor

app = Flask(__name__)
CORS(app)

# Initialize monitor
monitor = CardDropMonitor()

def background_scanner():
    """Background thread to scan retailers periodically"""
    while True:
        try:
            print("Running background scan...")
            results, alerts = monitor.run_scan()
            print(f"Scan complete. Found {len(results)} drops, {len(alerts)} alerts")
        except Exception as e:
            print(f"Error in background scan: {e}")
        
        # Wait 6 hours before next scan
        time.sleep(6 * 3600)

@app.route('/')
def index():
    """Serve the dashboard"""
    return send_file('dashboard.html')

@app.route('/api/drops', methods=['GET'])
def get_drops():
    """Get all drops from database"""
    try:
        status = request.args.get('status', 'upcoming')
        drops = monitor.get_all_drops(status)
        return jsonify({
            'success': True,
            'drops': drops,
            'count': len(drops)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/drops/<int:drop_id>', methods=['GET'])
def get_drop(drop_id):
    """Get a specific drop by ID"""
    try:
        conn = sqlite3.connect(monitor.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, product_name, retailer, url, price, drop_date, drop_time,
                   status, discovered_date, notified
            FROM drops
            WHERE id = ?
        ''', (drop_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            drop = {
                'id': row[0],
                'name': row[1],
                'retailer': row[2],
                'url': row[3],
                'price': row[4],
                'drop_date': row[5],
                'drop_time': row[6],
                'status': row[7],
                'discovered_date': row[8],
                'notified': row[9]
            }
            return jsonify({
                'success': True,
                'drop': drop
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Drop not found'
            }), 404
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/scan', methods=['POST'])
def trigger_scan():
    """Manually trigger a scan"""
    try:
        results, alerts = monitor.run_scan()
        return jsonify({
            'success': True,
            'results_count': len(results),
            'alerts_count': len(alerts),
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get statistics about drops"""
    try:
        drops = monitor.get_all_drops()
        
        # Calculate stats
        total = len(drops)
        by_retailer = {}
        
        for drop in drops:
            retailer = drop['retailer']
            by_retailer[retailer] = by_retailer.get(retailer, 0) + 1
        
        return jsonify({
            'success': True,
            'stats': {
                'total_drops': total,
                'by_retailer': by_retailer,
                'last_scan': datetime.now().isoformat()
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/alerts', methods=['GET'])
def get_alerts():
    """Get current alerts (drops within 7 days)"""
    try:
        alerts = monitor.check_for_alerts()
        return jsonify({
            'success': True,
            'alerts': alerts,
            'count': len(alerts)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    # Start background scanner thread
    scanner_thread = threading.Thread(target=background_scanner, daemon=True)
    scanner_thread.start()
    
    print("="*60)
    print("Card Drop Monitor Server Starting...")
    print("="*60)
    print("Dashboard: http://localhost:5000")
    print("API: http://localhost:5000/api/drops")
    print("="*60)
    
    # Run Flask app
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
