"""Convert MIDI to audio (MP3/WAV) using FluidSynth or fallback synthesis."""

import shutil
import subprocess
import tempfile
from pathlib import Path

import mido
import numpy as np


CHOIR_SOUNDFONT_PATHS = [
    "/usr/share/sounds/sf2/FluidR3_GM.sf2",
    "/usr/share/soundfonts/FluidR3_GM.sf2",
    "/usr/local/share/fluidsynth/FluidR3_GM.sf2",
]


def find_soundfont() -> str | None:
    for sf in CHOIR_SOUNDFONT_PATHS:
        if Path(sf).exists():
            return sf
    return None


def midi_to_wav_fluidsynth(midi_path: str, output_path: str | None = None) -> Path | None:
    """Convert MIDI to WAV using FluidSynth."""
    if not shutil.which("fluidsynth"):
        return None

    soundfont = find_soundfont()
    if not soundfont:
        return None

    if output_path is None:
        output_path = tempfile.mktemp(suffix=".wav", prefix="barbershop_audio_")

    result = subprocess.run(
        [
            "fluidsynth",
            "-ni",
            soundfont,
            str(midi_path),
            "-F", str(output_path),
            "-r", "44100",
        ],
        capture_output=True,
        timeout=120,
    )

    if result.returncode == 0 and Path(output_path).exists():
        return Path(output_path)
    return None


def midi_to_wav_sine(midi_path: str, output_path: str | None = None) -> Path:
    """Fallback: synthesize MIDI to WAV using sine waves."""
    if output_path is None:
        output_path = tempfile.mktemp(suffix=".wav", prefix="barbershop_sine_")

    mid = mido.MidiFile(str(midi_path))
    sample_rate = 44100
    duration = mid.length + 1.0
    samples = np.zeros(int(sample_rate * duration))

    active_notes = {}
    current_time = 0.0

    for msg in mid:
        current_time += msg.time
        if msg.type == "note_on" and msg.velocity > 0:
            active_notes[msg.note] = current_time
        elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
            if msg.note in active_notes:
                start = active_notes.pop(msg.note)
                freq = 440.0 * (2.0 ** ((msg.note - 69) / 12.0))
                start_sample = int(start * sample_rate)
                end_sample = int(current_time * sample_rate)
                t = np.arange(end_sample - start_sample) / sample_rate
                # Use multiple harmonics for a richer, more vocal-like tone
                wave = (
                    0.5 * np.sin(2 * np.pi * freq * t)
                    + 0.3 * np.sin(2 * np.pi * freq * 2 * t)
                    + 0.1 * np.sin(2 * np.pi * freq * 3 * t)
                )
                envelope = np.ones_like(t)
                attack = min(int(0.05 * sample_rate), len(t))
                release = min(int(0.1 * sample_rate), len(t))
                if attack > 0:
                    envelope[:attack] = np.linspace(0, 1, attack)
                if release > 0:
                    envelope[-release:] = np.linspace(1, 0, release)
                wave *= envelope * 0.3
                end_idx = min(start_sample + len(wave), len(samples))
                samples[start_sample:end_idx] += wave[: end_idx - start_sample]

    samples = np.clip(samples, -1.0, 1.0)
    samples_16 = (samples * 32767).astype(np.int16)

    import wave
    with wave.open(str(output_path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(samples_16.tobytes())

    return Path(output_path)


def midi_to_audio(midi_path: str, output_format: str = "wav") -> Path:
    """Convert MIDI to audio, trying FluidSynth first, then sine fallback."""
    result = midi_to_wav_fluidsynth(midi_path)
    if result:
        if output_format == "mp3":
            return wav_to_mp3(result)
        return result

    wav_path = midi_to_wav_sine(midi_path)
    if output_format == "mp3":
        return wav_to_mp3(wav_path)
    return wav_path


def wav_to_mp3(wav_path: Path) -> Path:
    """Convert WAV to MP3 using ffmpeg or pydub."""
    mp3_path = wav_path.with_suffix(".mp3")

    if shutil.which("ffmpeg"):
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(wav_path), "-q:a", "2", str(mp3_path)],
            capture_output=True,
            timeout=60,
        )
        if mp3_path.exists():
            return mp3_path

    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_wav(str(wav_path))
        audio.export(str(mp3_path), format="mp3")
        return mp3_path
    except Exception:
        return wav_path
