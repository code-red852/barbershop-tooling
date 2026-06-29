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


def score_to_pdf(score: stream.Score, output_path: str | None = None) -> Path | None:
    """Export score to PDF via music21's lilypond integration or musescore."""
    import shutil

    if output_path is None:
        output_path = Path(tempfile.mktemp(suffix=".pdf", prefix="barbershop_"))
    output_path = Path(output_path)

    # Try music21's built-in lilypond PDF export (handles .ly generation + lilypond call)
    if shutil.which("lilypond"):
        try:
            from music21 import environment
            us = environment.UserSettings()
            us["lilypondPath"] = shutil.which("lilypond")
            fp = score.write("lily.pdf", fp=str(output_path))
            if Path(fp).exists():
                return Path(fp)
        except Exception:
            pass

    # Fallback: try musescore if available
    for cmd in ["musescore", "musescore3", "musescore4", "mscore"]:
        if shutil.which(cmd):
            try:
                from music21 import environment
                us = environment.UserSettings()
                us["musicxmlPath"] = shutil.which(cmd)
                fp = score.write("musicxml.pdf", fp=str(output_path))
                if Path(fp).exists():
                    return Path(fp)
            except Exception:
                pass

    return None
