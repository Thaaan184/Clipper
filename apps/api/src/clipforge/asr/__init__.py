"""Targeted ASR subsystem for transcribing candidate audio windows."""

from clipforge.asr.models import CandidateTranscript, WordTimestamp
from clipforge.asr.whisper import extract_audio_slice, transcribe_candidate_slice

__all__ = [
    "CandidateTranscript",
    "WordTimestamp",
    "extract_audio_slice",
    "transcribe_candidate_slice",
]
