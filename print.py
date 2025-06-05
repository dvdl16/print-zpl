# /// script
# dependencies = [
#  "pycups; sys_platform != 'win32'",
#  "jinja2",
#  "requests"
# ]
# ///

"""
Reads asset data from a Homebox API, populates a ZPL Jinja2 template,
and sends the rendered ZPL to a network printer via IPP (CUPS) for a single print.

Requires Homebox API credentials and URL to be set as environment variables:
  HOMEBOX_API_URL:      e.g., https://your-homebox-instance.com
  HOMEBOX_USERNAME:     Your Homebox username
  HOMEBOX_PASSWORD:     Your Homebox password

Usage:
  uv run print_templated_zpl_homebox.py <path_to_zpl_template.j2> <asset_id_tag>
  
Example:
  uv run print_templated_zpl_homebox.py my_label_template.zpl.j2 "000-137"

ZPL Template Example (e.g., my_label_template.zpl.j2):
  ^XA
  ^FO50,50^A0N,30,30^FDAsset ID: {{ asset_id_tag }}^FS
  ^FO50,100^A0N,30,30^FDName: {{ name }}^FS
  ^FO50,150^A0N,25,25^FDLocation: {{ location_name | default('N/A') }}^FS
  ^FO50,200^A0N,20,20^FDModel: {{ model_number | default('N/A') }}^FS
  ^FO50,250^A0N,20,20^FDSerial: {{ serial_number | default('N/A') }}^FS
  ^FO50,300^A0N,20,20^FDURL: {{ asset_label_url }}^FS
  ^FO50,350^A0N,18,18^FDSummary: {{ summary_line | wordwrap(40) }}^FS 
  ^XZ
  
  Note: The wordwrap filter requires Jinja2 >= 2.7. For older versions, remove it
        or ensure your ZPL template handles line breaks within the summary manually.
"""

import sys
import os
import tempfile
import requests # For Homebox API calls
from jinja2 import Environment, FileSystemLoader, select_autoescape

# --- CUPS Configuration ---
PRINTER_QUEUE_NAME = "Zebra-ZD421-203dpi-ZPL"  # Replace with your printer's queue name
CUPS_SERVER_IP = "192.168.2.63"  # Replace with your CUPS server IP
CUPS_SERVER_PORT = 631
# --- End CUPS Configuration ---

# --- Homebox API Configuration ---
# These should be set as environment variables for security
HOMEBOX_API_URL = os.environ.get("HOMEBOX_API_URL")
HOMEBOX_USERNAME = os.environ.get("HOMEBOX_USERNAME")
HOMEBOX_PASSWORD = os.environ.get("HOMEBOX_PASSWORD")

# --- Additional label properties ---
OWNER_TEXT = os.environ.get("OWNER_TEXT")
ASSET_LABEL_URL_PREFIX = os.environ.get("ASSET_LABEL_URL_PREFIX")

REQUESTS_TIMEOUT = 10 # seconds for API requests
# --- End Homebox API Configuration ---

try:
    import cups
except ImportError:
    print("Error: pycups library is not installed or not available on this system.")
    print("If you are on Linux/macOS, ensure 'pycups' is in the script's dependencies.")
    print("pycups is not available on Windows. For Windows, a different approach is needed.")
    sys.exit(1)

def check_env_vars():
    """Checks if required environment variables are set."""
    missing_vars = []
    if not HOMEBOX_API_URL:
        missing_vars.append("HOMEBOX_API_URL")
    if not HOMEBOX_USERNAME:
        missing_vars.append("HOMEBOX_USERNAME")
    if not HOMEBOX_PASSWORD:
        missing_vars.append("HOMEBOX_PASSWORD")
    if not OWNER_TEXT:
        missing_vars.append("OWNER_TEXT")
    if not ASSET_LABEL_URL_PREFIX:
        missing_vars.append("ASSET_LABEL_URL_PREFIX")
    
    if missing_vars:
        print("Error: The following environment variables are not set:")
        for var in missing_vars:
            print(f"  - {var}")
        print("Please set them before running the script.")
        sys.exit(1)

