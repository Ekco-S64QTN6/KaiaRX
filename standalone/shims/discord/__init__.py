"""A stand-in for discord.py, for running Kaiacord's shared modules without it.

STANDALONE-ONLY FILE. The shared modules import `discord` for a few names: an
AudioSource base class (a source hands over 20 ms of 48 kHz stereo s16le per read()),
PCMAudio, FFmpegPCMAudio and VoiceClient in type positions, and opus.is_loaded().
Here a "voice channel" is the local speakers (standalone/speaker.py), which calls a
source's read() the way discord.py's voice thread does.

It is put on sys.path only when the real discord.py is not installed
(standalone/bootstrap.py). Anything else is Discord-only: using it raises
DiscordOnly with the name, so a shared module that starts needing more says so
plainly (and tests/test_discord_shim.py lists what the shared code uses).
"""
from __future__ import annotations

import subprocess
import types

STANDALONE_SHIM = True


class DiscordOnly(AttributeError):
    """An AttributeError, so getattr(discord, name, default) still works."""


class AudioSource:
    """discord.AudioSource: read() returns 3,840 bytes (20 ms) or b"" at the end."""

    def read(self) -> bytes:
        raise NotImplementedError

    def is_opus(self) -> bool:
        return False

    def cleanup(self) -> None:
        pass

    def __del__(self):
        try:
            self.cleanup()
        except Exception:
            pass


class PCMAudio(AudioSource):
    """Raw 48 kHz stereo s16le from a file-like object."""

    def __init__(self, stream) -> None:
        self.stream = stream

    def read(self) -> bytes:
        ret = self.stream.read(3840)
        return ret if len(ret) == 3840 else b""


class FFmpegPCMAudio(AudioSource):
    """ffmpeg decoding anything to 48 kHz stereo s16le, as discord.py's does."""

    def __init__(self, source, *, pipe: bool = False, executable: str = "ffmpeg",
                 before_options: str | None = None, options: str | None = None, stderr=None) -> None:
        args = [executable] + (before_options.split() if before_options else [])
        args += ["-i", "-" if pipe else str(source), "-f", "s16le", "-ar", "48000", "-ac", "2", "-loglevel", "warning"]
        args += (options.split() if options else []) + ["pipe:1"]
        self._stdin_src = source if pipe else None
        self._proc = subprocess.Popen(args, stdin=subprocess.PIPE if pipe else subprocess.DEVNULL,
                                      stdout=subprocess.PIPE, stderr=stderr)
        if pipe:
            import threading
            threading.Thread(target=self._feed, daemon=True).start()

    def _feed(self) -> None:
        try:
            while True:
                chunk = self._stdin_src.read(8192)
                if not chunk:
                    break
                self._proc.stdin.write(chunk)
        except Exception:
            pass
        finally:
            try:
                self._proc.stdin.close()
            except Exception:
                pass

    def read(self) -> bytes:
        ret = self._proc.stdout.read(3840)
        return ret if len(ret) == 3840 else b""

    def cleanup(self) -> None:
        p = getattr(self, "_proc", None)
        if p and p.poll() is None:
            p.kill()
            p.wait()


class VoiceClient:
    """Type position only; the local stand-in is standalone.speaker.SpeakerVoice."""


class _Opus(types.SimpleNamespace):
    @staticmethod
    def is_loaded() -> bool:
        return True                     # nothing is Opus-encoded for the speakers

    @staticmethod
    def _load_default() -> bool:
        return True


opus = _Opus()
errors = types.SimpleNamespace(DiscordException=Exception, ClientException=Exception,
                               NotFound=Exception, Forbidden=Exception, HTTPException=Exception)


def __getattr__(name: str):
    if name.startswith("__"):
        raise AttributeError(name)
    raise DiscordOnly(f"discord.{name} is Discord-only; the standalone shim does not provide it")

