# Image Steganography using LSB Encoding (Python + Pillow)
(Text hidden in image)

Hide and extract a secret text message inside an image by modifying the
least significant bit (LSB) of its pixel values.

## Files

| File | Purpose |
|---|---|
| `stego.py` | Encode / decode / capacity / compare command-line tool |
| `make_samples.py` | Generates sample cover images, embeds messages, and runs self-tests |
| `samples/*_cover.png` | Original (clean) images |
| `samples/*_stego.png` | Images with a hidden message |

## Setup

```
pip install pillow
```

## Usage

```
# How much can this image hide?
python stego.py capacity samples/sunset_cover.png

# Hide a message
python stego.py encode samples/sunset_cover.png secret.png -m "Meet at 6 PM"

# Hide the contents of a text file
python stego.py encode samples/sunset_cover.png secret.png -f message.txt

# Extract it
python stego.py decode secret.png
python stego.py decode secret.png -o recovered.txt

# Measure how much the image changed (PSNR / MSE)
python stego.py compare samples/sunset_cover.png secret.png

# Regenerate the sample images and run the self-tests
python make_samples.py
```

Try it on the provided samples: `python stego.py decode samples/sunset_stego.png`

## How it works

Each pixel has three 8-bit channels (R, G, B). Changing the last bit of a
channel alters its value by at most 1 out of 255, which the eye cannot see.
The tool writes the message one bit at a time into these last bits.

```
Pixel channel:   1 0 1 1 0 1 0 [1]   <- LSB replaced by a message bit
```

**Payload layout** (stored sequentially in the LSBs):

```
[ "STEG" magic (4 bytes) ][ message length (4 bytes, big-endian) ][ message (UTF-8) ]
```

- The magic marker lets the decoder detect images with no hidden message.
- The length field tells the decoder where the message ends.
- **Capacity** = `width x height x 3 / 8 - 8` bytes (e.g. 640x480 holds about 115 KB).

## Results (from `make_samples.py`)

| Image | Message size | Max pixel change | PSNR |
|---|---|---|---|
| sunset | 62 B | 1 | 85.3 dB |
| pattern | 88 B | 1 | 82.0 dB |
| shapes | 81 B | 1 | 82.5 dB |

A PSNR above ~40 dB is generally imperceptible; these are far above that.

## Limitations and security notes

- **Lossless output only.** Save as PNG or BMP. JPEG compression (and many
  social-media re-uploads) alters pixel values and destroys the message.
- **Not encrypted.** Anyone who knows the scheme can extract the text. For real
  secrecy, encrypt the message first (e.g. AES) and hide the ciphertext.
- **Detectable statistically.** Sequential LSB embedding can be found by
  steganalysis such as chi-square or RS analysis. Randomizing the embedding
  positions with a key is a standard improvement.
- Alpha channels are dropped; images are converted to RGB.

## Possible extensions

- Password-based AES encryption of the payload
- Pseudo-random pixel selection seeded by a key
- Hiding binary files, not just text
- A simple GUI (Tkinter) front end
