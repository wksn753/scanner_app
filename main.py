import datetime
import threading
import time
import uuid

from flask import Flask, render_template, request, jsonify, send_file
import os
import sys
import logging
import warnings

from scanner_manager import ScannerManager

# Suppress BJNP network discovery warnings (they're harmless)
warnings.filterwarnings("ignore", message=".*bjnp.*")
warnings.filterwarnings("ignore", message=".*bind socket.*")


# Redirect scanner backend warnings to null (optional)
class DevNull:
    def write(self, msg): pass

    def flush(self): pass


# Temporarily redirect stderr during scanner operations to reduce noise
original_stderr = sys.stderr

app = Flask(__name__)

# Configuration
UPLOAD_FOLDER = 'scans'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Global scanner manager instance
sm = ScannerManager()

# Store scan status for async operations
scan_status = {}

# Global variables for scanner management
available_scanners = []
scanner_detection_status = "initializing"
last_scan_detection = None


# Auto-detect scanners on startup
def auto_detect_scanners():
    """Automatically detect all available scanners (USB and wireless)"""
    global available_scanners, scanner_detection_status, last_scan_detection

    try:
        scanner_detection_status = "detecting"
        print("🔍 Auto-detecting scanners...")
        print("⚠️  Note: BJNP network discovery warnings are normal and can be ignored")

        # Add a small delay to avoid conflicts
        time.sleep(1)

        # Get all available scanners with error suppression
        try:
            # Temporarily suppress stderr to hide BJNP warnings
            sys.stderr = DevNull()
            scanners = sm.list_scanners()
            sys.stderr = original_stderr
        except Exception as scanner_error:
            sys.stderr = original_stderr
            print(f"⚠️  Scanner detection warning (continuing): {scanner_error}")
            # Try again with a delay
            time.sleep(2)
            try:
                sys.stderr = DevNull()
                scanners = sm.list_scanners()
                sys.stderr = original_stderr
            except Exception as retry_error:
                sys.stderr = original_stderr
                print(f"❌ Scanner detection failed on retry: {retry_error}")
                scanners = []

        available_scanners = []

        for i, scanner in enumerate(scanners):
            # Handle different scanner data types (string, tuple, list)
            scanner_name = ""
            scanner_raw = scanner
            scanner_device_id = ""
            scanner_manufacturer = ""
            scanner_model = ""
            connection_info = ""

            if isinstance(scanner, (tuple, list)) and len(scanner) >= 1:
                # Parse scanner tuple based on your actual data structure
                scanner_device_id = str(scanner[0])  # Device ID/connection string

                if len(scanner) >= 3:
                    scanner_manufacturer = str(scanner[1])  # Manufacturer or protocol
                    scanner_model = str(scanner[2])  # Model name

                if len(scanner) >= 4:
                    connection_info = str(scanner[3])  # Additional connection info

                # Create a friendly display name
                if scanner_model and scanner_manufacturer:
                    scanner_name = f"{scanner_manufacturer} {scanner_model}"
                elif scanner_model:
                    scanner_name = scanner_model
                else:
                    scanner_name = scanner_device_id.split(':')[-1] if ':' in scanner_device_id else scanner_device_id

            elif isinstance(scanner, str):
                scanner_name = scanner
                scanner_device_id = scanner
            else:
                scanner_name = str(scanner)
                scanner_device_id = str(scanner)

            # Clean up the name (remove technical prefixes)
            display_name = scanner_name
            if '[' in display_name and ']' in display_name:
                # Extract clean name from brackets like "HP Deskjet 4640 series [A95CBB]"
                display_name = display_name.split('[')[0].strip()

            scanner_info = {
                'index': i,
                'name': display_name,
                'device_id': scanner_device_id,
                'manufacturer': scanner_manufacturer,
                'model': scanner_model,
                'connection_info': connection_info,
                'raw_data': scanner_raw,  # Store original data for debugging
                'type': 'Unknown',
                'status': 'available',
                'last_used': None,
                'connection': 'Unknown'
            }

            # Enhanced scanner type detection
            device_lower = scanner_device_id.lower()

            # Network/Wireless detection
            if any(term in device_lower for term in ['airscan', 'escl', 'network', 'net', 'wifi', 'ip=']):
                scanner_info['type'] = 'Network'
                scanner_info['connection'] = 'WiFi/Network'
                if 'ip=' in connection_info:
                    ip = connection_info.split('ip=')[1].split('&')[0] if 'ip=' in connection_info else ''
                    if ip:
                        scanner_info['connection'] = f'Network ({ip})'
            # USB/Direct detection
            elif any(term in device_lower for term in ['hpaio', 'usb', 'direct', 'local']):
                scanner_info['type'] = 'USB/Direct'
                scanner_info['connection'] = 'USB or Direct Connection'
            # Brand-based detection
            elif any(brand in device_lower for brand in ['hp', 'canon', 'epson', 'brother', 'samsung']):
                scanner_info['type'] = 'USB'
                scanner_info['connection'] = 'USB Cable'

            available_scanners.append(scanner_info)

            # Debug print to understand the data structure
            print(f"   ✅ Processed Scanner {i}: {display_name}")
            print(f"      Device ID: {scanner_device_id}")
            print(f"      Type: {scanner_info['type']} ({scanner_info['connection']})")

        scanner_detection_status = "completed"
        last_scan_detection = datetime.datetime.now()  # FIXED: Use datetime.now() instead of datetime.time

        print(f"✅ Detection completed! Found {len(available_scanners)} scanner(s):")
        for scanner in available_scanners:
            print(f"   - {scanner['name']} ({scanner['type']})")
            if scanner['connection_info']:
                print(f"     Connection: {scanner['connection']}")

        if len(available_scanners) == 0:
            print("ℹ️  No scanners found. Make sure:")
            print("   - USB scanners are connected and powered on")
            print("   - Network scanners are on the same network")
            print("   - Scanner drivers are properly installed")

    except Exception as e:
        scanner_detection_status = "error"
        print(f"❌ Scanner detection failed: {e}")
        logging.error(f"Scanner detection error: {e}")
        available_scanners = []


