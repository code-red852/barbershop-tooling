"""Barbershop Learning Track Generator — Streamlit App."""

import tempfile
from pathlib import Path

import streamlit as st

from src.pdf_parser import pdf_to_musicxml, pdf_to_images, check_audiveris_installed
from src.score_processor import (
    load_score,
    identify_parts,
    get_key_signature,
    transpose_score,
    transpose_to_key,
    score_to_midi,
    generate_learning_tracks,
    score_to_pdf,
    BARBERSHOP_PARTS,
)
from src.audio_generator import midi_to_audio

ALL_KEYS = [
    "C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B",
    "c", "c#", "d", "eb", "e", "f", "f#", "g", "ab", "a", "bb", "b",
]

MAJOR_KEYS = ALL_KEYS[:12]
MINOR_KEYS = ALL_KEYS[12:]


def main():
    st.set_page_config(
        page_title="Barbershop Learning Tracks",
        page_icon="🎶",
        layout="wide",
    )

    st.title("🎶 Barbershop Learning Track Generator")
    st.markdown(
        "Upload a score (PDF or MusicXML), generate per-part learning tracks, "
        "and optionally transpose to a new key."
    )

    st.sidebar.header("Upload Score")

    uploaded_file = st.sidebar.file_uploader(
        "Choose a score file",
        type=["pdf", "musicxml", "mxl", "xml"],
        help="Upload a PDF score or MusicXML file",
    )

    if uploaded_file is None:
        st.info(
            "👈 Upload a barbershop score (PDF or MusicXML) to get started.\n\n"
            "**Supported formats:**\n"
            "- **PDF** — requires Audiveris for optical music recognition\n"
            "- **MusicXML / MXL** — direct import (most reliable)\n\n"
            "**What you'll get:**\n"
            "- Individual learning tracks for Tenor, Lead, Baritone, and Bass\n"
            "- Full mix track\n"
            "- Transposition to any key with updated score PDF"
        )
        return

    with tempfile.TemporaryDirectory(prefix="barbershop_") as tmpdir:
        input_path = Path(tmpdir) / uploaded_file.name
        input_path.write_bytes(uploaded_file.getvalue())

        score = _load_uploaded_score(input_path, tmpdir)
        if score is None:
            return

        _display_score_info(score)
        score = _handle_transposition(score)
        _generate_tracks_ui(score)


def _load_uploaded_score(input_path: Path, tmpdir: str):
    """Load and parse the uploaded score file."""
    suffix = input_path.suffix.lower()

    if suffix == ".pdf":
        st.subheader("📄 Score Preview")
        images = pdf_to_images(str(input_path))
        if images:
            for img in images:
                st.image(img, use_container_width=True)

        if not check_audiveris_installed():
            st.warning(
                "⚠️ Audiveris (OMR engine) is not installed in this environment. "
                "PDF-to-notation conversion requires Audiveris.\n\n"
                "**Options:**\n"
                "1. Install Audiveris locally and redeploy\n"
                "2. Convert your PDF to MusicXML using "
                "[Audiveris desktop](https://github.com/Audiveris/audiveris) "
                "and upload the MusicXML file instead"
            )
            alt_file = st.file_uploader(
                "Or upload MusicXML directly",
                type=["musicxml", "mxl", "xml"],
                key="alt_upload",
            )
            if alt_file:
                alt_path = Path(tmpdir) / alt_file.name
                alt_path.write_bytes(alt_file.getvalue())
                return _parse_score(alt_path)
            return None

        with st.spinner("Running optical music recognition..."):
            try:
                mxml_path = pdf_to_musicxml(str(input_path), tmpdir)
                return _parse_score(mxml_path)
            except Exception as e:
                st.error(f"OMR failed: {e}")
                return None
    else:
        return _parse_score(input_path)


def _parse_score(path: Path):
    """Parse a MusicXML file into a music21 Score."""
    with st.spinner("Parsing score..."):
        try:
            score = load_score(str(path))
            st.success("Score loaded successfully!")
            return score
        except Exception as e:
            st.error(f"Failed to parse score: {e}")
            return None


def _display_score_info(score):
    """Show score metadata and detected parts."""
    st.subheader("🎵 Score Information")

    parts = identify_parts(score)
    current_key = get_key_signature(score)

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Key", str(current_key))
        st.metric("Parts Detected", len(parts))
    with col2:
        measures = len(score.parts[0].getElementsByClass("Measure")) if score.parts else 0
        st.metric("Measures", measures)

    st.markdown("**Detected parts:**")
    for name, part in parts.items():
        note_count = len(part.flatten().notes)
        st.markdown(f"- **{name}**: {note_count} notes")


