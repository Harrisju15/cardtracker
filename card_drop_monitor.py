#!/usr/bin/env python3
"""
Pokemon & TCG Card Drop Monitor
Monitors Walmart, Target, Best Buy, and GameStop for upcoming card releases
"""

import requests
from bs4 import BeautifulSoup
import json
import sqlite3
from datetime import datetime, timedelta
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from typing import List, Dict, Optional
import re

class CardDropMonitor:
    def __init__(self, db_path='card_drops.db'):
        self.db_path = db_path
        self.init_database()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
    def init_database(self):
        """Initialize SQLite database to store drop information"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS drops (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_name TEXT NOT NULL,
                retailer TEXT NOT NULL,
                url TEXT NOT NULL,
                price REAL,
                drop_date TEXT,
                drop_time TEXT,
                status TEXT DEFAULT 'upcoming',
                discovered_date TEXT NOT NULL,
                last_checked TEXT NOT NULL,
                notified INTEGER DEFAULT 0,
                UNIQUE(product_name, retailer, url)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                drop_id INTEGER,
                notification_date TEXT NOT NULL,
                notification_type TEXT NOT NULL,
                FOREIGN KEY (drop_id) REFERENCES drops (id)
            )
        ''')
        
        conn.commit()
        conn.close()
        
    def search_walmart(self) -> List[Dict]:
        """Search Walmart for Pokemon and TCG products"""
        results = []
        search_terms = ['pokemon cards', 'pokemon trading card game', 'pokemon tcg']
        
        for term in search_terms:
            try:
                # Walmart's search API endpoint
                url = f"https://www.walmart.com/search?q={term.replace(' ', '+')}"
                response = requests.get(url, headers=self.headers, timeout=10)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # Look for product listings (Walmart's structure may vary)
                    # This is a simplified example - actual implementation would need more robust parsing
                    products = soup.find_all('div', {'data-item-id': True})
                    
                    for product in products[:10]:  # Limit to first 10 results
                        try:
                            name_elem = product.find('span', class_=re.compile('.*product-title.*'))
                            price_elem = product.find('div', class_=re.compile('.*price.*'))
                            link_elem = product.find('a', href=True)
                            
                            if name_elem and link_elem:
                                product_name = name_elem.get_text(strip=True)
                                price = self.extract_price(price_elem.get_text() if price_elem else '')
                                url = f"https://www.walmart.com{link_elem['href']}"
                                
                                # Check if it's a preorder or upcoming release
                                if self.is_preorder_or_upcoming(product_name, product.get_text()):
                                    results.append({
                                        'name': product_name,
                                        'retailer': 'Walmart',
                                        'url': url,
                                        'price': price,
                                        'drop_date': self.extract_date(product.get_text())
                                    })
                        except Exception as e:
                            continue
                            
            except Exception as e:
                print(f"Error searching Walmart: {e}")
                
        return results
    
    def search_target(self) -> List[Dict]:
        """Search Target for Pokemon and TCG products"""
        results = []
        search_terms = ['pokemon cards', 'pokemon tcg']
        
        for term in search_terms:
            try:
                url = f"https://www.target.com/s?searchTerm={term.replace(' ', '+')}"
                response = requests.get(url, headers=self.headers, timeout=10)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # Target uses React, so we'd need to parse their data differently
                    # Look for JSON data in script tags
                    scripts = soup.find_all('script', type='application/ld+json')
                    
                    for script in scripts:
                        try:
                            data = json.loads(script.string)
                            if isinstance(data, dict) and 'name' in data:
                                product_name = data.get('name', '')
                                if 'pokemon' in product_name.lower() or 'tcg' in product_name.lower():
                                    results.append({
                                        'name': product_name,
                                        'retailer': 'Target',
                                        'url': data.get('url', url),
                                        'price': self.extract_price(str(data.get('offers', {}).get('price', ''))),
                                        'drop_date': self.extract_date(str(data.get('offers', {}).get('availability', '')))
                                    })
                        except:
                            continue
                            
            except Exception as e:
                print(f"Error searching Target: {e}")
                
        return results
    
    def search_bestbuy(self) -> List[Dict]:
        """Search Best Buy for Pokemon and TCG products"""
        results = []
        search_terms = ['pokemon cards', 'pokemon tcg']
        
        for term in search_terms:
            try:
                url = f"https://www.bestbuy.com/site/searchpage.jsp?st={term.replace(' ', '+')}"
                response = requests.get(url, headers=self.headers, timeout=10)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # Best Buy product listings
                    products = soup.find_all('div', class_=re.compile('.*sku-item.*'))
                    
                    for product in products[:10]:
                        try:
                            name_elem = product.find('h4', class_=re.compile('.*sku-title.*'))
                            price_elem = product.find('div', class_=re.compile('.*priceView.*'))
                            link_elem = product.find('a', class_=re.compile('.*sku-link.*'))
                            
                            if name_elem and link_elem:
                                product_name = name_elem.get_text(strip=True)
                                price = self.extract_price(price_elem.get_text() if price_elem else '')
                                url = f"https://www.bestbuy.com{link_elem['href']}"
                                
                                if self.is_preorder_or_upcoming(product_name, product.get_text()):
                                    results.append({
                                        'name': product_name,
                                        'retailer': 'Best Buy',
                                        'url': url,
                                        'price': price,
                                        'drop_date': self.extract_date(product.get_text())
                                    })
                        except:
                            continue
                            
            except Exception as e:
                print(f"Error searching Best Buy: {e}")
                
        return results
    
    def search_gamestop(self) -> List[Dict]:
        """Search GameStop for Pokemon and TCG products"""
        results = []
        search_terms = ['pokemon cards', 'pokemon tcg']
        
        for term in search_terms:
            try:
                url = f"https://www.gamestop.com/search/?q={term.replace(' ', '+')}"
                response = requests.get(url, headers=self.headers, timeout=10)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    products = soup.find_all('div', class_=re.compile('.*product-grid-tile.*'))
                    
                    for product in products[:10]:
                        try:
                            name_elem = product.find('a', class_=re.compile('.*product-name.*'))
                            price_elem = product.find('span', class_=re.compile('.*price.*'))
                            
                            if name_elem:
                                product_name = name_elem.get_text(strip=True)
                                url = f"https://www.gamestop.com{name_elem['href']}"
                                price = self.extract_price(price_elem.get_text() if price_elem else '')
                                
                                if self.is_preorder_or_upcoming(product_name, product.get_text()):
                                    results.append({
                                        'name': product_name,
                                        'retailer': 'GameStop',
                                        'url': url,
                                        'price': price,
                                        'drop_date': self.extract_date(product.get_text())
                                    })
                        except:
                            continue
                            
            except Exception as e:
                print(f"Error searching GameStop: {e}")
                
        return results
    
    def is_preorder_or_upcoming(self, name: str, text: str) -> bool:
        """Check if product is a preorder or upcoming release"""
        keywords = ['preorder', 'pre-order', 'coming soon', 'releases', 'available', 
                   'street date', 'launch date', '2025', '2026']
        text_lower = (name + ' ' + text).lower()
        return any(keyword in text_lower for keyword in keywords)
    
    def extract_price(self, text: str) -> Optional[float]:
        """Extract price from text"""
        try:
            # Find price pattern like $19.99
            match = re.search(r'\$?(\d+\.?\d*)', text.replace(',', ''))
            if match:
                return float(match.group(1))
        except:
            pass
        return None
    
    def extract_date(self, text: str) -> Optional[str]:
        """Extract date from text"""
        try:
            # Look for date patterns
            date_patterns = [
                r'(\d{1,2})/(\d{1,2})/(\d{4})',  # MM/DD/YYYY
                r'(\w+)\s+(\d{1,2}),?\s+(\d{4})',  # Month DD, YYYY
                r'(\d{4})-(\d{2})-(\d{2})',  # YYYY-MM-DD
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, text)
                if match:
                    return match.group(0)
                    
        except:
            pass
        return None
    
    def save_drop(self, drop: Dict):
        """Save drop information to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO drops 
                (product_name, retailer, url, price, drop_date, discovered_date, last_checked)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                drop['name'],
                drop['retailer'],
                drop['url'],
                drop.get('price'),
                drop.get('drop_date'),
                datetime.now().isoformat(),
                datetime.now().isoformat()
            ))
            conn.commit()
        except sqlite3.IntegrityError:
            # Update existing entry
            cursor.execute('''
                UPDATE drops 
                SET price = ?, drop_date = ?, last_checked = ?
                WHERE product_name = ? AND retailer = ? AND url = ?
            ''', (
                drop.get('price'),
                drop.get('drop_date'),
                datetime.now().isoformat(),
                drop['name'],
                drop['retailer'],
                drop['url']
            ))
            conn.commit()
        finally:
            conn.close()
    
    def get_all_drops(self, status='upcoming') -> List[Dict]:
        """Get all drops from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, product_name, retailer, url, price, drop_date, drop_time, 
                   status, discovered_date, notified
            FROM drops
            WHERE status = ?
            ORDER BY drop_date ASC, discovered_date DESC
        ''', (status,))
        
        rows = cursor.fetchall()
        conn.close()
        
        drops = []
        for row in rows:
            drops.append({
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
            })
        
        return drops
    
    def check_for_alerts(self):
        """Check if any drops need alerts (7 days before drop)"""
        drops = self.get_all_drops()
        alerts = []
        
        for drop in drops:
            if drop['drop_date'] and not drop['notified']:
                try:
                    # Parse drop date
                    drop_date = datetime.fromisoformat(drop['drop_date'])
                    days_until_drop = (drop_date - datetime.now()).days
                    
                    # Alert if drop is within 7 days
                    if 0 <= days_until_drop <= 7:
                        alerts.append(drop)
                        self.mark_as_notified(drop['id'])
                except:
                    pass
        
        return alerts
    
    def mark_as_notified(self, drop_id: int):
        """Mark a drop as notified"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('UPDATE drops SET notified = 1 WHERE id = ?', (drop_id,))
        cursor.execute('''
            INSERT INTO notifications (drop_id, notification_date, notification_type)
            VALUES (?, ?, ?)
        ''', (drop_id, datetime.now().isoformat(), '7-day-alert'))
        
        conn.commit()
        conn.close()
    
    def send_email_notification(self, drops: List[Dict], email_to: str, email_from: str, smtp_config: Dict):
        """Send email notification about upcoming drops"""
        if not drops:
            return
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'🎴 {len(drops)} Pokemon/TCG Card Drop Alert!'
        msg['From'] = email_from
        msg['To'] = email_to
        
        # Create HTML email
        html = f"""
        <html>
          <head></head>
          <body>
            <h2>Upcoming Card Drops - Next 7 Days!</h2>
            <p>The following Pokemon/TCG products are releasing soon:</p>
            <table border="1" cellpadding="10" style="border-collapse: collapse;">
              <tr style="background-color: #f2f2f2;">
                <th>Product</th>
                <th>Retailer</th>
                <th>Price</th>
                <th>Drop Date</th>
                <th>Link</th>
              </tr>
        """
        
        for drop in drops:
            price_str = f"${drop['price']:.2f}" if drop['price'] else 'TBD'
            html += f"""
              <tr>
                <td>{drop['name']}</td>
                <td>{drop['retailer']}</td>
                <td>{price_str}</td>
                <td>{drop['drop_date'] or 'TBD'}</td>
                <td><a href="{drop['url']}">View Product</a></td>
              </tr>
            """
        
        html += """
            </table>
            <p><strong>Remember:</strong> Set reminders to check these sites at the drop time!</p>
          </body>
        </html>
        """
        
        msg.attach(MIMEText(html, 'html'))
        
        try:
            with smtplib.SMTP(smtp_config['host'], smtp_config['port']) as server:
                server.starttls()
                server.login(smtp_config['username'], smtp_config['password'])
                server.send_message(msg)
            print(f"Email notification sent for {len(drops)} drops")
        except Exception as e:
            print(f"Error sending email: {e}")
    
    def run_scan(self):
        """Run a complete scan of all retailers"""
        print(f"Starting scan at {datetime.now().isoformat()}")
        
        all_results = []
        
        print("Scanning Walmart...")
        all_results.extend(self.search_walmart())
        
        print("Scanning Target...")
        all_results.extend(self.search_target())
        
        print("Scanning Best Buy...")
        all_results.extend(self.search_bestbuy())
        
        print("Scanning GameStop...")
        all_results.extend(self.search_gamestop())
        
        print(f"Found {len(all_results)} potential drops")
        
        # Save to database
        for drop in all_results:
            self.save_drop(drop)
        
        # Check for alerts
        alerts = self.check_for_alerts()
        print(f"Generated {len(alerts)} alerts")
        
        return all_results, alerts


