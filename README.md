### Print ZPL

Scripts to send ZPL labels to a Zebra printer via CUPS.

#### Dependencies

```shell
apt update
apt install build-essential libcups2-dev clang
```

or for arch

```
sudo pacman -S base-devel cups clang
```

#### Usage (Generic — raw ZPL file)

Send any plain `.zpl` file directly to the printer:

```shell
uv run print.py <path_to_zpl_file.zpl>
```

#### Usage (Asset Labels)

Fetches asset data from Homebox, renders a Jinja2 ZPL template, and prints:

```shell
export HOMEBOX_API_URL="https://demo.homebox.site"
export HOMEBOX_USERNAME="asset@manager.com"
export HOMEBOX_PASSWORD=SOMEPASS
export OWNER_TEXT="my surname"
export ASSET_LABEL_URL_PREFIX="https://url.site.com/"

uv run print-asset.py <path_to_zpl_template.j2.zpl> "<ASSET-ID>"
```

#### Usage (Plant Labels)

```shell
uv run print-plant.py <path_to_zpl_template.j2.zpl> "<scientific>" "<afr>" "<eng>" "<sep>" "<region>" "<url>" "<planted_date>" "<flowering_range>" "<local_lang>"
```

#### Usage (Todoist Labels)

```shell
uv run print-todoist.py <path_to_zpl_template.j2.zpl> "<part_1>" "<part_2>" "<part_3>" "<url>"
```
