#!/usr/bin/env python3
"""
Desktop Notification System for Card Drops
Sends native desktop notifications for upcoming drops
"""

import sqlite3
from datetime import datetime, timedelta
import time
import platform

# Try to import notification libraries based on OS
system = platform.system()

if system == "Windows":
    try:
        from win10toast import ToastNotifier
        toaster = ToastNotifier()
    except ImportError:
        print("Install win10toast: pip install win10toast")
        toaster = None
elif system == "Darwin":  # macOS
    import subprocess
elif system == "Linux":
    try:
        import notify2
        notify2.init("Card Drop Monitor")
    except ImportError:
        print("Install notify2: pip install notify2")

class DesktopNotifier:
    def __init__(self, db_path='card_drops.db'):
        self.db_path = db_path
        self.system = platform.system()
        
    def send_notification(self, title, message, url=None):
        """Send a desktop notification based on OS"""
        try:
            if self.system == "Windows" and toaster:
                toaster.show_toast(
                    title,
                    message,
                    duration=10,
                    threaded=True
                )
            elif self.system == "Darwin":  # macOS
                script = f'display notification "{message}" with title "{title}"'
                if url:
                    script += f' sound name "Glass"'
                subprocess.run(['osascript', '-e', script])
            elif self.system == "Linux":
                notification = notify2.Notification(title, message)
                notification.set_urgency(notify2.URGENCY_NORMAL)
                notification.set_timeout(10000)  # 10 seconds
                notification.show()
            else:
                print(f"[NOTIFICATION] {title}: {message}")
        except Exception as e:
            print(f"Error sending notification: {e}")
            print(f"[NOTIFICATION] {title}: {message}")
    
    def check_upcoming_drops(self):
        """Check for drops happening soon and send notifications"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get all upcoming drops
        cursor.execute('''
            SELECT id, product_name, retailer, url, drop_date, drop_time
            FROM drops
            WHERE status = 'upcoming'
            ORDER BY drop_date ASC
        ''')
        
        drops = cursor.fetchall()
        conn.close()
        
        now = datetime.now()
        notifications_sent = []
        
        for drop in drops:
            drop_id, name, retailer, url, drop_date, drop_time = drop
            
            if not drop_date:
                continue
            
            try:
                # Parse drop date
                drop_datetime = datetime.fromisoformat(drop_date)
                time_diff = drop_datetime - now
                
                # Send notifications at different intervals
                if timedelta(hours=-1) < time_diff < timedelta(hours=0):
                    # Drop happened in the last hour
                    self.send_notification(
                        "🚨 Drop Available NOW!",
                        f"{name} at {retailer}",
                        url
                    )
                    notifications_sent.append(drop_id)
                    
                elif timedelta(hours=0) < time_diff < timedelta(hours=1):
                    # Drop happening within 1 hour
                    minutes = int(time_diff.total_seconds() / 60)
                    self.send_notification(
                        "⚠️ Drop Starting Soon!",
                        f"{name} at {retailer} in {minutes} minutes!",
                        url
                    )
                    notifications_sent.append(drop_id)
                    
                elif timedelta(hours=1) < time_diff < timedelta(hours=24):
                    # Drop happening within 24 hours
                    hours = int(time_diff.total_seconds() / 3600)
                    self.send_notification(
                        "📅 Drop Tomorrow",
                        f"{name} at {retailer} in {hours} hours",
                        url
                    )
                    notifications_sent.append(drop_id)
                    
                elif timedelta(days=6) < time_diff < timedelta(days=7):
                    # 7 day warning
                    self.send_notification(
                        "📢 Drop Next Week",
                        f"{name} at {retailer} on {drop_datetime.strftime('%m/%d')}",
                        url
                    )
                    notifications_sent.append(drop_id)
                    
            except Exception as e:
                print(f"Error processing drop {drop_id}: {e}")
        
        return notifications_sent
    
    def monitor_continuously(self, check_interval_minutes=15):
        """Continuously monitor and send notifications"""
        print(f"Desktop notification monitor started")
        print(f"Checking every {check_interval_minutes} minutes")
        print(f"Operating System: {self.system}")
        print("="*60)
        
        while True:
            try:
                notifications = self.check_upcoming_drops()
                if notifications:
                    print(f"Sent {len(notifications)} notifications at {datetime.now()}")
                
                # Wait before next check
                time.sleep(check_interval_minutes * 60)
                
            except KeyboardInterrupt:
                print("\nNotification monitor stopped by user")
                break
            except Exception as e:
                print(f"Error in monitor loop: {e}")
                time.sleep(60)  # Wait 1 minute on error

def main():
    """Main function"""
    notifier = DesktopNotifier()
    
    # Test notification
    notifier.send_notification(
        "Card Drop Monitor",
        "Desktop notifications are now active! You'll be alerted about upcoming drops."
    )
    
    # Start monitoring
    notifier.monitor_continuously(check_interval_minutes=15)

if __name__ == '__main__':
    main()
