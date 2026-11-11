import re
from pathlib import Path

import cairosvg

ROOT = Path(__file__).resolve().parent.parent / "assets" / "icons"
SIZE = 96
STROKE = "1.75"


def render(svg: Path, destino: Path):
    texto = svg.read_text(encoding="utf-8").replace("currentColor", "#000000")
    texto = re.sub(r'stroke-width="[\d.]+"', f'stroke-width="{STROKE}"', texto)
    cairosvg.svg2png(bytestring=texto.encode(), write_to=str(destino),
                     output_width=SIZE, output_height=SIZE)


def main():
    salida = ROOT / "png"
    salida.mkdir(exist_ok=True)
    for svg in sorted((ROOT / "svg").glob("*.svg")):
        render(svg, salida / f"{svg.stem}.png")
        print(svg.stem)


if __name__ == "__main__":
    main()
