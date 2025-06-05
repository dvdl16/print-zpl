# /// script
# dependencies = [
#  "pycups; sys_platform != 'win32'",
#  "jinja2",
#  "pandas"
# ]
# ///

"""
Reads data from a CSV, populates a ZPL Jinja2 template,
and sends the rendered ZPL to a network printer via IPP (CUPS) for a single print
(using the first data row of the CSV).

Usage:
  uv run print_templated_zpl.py <path_to_zpl_template.j2> <path_to_data.csv>
  
Example:
  uv run print_templated_zpl.py my_label_template.zpl.j2 data_source.csv

ZPL Template Example (e.g., my_label_template.zpl.j2):
  ^XA
  ^FO50,50^A0N,30,30^FDProduct: {{ product_name }}^FS
  ^FO50,100^A0N,30,30^FDID: {{ item_id }}^FS
  ^XZ

CSV Data Example (e.g., data_source.csv):
  product_name,item_id
  Awesome Gadget,AG-001
  Another Item,AI-002
"""

import sys
import os
import tempfile 
import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape

# --- CUPS Configuration ---
PRINTER_QUEUE_NAME = "Zebra-ZD421-203dpi-ZPL"
CUPS_SERVER_IP = "192.168.2.63"
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
    
    # If template_dir is empty (template is in current dir), FileSystemLoader needs '.'
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
        # Set global CUPS server and port (found necessary in some environments)
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
            'document-format': 'application/octet-stream', # Reliable for raw ZPL
            'raw': 'true'
        }
        
        base_job_title = "ZPL Templated Print"
        job_title = f"{base_job_title}: {job_title_identifier}" if job_title_identifier else base_job_title
        
        # Create a temporary file to hold the ZPL data
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
        # Clean up the temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
                # print(f"Cleaned up temporary file: {temp_file_path}") # Optional debug
            except OSError as e:
                print(f"Warning: Could not delete temporary file '{temp_file_path}': {e}")

def main():
    if len(sys.argv) < 3:
        print("Usage: uv run print_templated_zpl.py <path_to_zpl_template.j2> <path_to_data.csv>")
        print("Example: uv run print_templated_zpl.py my_label_template.zpl.j2 data_source.csv")
        sys.exit(1)
    
    zpl_template_file = sys.argv[1]
    csv_data_file = sys.argv[2]

    if not os.path.exists(zpl_template_file):
        print(f"Error: ZPL template file not found at '{zpl_template_file}'")
        sys.exit(1)
    if not os.path.exists(csv_data_file):
        print(f"Error: CSV data file not found at '{csv_data_file}'")
        sys.exit(1)

    # Read CSV data
    try:
        df = pd.read_csv(csv_data_file)
        if df.empty:
            print(f"Warning: CSV file '{csv_data_file}' is empty or contains no data rows after headers.")
            sys.exit(0) # Exit gracefully, no data to print
        
        # Convert all rows to a list of dictionaries
        data_records = df.to_dict(orient='records')
    except pd.errors.EmptyDataError:
        print(f"Error: CSV file '{csv_data_file}' is empty.")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading or processing CSV file '{csv_data_file}': {e}")
        sys.exit(1)

    # For this script, we process only the first data row for a "single print"
    # as per the spirit of the original request.
    # To print for all rows, you would loop through data_records.
    if not data_records: # Should be caught by df.empty, but as a safeguard
        print(f"No data records found in '{csv_data_file}'.")
        sys.exit(0)
        
    first_row_data = data_records[0]
    print(f"Using data from the first row of CSV: {first_row_data}")

    # Render the ZPL template with the first row's data
    rendered_zpl_string = render_zpl_template(zpl_template_file, first_row_data)

    if rendered_zpl_string:
        print("\n--- Rendered ZPL ---")
        print(rendered_zpl_string)
        print("---------------------\n")
        
        # ZPL data should be sent as bytes (UTF-8 is common for ZPL if non-ASCII chars are possible,
        # otherwise ASCII is fine).
        zpl_bytes_to_print = rendered_zpl_string.encode('utf-8')
        
        # Attempt to identify the job using a value from the CSV if possible
        # Try a common identifier like 'id', 'item_id', 'name', 'product_name'
        job_identifier_keys = ['id', 'item_id', 'name', 'product_name', df.columns[0] if len(df.columns) > 0 else '']
        job_id_value = "First Row"
        for key in job_identifier_keys:
            if key in first_row_data and first_row_data[key]:
                job_id_value = str(first_row_data[key])
                break
        
        _send_zpl_bytes_to_cups(zpl_bytes_to_print, job_title_identifier=job_id_value)
    else:
        print("Failed to render ZPL template. Nothing to print.")
        sys.exit(1)
    
    # To print labels for all rows in the CSV, you could do:
    # print(f"\n--- Printing for all {len(data_records)} records in CSV ---")
    # for i, record in enumerate(data_records):
    #     print(f"\nProcessing record {i+1}: {record}")
    #     rendered_zpl = render_zpl_template(zpl_template_file, record)
    #     if rendered_zpl:
    #         zpl_bytes = rendered_zpl.encode('utf-8')
    #         job_id_val = str(record.get(job_identifier_keys[0], f"Record {i+1}")) # Adjust identifier as needed
    #         _send_zpl_bytes_to_cups(zpl_bytes, job_title_identifier=job_id_val)
    #         # Consider adding a small delay if printing many labels rapidly:
    #         # import time
    #         # time.sleep(0.5) # 0.5 second delay
    #     else:
    #         print(f"Skipping record {i+1} due to template rendering error.")

if __name__ == "__main__":
    main()