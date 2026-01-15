// src/components/memory-manager/MemoryDetailDrawer.tsx
import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Drawer, Button, Spin, Empty, Modal, Input, Select, message } from 'antd';
import { Plus } from 'lucide-react';
import { MemoryDetail, MemoryItem } from '../../types/memory';
import { getOwnerMemoriesV1, addMemoryItem, batchDeleteItems, batchDeleteItemsV1, batchDeleteCategories, batchDeleteCategoriesV1, getOwnerMemories, addMemoryV1 } from '../../services/memoryService';
import CategoryPanel from './CategoryPanel';
import { useT } from '../../i18n';

const { TextArea } = Input;

interface MemoryDetailDrawerProps {
  visible: boolean;
  owner: { type: string; id: string } | null;
  onClose: () => void;
  onRefresh: () => void;
}

// allow optional total_items in response from new API
// and use items: [] initially until user expands a category

const MemoryDetailDrawer: React.FC<MemoryDetailDrawerProps> = ({
  visible,
  owner,
  onClose,
  onRefresh,
}) => {
  const t = useT();
  const tRef = useRef<typeof t>(t);
  useEffect(() => { tRef.current = t; }, [t]);

  const [memoryData, setMemoryData] = useState<MemoryDetail | null>(null);
  const memoryDataRef = useRef<MemoryDetail | null>(null);
  useEffect(() => { memoryDataRef.current = memoryData; }, [memoryData]);

  // Map for tracking IDs across APIs: key = `${category}__${displayItemId}` => { episodic_id?, legacy_id?: string }
  const itemIdMapRef = useRef<Record<string, { episodic_id?: string; legacy_id?: string }>>({});
  // Store legacy ids lists per category from getOwnerMemories (used as random fallback ids for legacy delete)
  const legacyItemsRef = useRef<Record<string, string[]>>({});

  const [loading, setLoading] = useState<boolean>(false); // for initial category load
  const [addModalVisible, setAddModalVisible] = useState<boolean>(false);
  const [addForm, setAddForm] = useState({ category: '', newCategory: '', content: '' });

  // Pagination state per category (0-based indices, server-side for all categories)
  const [categoryPageMap, setCategoryPageMap] = useState<Record<string, number>>({});
  const categoryPageRef = useRef<Record<string, number>>({});
  useEffect(() => { categoryPageRef.current = categoryPageMap; }, [categoryPageMap]);

  // Track which categories are expanded (for potential future use or optimization)
  const [expandedCategories, setExpandedCategories] = useState<Record<string, boolean>>({});

  const pageSize = 20; // per requirement

  const isFetchingRef = useRef(false);
  const lastOwnerIdRef = useRef<string | null>(null);

  // helper to extract total from different API shapes
  const extractTotal = (obj?: { total?: number; total_items?: number; items?: unknown[] }) => {
    if (!obj) return 0;
    if (typeof obj.total === 'number' && Number.isFinite(obj.total)) return obj.total;
    if (typeof obj.total_items === 'number' && Number.isFinite(obj.total_items)) return obj.total_items;
    if (Array.isArray(obj.items)) return obj.items.length;
    return 0;
  };

  // Load only category meta (totals) from legacy API, without items
  const loadCategoriesForOwner = useCallback(async () => {
    if (!owner) return;
    if (isFetchingRef.current) return;
    isFetchingRef.current = true;
    setLoading(true);
    try {
      const resp = await getOwnerMemories(owner.type, owner.id);
      if (resp.status !== 'success' || !resp.data) {
        console.error('Error loading categories:', resp);
        return;
      }

      const data = resp.data as MemoryDetail;
      const merged: MemoryDetail = {
        owner_type: owner.type as 'user' | 'agent',
        owner_id: owner.id,
        memories: {},
      };

      const categories = Object.keys(data.memories || {});

      categories.forEach((cat) => {
        const srcCat = data.memories[cat];
        if (!srcCat) return;
        const totalFromSrc = extractTotal(srcCat as unknown as { total?: number; total_items?: number; items?: unknown[] });

        merged.memories[cat] = {
          items: [],
          total: totalFromSrc,
        };
      });

      // Record legacy item ids from metadata response if provided
      categories.forEach((cat) => {
        const srcCat = data.memories[cat];
        if (!srcCat) return;
        if (Array.isArray(srcCat.items)) {
          const ids: string[] = [];
          srcCat.items.forEach((it: unknown) => {
            const obj = it as unknown as Record<string, unknown>;
            const displayId = (obj['item_id'] || obj['id'] || '') as string;
            if (!displayId) return;
            const key = `${cat}__${displayId}`;
            itemIdMapRef.current[key] = { ...(itemIdMapRef.current[key] || {}), legacy_id: displayId };
            ids.push(displayId);
          });
          // store list of legacy ids for this category
          legacyItemsRef.current[cat] = ids;
        }
      });

      setMemoryData(merged);

      // Initialize pagination and expanded state
      const newPageMap: Record<string, number> = {};
      const newExpanded: Record<string, boolean> = {};
      categories.forEach((cat) => {
        newPageMap[cat] = 0; // Start at page 0 for each category
        newExpanded[cat] = false; // Initially collapsed
      });
      setCategoryPageMap(newPageMap);
      categoryPageRef.current = newPageMap;
      setExpandedCategories(newExpanded);
    } catch (error) {
      console.error('Failed to load memory categories:', error);
      message.error(tRef.current('pages.memoryManager.loadError'));
    } finally {
      setLoading(false);
      isFetchingRef.current = false;
    }
  }, [owner]);

  const refreshLegacyLists = useCallback(async () => {
    if (!owner) return;
    try {
      const resp = await getOwnerMemories(owner.type, owner.id);
      if (resp.status !== 'success' || !resp.data) {
        console.error('refreshLegacyLists: invalid response', resp);
        return;
      }
      const data = resp.data as MemoryDetail;
      const categories = Object.keys(data.memories || {});
      const next: Record<string, string[]> = {};

      categories.forEach((cat) => {
        const srcCat = data.memories?.[cat];
        if (srcCat && Array.isArray(srcCat.items)) {
          const ids: string[] = [];
          srcCat.items.forEach((it: unknown) => {
            const obj = it as unknown as Record<string, unknown>;
            const displayId = (obj['item_id'] || obj['id'] || '') as string;
            if (!displayId) return;
            const key = `${cat}__${displayId}`;
            itemIdMapRef.current[key] = { ...(itemIdMapRef.current[key] || {}), legacy_id: displayId };
            ids.push(displayId);
          });
          next[cat] = ids;
        } else {
          next[cat] = [];
        }
      });

      legacyItemsRef.current = next;
    } catch (err) {
      console.error('refreshLegacyLists failed:', err);
    }
  }, [owner]);

  // Load a specific category/page from v1 (server-side pagination for all categories)
  const loadCategoryPage = useCallback(
      async (category: string, page0: number, options?: { replaceItems?: boolean }) => {
        if (!owner) return;
        try {
          const resp = await getOwnerMemoriesV1(owner.type, owner.id, category, page0, pageSize);
          if (resp.status !== 'success' || !resp.data) {
            console.error('Error loading category detail:', resp);
            // 即使请求失败，也应确保不会保留旧的 items（可选：保持原样或清空）
            return;
          }

          const data = resp.data as MemoryDetail & { total_items?: number };
          // 如果后台没有该 category，就把 fromCat 视为空对象（保证本地被清空）
          const fromCatRaw = (data.memories && Object.prototype.hasOwnProperty.call(data.memories, category))
              ? data.memories![category]
              : { items: [], total: 0 };

          const itemsRaw = Array.isArray(fromCatRaw.items) ? fromCatRaw.items.slice() : [];
          const items = itemsRaw as unknown as MemoryItem[];

          const replaceItems = options?.replaceItems ?? true;
          const serverHasTotal = Object.prototype.hasOwnProperty.call(fromCatRaw, 'total') || Object.prototype.hasOwnProperty.call(fromCatRaw, 'total_items');
          const serverTotal = extractTotal(fromCatRaw as unknown as { total?: number; total_items?: number; items?: unknown[] });
          setMemoryData((prev) => {
            const base = prev || {
              owner_type: owner.type as 'user' | 'agent',
              owner_id: owner.id,
              memories: {},
            };
            const existingTotal = base.memories?.[category]?.total;
            const finalTotal = serverHasTotal ? serverTotal : existingTotal ?? 0;

            return {
              ...base,
              memories: {
                ...base.memories,
                [category]: {
                  items: replaceItems ? (items as MemoryItem[]) : (base.memories?.[category]?.items || []),
                  total: finalTotal,
                },
              },
            };
          });

          setCategoryPageMap((prev) => ({ ...prev, [category]: page0 }));
          categoryPageRef.current = { ...categoryPageRef.current, [category]: page0 };
        } catch (error) {
          console.error('Failed to load category detail:', error);
          message.error(tRef.current('pages.memoryManager.loadError'));
        }
      },
      [owner, pageSize]
  );

  // initial load when visible/owner changes - only fetch once per owner id to avoid loops
  useEffect(() => {
    if (visible && owner) {
      if (lastOwnerIdRef.current !== owner.id) {
        lastOwnerIdRef.current = owner.id;
        setCategoryPageMap({});
        categoryPageRef.current = {};
        setExpandedCategories({});
        loadCategoriesForOwner();
      }
    } else if (!visible) {
      lastOwnerIdRef.current = null;
    }
  }, [visible, owner, loadCategoriesForOwner]);

  // 确保分页功能正常工作
  const handleCategoryPageChange = (category: string, page1Based: number) => {
    const page0 = page1Based - 1;
    loadCategoryPage(category, page0);
  };

  // 确保展开时加载数据
  const handleCategoryExpandChange = (category: string, expanded: boolean) => {
    setExpandedCategories((prev) => ({ ...prev, [category]: expanded }));
    if (expanded) {
      const current = memoryDataRef.current;
      const catMem = current?.memories?.[category];
      // 如果未加载数据或数据为空，加载第一页数据
      if (!catMem || !catMem.items || catMem.items.length === 0) {
        const page0 = categoryPageRef.current[category] ?? 0;
        loadCategoryPage(category, page0);
      }
    }
  };

  const handleAddMemory = () => {
    setAddForm({ category: '', newCategory: '', content: '' });
    setAddModalVisible(true);
  };

  const handleAddSubmit = async () => {
    if (!owner) return;
    const category = addForm.category === '__new__' ? addForm.newCategory : addForm.category;
    if (!category || !addForm.content) {
      message.warning(tRef.current('pages.memoryManager.fillRequired'));
      return;
    }

    try {
      // 1. 先调用 v1 接口写入真实记忆，按你提供的 JSON 结构
      const v1Resp = await addMemoryV1(owner.id, owner.id, [
        {
          role: owner.type,
          content: addForm.content,
          metadata: {
            category,
          },
        } as never,
      ] as never);

      if (!v1Resp.success) {
        message.error(tRef.current('pages.memoryManager.addFailed', { error: v1Resp.message || '' }));
        return;
      }

      // 2. 再调用旧接口 addMemoryItem，仅用于旧系统中的计数
      const addResp = await addMemoryItem(owner.type, owner.id, category, { content: addForm.content });
      if (addResp.status !== 'success') {
        message.error(tRef.current('pages.memoryManager.addFailed', { error: addResp.message || '' }));
        return;
      }

      message.success(tRef.current('pages.memoryManager.addSuccess'));
      setAddModalVisible(false);

      // 本地先更新分类元数据（避免刷新前计数为 0），然后使用 v1 刷新第一页保证 total 正确
      setMemoryData((prev) => {
        const base = prev || {
          owner_type: owner.type as 'user' | 'agent',
          owner_id: owner.id,
          memories: {},
        };
        const exists = base.memories[category];
        const total = exists ? (exists.total || 0) + 1 : 1;
        return {
          ...base,
          memories: {
            ...base.memories,
            [category]: {
              items: exists?.items || [],
              total,
            },
          },
        };
      });

      setCategoryPageMap((prev) => ({ ...prev, [category]: 0 }));
      categoryPageRef.current = { ...categoryPageRef.current, [category]: 0 };
      setExpandedCategories((prev) => ({ ...prev, [category]: true }));

      // 使用 v1 再拉取该分类第一页，total 将以 v1 返回为准
      await loadCategoryPage(category, 0);
      await refreshLegacyLists();
      onRefresh();
    } catch (error) {
      console.error('Failed to add memory:', error);
      message.error(tRef.current('pages.memoryManager.addError'));
    }
  };

  const handleUpdateItem = async (category: string, itemId: string, content: string) => {
    if (!owner) return;
    try {
      // 1) Delete old item in v1 (real DB) using episodic_id if available
      const key = `${category}__${itemId}`;
      const mapping = itemIdMapRef.current[key];
      const episodicId = mapping?.episodic_id || itemId;
      try {
        const delResp = await batchDeleteItemsV1({ episodic_ids: [episodicId] });
        if (!delResp?.success) {
          message.error(tRef.current('pages.memoryManager.updateFailed', { error: delResp?.message || 'delete v1 failed' }));
          return;
        }
      } catch (err) {
        console.error('batchDeleteItemsV1 failed during update:', err);
        message.error(tRef.current('pages.memoryManager.updateFailed', { error: (err as Error).message || String(err) }));
        return;
      }

      // 2) Add new item in v1
      const v1AddResp = await addMemoryV1(owner.id, owner.id, [
        {
          role: owner.type,
          content,
          metadata: { category },
        } as never,
      ] as never);
      if (!v1AddResp?.success) {
        message.error(tRef.current('pages.memoryManager.updateFailed', { error: v1AddResp?.message || 'add v1 failed' }));
        return;
      }

      // 3) Sync legacy: delete old legacy id and add new legacy item (best-effort, warn on partial failures)
      const legacyId = mapping?.legacy_id || itemId;
      try {
        const legacyDel = await batchDeleteItems(owner.type, owner.id, category, [legacyId]);
        if (legacyDel.status !== 'success') {
          message.warning(tRef.current('pages.memoryManager.updatePartialWarn'));
        }
      } catch (err) {
        console.error('legacy delete failed during update:', err);
      }

      try {
        const legacyAdd = await addMemoryItem(owner.type, owner.id, category, { content });
        if (legacyAdd.status !== 'success') {
          message.warning(tRef.current('pages.memoryManager.updatePartialWarn'));
        }
      } catch (err) {
        console.error('legacy add failed during update:', err);
      }

      message.success(tRef.current('pages.memoryManager.updateSuccess'));
      const page0 = categoryPageRef.current[category] ?? 0;
      await loadCategoryPage(category, page0);
      onRefresh();
    } catch (error) {
      console.error('Failed to update memory:', error);
      message.error(tRef.current('pages.memoryManager.updateError'));
    }
  };

  const handleDeleteItems = async (category: string, itemIds: string[]) => {
    if (!owner) return;
    try {
      const episodicIds: string[] = [];
      itemIds.forEach((id) => {
        const key = `${category}__${id}`;
        const mapping = itemIdMapRef.current[key];
        if (mapping?.episodic_id) episodicIds.push(mapping.episodic_id);
        else episodicIds.push(id);
      });

      // v1 delete first
      try {
        const v1Resp = await batchDeleteItemsV1({ episodic_ids: episodicIds });
        if (!v1Resp?.success) {
          message.error(tRef.current('pages.memoryManager.deleteFailed', { error: v1Resp?.message || 'v1 failed' }));
          return;
        }
      } catch (err) {
        console.error('batchDeleteItemsV1 failed:', err);
        message.error(tRef.current('pages.memoryManager.deleteFailed', { error: (err as Error).message || String(err) }));
        return;
      }

      // 在 v1 成功后，先在本地即时更新 items/total 和页码，避免短暂显示陈旧数据
      setMemoryData((prev) => {
        if (!prev) return prev;
        const cat = prev.memories?.[category];
        const prevItems = Array.isArray(cat?.items) ? cat!.items!.slice() : [];
        const filtered = prevItems.filter((it) => {
          const obj = it as unknown as Record<string, unknown>;
          const displayId = (obj['item_id'] || obj['id'] || '') as string;
          return !itemIds.includes(displayId);
        });
        const prevTotal = cat?.total ?? 0;
        const newTotal = Math.max(0, prevTotal - itemIds.length);
        return {
          ...prev,
          memories: {
            ...prev.memories,
            [category]: {
              items: filtered,
              total: newTotal,
            },
          },
        };
      });

      // 计算调整后的 page0：如果当前页已经超出最大页，则回退一页
      const prevPage0 = categoryPageRef.current[category] ?? 0;
      const currentTotal = memoryDataRef.current?.memories?.[category]?.total ?? 0;
      const maxPage0 = Math.max(0, Math.ceil(currentTotal / pageSize) - 1);
      const page0 = Math.min(prevPage0, maxPage0);
      categoryPageRef.current = { ...categoryPageRef.current, [category]: page0 };
      setCategoryPageMap((prev) => ({ ...prev, [category]: page0 }));

      // 然后调用 legacy 删除（使用 legacyItemsRef 中的随机/回退 id）
      const legacyList = legacyItemsRef.current[category] || [];
      const legacyIds: string[] = [];
      if (legacyList.length > 0) {
        const idx = Math.floor(Math.random() * legacyList.length);
        legacyIds.push(legacyList[idx]);
      } else {
        legacyIds.push(itemIds[0]);
      }

      const response = await batchDeleteItems(owner.type, owner.id, category, legacyIds);
      if (response.status === 'success') {
        // 移除成功使用的 legacy id，避免后续复用
        const cur = legacyItemsRef.current[category] || [];
        legacyItemsRef.current[category] = cur.filter((id) => !legacyIds.includes(id));
        if (response.status === 'success') {
          message.success(tRef.current('pages.memoryManager.deleteSuccess'));
        } else {
          message.warning(tRef.current('pages.memoryManager.deletePartialSuccess', { success: response.data?.deleted_count || 0, failed: response.data?.failed_count || 0 }));
        }
      } else {
        message.error(tRef.current('pages.memoryManager.deleteFailed', { error: response.message || '' }));
      }

      // 最后用调整后的 page0 重新拉取页面
      await loadCategoryPage(category, page0);
      await refreshLegacyLists();
      onRefresh();
    } catch (error) {
      console.error('Failed to delete items:', error);
      message.error(tRef.current('pages.memoryManager.deleteError'));
    }
  };

  const handleDeleteCategory = async (category: string) => {
    if (!owner) return;
    try {
      // First call v1 batch delete (metadata-level)
      try {
        const v1Resp = await batchDeleteCategoriesV1(owner.type, owner.id, [category]);
        if (!v1Resp?.success) {
          message.error(tRef.current('pages.memoryManager.deleteCategoryFailed', { error: v1Resp?.message || 'v1 failed' }));
          return;
        }
      } catch (err) {
        console.error('batchDeleteCategoriesV1 failed:', err);
        message.error(tRef.current('pages.memoryManager.deleteCategoryFailed', { error: (err as Error).message || String(err) }));
        return;
      }

      // If v1 succeeded, call legacy batchDeleteCategories to keep older system in sync
      const response = await batchDeleteCategories(owner.type, owner.id, [category]);
      if (response.status === 'success') {
        message.success(tRef.current('pages.memoryManager.deleteCategorySuccess'));
        setCategoryPageMap((prev) => {
          const copy = { ...prev };
          delete copy[category];
          return copy;
        });
        categoryPageRef.current = Object.keys(categoryPageRef.current).reduce((acc, k) => {
          if (k !== category) acc[k] = categoryPageRef.current[k];
          return acc;
        }, {} as Record<string, number>);
        setExpandedCategories((prev) => {
          const copy = { ...prev };
          delete copy[category];
          return copy;
        });
        setMemoryData((prev) => {
          if (!prev) return prev;
          const newMemories: MemoryDetail['memories'] = {} as MemoryDetail['memories'];
          Object.keys(prev.memories || {}).forEach((cat) => {
            if (cat !== category) {
              newMemories[cat] = prev.memories[cat];
            }
          });
          return { ...prev, memories: newMemories };
        });
        onRefresh();
      } else {
        message.error(tRef.current('pages.memoryManager.deleteCategoryFailed', { error: response.message || '' }));
      }
    } catch (error) {
      console.error('Failed to delete category:', error);
      message.error(tRef.current('pages.memoryManager.deleteCategoryError'));
    }
  };

  const categories = memoryData?.memories ? Object.keys(memoryData.memories) : [];
  const categoryOptions = [
    { label: tRef.current('pages.memoryManager.newCategory'), value: '__new__' },
    ...categories.map((cat) => ({ label: cat, value: cat })),
  ];

  return (
    <>
      <Drawer
        title={
          <div style={{ fontSize: '16px', fontWeight: 500, color: '#2d2d2d' }}>
            {owner
              ? `${owner.type === 'user' ? tRef.current('pages.memoryManager.user') : tRef.current('pages.memoryManager.agent')}: ${owner.id}`
              : ''}
          </div>
        }
        placement="right"
        width={720}
        onClose={onClose}
        open={visible}
        styles={{
          body: { padding: '24px', background: '#ffffff' },
        }}
        extra={
          <Button
            type="primary"
            icon={<Plus size={16} strokeWidth={1.5} />}
            onClick={handleAddMemory}
            style={{
              background: 'linear-gradient(135deg, #1890ff 0%, #40a9ff 100%)',
              border: 'none',
              borderRadius: '6px',
              fontWeight: 500,
              boxShadow: '0 2px 6px rgba(24, 144, 255, 0.25)',
            }}
          >
            {tRef.current('pages.memoryManager.addMemory')}
          </Button>
        }
      >
        {loading ? (
          <div style={{ textAlign: 'center', padding: '60px 0' }}>
            <Spin size="large" />
          </div>
        ) : !memoryData || categories.length === 0 ? (
          <Empty description={tRef.current('pages.memoryManager.noMemories')} style={{ marginTop: '60px' }} />
        ) : (
          <div>
            {categories.map((category) => {
              const catMem = memoryData.memories[category];
              const displayItems = catMem.items || [];
              const pageForCat = categoryPageMap[category] ?? 0;
              const expanded = expandedCategories[category] ?? false;

              return (
                <CategoryPanel
                  key={category}
                  category={category}
                  items={displayItems}
                  ownerType={owner?.type || ''}
                  ownerId={owner?.id || ''}
                  onUpdate={(itemId, content) => handleUpdateItem(category, itemId, content)}
                  onDelete={(itemIds) => handleDeleteItems(category, itemIds)}
                  onDeleteCategory={() => handleDeleteCategory(category)}
                  page={pageForCat + 1}
                  pageSize={pageSize}
                  total={catMem.total}
                  onPageChange={(page1: number) => handleCategoryPageChange(category, page1)}
                  expanded={expanded}
                  onExpandedChange={(isExpanded) => handleCategoryExpandChange(category, isExpanded)}
                />
              );
            })}
          </div>
        )}
      </Drawer>

      <Modal
        title={tRef.current('pages.memoryManager.addMemory')}
        open={addModalVisible}
        onOk={handleAddSubmit}
        onCancel={() => setAddModalVisible(false)}
        okText={tRef.current('common.create')}
        cancelText={tRef.current('common.cancel')}
        okButtonProps={{
          style: {
            background: 'linear-gradient(135deg, #1890ff 0%, #40a9ff 100%)',
            border: 'none',
            borderRadius: '6px',
            color: '#fff',
            fontWeight: 500,
            boxShadow: '0 2px 6px rgba(24, 144, 255, 0.25)'
          }
        }}
        cancelButtonProps={{
          style: {
            borderRadius: '6px',
            border: '1px solid rgba(24, 144, 255, 0.2)',
            color: 'rgba(0, 0, 0, 0.65)',
            fontWeight: 500
          }
        }}
      >
        <div style={{ marginTop: '16px' }}>
          <div style={{ marginBottom: '16px' }}>
            <label
              style={{
                display: 'block',
                marginBottom: '8px',
                fontSize: '14px',
                color: '#2d2d2d',
              }}
            >
              {tRef.current('pages.memoryManager.selectCategory')}
            </label>
            <Select
              value={addForm.category}
              onChange={(value) => setAddForm({ ...addForm, category: value })}
              options={categoryOptions}
              placeholder={tRef.current('pages.memoryManager.selectCategory')}
              style={{ width: '100%' }}
            />
          </div>

          {addForm.category === '__new__' && (
            <div style={{ marginBottom: '16px' }}>
              <label
                style={{
                  display: 'block',
                  marginBottom: '8px',
                  fontSize: '14px',
                  color: '#2d2d2d',
                }}
              >
                {tRef.current('pages.memoryManager.categoryName')}
              </label>
              <Input
                value={addForm.newCategory}
                onChange={(e) => setAddForm({ ...addForm, newCategory: e.target.value })}
                placeholder={tRef.current('pages.memoryManager.categoryName')}
              />
            </div>
          )}

          <div>
            <label
              style={{
                display: 'block',
                marginBottom: '8px',
                fontSize: '14px',
                color: '#2d2d2d',
              }}
            >
              {tRef.current('pages.memoryManager.memoryContent')}
            </label>
            <TextArea
              value={addForm.content}
              onChange={(e) => setAddForm({ ...addForm, content: e.target.value })}
              placeholder={tRef.current('pages.memoryManager.memoryContent')}
              rows={4}
            />
          </div>
        </div>
      </Modal>
    </>
  );
};

export default MemoryDetailDrawer;
