#!/usr/bin/env python3
"""
All-in-One Audio Enhancement Script
Automatically processes all audio files in a directory with maximum quality settings
Uses temporary folder for intermediate conversions
"""

import torch
import torchaudio
from denoiser import pretrained
from denoiser.dsp import convert_audio
import subprocess
from pathlib import Path
import argparse
import shutil
import time
from datetime import datetime
import sys


class AudioEnhancer:
    def __init__(self, model_name="dns64", temp_dir="tmp"):
        """
        Initialize audio enhancer

        Args:
            model_name: Model to use (dns48, dns64, master64)
            temp_dir: Temporary directory for intermediate files
        """
        self.model_name = model_name
        self.temp_dir = Path(temp_dir)
        self.model = None
        self.supported_formats = ['.wav', '.mp3', '.m4a', '.flac', '.ogg', '.aac', '.mp4']

    def setup_temp_dir(self):
        """Create temp directory if it doesn't exist"""
        self.temp_dir.mkdir(exist_ok=True)
        print(f"✓ Using temp directory: {self.temp_dir}")

    def cleanup_temp_dir(self, keep_dir=False):
        """Clean up temporary files"""
        if self.temp_dir.exists():
            for file in self.temp_dir.glob("*"):
                try:
                    file.unlink()
                except Exception as e:
                    print(f"Warning: Could not delete {file}: {e}")

            if not keep_dir:
                try:
                    self.temp_dir.rmdir()
                except:
                    pass

    def load_model(self):
        """Load the denoising model"""
        if self.model is not None:
            return

        print(f"\nLoading {self.model_name} model...")
        if self.model_name == "dns48":
            self.model = pretrained.dns48()
        elif self.model_name == "dns64":
            self.model = pretrained.dns64()
        elif self.model_name == "master64":
            self.model = pretrained.master64()
        else:
            raise ValueError(f"Unknown model: {self.model_name}")

        self.model = self.model.cpu()
        self.model.eval()
        print(f"✓ Model loaded successfully (processes at {self.model.sample_rate} Hz)")

    def get_audio_info(self, file_path):
        """Get audio file information using ffprobe"""
        cmd = [
            'ffprobe', '-v', 'error',
            '-show_entries', 'stream=sample_rate,bit_rate,codec_name,channels,duration',
            '-of', 'default=noprint_wrappers=1',
            str(file_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)

        info = {}
        for line in result.stdout.strip().split('\n'):
            if '=' in line:
                key, value = line.split('=', 1)
                info[key] = value

        return info

    def convert_to_wav(self, input_file, output_wav=None):
        """Convert any audio format to WAV in temp directory"""
        input_path = Path(input_file)

        if output_wav is None:
            output_wav = self.temp_dir / f"{input_path.stem}_input.wav"

        # If already WAV, just copy to temp
        if input_path.suffix.lower() == '.wav':
            shutil.copy2(input_file, output_wav)
            return str(output_wav)

        cmd = [
            'ffmpeg', '-v', 'error', '-i', str(input_file),
            '-ar', '48000',  # High sample rate
            '-ac', '1',  # Mono
            str(output_wav),
            '-y'
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"    ✗ Conversion error: {result.stderr}")
            return None

        return str(output_wav)

    def enhance_audio(self, input_file, output_file, high_bitrate=True, apply_loudnorm=True):
        """
        Enhance a single audio file with maximum quality

        Args:
            input_file: Input audio file path
            output_file: Output audio file path
            high_bitrate: Use high bitrate encoding (256 kbps for M4A, 320 kbps for MP3)
            apply_loudnorm: Apply loudness normalization as final step

        Returns:
            True if successful, False otherwise
        """
        input_path = Path(input_file)
        output_path = Path(output_file)

        if not input_path.exists():
            print(f"    ✗ File not found: {input_file}")
            return False

        try:
            # Get original audio specs
            original_info = self.get_audio_info(input_file)
            original_sr = int(original_info.get('sample_rate', 48000))
            original_format = input_path.suffix.lower()

            print(f"    Original: {original_sr} Hz, {original_info.get('codec_name', 'unknown')}")

            # Convert to WAV in temp directory
            print(f"    Converting to WAV...")
            temp_input_wav = self.convert_to_wav(input_file)
            if temp_input_wav is None:
                return False

            # Load audio
            wav, sr = torchaudio.load(temp_input_wav)

            # AI denoising
            print(f"    AI denoising with {self.model_name}...")
            wav_model = convert_audio(wav, sr, self.model.sample_rate, self.model.chin)
            wav_model = wav_model.unsqueeze(0)

            # Denoise
            with torch.no_grad():
                denoised = self.model(wav_model)[0]

            # Upsample back to original sample rate
            print(f"    Upsampling to {original_sr} Hz...")
            denoised = torchaudio.transforms.Resample(
                orig_freq=self.model.sample_rate,
                new_freq=original_sr
            )(denoised)

            # Save to temp WAV
            temp_output_wav = self.temp_dir / f"{output_path.stem}_output.wav"
            torchaudio.save(str(temp_output_wav), denoised.cpu(), original_sr)

            # Apply audio filters: professional audio cleanup chain
            if apply_loudnorm:
                print(f"    Applying professional audio cleanup...")
                print(f"      • adeclick: Removing clicks and pops")
                print(f"      • anlmdn: Removing reverb and echo")
                print(f"      • agate: Gating quiet noise (breathing, room tone)")
                print(f"      • speechnorm: Normalizing speech dynamics")
                print(f"      • loudnorm: Final loudness normalization")
                temp_normalized_wav = self.temp_dir / f"{output_path.stem}_normalized.wav"

                # Apply full professional audio cleanup chain
                # Order: adeclick → anlmdn → agate → speechnorm → loudnorm
                cmd = [
                    'ffmpeg', '-v', 'error', '-i', str(temp_output_wav),
                    '-af', 'adeclick,anlmdn,agate,speechnorm,loudnorm',
                    str(temp_normalized_wav),
                    '-y'
                ]

                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    # Use normalized version
                    temp_output_wav = temp_normalized_wav
                else:
                    print(f"    ⚠ Audio cleanup failed: {result.stderr}")
                    print(f"    ⚠ Using basic denoised audio")

            # Determine output format
            output_format = output_path.suffix.lower()
            if output_format == '':
                output_format = original_format
                output_path = output_path.with_suffix(original_format)

            # Convert to final format with high quality
            print(f"    Encoding to {output_format}...")

            if output_format == '.m4a':
                bitrate = '256k' if high_bitrate else '128k'
                codec_args = [
                    '-c:a', 'aac',
                    '-b:a', bitrate,
                    '-ar', str(original_sr),
                    '-q:a', '2'
                ]
            elif output_format == '.mp3':
                bitrate = '320k' if high_bitrate else '192k'
                codec_args = [
                    '-c:a', 'libmp3lame',
                    '-b:a', bitrate,
                    '-ar', str(original_sr),
                    '-q:a', '0'
                ]
            elif output_format == '.flac':
                codec_args = [
                    '-c:a', 'flac',
                    '-ar', str(original_sr),
                    '-compression_level', '8'
                ]
            elif output_format == '.wav':
                # Just move the temp file
                shutil.move(str(temp_output_wav), str(output_path))

                # Show results
                input_size = input_path.stat().st_size / (1024 * 1024)
                output_size = output_path.stat().st_size / (1024 * 1024)
                print(f"    ✓ Complete! {input_size:.2f} MB → {output_size:.2f} MB")
                return True
            else:
                # Default to AAC
                bitrate = '256k' if high_bitrate else '128k'
                codec_args = ['-c:a', 'aac', '-b:a', bitrate, '-ar', str(original_sr)]

            # Encode final output
            cmd = [
                'ffmpeg', '-v', 'error', '-i', str(temp_output_wav)
            ] + codec_args + [str(output_path), '-y']

            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"    ✗ Encoding error: {result.stderr}")
                return False

            # Show results
            input_size = input_path.stat().st_size / (1024 * 1024)
            output_size = output_path.stat().st_size / (1024 * 1024)

            output_info = self.get_audio_info(output_path)
            output_bitrate = int(output_info.get('bit_rate', 0)) // 1000

            print(f"    ✓ Complete! {input_size:.2f} MB → {output_size:.2f} MB ({output_bitrate} kbps)")

            return True

        except Exception as e:
            print(f"    ✗ Error: {e}")
            import traceback
            traceback.print_exc()
            return False

    def find_audio_files(self, input_dir, recursive=False):
        """Find all audio files in directory"""
        input_path = Path(input_dir)
        audio_files = []

        if recursive:
            for ext in self.supported_formats:
                audio_files.extend(input_path.rglob(f"*{ext}"))
        else:
            for ext in self.supported_formats:
                audio_files.extend(input_path.glob(f"*{ext}"))

        # Filter out already enhanced files and temp files
        audio_files = [
            f for f in audio_files
            if '_enhanced' not in f.stem.lower()
            and '_hq' not in f.stem.lower()
            and 'temp' not in f.stem.lower()
            and f.parent.name != 'tmp'
            and f.parent.name != 'enhanced-audios'
        ]

        return sorted(audio_files)

    def process_all(self, input_dir, output_dir, high_bitrate=True, suffix="", apply_loudnorm=True):
        """
        Process all audio files in directory

        Args:
            input_dir: Input directory path
            output_dir: Output directory path
            high_bitrate: Use high bitrate encoding
            suffix: Suffix to add to output filenames (empty = keep original name)
            apply_loudnorm: Apply loudness normalization
        """
        print("=" * 70)
        print("  🎵 Audio Enhancement Script - Professional Quality")
        print("=" * 70)

        # Setup
        self.setup_temp_dir()
        self.load_model()

        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        print(f"✓ Output directory: {output_path}\n")

        # Find audio files
        print(f"Scanning for audio files in: {input_dir}")
        audio_files = self.find_audio_files(input_dir)

        if not audio_files:
            print(f"\n✗ No audio files found!")
            print(f"  Supported formats: {', '.join(self.supported_formats)}")
            self.cleanup_temp_dir()
            return

        print(f"✓ Found {len(audio_files)} audio file(s)\n")

        # Process each file
        results = {
            'success': [],
            'failed': []
        }

        start_time = time.time()

        for i, audio_file in enumerate(audio_files, 1):
            print(f"\n[{i}/{len(audio_files)}] {audio_file.name}")
            print("-" * 70)

            # Determine output filename
            output_filename = f"{audio_file.stem}{suffix}{audio_file.suffix}"
            output_file = output_path / output_filename

            # Skip if already exists
            if output_file.exists():
                print(f"    ⚠ Already exists, skipping...")
                results['failed'].append((audio_file.name, "Already exists"))
                continue

            # Process
            success = self.enhance_audio(audio_file, output_file, high_bitrate, apply_loudnorm)

            if success:
                results['success'].append(audio_file.name)
            else:
                results['failed'].append((audio_file.name, "Processing error"))

        # Cleanup
        print("\n" + "=" * 70)
        print("Cleaning up temporary files...")
        self.cleanup_temp_dir()

        # Show summary
        elapsed_time = time.time() - start_time
        print("\n" + "=" * 70)
        print("  📊 PROCESSING SUMMARY")
        print("=" * 70)
        print(f"Total files processed: {len(audio_files)}")
        print(f"✓ Successful: {len(results['success'])}")
        print(f"✗ Failed: {len(results['failed'])}")
        print(f"⏱ Total time: {elapsed_time:.1f} seconds")

        if results['success']:
            print(f"\n✅ Enhanced audio saved to: {output_path}")
            print(f"\nSuccessfully enhanced files:")
            for filename in results['success']:
                print(f"  ✓ {filename}")

        if results['failed']:
            print(f"\n❌ Failed files:")
            for filename, reason in results['failed']:
                print(f"  ✗ {filename} - {reason}")

        print("\n" + "=" * 70)
        print(f"Settings used:")
        print(f"  AI Model: {self.model_name}")
        print(f"  Sample rate: Preserved from original")
        print(f"  Bitrate: {'256 kbps (M4A) / 320 kbps (MP3)' if high_bitrate else '128 kbps (M4A) / 192 kbps (MP3)'}")
        print(f"  Audio filters: {'adeclick + anlmdn + agate + speechnorm + loudnorm' if apply_loudnorm else 'None'}")
        print(f"  Filename suffix: '{suffix}' {'(original name)' if suffix == '' else ''}")
        print("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Enhance all audio files in a directory with maximum quality",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process all audio files in original-audios folder
  python enhance_all_audios.py

  # Use master64 model for best quality
  python enhance_all_audios.py --model master64

  # Use lower bitrate for smaller files
  python enhance_all_audios.py --low-bitrate

  # Custom directories
  python enhance_all_audios.py --input my-audios --output cleaned-audios

  # Custom suffix for output files
  python enhance_all_audios.py --suffix _enhanced

  # Skip audio cleanup filters (adeclick, loudnorm)
  python enhance_all_audios.py --no-loudnorm
        """
    )

    parser.add_argument(
        '--input',
        default='original-audios',
        help='Input directory containing audio files (default: original-audios)'
    )

    parser.add_argument(
        '--output',
        default='enhanced-audios',
        help='Output directory for enhanced audio (default: enhanced-audios)'
    )

    parser.add_argument(
        '--model',
        choices=['dns48', 'dns64', 'master64'],
        default='dns64',
        help='Model to use - dns64/master64 for best quality (default: dns64)'
    )

    parser.add_argument(
        '--temp-dir',
        default='tmp',
        help='Temporary directory for intermediate files (default: tmp)'
    )

    parser.add_argument(
        '--low-bitrate',
        action='store_true',
        help='Use lower bitrate (128k M4A / 192k MP3) for smaller files'
    )

    parser.add_argument(
        '--suffix',
        default='',
        help='Suffix to add to output filenames (default: none, keeps original name)'
    )

    parser.add_argument(
        '--recursive',
        action='store_true',
        help='Process subdirectories recursively'
    )

    parser.add_argument(
        '--no-loudnorm',
        action='store_true',
        help='Skip audio cleanup filters (adeclick and loudnorm)'
    )

    args = parser.parse_args()

    # Create enhancer
    enhancer = AudioEnhancer(
        model_name=args.model,
        temp_dir=args.temp_dir
    )

    # Process all files
    enhancer.process_all(
        input_dir=args.input,
        output_dir=args.output,
        high_bitrate=not args.low_bitrate,
        suffix=args.suffix,
        apply_loudnorm=not args.no_loudnorm
    )


if __name__ == "__main__":
    main()
