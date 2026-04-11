from __future__ import annotations

SYSTEM_PROMPT = """你是一个有记忆能力的智能助手。你能记住用户在之前对话中告诉你的信息。

## 你的记忆

### 长期记忆（从之前的对话中检索到的相关记忆）
{long_term_memories}

### 对话摘要（之前对话的压缩摘要）
{conversation_summary}

### 工作记忆（当前任务的关键信息）
{working_memory}

## 行为准则

1. 如果用户问你之前聊过的信息，先查看记忆再回答
2. 如果记忆中有相关信息，自然地引用（不要说"根据我的记忆"这种机械的说法）
3. 如果记忆中没有相关信息，坦诚说明
4. 在对话中注意收集用户的关键信息（姓名、偏好、习惯等）"""


COMPRESS_PROMPT = """请将以下对话历史压缩为一段简洁的摘要。保留关键信息（用户身份、偏好、讨论的主题和结论），去除闲聊和重复内容。

## 之前的摘要
{previous_summary}

## 需要压缩的对话
{messages}

## 要求

输出一段 200 字以内的摘要，使用第三人称描述用户（如"用户提到..."、"用户偏好..."）。直接输出摘要文本，不要有前缀。"""


EXTRACT_MEMORIES_PROMPT = """请从以下对话中提取值得长期记住的信息。只提取事实性、偏好性或重要的信息，忽略闲聊。

## 对话内容
{messages}

## 输出格式

请严格按 JSON 格式输出：

```json
{{
    "memories": [
        {{"content": "记忆内容", "category": "分类"}},
        ...
    ]
}}
```

category 可选值：personal_info（个人信息）、preference（偏好）、fact（事实）、task（任务相关）、other（其他）

如果没有值得记忆的内容，返回空列表：
```json
{{"memories": []}}
```"""


UPDATE_WORKING_MEMORY_PROMPT = """根据当前对话内容，更新工作记忆。工作记忆用于跟踪当前任务的关键信息。

## 当前工作记忆
{current_working_memory}

## 最新对话
用户: {user_message}
助手: {assistant_message}

## 输出格式

```json
{{
    "current_goal": "当前主要目标（一句话）",
    "key_facts": ["关键事实1", "关键事实2"],
    "pending_questions": ["待解决问题1"],
    "reasoning_steps": ["推理步骤1"]
}}
```

如果没有明确的任务目标，current_goal 填 "自由对话"。"""
