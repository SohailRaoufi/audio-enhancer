# Audio Quality Settings & Configurations

## Summary of Configurations Used

### ❌ Previous Version (Low Quality)
**File:** `47-53 page Dari 22th lesson_enhanced.wav` → converted to M4A

**Issues:**
- ❌ Sample rate: 48,000 Hz → **16,000 Hz** (downsampled!)
- ❌ Bitrate: 64 kbps → 68 kbps
- ❌ Lost high-frequency details (anything above 8 kHz removed)
- ❌ Muffled sound quality

**Why this happened:**
The denoiser model operates at 16kHz internally, and the previous script didn't upsample back to the original sample rate.

---

### ✅ New High-Quality Version (RECOMMENDED)
**File:** `47-53 page Dari 22th lesson_HQ.m4a`

**Settings:**
- ✅ Sample rate: **48,000 Hz** (preserved!)
- ✅ Bitrate: **256 kbps** (4x higher than original)
- ✅ Codec: AAC High Quality
- ✅ Upsampled after denoising to restore frequency range
- ✅ Maximum clarity preserved

**Processing pipeline:**
1. Load original (48 kHz)
2. Denoise at 16 kHz (model requirement)
3. **Upsample back to 48 kHz** ← KEY STEP
4. Encode with high bitrate (256 kbps)

---

## Configuration Details

### Model: DNS64 (Best Quality)
- **Architecture:** Demucs U-Net with 64 hidden channels
- **Processing:** 16 kHz (model limitation)
- **Training:** Deep Noise Suppression (DNS) Challenge dataset
- **Strengths:** Best noise reduction while preserving speech

### Encoding Settings (High Quality)

#### M4A/AAC Format:
```
Sample Rate: 48,000 Hz (original preserved)
Bitrate: 256 kbps (high quality)
Codec: AAC-LC
Quality Setting: 2 (high)
```

#### MP3 Format (if needed):
```
Sample Rate: 48,000 Hz
Bitrate: 320 kbps (maximum)
Codec: LAME MP3
Quality: 0 (highest)
```

#### FLAC Format (lossless):
```
Sample Rate: 48,000 Hz
Codec: FLAC
Compression: Level 8
No quality loss
```

---

## Comparison Chart

| Aspect | Original | Old Script | New High-Quality Script |
|--------|----------|------------|------------------------|
| **Sample Rate** | 48 kHz | ❌ 16 kHz | ✅ 48 kHz |
| **Bitrate** | 64 kbps | 68 kbps | ✅ 256 kbps |
| **Frequency Range** | 0-24 kHz | ❌ 0-8 kHz | ✅ 0-24 kHz |
| **File Size** | 0.21 MB | 0.22 MB | 0.42 MB |
| **Clarity** | Noisy | ❌ Muffled | ✅ Clear |
| **Noise Level** | High | Low | Low |

---

## How to Use

### For Maximum Quality (Recommended):
```bash
python denoise_high_quality.py "input.m4a" "output_HQ.m4a" --model dns64
```

**This will:**
- ✅ Preserve original 48 kHz sample rate
- ✅ Use 256 kbps bitrate
- ✅ Maintain audio clarity
- ✅ Remove noise effectively

### For Smaller File Size (if needed):
```bash
python denoise_high_quality.py "input.m4a" "output.m4a" --model dns64 --low-bitrate
```

**This will:**
- ✅ Preserve original sample rate
- Uses 128 kbps bitrate (smaller file)
- Good balance of quality/size

### For Fastest Processing:
```bash
python denoise_high_quality.py "input.m4a" "output.m4a" --model dns48
```

**This will:**
- Uses dns48 model (faster, slightly lower quality)
- Still preserves sample rate

---

## Technical Explanation

### Why Upsampling is Important

**The denoiser model works at 16 kHz**, which means:
- Frequency range: 0-8 kHz (Nyquist limit)
- Sufficient for basic speech (phone quality)
- **NOT sufficient for high-quality audio**

**Human speech contains frequencies up to 20 kHz:**
- Fundamental frequencies: 85-255 Hz (main voice)
- Harmonics and clarity: 2-8 kHz (intelligibility)
- **Naturalness and presence: 8-20 kHz** ← Lost without upsampling!

**Our solution:**
1. Denoise at 16 kHz (model requirement)
2. Upsample to 48 kHz using high-quality resampling
3. Encode with high bitrate to preserve detail

This gives you:
- ✅ Effective noise removal (from denoiser)
- ✅ Natural sound quality (from upsampling)
- ✅ Maximum clarity (from high bitrate)

---

## Batch Processing

To process multiple files with high quality:

```bash
# Edit batch_denoise.py to use the high-quality settings
# Or process files one by one:

for file in original-audios/*.m4a; do
    filename=$(basename "$file" .m4a)
    python denoise_high_quality.py "$file" "enhanced-audios/${filename}_HQ.m4a"
done
```

---

## Quality Assessment

### How to Check Your Audio Quality:

```bash
# Check sample rate and bitrate:
ffprobe -v error -show_entries stream=sample_rate,bit_rate "your_file.m4a"
```

**What to look for:**
- ✅ Sample rate should match original (usually 44100 or 48000 Hz)
- ✅ Bitrate should be ≥128 kbps for good quality
- ✅ Bitrate ≥256 kbps for excellent quality

### Listen For:
- ✅ **Clarity:** Voice should sound natural, not muffled
- ✅ **Presence:** Audio should feel "full", not thin
- ✅ **Sibilance:** "S" and "T" sounds should be clear
- ✅ **No artifacts:** No underwater or robotic sounds

---

## Recommendations

### For Voice Recordings (like yours):
**Use:** `denoise_high_quality.py` with default settings
- Model: dns64
- Preserve sample rate: Yes (default)
- High bitrate: Yes (default)

### For Music or Complex Audio:
**Use:** FLAC output for lossless quality
```bash
python denoise_high_quality.py "input.m4a" "output.flac" --model master64
```

### For Sharing/Streaming:
**Use:** M4A with high bitrate (default)
- Good compression
- High compatibility
- Excellent quality at 256 kbps

---

## Files Created

1. **denoise_high_quality.py** - Main high-quality script ⭐ RECOMMENDED
2. **denoise_audio_simple.py** - Simple single-file processor
3. **batch_denoise.py** - Batch processing (needs quality updates)
4. **denoise_audios.py** - Original approach

**Use `denoise_high_quality.py` for best results!**
