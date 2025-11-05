#!/usr/bin/env python3
"""
Audio Denoising Script using Facebook Research's Denoiser
Processes audio files with maximum quality settings
"""

import os
import subprocess
import sys
from pathlib import Path


class AudioDenoiser:
    def __init__(self, input_dir="original-audios", output_dir="enhanced-audios"):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.supported_formats = ['.wav', '.mp3', '.m4a', '.flac', '.ogg', '.aac']

    def check_denoiser_installed(self):
        """Check if denoiser package is installed"""
        try:
            subprocess.run(
                [sys.executable, "-m", "denoiser", "--help"],
                capture_output=True,
                check=True
            )
            print("✓ Denoiser package is installed")
            return True
        except subprocess.CalledProcessError:
            print("✗ Denoiser package not found")
            return False

    def install_denoiser(self):
        """Install denoiser package"""
        print("Installing denoiser package...")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "denoiser"],
                check=True
            )
            print("✓ Denoiser installed successfully")
            return True
        except subprocess.CalledProcessError as e:
            print(f"✗ Failed to install denoiser: {e}")
            return False

    def get_audio_files(self):
        """Get list of audio files from input directory"""
        if not self.input_dir.exists():
            print(f"✗ Input directory '{self.input_dir}' does not exist")
            return []

        audio_files = []
        for ext in self.supported_formats:
            audio_files.extend(self.input_dir.glob(f"*{ext}"))

        return sorted(audio_files)

    def process_audio(self, model="dns64", dry_run=False):
        """
        Process audio files with denoiser

        Args:
            model: Pre-trained model to use (dns48, dns64, master64)
                   dns64 and master64 provide best quality
            dry_run: If True, show what would be processed without actually processing
        """
        # Check installation
        if not self.check_denoiser_installed():
            if not self.install_denoiser():
                print("Failed to install denoiser. Please install manually:")
                print("  pip install denoiser")
                return

        # Get audio files
        audio_files = self.get_audio_files()

        if not audio_files:
            print(f"✗ No audio files found in '{self.input_dir}'")
            print(f"  Supported formats: {', '.join(self.supported_formats)}")
            return

        print(f"\nFound {len(audio_files)} audio file(s):")
        for i, audio_file in enumerate(audio_files, 1):
            size_mb = audio_file.stat().st_size / (1024 * 1024)
            print(f"  {i}. {audio_file.name} ({size_mb:.2f} MB)")

        if dry_run:
            print("\n[DRY RUN] Would process these files")
            return

        # Create output directory
        self.output_dir.mkdir(exist_ok=True)
        print(f"\n✓ Output directory: {self.output_dir}")

        # Process with denoiser
        print(f"\nProcessing with model: {model} (best quality)")
        print("This may take a while depending on file size...\n")

        cmd = [
            sys.executable, "-m", "denoiser.enhance",
            f"--{model}",  # Use best quality model
            "--noisy_dir", str(self.input_dir),
            "--out_dir", str(self.output_dir),
        ]

        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=False,  # Show output in real-time
                text=True
            )

            print("\n✓ Processing complete!")
            print(f"✓ Enhanced audio files saved to: {self.output_dir}")

            # List output files
            output_files = list(self.output_dir.glob("*"))
            if output_files:
                print(f"\nEnhanced files:")
                for output_file in sorted(output_files):
                    size_mb = output_file.stat().st_size / (1024 * 1024)
                    print(f"  - {output_file.name} ({size_mb:.2f} MB)")

        except subprocess.CalledProcessError as e:
            print(f"\n✗ Error processing audio files: {e}")
            print("\nTroubleshooting:")
            print("  - Ensure audio files are in supported formats")
            print("  - For GPU acceleration, install: pip install torch torchaudio")
            print("  - Check denoiser logs above for specific errors")

    def compare_sizes(self):
        """Compare file sizes before and after processing"""
        if not self.output_dir.exists():
            print("No enhanced files found yet. Run process_audio() first.")
            return

        print("\nFile Size Comparison:")
        print(f"{'Original':<40} {'Enhanced':<40} {'Change'}")
        print("-" * 90)

        for input_file in self.get_audio_files():
            # Look for corresponding output file
            output_candidates = list(self.output_dir.glob(f"{input_file.stem}*"))
            if output_candidates:
                output_file = output_candidates[0]
                input_size = input_file.stat().st_size / (1024 * 1024)
                output_size = output_file.stat().st_size / (1024 * 1024)
                change = ((output_size - input_size) / input_size) * 100

                print(f"{input_file.name:<40} {output_file.name:<40} {change:+.1f}%")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Denoise audio files using Facebook Research's Denoiser"
    )
    parser.add_argument(
        "--input-dir",
        default="original-audios",
        help="Input directory containing audio files (default: original-audios)"
    )
    parser.add_argument(
        "--output-dir",
        default="enhanced-audios",
        help="Output directory for enhanced audio files (default: enhanced-audios)"
    )
    parser.add_argument(
        "--model",
        choices=["dns48", "dns64", "master64"],
        default="dns64",
        help="Pre-trained model to use. dns64/master64 offer best quality (default: dns64)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be processed without actually processing"
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Compare file sizes after processing"
    )

    args = parser.parse_args()

    denoiser = AudioDenoiser(
        input_dir=args.input_dir,
        output_dir=args.output_dir
    )

    if args.compare:
        denoiser.compare_sizes()
    else:
        denoiser.process_audio(model=args.model, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