def main():
    """Main function to run the monitor"""
    monitor = CardDropMonitor()
    
    # Configuration
    config = {
        'email_enabled': False,  # Set to True to enable email notifications
        'email_to': 'your-email@example.com',
        'email_from': 'notifications@example.com',
        'smtp': {
            'host': 'smtp.gmail.com',
            'port': 587,
            'username': 'your-email@gmail.com',
            'password': 'your-app-password'
        },
        'scan_interval_hours': 6  # Scan every 6 hours
    }
    
    while True:
        try:
            results, alerts = monitor.run_scan()
            
            # Send notifications if enabled
            if config['email_enabled'] and alerts:
                monitor.send_email_notification(
                    alerts,
                    config['email_to'],
                    config['email_from'],
                    config['smtp']
                )
            
            # Display alerts to console
            if alerts:
                print("\n" + "="*60)
                print("UPCOMING DROPS (Next 7 Days):")
                print("="*60)
                for alert in alerts:
                    print(f"\n{alert['name']}")
                    print(f"  Retailer: {alert['retailer']}")
                    print(f"  Price: ${alert['price']:.2f}" if alert['price'] else "  Price: TBD")
                    print(f"  Drop Date: {alert['drop_date'] or 'TBD'}")
                    print(f"  URL: {alert['url']}")
                print("="*60 + "\n")
            
            # Wait before next scan
            wait_seconds = config['scan_interval_hours'] * 3600
            print(f"Next scan in {config['scan_interval_hours']} hours...")
            time.sleep(wait_seconds)
            
        except KeyboardInterrupt:
            print("\nMonitoring stopped by user")
            break
        except Exception as e:
            print(f"Error during scan: {e}")
            print("Retrying in 1 hour...")
            time.sleep(3600)


if __name__ == '__main__':
    main()
