# /// script
# dependencies = [
#  "pycups; sys_platform != 'win32'"
# ]
# ///

import sys
import os
import tempfile

# --- CUPS Configuration ---
PRINTER_QUEUE_NAME = "Zebra-ZD230-203dpi-ZPL"
CUPS_SERVER_IP = "192.168.2.63"
CUPS_SERVER_PORT = 631
# --- End CUPS Configuration ---

try:
    import cups
except ImportError:
    print("Error: pycups library is not installed or not available on this system.")
    sys.exit(1)

def send_zpl_file_to_cups(zpl_path):
    try:
        cups.setServer(CUPS_SERVER_IP)
        cups.setPort(CUPS_SERVER_PORT)
        conn = cups.Connection(host=CUPS_SERVER_IP, port=CUPS_SERVER_PORT)

        printers = conn.getPrinters()
        if not printers:
            print(f"Error: No printers found on server {CUPS_SERVER_IP}:{CUPS_SERVER_PORT}.")
            return False

        if PRINTER_QUEUE_NAME not in printers:
            print(f"Error: Printer queue '{PRINTER_QUEUE_NAME}' not found.")
            print("Available queues:")
            for name in printers:
                print(f"  - {name}")
            return False

        options = {'document-format': 'application/octet-stream', 'raw': 'true'}
        job_title = f"ZPL Print: {os.path.basename(zpl_path)}"

        with open(zpl_path, 'rb') as f:
            zpl_bytes = f.read()

        temp_file_path = None
        try:
            with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.zpl') as tmp:
                tmp.write(zpl_bytes)
                temp_file_path = tmp.name

            print(f"Sending '{zpl_path}' to printer '{PRINTER_QUEUE_NAME}'...")
            job_id = conn.printFile(PRINTER_QUEUE_NAME, temp_file_path, job_title, options)
            print(f"Successfully submitted print job. Job ID: {job_id}")
            return True
        finally:
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                except OSError:
                    pass

    except cups.IPPError as e:
        print(f"IPPError: {e}")
        return False
    except RuntimeError as e:
        print(f"RuntimeError: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False

def main():
    if len(sys.argv) != 2:
        print("Usage: uv run print.py <path_to_zpl_file.zpl>")
        sys.exit(1)

    zpl_file = sys.argv[1]

    if not os.path.exists(zpl_file):
        print(f"Error: ZPL file not found at '{zpl_file}'")
        sys.exit(1)

    if not send_zpl_file_to_cups(zpl_file):
        sys.exit(1)

if __name__ == "__main__":
    main()