def start_scanner_detection():
    """Start scanner detection with proper error handling"""
    try:
        detection_thread = threading.Thread(target=auto_detect_scanners, daemon=True)
        detection_thread.start()
        print("📡 Scanner auto-detection started in background...")
    except Exception as e:
        print(f"❌ Failed to start scanner detection: {e}")


# Start auto-detection in background thread on startup
start_scanner_detection()


@app.route('/')
def index():
    """Main page with scanner interface"""
    return render_template('scanner.html')


@app.route('/api/scanners', methods=['GET'])
def get_scanners():
    """Get list of available scanners with detailed information"""
    global available_scanners, scanner_detection_status, last_scan_detection

    return jsonify({
        'success': True,
        'scanners': available_scanners,
        'detection_status': scanner_detection_status,
        'last_detection': last_scan_detection.isoformat() if last_scan_detection else None,
        'total_count': len(available_scanners)
    })


@app.route('/api/scanners/refresh', methods=['POST'])
def refresh_scanners():
    """Manually refresh scanner list"""
    try:
        # Kill any existing detection processes
        global scanner_detection_status
        scanner_detection_status = "detecting"

        # Start detection in background thread with delay
        def delayed_detection():
            time.sleep(1)  # Small delay to avoid conflicts
            auto_detect_scanners()

        detection_thread = threading.Thread(target=delayed_detection, daemon=True)
        detection_thread.start()

        return jsonify({
            'success': True,
            'message': 'Scanner refresh started (this may take a few seconds)'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/debug/scanners', methods=['GET'])
def debug_scanners():
    """Debug route to see raw scanner data"""
    try:
        # Get raw scanner data
        raw_scanners = sm.list_scanners()

        debug_info = {
            'raw_scanners': raw_scanners,
            'scanner_count': len(raw_scanners) if raw_scanners else 0,
            'scanner_types': [type(scanner).__name__ for scanner in raw_scanners] if raw_scanners else [],
            'processed_scanners': available_scanners
        }

        # Try to understand each scanner's structure
        scanner_analysis = []
        for i, scanner in enumerate(raw_scanners if raw_scanners else []):
            analysis = {
                'index': i,
                'type': type(scanner).__name__,
                'value': str(scanner),
                'length': len(scanner) if hasattr(scanner, '__len__') else 'N/A'
            }

            if isinstance(scanner, (tuple, list)):
                analysis['elements'] = [str(elem) for elem in scanner]

            scanner_analysis.append(analysis)

        debug_info['scanner_analysis'] = scanner_analysis

        return jsonify({
            'success': True,
            'debug_info': debug_info
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'error_type': type(e).__name__
        }), 500


@app.route('/api/debug/system', methods=['GET'])
def debug_system():
    """Get system information for troubleshooting"""
    try:
        import platform
        import sys

        # Try to get SANE info if available
        sane_info = "Not available"
        try:
            import sane
            sane_info = f"SANE version: {sane.SANE_VERSION_MAJOR}.{sane.SANE_VERSION_MINOR}.{sane.SANE_VERSION_BUILD}"
        except ImportError:
            sane_info = "SANE not installed"
        except Exception as e:
            sane_info = f"SANE error: {str(e)}"

        return jsonify({
            'success': True,
            'system_info': {
                'platform': platform.platform(),
                'python_version': sys.version,
                'scanner_manager': 'Available' if sm else 'Not initialized',
                'sane_info': sane_info,
                'available_scanners_count': len(available_scanners),
                'detection_status': scanner_detection_status
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/scan', methods=['POST'])
def start_scan():
    """Start scanning process from selected scanner"""
    try:
        data = request.get_json()
        scanner_index = data.get('scanner_index')
        format_type = data.get('format', 'png')

        if scanner_index is None:
            return jsonify({
                'success': False,
                'error': 'Scanner index is required'
            }), 400

        # Validate scanner index
        if scanner_index >= len(available_scanners) or scanner_index < 0:
            return jsonify({
                'success': False,
                'error': 'Invalid scanner index'
            }), 400

        # Get scanner info
        selected_scanner = available_scanners[scanner_index]

        # Generate unique filename
        scan_id = str(uuid.uuid4())
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")  # FIXED: Use datetime.now()
        scanner_name = selected_scanner['name'].replace(' ', '_').replace('/', '_')[:20]
        filename = f"scan_{scanner_name}_{timestamp}_{scan_id}.{format_type}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        # Initialize scan status
        scan_status[scan_id] = {
            'status': 'scanning',
            'progress': 0,
            'filename': None,
            'error': None,
            'scanner_name': selected_scanner['name'],
            'scanner_type': selected_scanner['type']
        }

        # Update scanner last used
        available_scanners[scanner_index]['last_used'] = datetime.datetime.now().isoformat()  # FIXED: Use datetime.now()

        # Start scan in background thread
        thread = threading.Thread(
            target=perform_scan,
            args=(scan_id, scanner_index, filepath)
        )
        thread.start()

        return jsonify({
            'success': True,
            'scan_id': scan_id,
            'message': f'Scan started from {selected_scanner["name"]}',
            'scanner_info': selected_scanner
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/scan/network', methods=['POST'])
def start_network_scan():
    """Start network eSCL scanning process"""
    try:
        data = request.get_json()
        escl_url = data.get('escl_url')
        format_type = data.get('format', 'jpg')

        if not escl_url:
            return jsonify({
                'success': False,
                'error': 'eSCL URL is required'
            }), 400

        # Generate unique filename
        scan_id = str(uuid.uuid4())
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")  # FIXED: Use datetime.now()
        filename = f"network_scan_{timestamp}_{scan_id}.{format_type}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        # Initialize scan status
        scan_status[scan_id] = {
            'status': 'scanning',
            'progress': 0,
            'filename': None,
            'error': None
        }

        # Start network scan in background thread
        thread = threading.Thread(
            target=perform_network_scan,
            args=(scan_id, escl_url, filepath)
        )
        thread.start()

        return jsonify({
            'success': True,
            'scan_id': scan_id,
            'message': 'Network scan started'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/scan/status/<scan_id>', methods=['GET'])
def get_scan_status(scan_id):
    """Get status of a scan operation"""
    if scan_id not in scan_status:
        return jsonify({
            'success': False,
            'error': 'Scan ID not found'
        }), 404

    return jsonify({
        'success': True,
        'scan_status': scan_status[scan_id]
    })


@app.route('/api/download/<filename>')
def download_scan(filename):
    """Download a scanned file"""
    try:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.exists(filepath):
            return send_file(filepath, as_attachment=True)
        else:
            return jsonify({
                'success': False,
                'error': 'File not found'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/scans', methods=['GET'])
def list_scans():
    """List all available scans"""
    try:
        scans = []
        for filename in os.listdir(app.config['UPLOAD_FOLDER']):
            if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                stat = os.stat(filepath)
                scans.append({
                    'filename': filename,
                    'size': stat.st_size,
                    'created': datetime.datetime.fromtimestamp(stat.st_ctime).isoformat(),  # FIXED: Use datetime.datetime
                    'modified': datetime.datetime.fromtimestamp(stat.st_mtime).isoformat()   # FIXED: Use datetime.datetime
                })

        # Sort by creation time (newest first)
        scans.sort(key=lambda x: x['created'], reverse=True)

        return jsonify({
            'success': True,
            'scans': scans
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def perform_scan(scan_id, scanner_index, filepath):
    """Perform the actual scan operation in background thread"""
    try:
        # Update status to indicate scanning in progress
        scan_status[scan_id]['status'] = 'scanning'
        scan_status[scan_id]['progress'] = 25

        print(f"🖨️ Starting scan from scanner {scanner_index}: {available_scanners[scanner_index]['name']}")

        # Update progress
        scan_status[scan_id]['progress'] = 50

        # Perform the scan
        result = sm.scan(scanner_index, filepath)

        print(f"✅ Scan completed: {result}")

        # Update status on completion
        scan_status[scan_id]['status'] = 'completed'
        scan_status[scan_id]['progress'] = 100
        scan_status[scan_id]['filename'] = os.path.basename(result)

    except Exception as e:
        print(f"❌ Scan failed: {e}")
        scan_status[scan_id]['status'] = 'error'
        scan_status[scan_id]['error'] = str(e)


def perform_network_scan(scan_id, escl_url, filepath):
    """Perform the actual network scan operation in background thread"""
    try:
        # Update status to indicate scanning in progress
        scan_status[scan_id]['status'] = 'scanning'
        scan_status[scan_id]['progress'] = 25

        print(f"🌐 Starting network scan from: {escl_url}")

        # Update progress
        scan_status[scan_id]['progress'] = 50

        # Perform the network scan
        result = sm.scan_network_escl(escl_url, filepath)

        print(f"✅ Network scan completed: {result}")

        # Update status on completion
        scan_status[scan_id]['status'] = 'completed'
        scan_status[scan_id]['progress'] = 100
        scan_status[scan_id]['filename'] = os.path.basename(result)

    except Exception as e:
        print(f"❌ Network scan failed: {e}")
        scan_status[scan_id]['status'] = 'error'
        scan_status[scan_id]['error'] = str(e)


if __name__ == '__main__':
    print("🚀 Starting Web Scanner Application...")
    print("📡 Auto-detecting scanners in background...")
    print("🌐 Web interface will be available at http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)