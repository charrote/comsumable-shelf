#!/usr/bin/env python3
"""Render Mermaid diagram to SVG using Playwright + local mermaid.min.js (file:// approach)."""
import os, sys, urllib.request, re

MERMAID_URL = "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"
MERMAID_LOCAL = "/tmp/mermaid.min.js"

def ensure_mermaid():
    if os.path.exists(MERMAID_LOCAL) and os.path.getsize(MERMAID_LOCAL) > 100000:
        return
    print("Downloading mermaid.min.js...")
    urllib.request.urlretrieve(MERMAID_URL, MERMAID_LOCAL)
    print(f"  Saved: {os.path.getsize(MERMAID_LOCAL)} bytes")

if __name__ == '__main__':
    ensure_mermaid()
    
    # Read mermaid source
    md_path = 'docs/RebuildShelf/05.储位变化回调接口规范-供应商版.md'
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    blocks = re.findall(r'```mermaid\s*\n(.*?)\n```', content, re.DOTALL)
    if not blocks:
        print("No mermaid blocks found")
        sys.exit(1)
    
    mermaid_src = blocks[0].strip()
    print(f"Mermaid source ({len(mermaid_src)} chars): {mermaid_src[:80]}...")
    
    # Create a temp HTML file that references mermaid.min.js via file://
    import tempfile, shutil
    
    tmpdir = tempfile.mkdtemp(prefix="mmdc_")
    html_path = os.path.join(tmpdir, 'render.html')
    
    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
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
}});
</script>
</body>
</html>"""
    
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    from playwright.sync_api import sync_playwright
    
    svg = None
    err_text = None
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1200, "height": 800})
        
        try:
            print("Loading page...")
            page.goto(f"file://{html_path}", wait_until="networkidle", timeout=60000)
            
            # Poll for result
            for attempt in range(20):
                ready = page.evaluate("() => window.__ready")
                if ready:
                    break
                print(f"  Waiting... ({attempt+1}/20)")
                page.wait_for_timeout(3000)
            
            svg = page.evaluate("() => window.__svg")
            err_text = page.evaluate("() => window.__error")
            
            # Get page console for debugging
            # (console was already captured by Playwright)
            
        except Exception as e:
            print(f"Error: {e}")
        finally:
            browser.close()
    
    if err_text:
        print(f"Mermaid error: {err_text}")
    
    if svg and len(svg) > 100:
        out_path = '/Users/Yoo/SVN/00.GITHUB/ComsumableManager/docs/RebuildShelf/mermaid_seq.svg'
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(svg)
        print(f"SUCCESS: SVG saved to {out_path}")
        print(f"Size: {os.path.getsize(out_path)} bytes")
    else:
        print("FAILED: No SVG output")
        
        # Try debugging: get page content
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1200, "height": 800})
            try:
                page.goto(f"file://{html_path}", wait_until="load", timeout=30000)
                page.wait_for_timeout(5000)
                
                # Check if mermaid is loaded
                mermaid_loaded = page.evaluate("() => typeof mermaid")
                print(f"mermaid type: {mermaid_loaded}")
                
                # Check console
                # (Playwright doesn't expose console by default in sync API)
                
                # Get the page content
                title = page.title()
                print(f"Page title: {title}")
                
                # Check for errors
                body = page.evaluate("() => document.body.innerHTML.substring(0, 500)")
                print(f"Body content: {body[:200]}")
            except Exception as e2:
                print(f"Debug error: {e2}")
            finally:
                browser.close()
    
    shutil.rmtree(tmpdir, ignore_errors=True)
