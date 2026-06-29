# Barbershop Learning Track Generator

A web tool for barbershop quartets to generate per-part learning tracks from sheet music scores.

## Features

- **PDF Score Import** — Upload PDF scores with automatic optical music recognition (via Audiveris)
- **MusicXML Support** — Direct import of MusicXML/MXL files for maximum accuracy
- **Per-Part Learning Tracks** — Generates individual tracks for Tenor, Lead, Baritone, and Bass with the featured part prominent and others softened
- **Full Mix** — Combined track with all four parts
- **Transposition** — Transpose to any key by name or by semitones
- **Audio Export** — Download as MIDI, WAV, or MP3
- **Score Export** — Export transposed scores as PDF (via LilyPond) or MusicXML

## Quick Start

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy to Streamlit Cloud (Free)

1. Push this repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your repo and point to `app.py`
4. The `packages.txt` file handles system dependencies automatically

## Architecture

```
app.py                  # Streamlit UI
src/
  pdf_parser.py         # PDF → MusicXML (Audiveris OMR)
  score_processor.py    # Score parsing, transposition, MIDI generation (music21)
  audio_generator.py    # MIDI → WAV/MP3 (FluidSynth or sine synthesis fallback)
```

## Dependencies

- **music21** — Music theory and score manipulation
- **mido** — MIDI file parsing for audio synthesis
- **Audiveris** — Optical music recognition (optional, for PDF input)
- **FluidSynth** — MIDI-to-audio synthesis (optional, falls back to sine waves)
- **LilyPond** — Score-to-PDF rendering (optional)
