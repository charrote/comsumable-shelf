#!/usr/bin/env python3
"""Generate final PDF with Mermaid SVG embedded."""
import re, os, tempfile, shutil

MD_PATH = 'docs/RebuildShelf/05.储位变化回调接口规范-供应商版.md'
SVG_PATH = 'docs/RebuildShelf/mermaid_seq.svg'
OUTPUT_PATH = 'docs/RebuildShelf/05.储位变化回调接口规范-供应商版.pdf'

def build_html(md_path: str, svg_path: str) -> str:
    """Convert Markdown to HTML with embedded Mermaid SVG."""
    with open(md_path, 'r', encoding='utf-8') as f:
        md_text = f.read()
    
    # Read SVG
    with open(svg_path, 'r', encoding='utf-8') as f:
        svg_content = f.read()
    
    # Replace mermaid code block with inline SVG
    md_text = re.sub(
        r'```mermaid\s*\n(.*?)\n```',
        f'<div class="mermaid-diagram">{svg_content}</div>',
        md_text,
        flags=re.DOTALL
    )
    
    lines = md_text.split('\n')
    html_parts = []
    
    def escape_md(text):
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        # Don't escape our SVG
        return text
    
    i = 0
    in_table = False
    table_header = []
    table_rows = []
    
    def flush_table():
        nonlocal in_table, table_header, table_rows
        if in_table and table_header:
            html_parts.append('<table>')
            html_parts.append('<thead><tr>' + ''.join(f'<th>{escape_md(h)}</th>' for h in table_header) + '</tr></thead>')
            html_parts.append('<tbody>')
            for row in table_rows:
                html_parts.append('<tr>' + ''.join(f'<td>{escape_md(c)}</td>' for c in row) + '</tr>')
            html_parts.append('</tbody></table>')
        in_table = False
        table_header = []
        table_rows = []
    
    while i < len(lines):
        line = lines[i]
        
        # Horizontal rule
        if re.match(r'^[-]{3,}$', line.strip()):
            flush_table()
            html_parts.append('<hr>')
            i += 1
            continue
        
        # Headings
        h = re.match(r'^(#{1,6})\s+(.*)', line)
        if h:
            flush_table()
            level = len(h.group(1))
            text = h.group(2).strip()
            # Clean up link syntax in headings
            text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
            text = escape_md(text)
            html_parts.append(f'<h{level}>{text}</h{level}>')
            i += 1
            continue
        
        # Code blocks
        if line.startswith('```'):
            flush_table()
            lang = line[3:].strip()
            code = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith('```'):
                code.append(lines[i])
                i += 1
            i += 1  # skip closing ```
            escaped = '\n'.join(escape_md(l) for l in code)
            if lang:
                html_parts.append(f'<pre><code class="lang-{lang}">{escaped}</code></pre>')
            else:
                html_parts.append(f'<pre><code>{escaped}</code></pre>')
            continue
        
        # Tables
        if '|' in line and i + 1 < len(lines) and re.match(r'^\|?[-:]+\|', lines[i + 1]):
            in_table = True
            table_header = [c.strip() for c in line.split('|') if c.strip()]
            i += 2  # skip separator line
            while i < len(lines) and '|' in lines[i]:
                row = [c.strip() for c in lines[i].split('|') if c.strip()]
                if row:
                    table_rows.append(row)
                i += 1
            flush_table()
            continue
        
        # Blockquote
        if line.startswith('>'):
            flush_table()
            quote = re.sub(r'^>\s?', '', line)
            text = escape_md(quote.strip())
            html_parts.append(f'<blockquote>{text}</blockquote>')
            i += 1
            continue
        
        # List items (unordered)
        ul = re.match(r'^(\s*)[-*+]\s+(.*)', line)
        if ul:
            flush_table()
            indent = len(ul.group(1)) // 2 * 16
            text = escape_md(ul.group(2).strip())
            html_parts.append(f'<div style="margin-left:{indent}px">• {text}</div>')
            i += 1
            continue
        
        # List items (ordered)
        ol = re.match(r'^(\s*)\d+\.\s+(.*)', line)
        if ol:
            flush_table()
            indent = len(ol.group(1)) // 2 * 16
            text = escape_md(ol.group(2).strip())
            html_parts.append(f'<div style="margin-left:{indent}px">{text}</div>')
            i += 1
            continue
        
        # Empty lines
        if not line.strip():
            flush_table()
            i += 1
            continue
        
        # Paragraphs - collect consecutive lines
        para = []
        while i < len(lines):
            l = lines[i].strip()
            if not l:
                i += 1
                break
            # Stop on block elements
            if l.startswith('#') or l.startswith('```') or l.startswith('>') or '|' in l:
                if re.match(r'^[-]{3,}$', l):
                    i += 1
                    break
                if '|' in l and i + 1 < len(lines) and re.match(r'^\|?[-:]+\|', lines[i + 1]):
                    break
                if l.startswith('#') or l.startswith('```') or l.startswith('>'):
                    break
            if re.match(r'^(\s*)[-*+]\s+', l) or re.match(r'^(\s*)\d+\.\s+', l):
                break
            para.append(l)
            i += 1
        
        if para:
            flush_table()
            text = escape_md(' '.join(para))
            html_parts.append(f'<p>{text}</p>')
            continue
        
        i += 1
    
    flush_table()
    
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<style>
@page {{
    size: A4;
    margin: 20mm 18mm;
}}
body {{
    font-family: "PingFang SC","Microsoft YaHei","Noto Sans SC","Source Han Sans SC","WenQuanYi Micro Hei",sans-serif;
    font-size: 10.5pt;
    line-height: 1.6;
    color: #1a1a1a;
    -webkit-font-smoothing: antialiased;
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
    background: #f8f9fc;
}}
p {{
    margin: 4pt 0;
}}
code {{
    font-family: "Courier New","Menlo","Consolas",monospace;
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
    background: none;
    padding: 0;
    color: #282828;
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
    page-break-inside: auto;
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
}}
tr {{
    page-break-inside: avoid;
}}
tr:nth-child(even) td {{
    background: #fafbff;
}}
.list-item {{
    margin: 2pt 0;
}}
.mermaid-diagram {{
    text-align: center;
    margin: 12pt 0;
    page-break-inside: avoid;
}}
.mermaid-diagram svg {{
    max-width: 100%;
    height: auto;
    display: inline-block;
}}
</style>
</head>
<body>
{''.join(html_parts)}
</body>
</html>"""


def convert_to_pdf(html: str, output_path: str):
    """Convert HTML to PDF using Playwright."""
    from playwright.sync_api import sync_playwright
    
    img_dir = tempfile.mkdtemp(prefix="pdf_")
    
    try:
        html_path = os.path.join(img_dir, 'input.html')
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html)
        
        print("Generating PDF...")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1200, "height": 800})
            
            page.goto(f"file://{html_path}")
            page.wait_for_load_state("networkidle")
            
            page.pdf(
                path=output_path,
                format='A4',
                print_background=True,
                margin={
                    'top': '15mm',
                    'bottom': '15mm',
                    'left': '15mm',
                    'right': '15mm'
                },
            )
            
            browser.close()
        
        size = os.path.getsize(output_path) / 1024
        print(f"PDF saved: {output_path}")
        print(f"  Size: {size:.0f} KB")
        
    finally:
        shutil.rmtree(img_dir, ignore_errors=True)


if __name__ == '__main__':
    print("Building HTML...")
    html = build_html(MD_PATH, SVG_PATH)
    
    print("Converting to PDF...")
    convert_to_pdf(html, OUTPUT_PATH)
    
    # Verify
    import fitz
    doc = fitz.open(OUTPUT_PATH)
    print(f"Pages: {doc.page_count}")
    for i in range(doc.page_count):
        page = doc[i]
        text = page.get_text()
        has_svg = len(page.get_images()) > 0 or 'sequenceDiagram' not in text
        print(f"  Page {i+1}: {len(text)} chars, svg_embedded={has_svg}")
    doc.close()
