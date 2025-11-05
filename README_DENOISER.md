# Audio Denoising with Facebook Research's Denoiser

This project provides scripts to process audio files and remove noise using Facebook Research's state-of-the-art deep learning denoiser.

## Features

- Automatic model download and setup
- Supports multiple audio formats (WAV, MP3, M4A, FLAC, OGG, AAC)
- Uses best quality models (dns64/master64 with 64 hidden units)
- Batch processing of entire directories
- Automatic format conversion (preserves original format)
- High-quality noise reduction while preserving speech

## Quick Start

### 1. Install Dependencies

The denoiser package is already installed. If you need to reinstall:

```bash
pip install denoiser torch torchaudio
```

### 2. Process Audio Files

**Recommended: Batch Processing Script**

```bash
# Process all audio files in original-audios folder
python batch_denoise.py

# Use master64 model for alternative best quality
python batch_denoise.py --model master64

# Use dns48 model for faster processing
python batch_denoise.py --model dns48

# Output WAV only (don't convert back to original format)
python batch_denoise.py --wav-only

# Custom directories
python batch_denoise.py --input-dir /path/to/input --output-dir /path/to/output
```

**Single File Processing**

```bash
# Process a single file
python denoise_audio_simple.py "input.m4a" "output_enhanced.m4a" --model dns64
```

## Available Scripts

1. **batch_denoise.py** (Recommended)
   - Batch processes entire directories
   - Auto-converts between formats
   - Preserves original format

2. **denoise_audio_simple.py**
   - Single file processing
   - Direct WAV processing

3. **denoise_audios.py** (Original)
   - Alternative batch processing approach

## Model Comparison

| Model | Quality | Speed | Hidden Size | Best For |
|-------|---------|-------|-------------|----------|
| dns48 | Good | Fast | 48 | Quick processing |
| dns64 | **Best** | Moderate | 64 | **Best quality (recommended)** |
| master64 | **Best** | Moderate | 64 | Alternative best quality |

## Current Results

Your audio has been successfully processed:

**Input:** `original-audios/47-53 page Dari 22th lesson.m4a` (0.21 MB)
**Output:** `enhanced-audios/47-53 page Dari 22th lesson_enhanced.m4a` (0.22 MB)

The enhanced audio has significantly reduced background noise while preserving speech quality.

## Requirements

- Python 3.7+
- Internet connection (for initial model download)
- ~500MB disk space for models

## Troubleshooting

### "Denoiser not found" error
```bash
pip install --upgrade denoiser
```

### Slow processing
```bash
# Install GPU support (if you have NVIDIA GPU)
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu118
```

### Audio format not supported
Convert your audio to WAV first:
```bash
ffmpeg -i input.mp4 output.wav
```

## Advanced Options

```bash
# Show all options
python denoise_audios.py --help
```

## How It Works

The script uses Facebook Research's Denoiser, a real-time speech enhancement model trained on the DNS Challenge dataset. It removes background noise, echo, and other artifacts while preserving speech quality.

The model uses a U-Net architecture with skip connections and operates in the time-frequency domain for optimal noise reduction.

## References

- [Denoiser GitHub](https://github.com/facebookresearch/denoiser)
- [Research Paper](https://arxiv.org/abs/2006.12847)
