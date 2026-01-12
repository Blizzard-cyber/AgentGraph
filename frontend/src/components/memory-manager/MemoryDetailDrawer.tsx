// src/components/memory-manager/MemoryDetailDrawer.tsx
import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Drawer, Button, Spin, Empty, Modal, Input, Select, message } from 'antd';
import { Plus } from 'lucide-react';
import { MemoryDetail } from '../../types/memory';
import { getOwnerMemories, getOwnerMemoriesV1, addMemoryItem, updateMemoryItem, batchDeleteItems, batchDeleteCategories } from '../../services/memoryService';
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
type MaybePagedMemoryDetail = MemoryDetail & { total_items?: number };

const MemoryDetailDrawer: React.FC<MemoryDetailDrawerProps> = ({
  visible,
  owner,
  onClose,
  onRefresh,
}) => {
  const t = useT();
  // keep a ref to the translation function so fetchMemoryDetail doesn't need `t` in deps
  const tRef = useRef<typeof t>(t);
  useEffect(() => { tRef.current = t; }, [t]);

  const [memoryData, setMemoryData] = useState<MemoryDetail | null>(null);
  // also keep memoryData in a ref for use inside the stable fetch
  const memoryDataRef = useRef<MemoryDetail | null>(null);
  useEffect(() => { memoryDataRef.current = memoryData; }, [memoryData]);

  const [loading, setLoading] = useState<boolean>(false);
  const [addModalVisible, setAddModalVisible] = useState<boolean>(false);
  const [addForm, setAddForm] = useState({ category: '', newCategory: '', content: '' });

  // Pagination state per category (0-based indices)
  const [categoryPageMap, setCategoryPageMap] = useState<Record<string, number>>({});
  const categoryPageRef = useRef<Record<string, number>>({});
  useEffect(() => { categoryPageRef.current = categoryPageMap; }, [categoryPageMap]);

  const pageSize = 20; // per requirement

  // guard against overlapping fetches
  const isFetchingRef = useRef(false);

  // track last owner id we fetched for to avoid re-fetch loops when owner object identity changes
  const lastOwnerIdRef = useRef<string | null>(null);

  // stable fetch function (no translation or state deps) referenced via fetchRef
  const fetchRef = useRef<(fetchCategory?: string, fetchPage?: number) => Promise<void>>();

  const fetchMemoryDetail = useCallback(async (fetchCategory?: string, fetchPage?: number) => {
    if (!owner) return;
    if (isFetchingRef.current) return;
    isFetchingRef.current = true;
    setLoading(true);
    try {
      // Only fetch original full data when not fetching a single category (initial load or full refresh)
      let origResp = null;
      if (!fetchCategory) {
        origResp = await getOwnerMemories(owner.type, owner.id).catch((e) => {
          console.warn('getOwnerMemories failed:', e);
          return null;
        });
      }

      const merged: MemoryDetail = { owner_type: owner.type as 'user' | 'agent', owner_id: owner.id, memories: {} };

      // Merge original data (filter out 'episode') if loaded
      if (origResp && origResp.status === 'success' && origResp.data) {
        const data: MaybePagedMemoryDetail = origResp.data;
        const srcMemories = data.memories || {};
        Object.keys(srcMemories).forEach((cat) => {
          if (cat === 'episode') return; // filter out episode from original
          const srcCat = srcMemories[cat];
          if (!srcCat) return;
          const items = Array.isArray(srcCat.items) ? srcCat.items.slice() : [];
          const total = typeof srcCat.total === 'number' ? srcCat.total : items.length;
          merged.memories[cat] = { items, total };
        });
      } else {
        // fallback to existing memoryData if present (avoid clearing when only fetching one category)
        const existing = memoryDataRef.current;
        if (existing && existing.memories) {
          Object.keys(existing.memories).forEach((cat) => {
            if (cat === 'episode') return;
            merged.memories[cat] = { ...existing.memories[cat] };
          });
        }
      }

      // Determine which categories to fetch from v1
      // - If this is initial load (no fetchCategory): we only need to fetch 'episode' from v1 (server-paged)
      // - If fetchCategory provided and it's 'episode', fetch that page from v1
      // - If fetchCategory provided and it's non-episode, we do not fetch v1 (client-side pagination)
      const categoriesToFetch: string[] = [];
      if (!fetchCategory) {
        categoriesToFetch.push('episode');
      } else if (fetchCategory === 'episode') {
        categoriesToFetch.push('episode');
      }

      // Ensure category page map has entries for merged categories (non-episode)
      const categories = Object.keys(merged.memories);
      setCategoryPageMap((prev) => {
        const copy = { ...prev };
        let changed = false;
        categories.forEach((c) => {
          if (typeof copy[c] !== 'number') { copy[c] = 0; changed = true; }
        });
        if (changed) { categoryPageRef.current = { ...copy }; return copy; }
        return prev;
      });

      // Fetch v1 only for categoriesToFetch (episode)
      const pagedPromises = categoriesToFetch.map((cat) => {
        const page = (cat === 'episode' && typeof fetchPage === 'number') ? fetchPage : 0;
        return getOwnerMemoriesV1(owner.type, owner.id, page, pageSize, cat)
          .then((r) => ({ cat, resp: r }))
          .catch((e) => { console.warn('getOwnerMemoriesV1 failed for', cat, e); return { cat, resp: null }; });
      });

      const pagedResults = await Promise.all(pagedPromises);

      pagedResults.forEach(({ cat, resp }) => {
        if (!resp || resp.status !== 'success' || !resp.data) return;
        const data: MaybePagedMemoryDetail = resp.data;
        const srcCat = data.memories ? data.memories[cat] : undefined;
        if (srcCat) {
          const items = Array.isArray(srcCat.items) ? srcCat.items.slice() : [];
          const total = typeof srcCat.total === 'number' ? srcCat.total : items.length;
          merged.memories[cat] = { items, total };
        }
      });

      setMemoryData(merged);
    } catch (error) {
      console.error('Failed to load memory detail:', error);
      message.error(tRef.current('pages.memoryManager.loadError'));
    } finally {
      setLoading(false);
      isFetchingRef.current = false;
    }
  }, [owner, pageSize]);

  // expose stable fetch via ref to avoid useEffect dependency cycles
  useEffect(() => { fetchRef.current = fetchMemoryDetail; }, [fetchMemoryDetail]);

  // initial load when visible/owner changes - only fetch once per owner id to avoid loops
  useEffect(() => {
    if (visible && owner) {
      // if owner id changed (or first open), reset and fetch; otherwise do not auto-refetch
      if (lastOwnerIdRef.current !== owner.id) {
        lastOwnerIdRef.current = owner.id;
        setCategoryPageMap({});
        categoryPageRef.current = {};
        fetchRef.current?.();
      }
    } else if (!visible) {
      // when the drawer is closed, clear the lastOwnerIdRef so reopening triggers a fresh fetch
      lastOwnerIdRef.current = null;
    }
  }, [visible, owner]);

  // handlers now call fetchRef.current to avoid creating cycles
  const handleCategoryPageChange = (category: string, page1Based: number) => {
    const page0 = page1Based - 1;
    setCategoryPageMap((prev) => ({ ...prev, [category]: page0 }));
    categoryPageRef.current = { ...categoryPageRef.current, [category]: page0 };
    fetchRef.current?.(category, page0);
  };

  const handleAddMemory = () => { setAddForm({ category: '', newCategory: '', content: '' }); setAddModalVisible(true); };

  const handleAddSubmit = async () => {
    if (!owner) return;
    const category = addForm.category === '__new__' ? addForm.newCategory : addForm.category;
    if (!category || !addForm.content) { message.warning(tRef.current('pages.memoryManager.fillRequired')); return; }
    try {
      const response = await addMemoryItem(owner.type, owner.id, category, { content: addForm.content });
      if (response.status === 'success') {
        message.success(tRef.current('pages.memoryManager.addSuccess'));
        setAddModalVisible(false);
        setCategoryPageMap((prev) => ({ ...prev, [category]: 0 }));
        categoryPageRef.current = { ...categoryPageRef.current, [category]: 0 };
        fetchRef.current?.(category, 0);
        onRefresh();
      } else {
        message.error(tRef.current('pages.memoryManager.addFailed', { error: response.message || '' }));
      }
    } catch (error) {
      console.error('Failed to add memory:', error);
      message.error(tRef.current('pages.memoryManager.addError'));
    }
  };

  const handleUpdateItem = async (category: string, itemId: string, content: string) => {
    if (!owner) return;
    try {
      const response = await updateMemoryItem(owner.type, owner.id, category, itemId, { content });
      if (response.status === 'success') {
        message.success(tRef.current('pages.memoryManager.updateSuccess'));
        fetchRef.current?.(category);
        onRefresh();
      } else {
        message.error(tRef.current('pages.memoryManager.updateFailed', { error: response.message || '' }));
      }
    } catch (error) {
      console.error('Failed to update memory:', error);
      message.error(tRef.current('pages.memoryManager.updateError'));
    }
  };

  const handleDeleteItems = async (category: string, itemIds: string[]) => {
    if (!owner) return;
    try {
      const response = await batchDeleteItems(owner.type, owner.id, category, itemIds);
      if (response.status === 'success') {
        message.success(tRef.current('pages.memoryManager.deleteSuccess'));
        fetchRef.current?.(category);
        onRefresh();
      } else if (response.status === 'partial_success') {
        message.warning(tRef.current('pages.memoryManager.deletePartialSuccess', { success: response.data?.deleted_count || 0, failed: response.data?.failed_count || 0 }));
        fetchRef.current?.(category);
        onRefresh();
      } else {
        message.error(tRef.current('pages.memoryManager.deleteFailed', { error: response.message || '' }));
      }
    } catch (error) {
      console.error('Failed to delete items:', error);
      message.error(tRef.current('pages.memoryManager.deleteError'));
    }
  };

  const handleDeleteCategory = async (category: string) => {
    if (!owner) return;
    try {
      const response = await batchDeleteCategories(owner.type, owner.id, [category]);
      if (response.status === 'success') {
        message.success(tRef.current('pages.memoryManager.deleteCategorySuccess'));
        setCategoryPageMap((prev) => { const copy = { ...prev }; delete copy[category]; return copy; });
        categoryPageRef.current = Object.keys(categoryPageRef.current).reduce((acc, k) => { if (k !== category) acc[k] = categoryPageRef.current[k]; return acc; }, {} as Record<string, number>);
        fetchRef.current?.();
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
  const categoryOptions = [ { label: tRef.current('pages.memoryManager.newCategory'), value: '__new__' }, ...categories.map((cat) => ({ label: cat, value: cat })) ];

  return (
    <>
      <Drawer
        title={<div style={{ fontSize: '16px', fontWeight: 500, color: '#2d2d2d' }}>{owner ? `${owner.type === 'user' ? tRef.current('pages.memoryManager.user') : tRef.current('pages.memoryManager.agent')}: ${owner.id}` : ''}</div>}
        placement="right"
        width={720}
        onClose={onClose}
        open={visible}
        styles={{ body: { padding: '24px', background: '#faf8f5' } }}
        extra={
          <Button type="primary" icon={<Plus size={16} strokeWidth={1.5} />} onClick={handleAddMemory} style={{ background: 'linear-gradient(135deg, #b85845 0%, #a0826d 100%)', border: 'none', borderRadius: '6px', fontWeight: 500, boxShadow: '0 2px 6px rgba(184, 88, 69, 0.25)' }}>{tRef.current('pages.memoryManager.addMemory')}</Button>
        }
      >
        {loading ? (
          <div style={{ textAlign: 'center', padding: '60px 0' }}><Spin size="large" /></div>
        ) : !memoryData || categories.length === 0 ? (
          <Empty description={tRef.current('pages.memoryManager.noMemories')} style={{ marginTop: '60px' }} />
        ) : (
          <div>
            {categories.map((category) => {
              // compute items to display per category
              const catMem = memoryData.memories[category];
              let displayItems = catMem.items;
              const isEpisode = category === 'episode';
              const pageForCat = categoryPageMap[category] ?? 0;
              if (!isEpisode) {
                // client-side paginate non-episode categories
                const start = pageForCat * pageSize;
                displayItems = (catMem.items || []).slice(start, start + pageSize);
              }

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
                  page={(pageForCat + 1)}
                  pageSize={pageSize}
                  total={catMem.total}
                  onPageChange={(page1: number) => {
                    // for episode, fetch server page; for others, just change page map
                    if (category === 'episode') {
                      handleCategoryPageChange(category, page1);
                    } else {
                      setCategoryPageMap((prev) => ({ ...prev, [category]: page1 - 1 }));
                    }
                  }}
                />
              );
            })}
          </div>
        )}
      </Drawer>

      <Modal title={tRef.current('pages.memoryManager.addMemory')} open={addModalVisible} onOk={handleAddSubmit} onCancel={() => setAddModalVisible(false)} okText={tRef.current('common.create')} cancelText={tRef.current('common.cancel')} okButtonProps={{ style: { background: 'linear-gradient(135deg, #b85845 0%, #a0826d 100%)', border: 'none', borderRadius: '6px', color: '#fff', fontWeight: 500, boxShadow: '0 2px 6px rgba(184, 88, 69, 0.25)' } }} cancelButtonProps={{ style: { borderRadius: '6px', border: '1px solid rgba(139, 115, 85, 0.2)', color: '#8b7355', fontWeight: 500 } }}>
        <div style={{ marginTop: '16px' }}>
          <div style={{ marginBottom: '16px' }}>
            <label style={{ display: 'block', marginBottom: '8px', fontSize: '14px', color: '#2d2d2d' }}>{tRef.current('pages.memoryManager.selectCategory')}</label>
            <Select value={addForm.category} onChange={(value) => setAddForm({ ...addForm, category: value })} options={categoryOptions} placeholder={tRef.current('pages.memoryManager.selectCategory')} style={{ width: '100%' }} />
          </div>

          {addForm.category === '__new__' && (
            <div style={{ marginBottom: '16px' }}>
              <label style={{ display: 'block', marginBottom: '8px', fontSize: '14px', color: '#2d2d2d' }}>{tRef.current('pages.memoryManager.categoryName')}</label>
              <Input value={addForm.newCategory} onChange={(e) => setAddForm({ ...addForm, newCategory: e.target.value })} placeholder={tRef.current('pages.memoryManager.categoryName')} />
            </div>
          )}

          <div>
            <label style={{ display: 'block', marginBottom: '8px', fontSize: '14px', color: '#2d2d2d' }}>{tRef.current('pages.memoryManager.memoryContent')}</label>
            <TextArea value={addForm.content} onChange={(e) => setAddForm({ ...addForm, content: e.target.value })} placeholder={tRef.current('pages.memoryManager.memoryContent')} rows={4} />
          </div>
        </div>
      </Modal>
    </>
  );
};

export default MemoryDetailDrawer;
