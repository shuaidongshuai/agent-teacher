"""
代码解释 Demo

运行方式:
    python scripts/run_explain_code.py

说明:
    - 需要 OPENAI_API_KEY
    - Agent 会读取并解释指定代码文件
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.config import CodeAgentConfig
from app.llm_client import LLMClient
from app.prompts import EXPLAIN_CODE_PROMPT
from app.sandbox import Sandbox
from app.tools import read_file


def main():
    print("=" * 60)
    print("       Code Agent — 代码解释 Demo")
    print("=" * 60)

    config = CodeAgentConfig(project_root=project_root)

    if not config.openai_api_key:
        print("\n错误: 请先设置 OPENAI_API_KEY")
        print("  export OPENAI_API_KEY=your-key")
        return

    llm = LLMClient(
        api_key=config.openai_api_key,
        base_url=config.openai_base_url,
        model=config.openai_model,
    )

    sandbox = Sandbox(
        root_dir=config.sandbox_path,
        allowed_commands=config.allowed_commands,
        timeout=config.command_timeout,
    )

    # 要解释的文件
    files = ["calculator.py", "utils.py", "test_calculator.py"]

    print(f"\n将解释以下文件: {files}\n")

    for file_path in files:
        print(f"\n{'='*50}")
        print(f"文件: {file_path}")
        print(f"{'='*50}")

        result = read_file(sandbox, file_path)
        if result.get("success") != "true":
            print(f"  读取失败: {result.get('error', '未知错误')}")
            continue

        content = result["content"]

        prompt = EXPLAIN_CODE_PROMPT.format(
            file_path=file_path,
            code_content=content,
        )

        explanation = llm.generate(
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=2048,
        )

        print(explanation)


if __name__ == "__main__":
    main()
