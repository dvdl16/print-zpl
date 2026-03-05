# /// script
# dependencies = [
#  "pycups; sys_platform != 'win32'",
#  "jinja2"
# ]
# ///

"""
Renders a Todoist ZPL Jinja2 template with provided text parts and URL,
and sends the rendered ZPL to a network printer via IPP (CUPS) for a single print.

Usage:
  uv run print-todoist.py <path_to_zpl_template.zpl> "<part_1>" "<part_2>" "<part_3>" "<url>"

Example:
  uv run print-todoist.py Todoist-v1.j2.zpl "Buy groceries" "Milk, eggs" "By Friday" "https://todoist.com/app/task/12345"
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
        autoescape=select_autoescape(['html', 'xml', 'zpl'])
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

        base_job_title = "Todoist ZPL Print"
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
    if len(sys.argv) != 6:
        print('Usage: uv run print-todoist.py <path_to_zpl_template.zpl> "<part_1>" "<part_2>" "<part_3>" "<url>"')
        print('Example: uv run print-todoist.py Todoist-v1.j2.zpl "Buy groceries" "Milk, eggs" "By Friday" "https://todoist.com/app/task/12345"')
        sys.exit(1)

    zpl_template_file = sys.argv[1]
    part_1 = sys.argv[2]
    part_2 = sys.argv[3]
    part_3 = sys.argv[4]
    url = sys.argv[5]

    if not os.path.exists(zpl_template_file):
        print(f"Error: ZPL template file not found at '{zpl_template_file}'")
        sys.exit(1)

    template_context = {
        "part_1": part_1,
        "part_2": part_2,
        "part_3": part_3,
        "url": url,
    }
    print(f"\nUsing data: {template_context}")

    rendered_zpl_string = render_zpl_template(zpl_template_file, template_context)

    if rendered_zpl_string:
        print("\n--- Rendered ZPL ---")
        print(rendered_zpl_string)
        print("---------------------\n")

        zpl_bytes_to_print = rendered_zpl_string.encode('utf-8')
        _send_zpl_bytes_to_cups(zpl_bytes_to_print, job_title_identifier=part_1)
    else:
        print("Failed to render ZPL template. Nothing to print.")
        sys.exit(1)

if __name__ == "__main__":
    main()
