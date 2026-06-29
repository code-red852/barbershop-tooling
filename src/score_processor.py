"""Process MusicXML scores: parse parts, transpose, export."""

from pathlib import Path
import tempfile

from music21 import converter, instrument, interval, midi, stream, key


BARBERSHOP_PARTS = ["Tenor", "Lead", "Baritone", "Bass"]

PART_ALIASES = {
    "soprano": "Tenor",
    "alto": "Lead",
    "tenor": "Baritone",
    "bass": "Bass",
    "baritone": "Baritone",
    "lead": "Lead",
    "melody": "Lead",
}


def load_score(file_path: str) -> stream.Score:
    return converter.parse(file_path)


def identify_parts(score: stream.Score) -> dict[str, stream.Part]:
    """Map score parts to barbershop voice names."""
    parts = {}
    for i, part in enumerate(score.parts):
        name = part.partName or f"Part {i + 1}"
        normalized = name.strip().lower()

        if normalized in PART_ALIASES:
            bbs_name = PART_ALIASES[normalized]
        elif i < len(BARBERSHOP_PARTS):
            bbs_name = BARBERSHOP_PARTS[i]
        else:
            bbs_name = name

        parts[bbs_name] = part
    return parts


def get_key_signature(score: stream.Score) -> key.Key:
    """Extract the key signature from the score."""
    ks = score.flatten().getElementsByClass(key.KeySignature)
    if ks:
        return ks[0].asKey()
    analysis = score.analyze("key")
    return analysis


def transpose_score(score: stream.Score, semitones: int) -> stream.Score:
    """Transpose the entire score by the given number of semitones."""
    if semitones == 0:
        return score
    i = interval.ChromaticInterval(semitones)
    return score.transpose(i)


def transpose_to_key(score: stream.Score, target_key_str: str) -> stream.Score:
    """Transpose the score to a target key."""
    current = get_key_signature(score)
    target = key.Key(target_key_str)
    i = interval.Interval(current.tonic, target.tonic)
    return score.transpose(i)


def score_to_midi(score: stream.Score, output_path: str | None = None) -> Path:
    """Export the full score to a MIDI file."""
    if output_path is None:
        output_path = tempfile.mktemp(suffix=".mid", prefix="barbershop_")
    output_path = Path(output_path)

    mf = midi.translate.music21ObjectToMidiFile(score)
    mf.open(str(output_path), "wb")
    mf.write()
    mf.close()
    return output_path


def part_to_midi(part: stream.Part, output_path: str | None = None) -> Path:
    """Export a single part to a MIDI file."""
    if output_path is None:
        output_path = tempfile.mktemp(suffix=".mid", prefix="barbershop_part_")
    output_path = Path(output_path)

    s = stream.Score()
    s.append(part)
    mf = midi.translate.music21ObjectToMidiFile(s)
    mf.open(str(output_path), "wb")
    mf.write()
    mf.close()
    return output_path


def generate_learning_tracks(
    score: stream.Score,
) -> dict[str, Path]:
    """Generate individual MIDI learning tracks per part.

    Each track has the featured part at full volume and others reduced.
    """
    parts = identify_parts(score)
    tracks = {}

    for featured_name, featured_part in parts.items():
        learning_score = stream.Score()

        for part_name, part in parts.items():
            track = part.coreCopyAsDerivation("learning_track")
            if part_name == featured_name:
                for n in track.flatten().notes:
                    n.volume.velocity = 100
            else:
                for n in track.flatten().notes:
                    n.volume.velocity = 40

            learning_score.append(track)

        midi_path = score_to_midi(
            learning_score,
            tempfile.mktemp(suffix=f"_{featured_name}.mid", prefix="learning_"),
        )
        tracks[featured_name] = midi_path

    tracks["Full Mix"] = score_to_midi(score)
    return tracks


def _find_lilypond() -> str | None:
    """Find lilypond binary, checking PATH and common install locations."""
    import shutil

    found = shutil.which("lilypond")
    if found:
        return found

    for path in [
        "/usr/bin/lilypond",
        "/usr/local/bin/lilypond",
        "/snap/bin/lilypond",
    ]:
        if Path(path).is_file():
            return path
    return None


def score_to_pdf(score: stream.Score, output_path: str | None = None) -> tuple[Path | None, str]:
    """Export score to PDF. Returns (path, error_detail)."""
    import shutil
    import subprocess

    if output_path is None:
        output_path = Path(tempfile.mktemp(suffix=".pdf", prefix="barbershop_"))
    output_path = Path(output_path)
    errors = []

    lilypond_path = _find_lilypond()
    if lilypond_path:
        # Try music21's lily.pdf integration
        try:
            from music21 import environment
            us = environment.UserSettings()
            us["lilypondPath"] = lilypond_path
            fp = score.write("lily.pdf", fp=str(output_path))
            if Path(fp).exists():
                return Path(fp), ""
        except Exception as e:
            errors.append(f"music21 lily.pdf: {e}")

        # Manual fallback: generate .ly then call lilypond directly
        try:
            ly_path = Path(tempfile.mktemp(suffix=".ly", prefix="barbershop_"))
            score.write("lilypond", fp=str(ly_path))
            pdf_stem = str(output_path.with_suffix(""))
            result = subprocess.run(
                [lilypond_path, "--pdf", "-o", pdf_stem, str(ly_path)],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if output_path.exists():
                return output_path, ""
            errors.append(f"lilypond subprocess: {result.stderr[:500]}")
        except Exception as e:
            errors.append(f"lilypond manual: {e}")
    else:
        errors.append("LilyPond not found")

    # Fallback: try musescore if available
    for cmd in ["musescore", "musescore3", "musescore4", "mscore"]:
        ms_path = shutil.which(cmd)
        if ms_path:
            try:
                from music21 import environment
                us = environment.UserSettings()
                us["musicxmlPath"] = ms_path
                fp = score.write("musicxml.pdf", fp=str(output_path))
                if Path(fp).exists():
                    return Path(fp), ""
            except Exception as e:
                errors.append(f"musescore: {e}")

    return None, "; ".join(errors)
