// src/services/memoryService.ts
import api from './api';
import externalApi from './externalApi';
import {
    AddMemoryRequest,
    UpdateMemoryRequest,
    ImportMemoryRequest,
    GetMemoriesMetadataResponse,
    GetMemoriesResponse,
    MemoryResponse,
    BatchDeleteResponse, MemoryResponseV1
} from '../types/memory';

/**
 * 获取所有记忆元数据
 * @returns 所有记忆的元数据列表
 */
export const getMemories = async (): Promise<GetMemoriesMetadataResponse> => {
    const response = await api.get('/memory');
    return response.data;
};

/**
 * 获取特定owner的完整记忆
 * @param ownerType - owner类型 (user 或 agent)
 * @param ownerId - owner的ID
 * @returns 完整的记忆数据
 */
export const getOwnerMemories = async (
    ownerType: string,
    ownerId: string
): Promise<GetMemoriesResponse> => {
    const response = await api.post('/memory/detail', {
        owner_type: ownerType,
        owner_id: ownerId
    });
    return response.data;
};

/**
 * 调用后端 v1 路径获取特定 owner 的记忆（按分类 + 分页）
 * 新版请求 JSON 示例：
 * {
 *   "owner_id": "testName",
 *   "owner_type": "agent",
 *   "category": "episode",
 *   "page_size": 5,
 *   "page_num": 1
 * }
 */
export const getOwnerMemoriesV1 = async (
    ownerType: string,
    ownerId: string,
    category: string,
    page: number = 0,
    pageSize: number = 20,
): Promise<GetMemoriesResponse> => {
    const body = {
        owner_id: ownerId,
        owner_type: ownerType,
        category,
        page_size: pageSize,
        page_num: page,
    };

    const response = await externalApi.post('/detail', body);
    return response.data;
};

/**
 * 添加记忆条目
 * @param ownerType - owner类型 (user 或 agent)
 * @param ownerId - owner的ID
 * @param category - 记忆分类
 * @param request - 添加请求数据
 * @returns 操作结果
 */
export const addMemoryItem = async (
    ownerType: string,
    ownerId: string,
    category: string,
    request: AddMemoryRequest
): Promise<MemoryResponse> => {
    const response = await api.post('/memory/add', {
        owner_type: ownerType,
        owner_id: ownerId,
        category: category,
        content: request.content
    });
    return response.data;
};

/**
 * 更新记忆条目
 * @param ownerType - owner类型 (user 或 agent)
 * @param ownerId - owner的ID
 * @param category - 记忆分类
 * @param itemId - 记忆条目ID
 * @param request - 更新请求数据
 * @returns 操作结果
 */
export const updateMemoryItem = async (
    ownerType: string,
    ownerId: string,
    category: string,
    itemId: string,
    request: UpdateMemoryRequest
): Promise<MemoryResponse> => {
    const response = await api.put('/memory/update', {
        owner_type: ownerType,
        owner_id: ownerId,
        category: category,
        item_id: itemId,
        content: request.content
    });
    return response.data;
};

/**
 * 批量删除记忆条目
 * @param ownerType - owner类型 (user 或 agent)
 * @param ownerId - owner的ID
 * @param category - 记忆分类
 * @param itemIds - 要删除的记忆条目ID列表
 * @returns 批量删除结果
 */
export const batchDeleteItems = async (
    ownerType: string,
    ownerId: string,
    category: string,
    itemIds: string[]
): Promise<BatchDeleteResponse> => {
    const response = await api.delete('/memory/items', {
        data: {
            owner_type: ownerType,
            owner_id: ownerId,
            category: category,
            item_ids: itemIds
        }
    });
    return response.data;
};

/**
 * 批量删除分类 (legacy API)
 * @param ownerType - owner类型 (user 或 agent)
 * @param ownerId - owner的ID
 * @param categories - 要删除的分类列表
 * @returns 批量删除结果
 */
export const batchDeleteCategories = async (
    ownerType: string,
    ownerId: string,
    categories: string[]
): Promise<BatchDeleteResponse> => {
    const response = await api.delete('/memory/categories', {
        data: {
            owner_type: ownerType,
            owner_id: ownerId,
            categories: categories
        }
    });
    return response.data;
};

/**
 * v1: 批量删除分类（metadata 层面的删除）
 * NOTE: v1 的删除分类接口路径为 /categories/delete，
 *       请求体形如 { owner_id, owner_type, categories }
 *       返回示例：{ success: true, code: 200, message: '执行成功', data: null }
 */
export const batchDeleteCategoriesV1 = async (
    ownerType: string,
    ownerId: string,
    categories: string[]
): Promise<{ success: boolean; code?: number; message?: string; data?: unknown }> => {
    const response = await externalApi.delete('/delete_by_categories', {
        data: {
            owner_type: ownerType,
            owner_id: ownerId,
            categories: categories
        }
    });
    return response.data;
};

/**
 * 导出记忆
 * @param ownerType - owner类型 (user 或 agent)
 * @param ownerId - owner的ID
 * @param format - 导出格式 (json, txt, markdown, yaml)
 * @returns 导出的文件Blob
 */
export const exportMemories = async (
    ownerType: string,
    ownerId: string,
    format: 'json' | 'txt' | 'markdown' | 'yaml'
): Promise<Blob> => {
    const response = await api.post('/memory/export', {
        owner_type: ownerType,
        owner_id: ownerId,
        format: format
    }, {
        responseType: 'blob'
    });
    return response.data;
};

/**
 * 导入记忆
 * @param ownerType - owner类型 (user 或 agent)
 * @param ownerId - owner的ID
 * @param request - 导入请求数据
 * @returns 导入结果
 */
export const importMemories = async (
    ownerType: string,
    ownerId: string,
    request: ImportMemoryRequest
): Promise<MemoryResponse> => {
    const response = await api.post('/memory/import', {
        owner_type: ownerType,
        owner_id: ownerId,
        content: request.content,
        model_name: request.model_name
    });
    return response.data;
};

/**
 * 添加记忆到 v1 接口
 * @param userId - 用户ID
 * @param agentId - 代理ID
 * @param memoryInfos - 记忆信息数组
 * @returns 添加记忆的响应
 */
export const addMemoryV1 = async (
    userId: string,
    agentId: string,
    memoryInfos: { role: string; content: string }[]
): Promise<MemoryResponseV1> => {
    const response = await externalApi.post('/add_memory', {
        user_info: {
            user_id: userId,
            agent_id: agentId,
        },
        memory_infos: memoryInfos,
    });
    return response.data;
};

/**
 * v1: 批量删除 items（删除真实数据）
 * 请求体示例：{ org_id?, project_id?, episodic_id?, item_id?, episodic_ids: [] }
 * 返回示例：{ success: true, code: 200, message: '执行成功', data: null }
 * NOTE: 假设 endpoint 为 POST /items/delete
 */
export const batchDeleteItemsV1 = async (
    params: {
        org_id?: string | null;
        project_id?: string | null;
        episodic_id?: string | null;
        item_id?: string | null;
        episodic_ids?: string[];
    }
): Promise<{ success: boolean; code?: number; message?: string; data?: unknown }> => {

    const response = await externalApi.delete('/delete', {
        data: {
            org_id: params.org_id ?? null,
            project_id: params.project_id ?? null,
            episodic_id: params.episodic_id ?? null,
            item_id: params.item_id ?? null,
            episodic_ids: params.episodic_ids ?? [],
        }
    });
    return response.data;
};
