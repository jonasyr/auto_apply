#!/usr/bin/env python3
"""
Dashboard Server for JobSpy LLM Letters
Serves the dashboard with proper file access and CORS headers
"""

import os
import sys
import webbrowser
import http.server
import socketserver
from pathlib import Path
from urllib.parse import urlparse
import threading
import time

class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    """Custom handler with CORS headers and better file serving"""
    
    def __init__(self, *args, **kwargs):
        # Set the directory to serve files from
        self.directory = str(Path(__file__).parent / "out")
        super().__init__(*args, directory=self.directory, **kwargs)
    
    def end_headers(self):
        # Add CORS headers to allow local file access
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        super().end_headers()
    
    def do_GET(self):
        """Handle GET requests with special dashboard logic"""
        # Default to Dashboard.html if accessing root
        if self.path == '/' or self.path == '':
            self.path = '/Dashboard.html'
        
        # Check if requested file exists
        file_path = Path(self.directory) / self.path.lstrip('/')
        
        if not file_path.exists():
            if self.path.endswith('.html'):
                # Return friendly error for missing HTML files
                self.send_response(404)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                
                error_html = f"""
                <!DOCTYPE html>
                <html>
                <head><title>File Not Found</title></head>
                <body>
                    <h1>Dashboard File Not Found</h1>
                    <p>The file <code>{self.path}</code> was not found.</p>
                    <p>Make sure you have run <code>python main.py</code> first to generate the dashboard.</p>
                    <p><a href="/Dashboard.html">Try the main dashboard</a></p>
                </body>
                </html>
                """
                self.wfile.write(error_html.encode())
                return
        
        # For .txt files (cover letters), serve with proper content type
        if self.path.endswith('.txt'):
            self.send_response(200)
            self.send_header('Content-type', 'text/plain; charset=utf-8')
            self.end_headers()
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.wfile.write(content.encode('utf-8'))
            except Exception as e:
                error_msg = f"Error reading file: {e}"
                self.wfile.write(error_msg.encode('utf-8'))
            return
        
        # Use default handler for other files
        super().do_GET()
    
    def log_message(self, format, *args):
        """Override to provide cleaner logging"""
        if not self.path.startswith('/favicon'):  # Skip favicon requests
            message = format % args
            print(f"📊 Dashboard: {message}")

class DashboardServer:
    def __init__(self, port=8000, auto_open=True):
        self.port = port
        self.auto_open = auto_open
        self.server = None
        self.out_dir = Path(__file__).parent / "out"
        
    def check_files(self) -> bool:
        """Check if required files exist"""
        required_files = [
            self.out_dir / "Dashboard.html",
        ]
        
        missing_files = [f for f in required_files if not f.exists()]
        
        if missing_files:
            print("❌ Missing required files:")
            for file in missing_files:
                print(f"   • {file}")
            print("\n💡 Run 'python main.py' first to generate the dashboard files.")
            return False
        
        return True
    
    def find_available_port(self) -> int:
        """Find an available port starting from the preferred port"""
        import socket
        
        for port in range(self.port, self.port + 100):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('localhost', port))
                    return port
            except OSError:
                continue
        
        raise RuntimeError("No available ports found")
    
    def start_server(self) -> bool:
        """Start the dashboard server"""
        if not self.check_files():
            return False
        
        try:
            # Find available port
            self.port = self.find_available_port()
            
            # Create server
            self.server = socketserver.TCPServer(("", self.port), DashboardHandler)
            
            print(f"🚀 Starting dashboard server on port {self.port}")
            print(f"📊 Dashboard URL: http://localhost:{self.port}")
            print(f"📁 Serving files from: {self.out_dir.absolute()}")
            
            # Check for jobs.csv
            jobs_csv = self.out_dir / "jobs.csv"
            if jobs_csv.exists():
                print(f"✅ Found jobs data: {jobs_csv}")
            else:
                print("⚠️  No jobs.csv found - upload it through the dashboard interface")
            
            # Count cover letters
            txt_files = list(self.out_dir.glob("*.txt"))
            if txt_files:
                print(f"✅ Found {len(txt_files)} cover letters")
            else:
                print("📄 No cover letters found - they will be generated when you run main.py")
            
            print("\n" + "="*50)
            print("🎯 Dashboard is ready!")
            print("   • Upload jobs.csv if not already present")
            print("   • Upload cover letter .txt files (optional)")
            print("   • Use filters to find relevant jobs")
            print("   • Click 'Anschreiben anzeigen' to view cover letters")
            print("="*50)
            
            # Auto-open browser
            if self.auto_open:
                def open_browser():
                    time.sleep(1)  # Give server time to start
                    webbrowser.open(f"http://localhost:{self.port}")
                
                threading.Thread(target=open_browser, daemon=True).start()
            
            # Start serving
            print("\n🔄 Server running... Press Ctrl+C to stop")
            self.server.serve_forever()
            
        except KeyboardInterrupt:
            print("\n🛑 Server stopped by user")
            return True
        except Exception as e:
            print(f"❌ Server error: {e}")
            return False
        finally:
            if self.server:
                self.server.shutdown()
                self.server.server_close()
    
    def stop_server(self):
        """Stop the server"""
        if self.server:
            self.server.shutdown()

def main():
    """Main function to start dashboard server"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Start JobSpy LLM Letters Dashboard Server")
    parser.add_argument("--port", "-p", type=int, default=8000, 
                       help="Port to serve on (default: 8000)")
    parser.add_argument("--no-open", action="store_true", 
                       help="Don't automatically open browser")
    parser.add_argument("--check-only", action="store_true",
                       help="Only check files, don't start server")
    
    args = parser.parse_args()
    
    if args.check_only:
        # Just check if files exist
        server = DashboardServer(args.port, auto_open=False)
        if server.check_files():
            print("✅ All dashboard files are ready")
            return True
        else:
            return False
    
    # Start the server
    server = DashboardServer(args.port, auto_open=not args.no_open)
    return server.start_server()

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        sys.exit(0)