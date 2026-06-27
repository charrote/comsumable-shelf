#!/usr/bin/env python3
"""
Render Mermaid diagrams to PDF via a two-step process:
1. Extract mermaid blocks and render as SVG (either via Kroki or local HTML)
2. Build HTML with images, then use Playwright to convert HTML to PDF

Usage: python3 scripts/md_to_pdf.py <input.md> <output.pdf>
"""

import os
import re
import sys
import tempfile
import shutil
import base64
import urllib.request
import urllib.parse

def render_mermaid_via_kroki(mermaid_code: str) -> str | None:
    """Render mermaid via Kroki API using proper base64url encoding. Returns base64 PNG string."""
    try:
        import urllib.request
        # Use base64url encoding for Kroki POST body
        encoded = base64.urlencode({
            "d": mermaid_code.strip()
        }).replace("%3D", "=")
        
        # Kroki POST endpoint
        url = "https://kroki.io/mermaid/png"
        data = mermaid_code.strip().encode('utf-8')
        
        req = urllib.request.Request(url, data=data, headers={
            "Content-Type": "text/plain",
            "Accept": "image/png"
        })
        with urllib.request.urlopen(req, timeout=60) as resp:
            if resp.status == 200:
                png_bytes = resp.read()
                if len(png_bytes) > 100:
                    return base64.b64encode(png_bytes).decode('utf-8')
            else:
                print(f"  [WARN] Kroki returned {resp.status}")
                return None
    except Exception as e:
        print(f"  [WARN] Kroki failed: {e}")
    return None

def render_mermaid_local(mermaid_code: str, img_dir: str, index: int) -> str | None:
    """Render mermaid using Playwright + local mermaid.js. Returns path or None."""
    from playwright.sync_api import sync_playwright

    LOCAL_MERMAID_DIR = "/opt/homebrew/lib/node_modules/@slidev/cli/node_modules/mermaid/dist"

    # Copy entire mermaid dist to temp dir
    mermaid_dir = os.path.join(img_dir, "mermaid_dist")
    if os.path.exists(mermaid_dir):
        shutil.rmtree(mermaid_dir)
    shutil.copytree(LOCAL_MERMAID_DIR, mermaid_dir, dirs_exist_ok=True)

    # Build HTML that renders mermaid and returns SVG
    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
