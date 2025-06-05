# /// script
# dependencies = [
#  "pycups; sys_platform != 'win32'"
# ]
# ///

"""
Sends a ZPL file to a network printer via IPP (CUPS).

Usage:
  uv run print_zpl.py <path_to_zpl_file.zpl>
  
Example:
  uv run print_zpl.py my_label.zpl

Note:
  For this script to work in a specific environment, it was found necessary
  to call cups.setServer() and cups.setPort() before creating the
  cups.Connection() object, even if the host and port are also passed
  to the Connection constructor.
"""

import sys
import os

# --- Configuration ---
PRINTER_QUEUE_NAME = "Zebra-ZD421-203dpi-ZPL"
CUPS_SERVER_IP = "192.168.2.63"
CUPS_SERVER_PORT = 631
# --- End Configuration ---

try:
    import cups
    print(f"Using pycups version: {cups.__version__}")
except ImportError:
    print("Error: pycups library is not installed or not available on this system.")
    print("If you are on Linux/macOS, ensure 'pycups' is in the script's dependencies.")
    print("pycups is not available on Windows. For Windows, a different approach is needed.")
    sys.exit(1)


def print_zpl_to_network_printer(zpl_file_path):
    """
    Sends the content of a ZPL file to the configured network printer.
    """
    if not os.path.exists(zpl_file_path):
        print(f"Error: ZPL file not found at '{zpl_file_path}'")
        sys.exit(1)

    try:
        # Set global CUPS server and port (found necessary in some environments)
        print(f"Setting CUPS default server to: {CUPS_SERVER_IP}:{CUPS_SERVER_PORT}")
        cups.setServer(CUPS_SERVER_IP)
        cups.setPort(CUPS_SERVER_PORT)

        print(f"Attempting to connect to CUPS/IPP server: {CUPS_SERVER_IP}:{CUPS_SERVER_PORT}...")
        # Explicitly passing host/port to Connection as well for clarity,
        # though setServer/setPort might make them redundant for default connection.
        conn = cups.Connection(host=CUPS_SERVER_IP, port=CUPS_SERVER_PORT)
        
        printers = conn.getPrinters()
        if not printers:
            print(f"Error: No printers found on server {CUPS_SERVER_IP}:{CUPS_SERVER_PORT}.")
            print("Please check the server address, port, and its CUPS configuration.")
            sys.exit(1)

        if PRINTER_QUEUE_NAME not in printers:
            print(f"Error: Printer queue '{PRINTER_QUEUE_NAME}' not found on server {CUPS_SERVER_IP}:{CUPS_SERVER_PORT}.")
            print("Available printer queues on this server:")
            for printer_name in printers:
                print(f"  - {printer_name}")
            print(f"\nPlease ensure PRINTER_QUEUE_NAME ('{PRINTER_QUEUE_NAME}') is correct.")
            sys.exit(1)

        print(f"Found printer queue: '{PRINTER_QUEUE_NAME}'")
        
        # Using 'application/octet-stream' was found to be reliable for ZPL.
        options = {
            'document-format': 'application/octet-stream'
        }
        
        job_title = f"ZPL Print (Python): {os.path.basename(zpl_file_path)}"
        
        print(f"\nSending '{zpl_file_path}' to printer '{PRINTER_QUEUE_NAME}' with options: {options}...")
        job_id = conn.printFile(PRINTER_QUEUE_NAME, zpl_file_path, job_title, options)
        
        print(f"Successfully submitted print job. Job ID: {job_id}")
        print("The job has been sent to the printer's queue.")

    except cups.IPPError as e:
        print(f"IPPError communicating with CUPS/IPP server: {e}")
        print(f"Details: Server={CUPS_SERVER_IP}:{CUPS_SERVER_PORT}, Queue={PRINTER_QUEUE_NAME}, Options={options}")
        print("Please check:")
        print("1. The CUPS/IPP server is running and accessible.")
        print("2. The printer is online, idle, and accepting jobs on the CUPS server.")
        print("3. The printer queue name is correct.")
        print("4. CUPS server logs might provide more details on the rejection.")
        sys.exit(1)
    except RuntimeError as e:
        # pycups can raise RuntimeError for various connection issues
        print(f"RuntimeError (often connection-related with CUPS): {e}")
        print(f"Could not connect to or operate with CUPS/IPP server at {CUPS_SERVER_IP}:{CUPS_SERVER_PORT}.")
        print("Ensure the server is reachable and the CUPS service is running on it.")
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: uv run print_zpl.py <path_to_zpl_file.zpl>")
        print("Example: uv run print_zpl.py my_label.zpl")
        sys.exit(1)
    
    file_to_print = sys.argv[1]
    print_zpl_to_network_printer(file_to_print)