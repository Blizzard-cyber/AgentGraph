"""流式响应处理器 - 负责处理SSE流式响应"""

import json
import logging
import time  # <--- 新增
from typing import AsyncGenerator, Dict, Any

logger = logging.getLogger(__name__)


class StreamAccumulator:
    """流式响应累积器 - 用于处理和累积流式API响应"""

    def __init__(self):
        self.accumulated_content = ""
        self.accumulated_reasoning = ""
        self.tool_calls_dict = {}
        self.api_usage = None

    def process_chunk(self, chunk):
        """处理单个chunk并累积数据

        Args:
            chunk: API返回的chunk对象，可能是 OpenAI SDK 对象，也可能是 dict（缓存命中场景），
                   甚至是 SSE 字符串（已在上层拆分为 dict）
        """
        # 如果是字符串，这里不处理（由上层解析后再次调用）
        if isinstance(chunk, str):
            return

        # ===== dict 结构（缓存命中场景）=====
        if isinstance(chunk, dict):
            try:
                choices = chunk.get("choices") or []
                if choices:
                    delta = choices[0].get("delta", {})

                    # 累积 content
                    if delta.get("content"):
                        self.accumulated_content += delta["content"]

                    # 累积 reasoning_content
                    if delta.get("reasoning_content"):
                        self.accumulated_reasoning += delta["reasoning_content"]

                    if delta.get("reasoning"):
                        self.accumulated_reasoning += delta["reasoning"]

                    # 累积 tool_calls
                    if delta.get("tool_calls"):
                        for tool_call_delta in delta["tool_calls"]:
                            index = tool_call_delta.get("index")
                            if index is None:
                                continue
                            if index not in self.tool_calls_dict:
                                self.tool_calls_dict[index] = {
                                    "id": tool_call_delta.get("id", ""),
                                    "type": "function",
                                    "function": {"name": "", "arguments": ""},
                                }

                            if tool_call_delta.get("id"):
                                self.tool_calls_dict[index]["id"] = tool_call_delta["id"]

                            function_data = tool_call_delta.get("function", {})
                            if function_data.get("name"):
                                self.tool_calls_dict[index]["function"]["name"] += function_data["name"]
                            if function_data.get("arguments"):
                                self.tool_calls_dict[index]["function"]["arguments"] += function_data["arguments"]

                # 收集 usage
                usage = chunk.get("usage")
                if usage is not None:
                    self.api_usage = {
                        "total_tokens": usage.get("total_tokens", 0),
                        "prompt_tokens": usage.get("prompt_tokens", 0),
                        "completion_tokens": usage.get("completion_tokens", 0),
                    }
            except Exception as e:
                logger.warning(f"解析 dict chunk 失败: {e}")
            return  # 处理完毕

        # ===== OpenAI SDK 对象（默认逻辑）=====
        """处理单个chunk并累积数据

        Args:
            chunk: API返回的chunk对象
        """
        if chunk.choices and chunk.choices[0].delta:
            delta = chunk.choices[0].delta

            # 累积content
            if delta.content:
                self.accumulated_content += delta.content

            # 累积reasoning_content
            if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                self.accumulated_reasoning += delta.reasoning_content

            # 累积reasoning_content
            if hasattr(delta, "reasoning") and delta.reasoning:
                self.accumulated_reasoning += delta.reasoning

            # 累积tool_calls
            if delta.tool_calls:
                for tool_call_delta in delta.tool_calls:
                    index = tool_call_delta.index

                    if index not in self.tool_calls_dict:
                        self.tool_calls_dict[index] = {
                            "id": tool_call_delta.id or "",
                            "type": "function",
                            "function": {"name": "", "arguments": ""},
                        }

                    if tool_call_delta.id:
                        self.tool_calls_dict[index]["id"] = tool_call_delta.id

                    if tool_call_delta.function:
                        if tool_call_delta.function.name:
                            self.tool_calls_dict[index]["function"][
                                "name"
                            ] += tool_call_delta.function.name
                        if tool_call_delta.function.arguments:
                            self.tool_calls_dict[index]["function"][
                                "arguments"
                            ] += tool_call_delta.function.arguments

        # 收集usage信息
        if hasattr(chunk, "usage") and chunk.usage is not None:
            self.api_usage = {
                "total_tokens": chunk.usage.total_tokens,
                "prompt_tokens": chunk.usage.prompt_tokens,
                "completion_tokens": chunk.usage.completion_tokens,
            }

    def get_tool_calls_list(self):
        """获取tool_calls列表"""
        return list(self.tool_calls_dict.values())

    def get_result(self):
        """获取累积的结果"""
        return {
            "accumulated_content": self.accumulated_content,
            "accumulated_reasoning": self.accumulated_reasoning,
            "tool_calls_dict": self.tool_calls_dict,
            "tool_calls_list": self.get_tool_calls_list(),
            "api_usage": self.api_usage,
        }


