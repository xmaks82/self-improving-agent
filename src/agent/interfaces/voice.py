"""Voice input — push-to-talk via SoX/arecord with Whisper transcription."""

import asyncio
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000


def check_voice_deps() -> tuple[bool, str]:
    """Check for recording + transcription dependencies."""
    has_rec = shutil.which("rec") is not None
    has_arecord = shutil.which("arecord") is not None
    if not has_rec and not has_arecord:
        return False, "Voice requires SoX (rec) or arecord. Install: sudo apt install sox"

    has_whisper = shutil.which("whisper") is not None
    has_api_key = bool(os.environ.get("OPENAI_API_KEY"))
    if not has_whisper and not has_api_key:
        return False, "Voice requires `whisper` CLI or OPENAI_API_KEY for transcription."

    return True, ""


class VoiceRecorder:
    """Records audio via SoX or arecord."""

    def __init__(self):
        self._process: Optional[subprocess.Popen] = None

    def start(self, output_path: str) -> bool:
        cmd = self._get_cmd(output_path)
        if not cmd:
            return False
        self._process = subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True

    def stop(self) -> bool:
        if not self._process:
            return False
        self._process.terminate()
        try:
            self._process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._process.kill()
        self._process = None
        return True

    @property
    def is_recording(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def _get_cmd(self, output_path: str) -> Optional[list[str]]:
        if shutil.which("rec"):
            return ["rec", "-q", "-r", str(SAMPLE_RATE), "-c", "1", "-b", "16", output_path]
        if shutil.which("arecord"):
            return ["arecord", "-f", "S16_LE", "-r", str(SAMPLE_RATE),
                    "-c", "1", "-t", "wav", output_path]
        return None


async def transcribe(audio_path: str) -> str:
    """Transcribe audio to text via Whisper API or local CLI."""
    if os.environ.get("OPENAI_API_KEY"):
        return await _transcribe_api(audio_path)
    return await _transcribe_local(audio_path)


async def _transcribe_api(audio_path: str) -> str:
    try:
        import httpx
        async with httpx.AsyncClient(timeout=30) as client:
            with open(audio_path, "rb") as f:
                resp = await client.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
                    files={"file": f},
                    data={"model": "whisper-1"},
                )
            return resp.json().get("text", "")
    except Exception as e:
        logger.warning("Whisper API transcription failed: %s", e)
        return ""


async def _transcribe_local(audio_path: str) -> str:
    try:
        proc = await asyncio.create_subprocess_exec(
            "whisper", audio_path, "--output_format", "txt",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, _ = await proc.communicate()
        txt_path = Path(audio_path).with_suffix(".txt")
        if txt_path.exists():
            text = txt_path.read_text().strip()
            txt_path.unlink(missing_ok=True)
            return text
        return stdout.decode().strip()
    except Exception as e:
        logger.warning("Local whisper transcription failed: %s", e)
        return ""
