# Audio Enhancement Tool

Professional audio enhancement using AI denoising and ffmpeg filters.

## 🚀 Quick Start

```bash
python enhance_all_audios.py
```

## 📋 What It Does

This tool provides professional-grade audio enhancement with a comprehensive processing chain:

1. **AI Denoising** - Facebook Research's DNS64 model for speech enhancement
2. **Click Removal** - Removes clicks and pops using adeclick filter
3. **Reverb Removal** - Removes echo and reverb using anlmdn filter
4. **Noise Gating** - Suppresses quiet noise (breathing, room tone) using agate filter
5. **Speech Normalization** - Creates studio-quality dry voice using speechnorm filter
6. **Volume Normalization** - Consistent loudness using loudnorm filter
7. **Quality Preservation** - Maintains original sample rate and uses high bitrate encoding

## 📊 Results

**Processing Time:** ~2 seconds per file

**Quality:**
- Sample Rate: Preserved (typically 48kHz)
- Bitrate: 256 kbps (M4A) / 320 kbps (MP3)
- Format: Preserved (M4A → M4A, MP3 → MP3, etc.)

**Features Applied:**
- ✅ AI denoising (Facebook DNS64)
- ✅ Click/pop removal (adeclick)
- ✅ Reverb/echo removal (anlmdn)
- ✅ Noise gating (agate)
- ✅ Speech normalization (speechnorm)
- ✅ Volume normalization (loudnorm)
- ✅ High-quality encoding

## 📁 Project Structure

```
sound1/
├── enhance_all_audios.py    # Main script (all-in-one)
├── QUICK_START.md            # Detailed usage guide
├── README.md                 # This file
│
├── original-audios/          # Input folder
│   └── your-audio.m4a
│
└── enhanced-audios/          # Output folder (auto-created)
    └── your-audio.m4a        # Same name, enhanced audio
```

## ⚙️ Options

```bash
# Basic usage (recommended)
python enhance_all_audios.py

# Use different model
python enhance_all_audios.py --model master64

# Lower bitrate (smaller files)
python enhance_all_audios.py --low-bitrate

# Skip cleanup filters (denoising only)
python enhance_all_audios.py --no-loudnorm

# Custom directories
python enhance_all_audios.py --input my-audios --output cleaned

# Add suffix to output files
python enhance_all_audios.py --suffix _enhanced
```

## 🔧 Technical Details

**AI Model:**
- **Facebook DNS64** - Speech Enhancement
  - Processes at 16kHz for speech optimization
  - Trained on DNS Challenge dataset
  - Specialized for speech/voice clarity
  - Upsamples back to original rate

**Audio Filters:**
- `adeclick` - Removes clicks and pops
- `anlmdn` - Removes reverb and echo (Audio Non-Local Means Denoiser)
- `agate` - Gates quiet noise like breathing and room tone
- `speechnorm` - Normalizes speech dynamics for studio-quality dry voice
- `loudnorm` - EBU R128 loudness normalization

**Encoding:**
- M4A: AAC 256 kbps, quality preset 2
- MP3: LAME 320 kbps, quality preset 0
- FLAC: Lossless, compression level 8

## 📖 Documentation

See **QUICK_START.md** for detailed usage examples and troubleshooting.

## 🎯 Use Cases

Perfect for:
- Voice recordings
- Podcasts
- Interviews
- Lectures
- Voice memos
- Any speech audio with background noise

## ⚡ Performance

**System Requirements:**
- Python 3.7+
- ~500MB disk space (for models)
- CPU or GPU (GPU faster but not required)

**Processing Speed:**
- Typical: 2-4 seconds per file (CPU)
- Batch: Automatically processes all files
- Temp cleanup: Automatic

## 📝 Notes

- Original files are never modified
- Output files use same name as input (can add suffix with `--suffix`)
- Already processed files are skipped automatically
- Temporary files stored in `tmp/` and auto-cleaned
- Supports: WAV, MP3, M4A, FLAC, OGG, AAC formats

---

For more details, see **QUICK_START.md**