body {{ margin: 0; padding: 10px; }}
#diagram {{ display: flex; justify-content: center; }}
</style>
</head>
<body>
<div id="diagram">{mermaid_code}</div>
<script type="module">
import {{ default: mermaid }} from './mermaid_dist/mermaid.esm.mjs';
mermaid.initialize({{ startOnLoad: false, theme: 'neutral', securityLevel: 'loose', fontFamily: '"PingFang SC","Microsoft YaHei",sans-serif' }});
mermaid.run({{ nodes: [document.querySelector('#diagram')] }}).then(() => {{
    const svg = document.querySelector('#diagram svg');
    const svgString = new XMLSerializer().serializeToString(svg);
    window.__svg = svgString;
    window.__ready = true;
}}).catch(e => {{
    window.__error = e.message;
    window.__ready = true;
}});
</script>
</body>
</html>"""

    html_path = os.path.join(img_dir, "mermaid_input.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    svg = None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewbox={"width": 1200, "height": 800})
            try:
                page.goto(f"file://{html_path}", wait_until="networkidle", timeout=60000)
                # Poll for ready state with longer timeout
                for _ in range(30):
                    ready = page.evaluate("() => window.__ready")
                    if ready:
                        break
                    page.wait_for_timeout(2000)
                
                svg = page.evaluate("() => window.__svg")
                err = page.evaluate("() => window.__error")
                if err:
                    print(f"  [WARN] Mermaid JS error: {err}")
            except Exception as e:
                print(f"  [WARN] Page load/render failed: {e}")
            finally:
                browser.close()
    except Exception as e:
        print(f"  [WARN] Playwright failed: {e}")

    if svg and len(svg) > 100:
        svg_path = os.path.join(img_dir, f"mermaid_{index}.svg")
        with open(svg_path, "w", encoding="utf-8") as f:
            f.write(svg)
        return f"mermaid_{index}.svg"
    return None

def render_all_mermaid(md_text: str, img_dir: str) -> str:
    """Find all mermaid blocks, render them, replace in text."""
    counter = [0]

    def replacer(match):
        counter[0] += 1
        mermaid_code = match.group(1)
        
        # Try local first, then Kroki as fallback
        path = render_mermaid_local(mermaid_code, img_dir, counter[0])
        if not path:
            path = render_mermaid_local(mermaid_code, img_dir, counter[0])  # retry
        
        if path:
            return f"\n![sequence diagram]({path})\n"
        else:
            # Keep as code block with warning
            return f"\n⚠️ Mermaid diagram not rendered (rendering disabled)\n```mermaid\n{mermaid_code}\n```\n"

    return re.sub(r'```mermaid\s*\n(.*?)\n```', replacer, md_text, flags=re.DOTALL)

def build_html(md_path: str, img_dir: str) -> str:
    """Convert Markdown to styled HTML for PDF rendering."""
    with open(md_path, 'r', encoding='utf-8') as f:
        md_text = f.read()

    # First pass: render mermaid diagrams
    md_text = render_all_mermaid(md_text, img_dir)

    lines = md_text.split('\n')
    html_parts = []
    i = 0
    table_header = []
    table_rows = []

    def flush_table():
        if table_header:
            html_parts.append('<table class="table">')
            html_parts.append('<thead><tr>')
            for h in table_header:
                html_parts.append(f'<th>{escape_md(h)}</th>')
            html_parts.append('</tr></thead>')
            html_parts.append('<tbody>')
            for row in table_rows:
                html_parts.append('<tr>')
                for cell in row:
                    html_parts.append(f'<td>{escape_md(cell)}</td>')
                html_parts.append('</tr>')
            html_parts.append('</tbody></table>')
        table_header.clear()
        table_rows.clear()

    def escape_md(text: str) -> str:
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        text = re.sub(r'`([^`]+?)`', r'<code>\1</code>', text)
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
        return text

    def is_block_boundary(l, i, lines):
        if l.startswith('#') and re.match(r'^#{1,6}\s', l):
            return True
        if l.startswith('```'):
            return True
        if l.startswith('>'):
            return True
        if re.match(r'^[-]{3,}$', l.strip()):
            return True
        if '|' in l and i + 1 < len(lines) and re.match(r'^\|?[-:]+\|', lines[i + 1]):
            return True
        if re.match(r'^\s*[\*\-\+]\s+', l):
            return True
        if re.match(r'^\s*\d+\.\s+', l):
            return True
        return False

    while i < len(lines):
        line = lines[i]

        if not line.strip():
            i += 1
            continue

        # Horizontal rule
        if re.match(r'^[-]{3,}$', line.strip()):
            flush_table()
            html_parts.append('<hr>')
            i += 1
            continue

        # Headings
        h_match = re.match(r'^(#{1,6})\s+(.*)', line)
        if h_match:
            flush_table()
            level = len(h_match.group(1))
            text = h_match.group(2).strip()
            link_match = re.match(r'\[([^\]]+)\]\([^)]+\)', text)
            if link_match:
                text = link_match.group(1)
            text = escape_md(text)
            html_parts.append(f'<h{level}>{text}</h{level}>')
            i += 1
            continue

        # Blockquote
        if line.startswith('>'):
            flush_table()
            quote_lines = []
            while i < len(lines) and lines[i].startswith('>'):
                q = re.sub(r'^>\s?', '', lines[i])
                quote_lines.append(q)
                i += 1
            text = ' '.join(quote_lines)
            text = escape_md(text)
            html_parts.append(f'<blockquote class="quote">{text}</blockquote>')
            continue

        # Code block
        if line.startswith('```'):
            flush_table()
            lang = line[3:].strip()
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith('```'):
                code_lines.append(escape_md(lines[i]))
                i += 1
            i += 1  # skip closing ```
            code = '\n'.join(code_lines)
            if lang:
                html_parts.append(f'<pre><code class="lang-{lang}">{code}</code></pre>')
            else:
                html_parts.append(f'<pre><code>{code}</code></pre>')
            continue

        # Table
        if '|' in line and i + 1 < len(lines) and re.match(r'^\|?[-:]+\|', lines[i + 1]):
            flush_table()
            table_header = [c.strip() for c in line.split('|') if c.strip()]
            i += 2  # skip separator
            while i < len(lines) and '|' in lines[i]:
                row = [c.strip() for c in lines[i].split('|') if c.strip()]
                if row:
                    table_rows.append(row)
                i += 1
            continue

        # Unordered list
        ul_match = re.match(r'^(\s*)([*\-+])\s+(.*)', line)
        if ul_match:
            flush_table()
            level = len(ul_match.group(1)) // 2
            text = escape_md(ul_match.group(3))
            indent = level * 20
            html_parts.append(
                f'<div class="list-item" style="margin-left:{indent}px">&#8226; {text}</div>'
            )
            i += 1
            continue

        # Ordered list
        ol_match = re.match(r'^(\s*)(\d+)\.\s+(.*)', line)
        if ol_match:
            flush_table()
            level = len(ol_match.group(1)) // 2
            prefix = ol_match.group(2)
            text = escape_md(ol_match.group(3))
            indent = level * 20
            html_parts.append(
                f'<div class="list-item" style="margin-left:{indent}px">{prefix}. {text}</div>'
            )
            i += 1
            continue

        # Image reference on its own line
        img_match = re.match(r'^!\[([^\]]*)\]\(([^)]+)\)$', line.strip())
        if img_match:
            flush_table()
            alt = img_match.group(1)
            src = img_match.group(2)
            abs_path = os.path.join(img_dir, src)
            if os.path.exists(abs_path):
                html_parts.append(
                    f'<div class="mermaid-img"><img src="{abs_path}" alt="{alt}" class="mermaid-img"></div>'
                )
            else:
                # SVG from mermaid rendering
                html_parts.append(
                    f'<div class="mermaid-img"><svg class="mermaid-svg" viewBox="0 0 800 400" xmlns="http://www.w3.org/2000/svg">{src}</svg></div>'
                )
            i += 1
            continue

        # Regular paragraph - collect consecutive lines
        para_lines = []
        while i < len(lines):
            l = lines[i]
            if not l.strip():
                i += 1
                break
            if is_block_boundary(l, i, lines):
                break
            para_lines.append(l)
            i += 1
        if para_lines:
            flush_table()
            text = ' '.join(para_lines).strip()
            text = escape_md(text)
            html_parts.append(f'<p>{text}</p>')
            continue

        i += 1

    flush_table()

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<style>
@page {{
    size: A4;
    margin: 20mm 18mm 20mm 18mm;
}}
body {{
    font-family: "STSongti", "Noto Sans CJK SC", "Microsoft YaHei", "WenQuanYi Micro Hei", "PingFang SC", sans-serif;
    font-size: 10.5pt;
    line-height: 1.6;
    color: #1a1a1a;
}}
h1 {{
    font-size: 18pt;
    color: #1a3a66;
    border-bottom: 2px solid #b4c8de;
    padding-bottom: 6px;
    margin-top: 18pt;
    margin-bottom: 8pt;
    page-break-after: avoid;
}}
h2 {{
    font-size: 14pt;
    color: #214678;
    border-bottom: 1px solid #b4c8de;
    padding-bottom: 4px;
    margin-top: 14pt;
    margin-bottom: 6pt;
    page-break-after: avoid;
}}
h3 {{
    font-size: 12pt;
    color: #325a82;
    margin-top: 10pt;
    margin-bottom: 4pt;
    page-break-after: avoid;
}}
h4, h5, h6 {{
    font-size: 10pt;
    margin-top: 8pt;
    margin-bottom: 4pt;
    page-break-after: avoid;
}}
hr {{
    border: none;
    border-top: 1px solid #b4c8dc;
    margin: 12pt 0;
}}
blockquote {{
    border-left: 3px solid #6488c8;
    margin: 8pt 0;
    padding: 4pt 12pt;
    color: #3c3c3c;
    font-style: italic;
    background: #f8f9fc;
}}
p {{
    margin: 4pt 0;
}}
code {{
    font-family: "Courier New", "Menlo", monospace;
    background: #f0f4f8;
    padding: 1px 4px;
    border-radius: 2px;
    font-size: 9pt;
    color: #dc322f;
}}
pre {{
    background: #f5f8fc;
    border: 1px solid #c8d8e1;
    border-radius: 4px;
    padding: 8px 12px;
    margin: 8pt 0;
    overflow-x: auto;
}}
pre code {{
    font-size: 8pt;
    color: #282828;
    background: none;
    padding: 0;
}}
pre code::before {{
    content: attr(class);
    display: block;
    font-size: 7pt;
    font-weight: bold;
    color: #fff;
    background: #505050;
    padding: 1px 6px;
    margin: -8px -12px 6px -12px;
    border-radius: 4px 4px 0 0;
}}
table {{
    border-collapse: collapse;
    width: 100%;
    margin: 8pt 0;
    font-size: 9pt;
}}
th {{
    background: #e6f0fa;
    border: 1px solid #b4c8dc;
    padding: 4pt 8pt;
    font-weight: bold;
    color: #1a3a66;
    text-align: left;
}}
td {{
    border: 1px solid #c8d8e1;
    padding: 3pt 8pt;
    color: #1a1a1a;
}}
tr:nth-child(even) td {{
    background: #fafbff;
}}
.list-item {{
    margin: 2pt 0;
}}
.mermaid-img {{
    text-align: center;
    margin: 8pt 0;
}}
.mermaid-img img {{
    max-width: 100%;
    height: auto;
    display: inline-block;
}}
.mermaid-svg {{
    max-width: 100%;
    height: auto;
    display: inline-block;
}}
</style>
</head>
<body>
"""
    for part in html_parts:
        html += part + '\n'

    html += '</body>\n</html>'
    return html


