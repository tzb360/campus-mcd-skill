import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Config:
    token: str = field(repr=False)
    timeout: float = 25
    # Intentionally fixed: bearer credentials must never follow a user-supplied URL.
    url: str = field(default="https://mcp.mcd.cn", init=False)

    @classmethod
    def from_env(cls):
        token = os.environ.get("MCD_MCP_TOKEN", "").strip()
        if not token:
            path = Path(os.environ.get("CAMPUS_MCD_TOKEN_FILE", "private/mcd-token.txt"))
            if path.is_file():
                if os.name != "nt" and path.stat().st_mode & 0o077:
                    raise ValueError("Token文件权限过宽，请chmod 600后重试")
                token = path.read_text(encoding="utf-8").strip()
        if not token or token.startswith("${"):
            raise ValueError("请先在本地环境设置 MCD_MCP_TOKEN；不要把凭据发到对话或网页")
        timeout = float(os.environ.get("CAMPUS_MCD_TIMEOUT", "25"))
        if not 1 <= timeout <= 60:
            raise ValueError("CAMPUS_MCD_TIMEOUT 须为1到60秒")
        return cls(token=token, timeout=timeout)
