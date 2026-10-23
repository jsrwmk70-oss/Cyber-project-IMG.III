#!/usr/bin/env python3
"""
stego.py - LSB image steganography tool (Python + Pillow)

Hides a secret text message inside an image by replacing the least
significant bit (LSB) of each R, G and B byte with one bit of the message.
The output MUST be a lossless format (PNG/BMP); JPEG compression destroys
the hidden bits.

Payload layout (all bits written sequentially into the LSBs):
    [ 4 bytes magic "STEG" ][ 4 bytes message length, big-endian ][ message bytes (UTF-8) ]

Usage:
    python stego.py capacity cover.png
    python stego.py encode cover.png stego.png -m "secret message"
    python stego.py encode cover.png stego.png -f secret.txt
    python stego.py decode stego.png
    python stego.py decode stego.png -o recovered.txt
    python stego.py compare cover.png stego.png
"""

import argparse
import sys

from PIL import Image

MAGIC = b"STEG"
HEADER_BYTES = len(MAGIC) + 4  # magic + 4-byte length


# ---------------------------------------------------------------- helpers
def _load_rgb(path):
    img = Image.open(path)
    if img.mode != "RGB":
        img = img.convert("RGB")
    return img


def capacity_bytes(img):
    """Max message size in bytes (3 bits per pixel, minus the header)."""
    total_bits = img.width * img.height * 3
    return max(0, total_bits // 8 - HEADER_BYTES)


def _bytes_to_bits(data):
    for byte in data:
        for i in range(7, -1, -1):
            yield (byte >> i) & 1


def _bits_to_bytes(bits):
    out = bytearray()
    for i in range(0, len(bits) - len(bits) % 8, 8):
        byte = 0
        for b in bits[i:i + 8]:
            byte = (byte << 1) | b
        out.append(byte)
    return bytes(out)


# ----------------------------------------------------------------- encode
def encode(cover_path, output_path, message: bytes):
    if not output_path.lower().endswith((".png", ".bmp")):
        raise ValueError("Output must be .png or .bmp (lossless). JPEG would destroy the message.")

    img = _load_rgb(cover_path)
    cap = capacity_bytes(img)
    if len(message) > cap:
        raise ValueError(
            f"Message too large: {len(message)} bytes, but this image holds at most {cap} bytes."
        )

    payload = MAGIC + len(message).to_bytes(4, "big") + message
    pixels = bytearray(img.tobytes())  # flat R,G,B,R,G,B,...

    for idx, bit in enumerate(_bytes_to_bits(payload)):
        pixels[idx] = (pixels[idx] & 0xFE) | bit  # clear LSB, set to message bit

    Image.frombytes("RGB", img.size, bytes(pixels)).save(output_path)
    return len(message), cap


# ----------------------------------------------------------------- decode
def decode(stego_path) -> bytes:
    img = _load_rgb(stego_path)
    pixels = img.tobytes()

    def read_bytes(start_byte, count):
        bits = [pixels[i] & 1 for i in range(start_byte * 8, (start_byte + count) * 8)]
        return _bits_to_bytes(bits)

    if len(pixels) // 8 < HEADER_BYTES:
        raise ValueError("Image is too small to contain a hidden message.")

    header = read_bytes(0, HEADER_BYTES)
    if header[:4] != MAGIC:
        raise ValueError("No hidden message found (magic marker missing).")

    length = int.from_bytes(header[4:8], "big")
    if (HEADER_BYTES + length) * 8 > len(pixels):
        raise ValueError("Corrupt header: declared length exceeds image capacity.")

    return read_bytes(HEADER_BYTES, length)


# ---------------------------------------------------------------- compare
def compare(cover_path, stego_path):
    a, b = _load_rgb(cover_path), _load_rgb(stego_path)
    if a.size != b.size:
        raise ValueError("Images must have the same dimensions.")
    pa, pb = a.tobytes(), b.tobytes()
    changed = sum(1 for x, y in zip(pa, pb) if x != y)
    max_diff = max(abs(x - y) for x, y in zip(pa, pb))
    mse = sum((x - y) ** 2 for x, y in zip(pa, pb)) / len(pa)
    import math
    psnr = float("inf") if mse == 0 else 10 * math.log10(255 ** 2 / mse)
    return changed, len(pa), max_diff, mse, psnr


# -------------------------------------------------------------------- CLI
def main():
    p = argparse.ArgumentParser(description="LSB image steganography (encode / decode)")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("capacity", help="show how many bytes an image can hide")
    c.add_argument("image")

    e = sub.add_parser("encode", help="hide a message in an image")
    e.add_argument("cover", help="input cover image")
    e.add_argument("output", help="output stego image (.png or .bmp)")
    g = e.add_mutually_exclusive_group(required=True)
    g.add_argument("-m", "--message", help="message text to hide")
    g.add_argument("-f", "--file", help="text file whose contents to hide")

    d = sub.add_parser("decode", help="extract a hidden message from an image")
    d.add_argument("image")
    d.add_argument("-o", "--output", help="write message to this file instead of printing")

    k = sub.add_parser("compare", help="measure how much encoding changed the image")
    k.add_argument("cover")
    k.add_argument("stego")

    args = p.parse_args()

    try:
        if args.cmd == "capacity":
            img = _load_rgb(args.image)
            print(f"{args.image}: {img.width}x{img.height}px -> can hide up to {capacity_bytes(img)} bytes")

        elif args.cmd == "encode":
            if args.message is not None:
                msg = args.message.encode("utf-8")
            else:
                with open(args.file, "rb") as fh:
                    msg = fh.read()
            used, cap = encode(args.cover, args.output, msg)
            print(f"Encoded {used} bytes into {args.output} ({used / cap * 100:.2f}% of {cap}-byte capacity)")

        elif args.cmd == "decode":
            msg = decode(args.image)
            if args.output:
                with open(args.output, "wb") as fh:
                    fh.write(msg)
                print(f"Wrote {len(msg)} bytes to {args.output}")
            else:
                print(msg.decode("utf-8", errors="replace"))

        elif args.cmd == "compare":
            changed, total, max_diff, mse, psnr = compare(args.cover, args.stego)
            print(f"Bytes changed : {changed} / {total} ({changed / total * 100:.2f}%)")
            print(f"Max per-channel difference: {max_diff} (of 255)")
            print(f"MSE: {mse:.5f}   PSNR: {psnr:.2f} dB")

    except (ValueError, FileNotFoundError) as err:
        print(f"Error: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
