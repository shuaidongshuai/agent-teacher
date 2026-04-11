from __future__ import annotations

import logging
import subprocess
from typing import Dict

from ..sandbox import Sandbox

logger = logging.getLogger(__name__)


def run_command(sandbox: Sandbox, cmd: str) -> Dict[str, str]:
    """
    在沙箱中执行命令。

    安全措施：
    1. 命令白名单检查
    2. 超时控制
    3. 输出截断
    4. 工作目录限制在沙箱内
    """
    try:
        sandbox.validate_command(cmd)
    except PermissionError as e:
        return {"success": "false", "error": str(e)}

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=sandbox.timeout,
            cwd=str(sandbox.root_dir),
        )

        stdout = sandbox.truncate_output(result.stdout)
        stderr = sandbox.truncate_output(result.stderr)

        output_parts = []
        if stdout:
            output_parts.append(f"[STDOUT]\n{stdout}")
        if stderr:
            output_parts.append(f"[STDERR]\n{stderr}")

        output = "\n".join(output_parts) if output_parts else "（无输出）"

        return {
            "success": "true" if result.returncode == 0 else "false",
            "return_code": str(result.returncode),
            "output": output,
        }

    except subprocess.TimeoutExpired:
        return {
            "success": "false",
            "error": f"命令执行超时（{sandbox.timeout}秒）: {cmd}",
        }
    except Exception as e:
        return {
            "success": "false",
            "error": f"命令执行失败: {e}",
        }