class StreamHandler:
    """流式响应处理器"""

    @staticmethod
    async def stream_and_accumulate(
        stream, yield_chunks: bool = True
    ) -> AsyncGenerator[str | Dict[str, Any], None]:
        """处理流式响应，实时 yield chunk 并累积结果

        兼容三种流式返回格式：
        1. OpenAI SDK 对象（正常流式）
        2. dict 对象（缓存命中后手动构造）
        3. 原始 SSE 字符串，例如 "data:{...}" / "data:[DONE]"
        """
        accumulator = StreamAccumulator()

        # ---------------- 记录模型调用耗时 ----------------
        start_time = time.monotonic()

        async for raw_chunk in stream:
            # ================= 处理三种数据格式 =================
            parsed_chunk_for_acc = None  # 传给 accumulator 的对象

            # -------- 1. 原始字符串（SSE 行） --------
            if isinstance(raw_chunk, str):
                # 可能包含多个紧凑拼接的 "data:" 片段，将其拆分逐一处理
                segments = []
                if raw_chunk.startswith("data:") and raw_chunk.count("data:") > 1:
                    parts = raw_chunk.split("data:")
                    # split 会导致第一个元素为空字符串
                    for p in parts[1:]:
                        seg = ("data:" + p).strip()
                        if seg:
                            segments.append(seg)
                else:
                    segments.append(raw_chunk.strip())

                for line in segments:
                    if not line:
                        continue

                    # 向前端透传原始行（保持兼容）
                    if yield_chunks:
                        if not line.endswith("\n\n"):
                            yield f"{line}\n\n"
                        else:
                            yield line

                    # 解析 JSON 部分（除 [DONE] 行外）
                    if line.strip().startswith("data:[DONE"):
                        parsed_chunk_for_acc = {"choices": [{"delta": {}, "finish_reason": "stop"}]}
                    elif line.startswith("data:"):
                        json_str = line[len("data:"):].strip()
                        try:
                            parsed_chunk_for_acc = json.loads(json_str)
                        except Exception as e:
                            logger.warning(f"无法解析 SSE JSON: {e}, line: {line}")
                            parsed_chunk_for_acc = None  # 本段不参与累积
                    else:
                        parsed_chunk_for_acc = None

                    if parsed_chunk_for_acc is not None:
                        accumulator.process_chunk(parsed_chunk_for_acc)
                        # 检测 finish_reason
                        finish_reason = None
                        choices = parsed_chunk_for_acc.get("choices") or [] if isinstance(parsed_chunk_for_acc, dict) else []
                        if choices:
                            finish_reason = choices[0].get("finish_reason")
                        if finish_reason:
                            logger.debug(f"流式响应完成，finish_reason: {finish_reason}")

                # 字符串模式已全部处理完毕，继续下一 raw_chunk
                continue

            # -------- 2. dict 格式（缓存场景） --------
            elif isinstance(raw_chunk, dict):
                parsed_chunk_for_acc = raw_chunk

                # 同样将数据透传给前端
                if yield_chunks:
                    yield f"data: {json.dumps(raw_chunk)}\n\n"

            # -------- 3. OpenAI SDK 对象 --------
            else:
                parsed_chunk_for_acc = raw_chunk

                if yield_chunks:
                    if hasattr(raw_chunk, "model_dump"):
                        try:
                            yield f"data: {json.dumps(raw_chunk.model_dump())}\n\n"
                        except Exception:
                            pass

            # ================= 累积处理 =================
            if parsed_chunk_for_acc is not None:
                accumulator.process_chunk(parsed_chunk_for_acc)

                # 检测 finish_reason
                finish_reason = None
                if isinstance(parsed_chunk_for_acc, dict):
                    choices = parsed_chunk_for_acc.get("choices") or []
                    if choices:
                        finish_reason = choices[0].get("finish_reason")
                else:
                    try:
                        finish_reason = parsed_chunk_for_acc.choices[0].finish_reason
                    except Exception:
                        pass

                if finish_reason:
                    logger.debug(f"流式响应完成，finish_reason: {finish_reason}")

        # ---------------- 计算耗时 ----------------
        end_time = time.monotonic()
        elapsed_time_ms = int((end_time - start_time) * 1000)

        # ================= 返回累积结果 =================
        result = {
            "accumulated_content": accumulator.accumulated_content,
            "accumulated_reasoning": accumulator.accumulated_reasoning,
            "tool_calls": accumulator.get_tool_calls_list(),
            "api_usage": accumulator.api_usage,
            "elapsed_time_ms": elapsed_time_ms,  # 前端展示的模型调用耗时（毫秒）
        }

        yield result
