# Quick Start Guide - Audio Enhancement

## 🚀 One-Command Solution

```bash
python enhance_all_audios.py
```

That's it! This single command will:
- ✅ Find all audio files in `original-audios/`
- ✅ Enhance them with maximum quality (dns64 model)
- ✅ Preserve original sample rate (48kHz)
- ✅ Use high bitrate encoding (256 kbps)
- ✅ Apply loudness normalization (consistent volume)
- ✅ Save to `enhanced-audios/` with **original filename** (no suffix)
- ✅ Use `tmp/` folder for conversions (auto-cleaned)
- ✅ Skip already processed files

---

## 📁 File Structure

```
sound1/
├── original-audios/          # Put your audio files here
│   ├── audio1.m4a
│   ├── audio2.mp3
│   └── audio3.wav
│
├── enhanced-audios/          # Enhanced files go here (auto-created)
│   ├── audio1.m4a           # Same name, same format
│   ├── audio2.mp3
│   └── audio3.wav
│
├── tmp/                      # Temporary files (auto-cleaned)
│
└── enhance_all_audios.py     # Main script
```

---

## ⚙️ Common Options

### Use Different Model
```bash
# dns48 - Faster processing, good quality
python enhance_all_audios.py --model dns48

# dns64 - Best quality (default, recommended)
python enhance_all_audios.py --model dns64

# master64 - Alternative best quality
python enhance_all_audios.py --model master64
```

### Custom Directories
```bash
python enhance_all_audios.py --input my-audios --output cleaned-audios
```

### Lower Bitrate (Smaller Files)
```bash
# Use 128 kbps instead of 256 kbps
python enhance_all_audios.py --low-bitrate
```

### Custom Output Suffix
```bash
# Add suffix to output files: "audio_enhanced.m4a"
python enhance_all_audios.py --suffix _enhanced

# Keep original name (default)
python enhance_all_audios.py
```

### Skip Loudness Normalization
```bash
# Don't apply loudness normalization (if you want to do it manually)
python enhance_all_audios.py --no-loudnorm
```

### Process Subdirectories
```bash
# Process all audio in subdirectories too
python enhance_all_audios.py --recursive
```

---

## 📊 What You Get

### Quality Settings (Default - Recommended)

**For M4A files:**
- Sample Rate: **48,000 Hz** (preserved from original)
- Bitrate: **256 kbps** (high quality)
- Codec: AAC with quality preset

**For MP3 files:**
- Sample Rate: **48,000 Hz** (preserved)
- Bitrate: **320 kbps** (maximum)
- Codec: LAME MP3, highest quality

**For FLAC files:**
- Sample Rate: Preserved
- Lossless compression
- Maximum quality

### Processing Steps (Automatic)

1. **Load original audio** → Detect format and sample rate
2. **Convert to WAV** → Store in `tmp/` folder
3. **Denoise at 16kHz** → AI model removes noise
4. **Upsample to original rate** → Restore full frequency range
5. **Apply loudness normalization** → Consistent volume using ffmpeg loudnorm
6. **Encode with high quality** → Create final output
7. **Clean up temp files** → Remove `tmp/` files

---

## 🎯 Latest Test Results

Successfully processed **2 files** in **3.6 seconds**:

| File | Original | Enhanced | Quality | Features |
|------|----------|----------|---------|----------|
| 47-53 page Dari 22th lesson.m4a | 0.21 MB | 0.52 MB | 48kHz, 168kbps | ✅ Denoised + Loudnorm |
| New Recording 602.m4a | 0.06 MB | 0.14 MB | 48kHz, 172kbps | ✅ Denoised + Loudnorm |

All files:
- ✅ Noise removed
- ✅ Quality preserved
- ✅ Sample rate maintained (48kHz)
- ✅ Volume normalized
- ✅ Original filename kept

---

## 🔍 Verify Quality

Check your enhanced audio specs:
```bash
ffprobe -v error -show_entries stream=sample_rate,bit_rate "enhanced-audios/your_file_HQ.m4a"
```

You should see:
- ✅ `sample_rate=48000` (or your original rate)
- ✅ `bit_rate=256000` (256 kbps) or higher

---

## 💡 Tips

1. **First time?** Just run `python enhance_all_audios.py` with defaults
2. **Need smaller files?** Add `--low-bitrate` flag
3. **Processing many files?** The script auto-skips files already in output directory
4. **Want to re-process?** Delete files from `enhanced-audios/` or use different `--suffix`
5. **Temp folder full?** Script auto-cleans after each file
6. **Volume too loud/quiet?** Loudness normalization is enabled by default (use `--no-loudnorm` to disable)

---

## 🆘 Troubleshooting

### Script runs but no files processed
- Check that audio files are in `original-audios/` folder
- Make sure files don't already exist in `enhanced-audios/` folder (script skips existing files)
- Files from `enhanced-audios/` folder are automatically excluded from processing

### Quality doesn't sound good
- Check sample rate with `ffprobe` (should match original)
- Try `--model master64` for alternative processing
- Don't use `--low-bitrate` for best quality

### Temp folder not cleaned
- Script auto-cleans after completion
- Manually remove with `rm -rf tmp/`

### Out of memory
- Use `--model dns48` (smaller model)
- Process files one at a time

---

## 📚 All Available Scripts

1. **enhance_all_audios.py** ⭐ **USE THIS ONE**
   - All-in-one batch processor
   - Automatic temp cleanup
   - Maximum quality by default

2. **denoise_high_quality.py**
   - Single file processing
   - Manual quality control
   - Use for special cases

3. **QUALITY_SETTINGS.md**
   - Technical documentation
   - Configuration details
   - Quality comparison

---

## ✅ Summary

**To enhance all your audio files with maximum quality:**

```bash
python enhance_all_audios.py
```

**Your files will be:**
- Noise-free (background noise removed)
- Clear (speech enhanced)
- High quality (original sample rate + high bitrate)
- Same format (M4A → M4A, MP3 → MP3, etc.)

**Output location:** `enhanced-audios/filename.m4a` (same name as original)

Done! 🎵

## 📝 What's New

### Latest Updates:
1. ✅ **Original Filename** - No more `_HQ` suffix (keeps original name)
2. ✅ **Loudness Normalization** - Consistent volume using ffmpeg loudnorm filter
3. ✅ **Better Quality** - Enhanced audio is now normalized for professional sound
4. ✅ **Cleaner Output** - Files have same name, just cleaner audio

### Processing Pipeline:
```
Original Audio (noisy, varying volume)
    ↓
Denoise with AI (remove background noise)
    ↓
Upsample to original rate (preserve quality)
    ↓
Loudness Normalization (consistent volume)
    ↓
High-quality encoding (256 kbps)
    ↓
Enhanced Audio (clean, normalized, high quality)
```
