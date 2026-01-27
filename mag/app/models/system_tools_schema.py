from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, ConfigDict


class SystemToolSchema(BaseModel):
    """系统工具 Schema"""

    # 允许使用字段名或别名进行赋值
    model_config = ConfigDict(populate_by_name=True)
    name: str = Field(..., description="工具名称")
    # 避免与 BaseModel 的 `schema` 方法/属性冲突，使用内部字段并提供别名
    tool_schema: Dict[str, Any] = Field(
        ...,
        description="工具的 OpenAI Function Schema",
        validation_alias="schema",
        serialization_alias="schema",
    )


class ToolCategory(BaseModel):
    """工具类别"""

    category: str = Field(..., description="类别名称")
    tools: List[SystemToolSchema] = Field(..., description="该类别下的工具列表")
    tool_count: int = Field(..., description="工具数量")


class SystemToolListResponse(BaseModel):
    """系统工具列表响应（分类格式）"""

    success: bool = Field(..., description="是否成功")
    categories: List[ToolCategory] = Field(..., description="工具类别列表")
    total_count: int = Field(..., description="工具总数")


class SystemToolDetailResponse(BaseModel):
    """系统工具详情响应"""

    # 允许使用字段名或别名进行赋值
    model_config = ConfigDict(populate_by_name=True)
    success: bool = Field(..., description="是否成功")
    name: str = Field(..., description="工具名称")
    tool_schema: Dict[str, Any] = Field(
        ...,
        description="工具的 OpenAI Function Schema",
        validation_alias="schema",
        serialization_alias="schema",
    )
    error: Optional[str] = Field(None, description="错误信息")
