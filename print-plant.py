# /// script
# dependencies = [
#  "pycups; sys_platform != 'win32'",
#  "jinja2"
# ]
# ///

"""
Reads plant data from parameters, populates a ZPL Jinja2 template,
and sends the rendered ZPL to a network printer via IPP (CUPS) for a single print.

Usage:
  uv run print-plant.py <path_to_zpl_template.zpl> "<scientific>" "<afr>" "<eng>" "<sep>" "<region>" "<url>"
  
Example:
  uv run print-plant.py my_label_template.zpl "Dombeya rotundifolia" "drolpeer" "wild pear" "mohlabaphala" "magaliesberg" "https://url.site.com"

ZPL Template Example (e.g., my_label_template.zpl):
  ^XA
  ^FT0,46^A0N,39,48^FH\^FD{{ scientific }}^FS
  ^FO0,53^GB500,0,4^FS
  ^FO497,3^GB0,157,4^FS
  ^FT0,90^A@N,28,29,TT0003M_^FH\^CI17^F8^FD{{ afr }}^FS^CI0
  ^FT0,118^A@N,28,29,TT0003M_^FH\^CI17^F8^FD{{ eng }}^FS^CI0
  ^FT0,148^A@N,28,29,TT0003M_^FH\^CI17^F8^FD{{ sep }}^FS^CI0
  ^FT312,114^A@N,28,29,TT0003M_^FH\^CI17^F8^FD{{ region }}^FS^CI0
  ^XZ
"""

import sys
import os
import tempfile
from jinja2 import Environment, FileSystemLoader, select_autoescape

# --- CUPS Configuration ---
PRINTER_QUEUE_NAME = "Zebra-ZD421-203dpi-ZPL"  # Replace with your printer's queue name
CUPS_SERVER_IP = "192.168.2.63"  # Replace with your CUPS server IP
CUPS_SERVER_PORT = 631
# --- End CUPS Configuration ---


try:
    import cups
except ImportError:
    print("Error: pycups library is not installed or not available on this system.")
    print("If you are on Linux/macOS, ensure 'pycups' is in the script's dependencies.")
    print("pycups is not available on Windows. For Windows, a different approach is needed.")
    sys.exit(1)

def render_zpl_template(template_path, data_context):
    """
    Renders a ZPL Jinja2 template with the given data context.
    Returns the rendered ZPL string or None if an error occurs.
    """
    if not os.path.exists(template_path):
        print(f"Error: ZPL template file not found at '{template_path}'")
        return None
    
    template_dir = os.path.dirname(template_path)
    template_filename = os.path.basename(template_path)
    
    env = Environment(
        loader=FileSystemLoader(template_dir if template_dir else '.'),
        autoescape=select_autoescape(['html', 'xml', 'zpl']) # ZPL isn't an official autoescape target
    )
    
    try:
        template = env.get_template(template_filename)
        rendered_zpl = template.render(data_context)
        return rendered_zpl
    except Exception as e:
        print(f"Error rendering ZPL template '{template_path}': {e}")
        return None

def _send_zpl_bytes_to_cups(zpl_data_bytes, job_title_identifier=""):
    """
    Internal function to send ZPL data (as bytes) to the CUPS printer.
    Writes data to a temporary file first.
    """
    temp_file_path = None
    try:
        cups.setServer(CUPS_SERVER_IP)
        cups.setPort(CUPS_SERVER_PORT)

        conn = cups.Connection(host=CUPS_SERVER_IP, port=CUPS_SERVER_PORT)
        
        printers = conn.getPrinters()
        if not printers:
            print(f"Error: No printers found on server {CUPS_SERVER_IP}:{CUPS_SERVER_PORT}.")
            return False

        if PRINTER_QUEUE_NAME not in printers:
            print(f"Error: Printer queue '{PRINTER_QUEUE_NAME}' not found on server {CUPS_SERVER_IP}:{CUPS_SERVER_PORT}.")
            print("Available printer queues on this server:")
            for printer_name in printers:
                print(f"  - {printer_name}")
            return False
        
        options = {
            'document-format': 'application/octet-stream', 
            'raw': 'true'
        }
        
        base_job_title = "Homebox ZPL Print"
        job_title = f"{base_job_title}: {job_title_identifier}" if job_title_identifier else base_job_title
        
        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.zpl') as tmp:
            tmp.write(zpl_data_bytes)
            temp_file_path = tmp.name
        
        print(f"Sending ZPL data from temporary file '{temp_file_path}' to printer '{PRINTER_QUEUE_NAME}' (Job: '{job_title}')...")
        job_id = conn.printFile(PRINTER_QUEUE_NAME, temp_file_path, job_title, options)
        
        print(f"Successfully submitted print job. Job ID: {job_id}")
        return True

    except cups.IPPError as e:
        print(f"IPPError communicating with CUPS/IPP server: {e}")
        print(f"Details: Server={CUPS_SERVER_IP}:{CUPS_SERVER_PORT}, Queue={PRINTER_QUEUE_NAME}")
        return False
    except RuntimeError as e:
        print(f"RuntimeError (often connection-related with CUPS): {e}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred during printing: {e}")
        return False
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except OSError as e:
                print(f"Warning: Could not delete temporary file '{temp_file_path}': {e}")

def main():
    if len(sys.argv) != 8:
        print('Usage: uv run print-plant.py <path_to_zpl_template.zpl> "<scientific>" "<afr>" "<eng>" "<sep>" "<region>" "<url>"')
        print('Example: uv run print-plant.py my_label_template.zpl "Dombeya rotundifolia" "drolpeer" "wild pear" "mohlabaphala" "magaliesberg" "https://url.site.com"')
        sys.exit(1)
    
    zpl_template_file = sys.argv[1]
    scientific = sys.argv[2]
    afr = sys.argv[3]
    eng = sys.argv[4]
    sep = sys.argv[5]
    region = sys.argv[6]
    url = sys.argv[7]

    if not os.path.exists(zpl_template_file):
        print(f"Error: ZPL template file not found at '{zpl_template_file}'")
        sys.exit(1)

    template_context = {
        "scientific": scientific,
        "afr": afr,
        "eng": eng,
        "sep": sep,
        "region": region,
        "url": url
    }
    print(f"\nUsing data for plant: {template_context}")

    rendered_zpl_string = render_zpl_template(zpl_template_file, template_context)

    if rendered_zpl_string:
        print("\n--- Rendered ZPL ---")
        print(rendered_zpl_string)
        print("---------------------\n")
        
        zpl_bytes_to_print = rendered_zpl_string.encode('utf-8')
        
        job_identifier = template_context.get('scientific', 'Unknown Plant')

        _send_zpl_bytes_to_cups(zpl_bytes_to_print, job_title_identifier=job_identifier)
    else:
        print("Failed to render ZPL template. Nothing to print.")
        sys.exit(1)

if __name__ == "__main__":
    main()