#!/usr/bin/env python3
"""
High-quality audio denoising that preserves original sample rate and audio fidelity
"""

import torch
import torchaudio
from denoiser import pretrained
from denoiser.dsp import convert_audio
import subprocess
from pathlib import Path
import argparse


class HighQualityDenoiser:
    def __init__(self, model_name="dns64", preserve_sample_rate=True):
        """
        Initialize high-quality denoiser

        Args:
            model_name: Model to use (dns48, dns64, master64)
            preserve_sample_rate: If True, upsample back to original sample rate
        """
        self.model_name = model_name
        self.preserve_sample_rate = preserve_sample_rate
        self.model = None

    def load_model(self):
        """Load the denoising model"""
        if self.model is not None:
            return

        print(f"Loading {self.model_name} model...")
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
        print(f"✓ Model loaded (operates at {self.model.sample_rate} Hz)")

    def get_audio_info(self, file_path):
        """Get audio file information using ffprobe"""
        cmd = [
            'ffprobe', '-v', 'error',
            '-show_entries', 'stream=sample_rate,bit_rate,codec_name,channels',
            '-of', 'default=noprint_wrappers=1',
            str(file_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)

        info = {}
        for line in result.stdout.strip().split('\n'):
            if '=' in line:
                key, value = line.split('=')
                info[key] = value

        return info

    def convert_to_wav(self, input_file, target_sr=None):
        """Convert audio to WAV with optional target sample rate"""
        input_path = Path(input_file)
        temp_wav = input_path.parent / f"{input_path.stem}_temp_input.wav"

        cmd = ['ffmpeg', '-i', str(input_file)]

        if target_sr:
            cmd.extend(['-ar', str(target_sr)])

        cmd.extend(['-ac', '1', str(temp_wav), '-y'])

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return None

        return str(temp_wav)

    def denoise_file(self, input_file, output_file, output_format=None, high_bitrate=True):
        """
        Denoise audio file with maximum quality preservation

        Args:
            input_file: Input audio file path
            output_file: Output audio file path
            output_format: Output format (m4a, mp3, flac, wav). Auto-detect if None
            high_bitrate: Use high bitrate for encoding
        """
        self.load_model()

        input_path = Path(input_file)
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        print(f"\nProcessing: {input_path.name}")
        print("-" * 60)

        # Get original audio info
        original_info = self.get_audio_info(input_file)
        original_sr = int(original_info.get('sample_rate', 48000))
        original_codec = original_info.get('codec_name', 'unknown')
        original_bitrate = original_info.get('bit_rate', 'unknown')

        print(f"Original specs:")
        print(f"  Sample rate: {original_sr} Hz")
        print(f"  Codec: {original_codec}")
        print(f"  Bitrate: {original_bitrate} bps")

        # Convert to WAV for processing
        original_format = input_path.suffix.lower()
        if original_format != '.wav':
            print(f"\nConverting {original_format} to WAV...")
            wav_file = self.convert_to_wav(input_file)
            if wav_file is None:
                print("✗ Conversion failed")
                return False
            temp_input = wav_file
        else:
            temp_input = str(input_file)
            wav_file = None

        # Load audio
        try:
            wav, sr = torchaudio.load(temp_input)
        except Exception as e:
            print(f"✗ Error loading file: {e}")
            if wav_file:
                Path(wav_file).unlink(missing_ok=True)
            return False

        print(f"\nDenoising with {self.model_name}...")
        print(f"  Processing at: {self.model.sample_rate} Hz")

        # Convert to model format (this will downsample to 16kHz)
        wav_model = convert_audio(wav, sr, self.model.sample_rate, self.model.chin)
        wav_model = wav_model.unsqueeze(0)

        # Denoise
        with torch.no_grad():
            denoised = self.model(wav_model)[0]

        # Upsample back to original sample rate if requested
        if self.preserve_sample_rate and sr != self.model.sample_rate:
            print(f"  Upsampling back to: {original_sr} Hz")
            denoised = torchaudio.transforms.Resample(
                orig_freq=self.model.sample_rate,
                new_freq=original_sr
            )(denoised)

        # Save to temp WAV first
        temp_output_wav = output_path.parent / f"{output_path.stem}_temp_output.wav"
        final_sr = original_sr if self.preserve_sample_rate else self.model.sample_rate
        torchaudio.save(str(temp_output_wav), denoised.cpu(), final_sr)

        # Determine output format
        if output_format is None:
            output_format = output_path.suffix.lower()

        # Convert to final format with high quality settings
        if output_format != '.wav':
            print(f"\nEncoding to {output_format} with high quality...")

            # High-quality encoding settings
            if output_format == '.m4a':
                if high_bitrate:
                    # Use AAC with high bitrate and quality
                    codec_args = [
                        '-c:a', 'aac',
                        '-b:a', '256k',  # High bitrate
                        '-ar', str(original_sr),  # Preserve sample rate
                        '-q:a', '2'  # High quality
                    ]
                else:
                    codec_args = ['-c:a', 'aac', '-b:a', '128k', '-ar', str(original_sr)]

            elif output_format == '.mp3':
                if high_bitrate:
                    codec_args = [
                        '-c:a', 'libmp3lame',
                        '-b:a', '320k',  # Maximum MP3 bitrate
                        '-ar', str(original_sr),
                        '-q:a', '0'  # Highest quality
                    ]
                else:
                    codec_args = ['-c:a', 'libmp3lame', '-b:a', '192k', '-ar', str(original_sr)]

            elif output_format == '.flac':
                # FLAC is lossless
                codec_args = [
                    '-c:a', 'flac',
                    '-ar', str(original_sr),
                    '-compression_level', '8'  # Best compression
                ]
            else:
                codec_args = ['-c:a', 'aac', '-b:a', '256k', '-ar', str(original_sr)]

            cmd = ['ffmpeg', '-i', str(temp_output_wav)] + codec_args + [str(output_path), '-y']
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                print("✓ Encoding successful")
            else:
                print(f"✗ Encoding failed: {result.stderr}")
                return False
        else:
            # Just rename for WAV output
            temp_output_wav.rename(output_path)

        # Cleanup
        if wav_file:
            Path(wav_file).unlink(missing_ok=True)
        if temp_output_wav.exists():
            temp_output_wav.unlink(missing_ok=True)

        # Show final results
        output_info = self.get_audio_info(output_path)
        output_sr = output_info.get('sample_rate', 'unknown')
        output_codec = output_info.get('codec_name', 'unknown')
        output_bitrate = output_info.get('bit_rate', 'unknown')

        input_size = input_path.stat().st_size / (1024 * 1024)
        output_size = output_path.stat().st_size / (1024 * 1024)

        print(f"\n" + "=" * 60)
        print(f"✓ Processing complete!")
        print(f"\nOutput specs:")
        print(f"  Sample rate: {output_sr} Hz")
        print(f"  Codec: {output_codec}")
        print(f"  Bitrate: {output_bitrate} bps")
        print(f"\nFile sizes:")
        print(f"  Input:  {input_size:.2f} MB")
        print(f"  Output: {output_size:.2f} MB")
        print(f"\nSaved to: {output_path}")

        return True


def main():
    parser = argparse.ArgumentParser(
        description="High-quality audio denoising with sample rate preservation"
    )
    parser.add_argument("input", help="Input audio file")
    parser.add_argument("output", help="Output audio file")
    parser.add_argument(
        "--model",
        choices=["dns48", "dns64", "master64"],
        default="dns64",
        help="Model to use (default: dns64)"
    )
    parser.add_argument(
        "--no-upsample",
        action="store_true",
        help="Don't upsample back to original sample rate (keep at 16kHz)"
    )
    parser.add_argument(
        "--low-bitrate",
        action="store_true",
        help="Use lower bitrate for smaller file size"
    )

    args = parser.parse_args()

    denoiser = HighQualityDenoiser(
        model_name=args.model,
        preserve_sample_rate=not args.no_upsample
    )

    denoiser.denoise_file(
        args.input,
        args.output,
        high_bitrate=not args.low_bitrate
    )


if __name__ == "__main__":
    main()
