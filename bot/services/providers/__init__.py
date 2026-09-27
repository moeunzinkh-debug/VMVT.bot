"""Download providers used by VMVT.bot."""

from .base import MediaResult, ProviderError
from .tikwm import TikWMProvider
from .ytdlp import YtDlpProvider

__all__ = ["MediaResult", "ProviderError", "TikWMProvider", "YtDlpProvider"]
