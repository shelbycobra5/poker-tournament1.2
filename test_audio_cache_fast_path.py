"""Regression test for the audio cache fast path on slower PCs."""
from pathlib import Path
import tempfile
import wave
from unittest.mock import patch
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import poker_tournament_director as app_module


def make_test_wav(path: Path):
    # Short mono 16-bit PCM file; enough to exercise the normal scaling path.
    sample_rate = 8000
    samples = b"\x10\x00\xf0\xff" * 400
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(samples)


def main():
    director = app_module.TournamentDirector.__new__(app_module.TournamentDirector)
    with tempfile.TemporaryDirectory(prefix="mpt_audio_cache_test_") as td:
        temp = Path(td)
        source = temp / "sample.wav"
        make_test_wav(source)
        with patch.object(app_module.tempfile, "gettempdir", return_value=str(temp / "cache")):
            first = director._scaled_custom_wav_path(str(source), 70)
            assert first and Path(first).is_file(), "Initial call should create the scaled WAV cache file."
            assert Path(first).stat().st_size > 44, "Cached WAV should contain audio frames."
            # If the cache lookup is after PCM processing, this deliberately fails.
            with patch.object(app_module.wave, "open", side_effect=AssertionError("Cache hit reread/reprocessed audio")):
                second = director._scaled_custom_wav_path(str(source), 70)
            assert first == second, "Repeated call should return the same cached WAV path."
    print("Audio cache fast-path regression check passed.")


if __name__ == "__main__":
    main()
