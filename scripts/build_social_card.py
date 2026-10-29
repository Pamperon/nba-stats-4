"""Build the repository's social cover from the existing inline brand mark.

Run with CairoSVG installed locally: python scripts/build_social_card.py.
CairoSVG is a design-time dependency; production serves the committed PNG.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def main():
    import cairosvg
    from PIL import Image
    html = (ROOT / 'web/index.html').read_text()
    mark = re.search(r'<svg viewBox="0 0 96 96"[^>]*>(.*?)</svg>', html).group(1)
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="400" viewBox="0 0 1200 400">
<defs><linearGradient id="background" x2="1" y2="1"><stop stop-color="#101d31"/><stop offset="1" stop-color="#0b1220"/></linearGradient></defs>
<rect width="1200" height="400" fill="url(#background)"/>
<g stroke="#23354e" fill="none" stroke-width="2" opacity=".6"><circle cx="1200" cy="0" r="330"/><circle cx="1200" cy="0" r="220"/><circle cx="0" cy="400" r="180"/></g>
<g transform="translate(130 25) scale(3.4)">{mark}</g>
<g font-family="DejaVu Sans,sans-serif">
<text x="460" y="180" fill="#f5f9ff" font-size="79" font-weight="bold" letter-spacing="-2">BASKET <tspan fill="#fa9148">LAB</tspan></text>
<text x="465" y="235" fill="#aebed1" font-size="30">Statistiche e analisi NBA</text>
<rect x="465" y="262" width="48" height="3" rx="1.5" fill="#fa9148"/>
<text x="465" y="312" fill="#f5f9ff" font-size="27">basketlab.it</text>
</g></svg>'''
    (ROOT / 'web/social-card-v2.svg').write_text(svg)
    output = ROOT / 'web/social-card-v2.png'
    cairosvg.svg2png(bytestring=svg.encode(), write_to=str(output))
    with Image.open(output) as image:
        optimized = image.convert('RGB').quantize(colors=128)
    optimized.save(output, optimize=True)


if __name__ == '__main__':
    main()
