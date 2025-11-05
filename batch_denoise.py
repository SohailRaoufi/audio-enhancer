#!/usr/bin/env python3
"""
Batch audio denoising script for processing multiple audio files
Supports M4A, WAV, MP3, FLAC, and other common formats
"""

import torch
import torchaudio
from denoiser import pretrained
from denoiser.dsp import convert_audio
import os
import subprocess
from pathlib import Path


class BatchDenoiser:
    def __init__(self, model_name="dns64"):
        """Initialize the denoiser with a specific model"""
        self.model_name = model_name
        self.model = None
        self.supported_formats = ['.wav', '.mp3', '.m4a', '.flac', '.ogg', '.aac']

    def load_model(self):
        """Load the denoising model"""
        if self.model is not None:
            return

        print(f"Loading {self.model_name} model (best quality)...")
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
        print("✓ Model loaded\n")

    def convert_to_wav(self, input_file, sample_rate=16000):
        """Convert any audio format to WAV using ffmpeg"""
        input_path = Path(input_file)

        if input_path.suffix.lower() == '.wav':
            return str(input_file)

        # Create temp WAV file
        temp_wav = input_path.parent / f"{input_path.stem}_temp.wav"

        print(f"  Converting {input_path.suffix} to WAV...")
        cmd = [
            'ffmpeg', '-i', str(input_file),
            '-ar', str(sample_rate),
            '-ac', '1',  # mono
            str(temp_wav),
            '-y'
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  ✗ Conversion failed: {result.stderr}")
            return None

        return str(temp_wav)

    def denoise_file(self, input_file, output_dir, keep_format=True):
        """
        Denoise a single audio file

        Args:
            input_file: Path to input audio file
            output_dir: Directory to save output
            keep_format: If True, convert back to original format
        """
        input_path = Path(input_file)
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        print(f"\nProcessing: {input_path.name}")

        # Convert to WAV if needed
        original_format = input_path.suffix.lower()
        temp_file = None

        if original_format != '.wav':
            wav_file = self.convert_to_wav(input_file)
            if wav_file is None:
                return False
            temp_file = wav_file
        else:
            wav_file = str(input_file)

        # Load audio
        try:
            wav, sr = torchaudio.load(wav_file)
        except Exception as e:
            print(f"  ✗ Error loading file: {e}")
            if temp_file:
                Path(temp_file).unlink(missing_ok=True)
            return False

        # Convert to model format
        wav = convert_audio(wav, sr, self.model.sample_rate, self.model.chin)
        wav = wav.unsqueeze(0)

        # Denoise
        print(f"  Removing noise with {self.model_name} model...")
        with torch.no_grad():
            denoised = self.model(wav)[0]

        # Save enhanced WAV
        output_wav = output_path / f"{input_path.stem}_enhanced.wav"
        torchaudio.save(str(output_wav), denoised.cpu(), self.model.sample_rate)

        # Convert back to original format if requested
        final_output = output_wav
        if keep_format and original_format != '.wav':
            print(f"  Converting back to {original_format}...")
            output_final = output_path / f"{input_path.stem}_enhanced{original_format}"

            # Use appropriate codec and bitrate
            if original_format == '.m4a':
                codec_args = ['-c:a', 'aac', '-b:a', '128k']
            elif original_format == '.mp3':
                codec_args = ['-c:a', 'libmp3lame', '-b:a', '192k']
            elif original_format == '.flac':
                codec_args = ['-c:a', 'flac']
            else:
                codec_args = ['-c:a', 'aac', '-b:a', '128k']

            cmd = ['ffmpeg', '-i', str(output_wav)] + codec_args + [str(output_final), '-y']
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                final_output = output_final
                # Optionally remove WAV if conversion succeeded
                # output_wav.unlink()
            else:
                print(f"  ⚠ Conversion failed, keeping WAV format")

        # Cleanup temp file
        if temp_file:
            Path(temp_file).unlink(missing_ok=True)

        # Show results
        input_size = input_path.stat().st_size / (1024 * 1024)
        output_size = final_output.stat().st_size / (1024 * 1024)

        print(f"  ✓ Complete!")
        print(f"  Input:  {input_size:.2f} MB")
        print(f"  Output: {output_size:.2f} MB ({final_output.name})")

        return True

    def process_directory(self, input_dir, output_dir, keep_format=True):
        """Process all audio files in a directory"""
        self.load_model()

        input_path = Path(input_dir)
        audio_files = []

        # Find all audio files
        for ext in self.supported_formats:
            audio_files.extend(input_path.glob(f"*{ext}"))

        # Filter out temp files
        audio_files = [f for f in audio_files if '_temp' not in f.stem and '_enhanced' not in f.stem]

        if not audio_files:
            print(f"No audio files found in {input_dir}")
            print(f"Supported formats: {', '.join(self.supported_formats)}")
            return

        print(f"Found {len(audio_files)} audio file(s) to process\n")
        print("=" * 60)

        success_count = 0
        for i, audio_file in enumerate(sorted(audio_files), 1):
            print(f"\n[{i}/{len(audio_files)}]", end=" ")
            if self.denoise_file(audio_file, output_dir, keep_format):
                success_count += 1

        print("\n" + "=" * 60)
        print(f"\n✓ Processing complete!")
        print(f"  Successfully processed: {success_count}/{len(audio_files)} files")
        print(f"  Output directory: {output_dir}")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Batch denoise audio files using Facebook Research's Denoiser"
    )
    parser.add_argument(
        "--input-dir",
        default="original-audios",
        help="Input directory containing audio files (default: original-audios)"
    )
    parser.add_argument(
        "--output-dir",
        default="enhanced-audios",
        help="Output directory for enhanced audio (default: enhanced-audios)"
    )
    parser.add_argument(
        "--model",
        choices=["dns48", "dns64", "master64"],
        default="dns64",
        help="Model to use - dns64/master64 for best quality (default: dns64)"
    )
    parser.add_argument(
        "--wav-only",
        action="store_true",
        help="Output WAV format only (don't convert back to original format)"
    )

    args = parser.parse_args()

    denoiser = BatchDenoiser(model_name=args.model)
    denoiser.process_directory(
        args.input_dir,
        args.output_dir,
        keep_format=not args.wav_only
    )


if __name__ == "__main__":
    main()
