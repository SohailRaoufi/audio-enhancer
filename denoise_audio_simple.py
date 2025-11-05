#!/usr/bin/env python3
"""
Simple audio denoising script that works around torchaudio compatibility issues
"""

import torch
import torchaudio
from denoiser import pretrained
from denoiser.dsp import convert_audio
import os
from pathlib import Path


def denoise_audio(input_file, output_file, model_name="dns64"):
    """
    Denoise an audio file using Facebook's denoiser

    Args:
        input_file: Path to input audio file
        output_file: Path to output audio file
        model_name: Model to use (dns48, dns64, master64)
    """
    print(f"Loading {model_name} model...")

    # Load the pre-trained model based on model name
    if model_name == "dns48":
        model = pretrained.dns48()
    elif model_name == "dns64":
        model = pretrained.dns64()
    elif model_name == "master64":
        model = pretrained.master64()
    else:
        raise ValueError(f"Unknown model: {model_name}")

    model = model.cpu()
    model.eval()

    print(f"Loading audio: {input_file}")
    # Load audio file
    try:
        wav, sr = torchaudio.load(str(input_file))
    except Exception as e:
        print(f"Error loading file: {e}")
        return False

    print(f"Original audio: {wav.shape}, Sample rate: {sr} Hz")

    # Convert to model's expected format (16kHz mono)
    wav = convert_audio(wav, sr, model.sample_rate, model.chin)
    print(f"Converted audio: {wav.shape}, Sample rate: {model.sample_rate} Hz")

    # Add batch dimension
    wav = wav.unsqueeze(0)

    print("Processing audio (removing noise)...")
    with torch.no_grad():
        denoised = model(wav)[0]

    # Create output directory if it doesn't exist
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Saving enhanced audio: {output_file}")
    torchaudio.save(str(output_file), denoised.cpu(), model.sample_rate)

    print("✓ Audio denoising complete!")

    # Show file sizes
    input_size = os.path.getsize(input_file) / (1024 * 1024)
    output_size = os.path.getsize(output_file) / (1024 * 1024)
    print(f"\nFile sizes:")
    print(f"  Input:  {input_size:.2f} MB")
    print(f"  Output: {output_size:.2f} MB")

    return True


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Denoise audio files")
    parser.add_argument("input", help="Input audio file")
    parser.add_argument("output", help="Output audio file")
    parser.add_argument(
        "--model",
        choices=["dns48", "dns64", "master64"],
        default="dns64",
        help="Model to use (default: dns64)"
    )

    args = parser.parse_args()

    denoise_audio(args.input, args.output, args.model)


if __name__ == "__main__":
    main()
