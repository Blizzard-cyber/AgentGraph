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
  BatchDeleteResponse
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
 * 调用后端 v1 路径获取特定owner的完整记忆（支持分页）
 * 使用项目的 `api` 实例并调用 '/v1/detail'，让 Vite proxy 转发到 192.168.1.85:8851，避免 CORS
 * @param ownerType - owner类型 (user 或 agent)
 * @param ownerId - owner的ID
 * @param page - 页号（后端要求0为起始页）
 * @param pageSize - 每页大小
 * @param category - 记忆分类（可选）
 * @returns 完整的记忆数据
 */
export const getOwnerMemoriesV1 = async (
  ownerType: string,
  ownerId: string,
  page: number = 0,
  pageSize: number = 20,
  category?: string
): Promise<GetMemoriesResponse> => {
  // call through the same api instance to benefit from interceptors and to use the Vite proxy (/api base)
  const body: { owner_type: string; owner_id: string; page: number; page_size: number; category?: string } = {
    owner_type: ownerType,
    owner_id: ownerId,
    page: page,
    page_size: pageSize,
  };
  if (category) {
    body.category = category;
  }

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
 * 批量删除分类
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
