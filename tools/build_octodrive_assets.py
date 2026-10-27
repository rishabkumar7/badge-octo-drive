#!/usr/bin/env python3
"""Generate the Octo Drive badge-menu icon."""

from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "octo_drive" / "icon.png"


def main():
    image = Image.new("RGBA", (24, 24), (76, 156, 224, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 11, 23, 23), fill=(42, 142, 82, 255))
    draw.polygon(((9, 10), (15, 10), (21, 23), (3, 23)), fill=(64, 68, 78, 255))
    draw.polygon(((8, 10), (10, 10), (7, 23), (3, 23)), fill=(255, 255, 255, 255))
    draw.polygon(((14, 10), (16, 10), (21, 23), (17, 23)), fill=(235, 72, 78, 255))
    draw.rectangle((9, 15, 15, 21), fill=(242, 242, 248, 255))
    draw.rectangle((10, 13, 14, 17), fill=(242, 242, 248, 255))
    draw.rectangle((11, 14, 13, 15), fill=(76, 156, 224, 255))
    draw.rectangle((9, 19, 15, 20), fill=(235, 72, 78, 255))
    draw.rectangle((9, 21, 10, 23), fill=(20, 20, 28, 255))
    draw.rectangle((14, 21, 15, 23), fill=(20, 20, 28, 255))
    image.save(TARGET)
    print("wrote", TARGET)


if __name__ == "__main__":
    main()