def _handle_transposition(score):
    """UI for transposing the score."""
    st.subheader("🔄 Transposition")

    col1, col2 = st.columns(2)

    with col1:
        method = st.radio(
            "Transpose by",
            ["Key", "Semitones"],
            horizontal=True,
        )

    with col2:
        if method == "Key":
            current_key = get_key_signature(score)
            is_minor = current_key.mode == "minor"
            keys = MINOR_KEYS if is_minor else MAJOR_KEYS
            labels = [f"{k} {'minor' if k.islower() else 'major'}" for k in keys]
            current_idx = 0
            for i, k in enumerate(keys):
                if k.lower() == str(current_key.tonic).lower():
                    current_idx = i
                    break

            target = st.selectbox("Target key", keys, index=current_idx, format_func=lambda k: f"{k} {'minor' if k.islower() else 'major'}")

            if target != keys[current_idx]:
                with st.spinner("Transposing..."):
                    score = transpose_to_key(score, target)
                    st.success(f"Transposed to {target}")
        else:
            semitones = st.slider("Semitones", -12, 12, 0)
            if semitones != 0:
                with st.spinner("Transposing..."):
                    score = transpose_score(score, semitones)
                    st.success(f"Transposed by {semitones} semitones")

    return score


def _generate_tracks_ui(score):
    """Generate and display learning tracks."""
    st.subheader("🎧 Learning Tracks")

    output_format = st.radio(
        "Output format",
        ["MIDI", "WAV", "MP3"],
        horizontal=True,
        help="MIDI is fastest. WAV/MP3 use synthesized audio.",
    )

    if st.button("🎼 Generate Learning Tracks", type="primary", use_container_width=True):
        with st.spinner("Generating learning tracks..."):
            try:
                tracks = generate_learning_tracks(score)
            except Exception as e:
                st.error(f"Failed to generate tracks: {e}")
                return

        st.success(f"Generated {len(tracks)} tracks!")

        for part_name, midi_path in tracks.items():
            with st.expander(f"🎤 {part_name}", expanded=True):
                if output_format == "MIDI":
                    midi_bytes = midi_path.read_bytes()
                    st.download_button(
                        f"Download {part_name} MIDI",
                        data=midi_bytes,
                        file_name=f"{part_name.lower().replace(' ', '_')}.mid",
                        mime="audio/midi",
                        key=f"dl_{part_name}",
                    )
                else:
                    fmt = output_format.lower()
                    with st.spinner(f"Synthesizing {part_name} audio..."):
                        audio_path = midi_to_audio(str(midi_path), fmt)
                    audio_bytes = audio_path.read_bytes()
                    mime = "audio/wav" if fmt == "wav" else "audio/mpeg"
                    st.audio(audio_bytes, format=mime)
                    st.download_button(
                        f"Download {part_name} {output_format}",
                        data=audio_bytes,
                        file_name=f"{part_name.lower().replace(' ', '_')}.{fmt}",
                        mime=mime,
                        key=f"dl_{part_name}",
                    )

    st.divider()
    st.subheader("📄 Export Transposed Score")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Export as PDF", use_container_width=True):
            with st.spinner("Rendering PDF (this may take a moment)..."):
                try:
                    result = score_to_pdf(score)
                    pdf_path, error_detail = result
                except Exception as e:
                    pdf_path, error_detail = None, str(e)
            if pdf_path:
                st.download_button(
                    "Download PDF",
                    data=pdf_path.read_bytes(),
                    file_name="transposed_score.pdf",
                    mime="application/pdf",
                    key="dl_pdf",
                )
            else:
                st.error(f"PDF export failed: {error_detail}")
    with col2:
        if st.button("Export as MusicXML", use_container_width=True):
            with st.spinner("Exporting MusicXML..."):
                mxml_path = Path(tempfile.mktemp(suffix=".musicxml"))
                score.write("musicxml", fp=str(mxml_path))
            st.download_button(
                "Download MusicXML",
                data=mxml_path.read_bytes(),
                file_name="transposed_score.musicxml",
                mime="application/xml",
                key="dl_mxml",
            )


if __name__ == "__main__":
    main()
