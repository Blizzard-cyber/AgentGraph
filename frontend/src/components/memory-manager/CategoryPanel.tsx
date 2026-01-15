// src/components/memory-manager/CategoryPanel.tsx
import React from 'react';
import { Collapse, Typography, Space, App, Popconfirm, Pagination } from 'antd';
import type { CollapseProps } from 'antd';
import { ChevronDown, Trash2 } from 'lucide-react';
import { MemoryItem } from '../../types/memory';
import MemoryItemCard from './MemoryItemCard';
import { useT } from '../../i18n';

const { Text } = Typography;

interface CategoryPanelProps {
  category: string;
  items: MemoryItem[];
  ownerType: string;
  ownerId: string;
  onUpdate: (itemId: string, content: string) => void;
  onDelete: (itemIds: string[]) => void;
  onDeleteCategory: () => void;
  // pagination props
  page?: number; // 1-based
  pageSize?: number;
  total?: number;
  onPageChange?: (page: number) => void;
  // controlled expand state
  expanded?: boolean;
  onExpandedChange?: (expanded: boolean) => void;
}

const CategoryPanel: React.FC<CategoryPanelProps> = ({
  category,
  items,
  onUpdate,
  onDelete,
  onDeleteCategory,
  page = 1,
  pageSize = 20,
  total = 0,
  onPageChange,
  expanded,
  onExpandedChange,
}) => {
  const t = useT();
  const { modal } = App.useApp();



  const handleEditItem = (item: MemoryItem) => {
    // Use setTimeout to defer modal creation to avoid interfering with parent UI events (e.g., Tabs editing state)
    setTimeout(() => {
      modal.confirm({
        title: t('pages.memoryManager.editMemory'),
        content: (
          <textarea
            id={`edit-memory-content-${category}`}
            defaultValue={item.content}
            placeholder={t('pages.memoryManager.memoryContent')}
            aria-label={t('pages.memoryManager.memoryContent')}
            style={{
              width: '100%',
              minHeight: '120px',
              padding: '10px 14px',
              borderRadius: '6px',
              border: '1px solid rgba(139, 115, 85, 0.2)',
              background: 'rgba(255, 255, 255, 0.85)',
              fontSize: '14px',
              color: '#2d2d2d',
              resize: 'vertical',
            }}
          />
        ),
        okText: t('common.save'),
        cancelText: t('common.cancel'),
        okButtonProps: {
          style: {
            background: 'linear-gradient(135deg, #b85845 0%, #a0826d 100%)',
            border: 'none',
            borderRadius: '6px',
            color: '#fff',
            fontWeight: 500,
            boxShadow: '0 2px 6px rgba(184, 88, 69, 0.25)'
          }
        },
        cancelButtonProps: {
          style: {
            borderRadius: '6px',
            border: '1px solid rgba(139, 115, 85, 0.2)',
            color: '#8b7355',
            fontWeight: 500
          }
        },
        onOk: () => {
          const textarea = document.getElementById(`edit-memory-content-${category}`) as HTMLTextAreaElement;
          const newContent = textarea?.value?.trim();
          if (newContent && newContent !== item.content) {
            onUpdate(item.item_id, newContent);
          }
        },
      });
    }, 0);
  };

  const panelHeader = (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
      <Space size="middle">
        <Text
          strong
          style={{
            fontSize: '15px',
            color: '#2d2d2d',
            fontWeight: 500,
          }}
        >
          {category}
        </Text>
        <Text
          style={{
            fontSize: '12px',
            color: 'rgba(45, 45, 45, 0.65)',
          }}
        >
          {total} {t('pages.memoryManager.items')}
        </Text>
      </Space>
      <Popconfirm
        title={t('pages.memoryManager.deleteCategoryConfirm')}
        onConfirm={() => {
          // defer actual deletion call to avoid interfering with outer UI drag/edit operations
          setTimeout(() => onDeleteCategory(), 0);
        }}
        okText={t('common.confirm')}
        cancelText={t('common.cancel')}
        okButtonProps={{
          style: {
            background: 'linear-gradient(135deg, #b85845 0%, #a0826d 100%)',
            border: 'none',
            borderRadius: '6px',
            color: '#fff',
            fontWeight: 500,
            boxShadow: '0 2px 6px rgba(184, 88, 69, 0.25)'
          }
        }}
        cancelButtonProps={{
          style: {
            borderRadius: '6px',
            border: '1px solid rgba(139, 115, 85, 0.2)',
            color: '#8b7355',
            fontWeight: 500
          }
        }}
        styles={{ body: { borderRadius: '8px', boxShadow: '0 4px 12px rgba(139, 115, 85, 0.2)' } }}
      >
        <div
          role="button"
          tabIndex={0}
          onClick={(e) => e.stopPropagation()}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.stopPropagation();
            }
          }}
          aria-label={t('pages.memoryManager.deleteCategory')}
          style={{
            padding: '4px',
            borderRadius: '4px',
            color: '#8b7355',
            cursor: 'pointer',
            transition: 'all 0.2s ease',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.color = '#b85845';
            e.currentTarget.style.background = 'rgba(184, 88, 69, 0.08)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.color = '#8b7355';
            e.currentTarget.style.background = 'transparent';
          }}
        >
          <Trash2 size={14} strokeWidth={1.5} />
        </div>
      </Popconfirm>
    </div>
  );

  const collapseItems: CollapseProps['items'] = [
    {
      key: category,
      label: panelHeader,
      children: (
        <div style={{ padding: '8px 0' }}>
          {items.length > 0 ? (
            items.map((item) => (
              <MemoryItemCard
                key={item.item_id}
                item={item}
                onEdit={() => handleEditItem(item)}
                onDelete={() => onDelete([item.item_id])}
              />
            ))
          ) : (
            <Text type="secondary" style={{ display: 'block', textAlign: 'center', marginTop: 12 }}>
              {t('pages.memoryManager.noItems')}
            </Text>
          )}

          {/* per-category pagination */}
          {total > pageSize && onPageChange && (
            <div style={{ textAlign: 'center', marginTop: 12 }}>
              <Pagination
                current={page}
                pageSize={pageSize}
                total={total}
                onChange={(p) => onPageChange(p)}
                showSizeChanger={false}
              />
            </div>
          )}
        </div>
      ),
      style: {
        border: 'none',
      },
    },
  ];

  return (
    <Collapse
      items={collapseItems}
      activeKey={expanded ? category : undefined}
      onChange={(keys) => {
        const isActive = Array.isArray(keys) ? keys.includes(category) : keys === category;
        onExpandedChange?.(isActive);
      }}
      expandIcon={({ isActive }) => (
        <ChevronDown
          size={18}
          strokeWidth={2}
          style={{
            color: '#8b7355',
            transform: isActive ? 'rotate(180deg)' : 'rotate(0deg)',
            transition: 'transform 0.3s ease',
          }}
        />
      )}
      style={{
        marginBottom: '16px',
        borderRadius: '8px',
        border: '1px solid rgba(139, 115, 85, 0.15)',
        background: 'rgba(250, 248, 245, 0.6)',
        overflow: 'hidden',
      }}
    />
  );
};

export default CategoryPanel;