def convert_md_to_pdf(md_path: str, output_path: str):
    """Main conversion function using Playwright chromium."""
    md_path = os.path.abspath(md_path)
    if not os.path.exists(md_path):
        print(f"ERROR: File not found: {md_path}")
        sys.exit(1)

    img_dir = tempfile.mkdtemp(prefix="md2pdf_")

    try:
        print("Step 1: Rendering Mermaid diagrams...")
        html = build_html(md_path, img_dir)
        print("  HTML generated")

        print("Step 2: Rendering PDF with Playwright chromium...")
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()

            html_path = os.path.join(img_dir, "input.html")
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html)

            page.goto(f"file://{html_path}")
            page.wait_for_load_state("networkidle")

            # Export PDF
            page.pdf(
                path=output_path,
                format='A4',
                print_background=True,
                margin={'top': '20mm', 'bottom': '20mm', 'left': '18mm', 'right': '18mm'},
            )
            browser.close()

        print(f"Step 3: Saved to {output_path}")
        size_kb = os.path.getsize(output_path) / 1024
        print(f"  File size: {size_kb:.1f} KB")

    finally:
        shutil.rmtree(img_dir, ignore_errors=True)


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python3 scripts/md_to_pdf.py <input.md> <output.pdf>")
        sys.exit(1)

    input_md = sys.argv[1]
    output_pdf = sys.argv[2]
    convert_md_to_pdf(input_md, output_pdf)
