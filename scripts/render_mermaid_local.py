#!/usr/bin/env python3
"""Render Mermaid diagrams using Playwright + local mermaid.min.js."""
import re, os, sys, urllib.request, urllib.parse

MERMAID_URL = "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"
MERMAID_LOCAL = "/tmp/mermaid.min.js"

def ensure_mermaid():
    """Download mermaid.min.js if not present."""
    if os.path.exists(MERMAID_LOCAL) and os.path.getsize(MERMAID_LOCAL) > 100000:
        return True
    
    print("Downloading mermaid.min.js...")
    urllib.request.urlretrieve(MERMAID_URL, MERMAID_LOCAL)
    print(f"  Saved: {os.path.getsize(MERMAID_LOCAL)} bytes")
    return True


def render_mermaid_to_svg(mermaid_src: str) -> str | None:
    """Render mermaid source to SVG using Playwright + local mermaid.min.js."""
    from playwright.sync_api import sync_playwright
    
    ensure_mermaid()
    
    # Build HTML page that loads local mermaid.min.js and renders
    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
body {{ margin: 0; padding: 10px; }}
#diagram {{ text-align: center; }}
</style>
</head>
<body>
<div id="diagram">{mermaid_src}</div>
<script src="file://{MERMAID_LOCAL}"></script>
<script>
mermaid.initialize({{ 
    startOnLoad: false, 
    theme: 'neutral', 
    securityLevel: 'loose',
    fontFamily: '"PingFang SC","Microsoft YaHei","Noto Sans SC",sans-serif',
    flowchart: {{ curve: 'basis', useMaxWidth: true }},
    sequence: {{ diagramMarginX: 50, diagramMarginY: 30, actorMargin: 50, width: 200, height: 80 }},
}});
mermaid.run({{ nodes: [document.querySelector('#diagram')] }}).then(() => {{
    const svg = document.querySelector('#diagram svg');
    const svgString = new XMLSerializer().serializeToString(svg);
    window.__svg = svgString;
    window.__ready = true;
}}).catch(e => {{
    window.__error = e.message;
    window.__ready = true;
    console.error('Mermaid error:', e);
}});
</script>
</body>
</html>"""
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        try:
            page.goto("data:text/html;charset=utf-8," + urllib.parse.quote(html), timeout=60000)
            
            # Wait for mermaid initialization
            for _ in range(20):
                ready = page.evaluate("() => window.__ready")
                if ready:
                    break
                page.wait_for_timeout(3000)
            
            svg = page.evaluate("() => window.__svg")
            err = page.evaluate("() => window.__error")
            
            if err:
                print(f"  [WARN] Mermaid error: {err}", file=sys.stderr)
            if svg and len(svg) > 100:
                return svg
            
            return None
        except Exception as e:
            print(f"  [WARN] Playwright failed: {e}", file=sys.stderr)
            return None
        finally:
            browser.close()


def render_all_and_replace(img_dir: str) -> str:
    """Render all mermaid diagrams and return HTML with embedded SVG."""
    with open('docs/RebuildShelf/05.储位变化回调接口规范-供应商版.md', 'r', encoding='utf-8') as f:
        content = f.read()
    
    counter = [0]
    
    def replacer(match):
        counter[0] += 1
        mermaid_src = match.group(1).strip()
        
        svg = render_mermaid_to_svg(mermaid_src)
        
        if svg:
            svg_path = os.path.join(img_dir, f"mermaid_{counter[0]}.svg")
            with open(svg_path, 'w', encoding='utf-8') as f:
                f.write(svg)
            
            svg_size = os.path.getsize(svg_path)
            print(f"  Rendered mermaid_{counter[0]}: {svg_size} bytes")
            return f'![sequence diagram]({svg_path})'
        else:
            print(f"  [WARN] Failed to render mermaid block {counter[0]}")
            return match.group(0)  # keep original
    
    return re.sub(r'```mermaid\s*\n(.*?)\n```', replacer, content, flags=re.DOTALL)


def build_pdf(md_content: str, output_path: str):
    """Build HTML from markdown content and convert to PDF."""
    import tempfile, shutil
    from playwright.sync_api import sync_playwright
    
    img_dir = tempfile.mkdtemp(prefix="pdf_")
    
    try:
        # Render mermaid diagrams
        print("Step 1: Rendering Mermaid diagrams...")
        content = render_all_and_replace(img_dir)
        
        # Convert markdown to HTML
        lines = content.split('\n')
        html_parts = []
        
        def escape_md(text):
            text = text.replace('&', '&amp;')
            text = text.replace('<', '&lt;')
            text = text.replace('>', '&gt;')
            text = re.sub(r'`([^`]+?)`', r'<code>\1</code>', text)
            text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
            text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
            return text
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            if not line:
                i += 1
                continue
            
            # Headings
            h = re.match(r'^(#{1,6})\s+(.*)', lines[i])
            if h:
                level = len(h.group(1))
                text = escape_md(h.group(2).strip())
                html_parts.append(f'<h{level}>{text}</h{level}>')
                i += 1
                continue
            
            # Code block
            if lines[i].startswith('```'):
                lang = lines[i][3:].strip()
                code = []
                i += 1
                while i < len(lines) and not lines[i].strip().startswith('```'):
                    code.append(lines[i])
                    i += 1
                i += 1  # skip closing ```
                escaped = '\n'.join(escape_md(l) for l in code)
                html_parts.append(f'<pre><code>{escaped}</code></pre>')
                continue
            
            # Table
            if '|' in lines[i] and i + 1 < len(lines) and re.match(r'^\|?[-:]+\|', lines[i + 1]):
                header = [c.strip() for c in lines[i].split('|') if c.strip()]
                i += 2
                rows = []
                while i < len(lines) and '|' in lines[i]:
                    row = [c.strip() for c in lines[i].split('|') if c.strip()]
                    if row:
                        rows.append(row)
                    i += 1
                
                html_parts.append('<table>')
                html_parts.append('<thead><tr>' + ''.join(f'<th>{escape_md(h)}</th>' for h in header) + '</tr></thead>')
                html_parts.append('<tbody>')
                for row in rows:
                    html_parts.append('<tr>' + ''.join(f'<td>{escape_md(c)}</td>' for c in row) + '</tr>')
                html_parts.append('</tbody></table>')
                continue
            
            # Images
            img = re.match(r'!\[([^\]]*)\]\(([^)]+)\)', line)
            if img:
                html_parts.append(f'<img src="{img.group(2)}" alt="{img.group(1)}" style="max-width:100%">')
                i += 1
                continue
            
            # Quote
            if lines[i].startswith('>'):
                text = escape_md(re.sub(r'^>\s*', '', lines[i]))
                html_parts.append(f'<blockquote>{text}</blockquote>')
                i += 1
                continue
            
            # List items
            if re.match(r'^(\s*[-*+])\s+', lines[i]):
                text = escape_md(re.match(r'^(\s*[-*+])\s+(.*)', lines[i]).group(2))
                indent = (len(lines[i]) - len(lines[i].lstrip())) * 2
                html_parts.append(f'<div style="margin-left:{indent}px">• {text}</div>')
                i += 1
                continue
            
            # Paragraphs
            para = []
            while i < len(lines):
                l = lines[i].strip()
                if not l:
                    i += 1
                    break
                if l.startswith('#') or l.startswith('```') or l.startswith('>') or '|' in l:
                    break
                para.append(l)
                i += 1
            
            if para:
                html_parts.append(f'<p>{escape_md(" ".join(para))}</p>')
                continue
            
            i += 1
        
        full_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<style>
@page {{ size: A4; margin: 20mm 18mm; }}
body {{
    font-family: "PingFang SC","Microsoft YaHei","Noto Sans SC","Source Han Sans SC",sans-serif;
    font-size: 10.5pt;
    line-height: 1.6;
    color: #1a1a1a;
}}
h1 {{ font-size: 18pt; color: #1a3a66; border-bottom: 2px solid #b4c8de; padding-bottom: 6px; }}
h2 {{ font-size: 14pt; color: #214678; border-bottom: 1px solid #b4c8de; padding-bottom: 4px; }}
h3 {{ font-size: 12pt; color: #325a82; }}
h4,h5,h6 {{ font-size: 10pt; }}
p {{ margin: 4pt 0; }}
code {{
    font-family: "Courier New","Menlo",monospace;
    background: #f0f4f8;
    padding: 1px 4px;
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
}}
td {{
    border: 1px solid #c8d8e1;
    padding: 3pt 8pt;
}}
tr:nth-child(even) td {{ background: #fafbff; }}
blockquote {{
    border-left: 3px solid #6488c8;
    margin: 8pt 0;
    padding: 4pt 12pt;
    color: #3c3c3c;
    background: #f8f9fc;
}}
img {{ max-width: 100%; margin: 8pt 0; display: block; }}
</style>
</head>
<body>
{''.join(html_parts)}
</body>
</html>"""
        
        print("Step 2: Converting to PDF...")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1200, "height": 800})
            
            html_path = os.path.join(img_dir, "input.html")
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(full_html)
            
            page.goto(f"file://{html_path}")
            page.wait_for_load_state("networkidle")
            
            page.pdf(
                path=output_path,
                format='A4',
                print_background=True,
                margin={'top': '15mm', 'bottom': '15mm', 'left': '15mm', 'right': '15mm'},
            )
            
            browser.close()
        
        size = os.path.getsize(output_path) / 1024
        print(f"Step 3: Saved to {output_path} ({size:.0f} KB)")
        
    finally:
        shutil.rmtree(img_dir, ignore_errors=True)


if __name__ == '__main__':
    output = sys.argv[1] if len(sys.argv) > 1 else 'docs/RebuildShelf/05.储位变化回调接口规范-供应商版.pdf'
    build_pdf('docs/RebuildShelf/05.储位变化回调接口规范-供应商版.md', output)