def get_homebox_api_token(session):
    """Authenticates with Homebox API and returns the API token."""
    login_url = f"{HOMEBOX_API_URL}/api/v1/users/login"
    payload = {
        "username": HOMEBOX_USERNAME,
        "password": HOMEBOX_PASSWORD,
        "stayLoggedIn": "false"
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json"
    }
    try:
        print(f"Attempting to get API token from {login_url}...")
        response = session.post(login_url, data=payload, headers=headers, timeout=REQUESTS_TIMEOUT)
        response.raise_for_status()  # Raises HTTPError for bad responses (4XX or 5XX)
        token_data = response.json()
        print("Successfully obtained API token.")
        return token_data.get("token")
    except requests.exceptions.RequestException as e:
        print(f"Error during API login: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status: {e.response.status_code}")
            try:
                print(f"Response body: {e.response.json()}")
            except ValueError:
                print(f"Response body: {e.response.text}")
        return None
    except ValueError: # JSONDecodeError
        print("Error: Could not parse JSON response from API login.")
        return None

def get_asset_record_id(session, asset_id_tag, api_token):
    """Fetches the asset's internal record ID (UUID) using the human-readable asset_id_tag."""
    asset_search_url = f"{HOMEBOX_API_URL}/api/v1/assets/{asset_id_tag}"
    headers = {
        "Accept": "application/json",
        "Authorization": api_token # Note: Homebox API docs usually expect "Bearer <token>"
                                   # The provided curl example just uses the token directly.
                                   # Adjust if "Bearer " prefix is needed.
    }
    try:
        print(f"Fetching asset record ID for '{asset_id_tag}' from {asset_search_url}...")
        response = session.get(asset_search_url, headers=headers, timeout=REQUESTS_TIMEOUT)
        response.raise_for_status()
        asset_list_data = response.json()
        
        if asset_list_data.get("total", 0) > 0 and asset_list_data.get("items"):
            record_id = asset_list_data["items"][0].get("id")
            if record_id:
                print(f"Found asset record ID: {record_id}")
                return record_id
            else:
                print(f"Error: 'id' field missing in asset item for '{asset_id_tag}'.")
                return None
        else:
            print(f"Error: Asset with ID tag '{asset_id_tag}' not found or no items returned.")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching asset record ID for '{asset_id_tag}': {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status: {e.response.status_code}")
            try:
                print(f"Response body: {e.response.json()}")
            except ValueError:
                print(f"Response body: {e.response.text}")
        return None
    except (ValueError, KeyError, IndexError) as e:
        print(f"Error parsing asset record ID response for '{asset_id_tag}': {e}")
        return None

def get_asset_details(session, record_id, api_token):
    """Fetches full details for an asset using its record ID (UUID)."""
    item_details_url = f"{HOMEBOX_API_URL}/api/v1/items/{record_id}"
    headers = {
        "Accept": "application/json",
        "Authorization": api_token # Same note as above about "Bearer "
    }
    try:
        print(f"Fetching details for asset record ID '{record_id}' from {item_details_url}...")
        response = session.get(item_details_url, headers=headers, timeout=REQUESTS_TIMEOUT)
        response.raise_for_status()
        item_details = response.json()
        print(f"Successfully fetched details for asset '{item_details.get('name', record_id)}'.")
        return item_details
    except requests.exceptions.RequestException as e:
        print(f"Error fetching asset details for record ID '{record_id}': {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status: {e.response.status_code}")
            try:
                print(f"Response body: {e.response.json()}")
            except ValueError:
                print(f"Response body: {e.response.text}")
        return None
    except ValueError: # JSONDecodeError
        print(f"Error: Could not parse JSON response for asset details (ID: {record_id}).")
        return None

def prepare_template_context(item_details):
    """Prepares the data context dictionary for the Jinja2 template."""
    if not item_details:
        return {}

    asset_id_tag = item_details.get('assetId', 'N/A')
    model_number = item_details.get('modelNumber', 'N/A')
    serial_number = item_details.get('serialNumber', 'N/A')
    purchase_from = item_details.get('purchaseFrom', 'N/A')
    purchase_price = item_details.get('purchasePrice', 0)
    purchase_time = item_details.get('purchaseTime', 'N/A') # Format: "YYYY-MM-DD"

    summary = (
        f"{asset_id_tag} | {model_number} | Serial {serial_number} | "
        f"Seller {purchase_from} | ZAR {purchase_price} on {purchase_time}"
    )

    context = {
        'asset_id_tag': asset_id_tag,
        'name': item_details.get('name', 'N/A'),
        'description': item_details.get('description', 'N/A')[:28], # limit characaters due to space on label
        'model_number': model_number,
        'serial_number': serial_number[-10:],
        'purchase_price': purchase_price,
        'purchase_from': purchase_from,
        'purchase_date': purchase_time,
        'location_name': item_details.get('location', {}).get('name', 'N/A'),
        'asset_label_url': f"{ASSET_LABEL_URL_PREFIX}{asset_id_tag}" if asset_id_tag != 'N/A' else 'N/A',
        'summary_line': summary,
        'owner_text': OWNER_TEXT,
        'raw_api_response': item_details # For advanced template usage if needed
    }
    return context

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
    check_env_vars()

    if len(sys.argv) < 3:
        print("Usage: uv run print_templated_zpl_homebox.py <path_to_zpl_template.j2> <asset_id_tag>")
        print("Example: uv run print_templated_zpl_homebox.py my_label_template.zpl.j2 \"000-137\"")
        sys.exit(1)
    
    zpl_template_file = sys.argv[1]
    asset_id_tag_input = sys.argv[2] # e.g., "000-137"

    if not os.path.exists(zpl_template_file):
        print(f"Error: ZPL template file not found at '{zpl_template_file}'")
        sys.exit(1)

    item_details = None
    with requests.Session() as session:
        api_token = get_homebox_api_token(session)
        if not api_token:
            print("Failed to obtain API token. Exiting.")
            sys.exit(1)

        # The curl example for Authorization only uses the token, not "Bearer <token>"
        # If your Homebox instance needs "Bearer ", adjust here or in helper functions.
        # session.headers.update({"Authorization": f"Bearer {api_token}"})
        session.headers.update({"Authorization": api_token})


        asset_record_id = get_asset_record_id(session, asset_id_tag_input, api_token) # api_token passed for consistency, though session has it
        if not asset_record_id:
            print(f"Failed to find asset record ID for '{asset_id_tag_input}'. Exiting.")
            sys.exit(1)
        
        item_details = get_asset_details(session, asset_record_id, api_token) # api_token passed for consistency
        if not item_details:
            print(f"Failed to fetch details for asset record ID '{asset_record_id}'. Exiting.")
            sys.exit(1)

    if not item_details:
        print("No asset data fetched. Cannot proceed.")
        sys.exit(1)
        
    template_context = prepare_template_context(item_details)
    print(f"\nUsing data for asset '{template_context.get('name', asset_id_tag_input)}': {template_context}")

    rendered_zpl_string = render_zpl_template(zpl_template_file, template_context)

    if rendered_zpl_string:
        print("\n--- Rendered ZPL ---")
        print(rendered_zpl_string)
        print("---------------------\n")
        
        zpl_bytes_to_print = rendered_zpl_string.encode('utf-8')
        
        job_identifier = template_context.get('asset_id_tag', 'Unknown Asset')
        if template_context.get('name') and template_context.get('name') != 'N/A':
             job_identifier += f" ({template_context.get('name')})"
        
        _send_zpl_bytes_to_cups(zpl_bytes_to_print, job_title_identifier=job_identifier)
    else:
        print("Failed to render ZPL template. Nothing to print.")
        sys.exit(1)

if __name__ == "__main__":
    main()