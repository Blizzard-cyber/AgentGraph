import React, { useState, useEffect } from 'react';
import { Modal, Table, Button, message, Space, Tag, Typography } from 'antd';
import { Download, Cloud, RefreshCw } from 'lucide-react';
import { CloudAgent, listCloudAgents, importFromCloud } from '../../services/agentService';
import { useT } from '../../i18n/hooks';

const { Text } = Typography;

interface CloudImportModalProps {
    visible: boolean;
    onClose: () => void;
    onSuccess: () => void;
}

/**
 * 云端Agent导入模态框
 */
const CloudImportModal: React.FC<CloudImportModalProps> = ({ visible, onClose, onSuccess }) => {
    const t = useT();
    const [loading, setLoading] = useState(false);
    const [importing, setImporting] = useState<number | null>(null);
    const [cloudAgents, setCloudAgents] = useState<CloudAgent[]>([]);

    // 加载云端Agent列表
    const loadCloudAgents = async () => {
        setLoading(true);
        try {
            const response = await listCloudAgents();
            setCloudAgents(response.agents || []);
        } catch (error: any) {
            message.error('获取云端Agent列表失败: ' + (error.response?.data?.detail || error.message));
        } finally {
            setLoading(false);
        }
    };

    // 导入Agent
    const handleImport = async (agent: CloudAgent) => {
        setImporting(agent.id);
        try {
            await importFromCloud(agent.id, agent.name);
            message.success(`成功导入 Agent: ${agent.name}`);
            onSuccess();
        } catch (error: any) {
            message.error('导入失败: ' + (error.response?.data?.detail || error.message));
        } finally {
            setImporting(null);
        }
    };

    // 格式化文件大小
    const formatFileSize = (bytes: number) => {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    };

    // 组件加载时获取云端列表
    useEffect(() => {
        if (visible) {
            loadCloudAgents();
        }
    }, [visible]);

    const columns = [
        {
            title: 'Agent名称',
            dataIndex: 'name',
            key: 'name',
            width: 200,
            render: (name: string, record: CloudAgent) => (
                <Space direction="vertical" size={0}>
                    <Text strong style={{ color: '#2d2d2d' }}>{name}</Text>
                    <Text type="secondary" style={{ fontSize: '12px' }}>版本: {record.version}</Text>
                </Space>
            ),
        },
        {
            title: '描述',
            dataIndex: 'description',
            key: 'description',
            ellipsis: true,
        },
        {
            title: '状态',
            dataIndex: 'status',
            key: 'status',
            width: 80,
            render: (status: string) => (
                <Tag color={status === 'active' ? 'green' : 'default'}>
                    {status === 'active' ? '可用' : status}
                </Tag>
            ),
        },
        {
            title: '大小',
            dataIndex: 'size',
            key: 'size',
            width: 100,
            render: (size: number) => (
                <Text style={{ fontSize: '12px' }}>{formatFileSize(size)}</Text>
            ),
        },
        {
            title: '创建者',
            dataIndex: 'creator',
            key: 'creator',
            width: 100,
        },
        {
            title: '操作',
            key: 'action',
            width: 100,
            render: (_: any, record: CloudAgent) => (
                <Button
                    type="primary"
                    size="small"
                    icon={<Download size={14} />}
                    loading={importing === record.id}
                    onClick={() => handleImport(record)}
                    style={{
                        background: 'linear-gradient(135deg, #b85845 0%, #a64a38 100%)',
                        border: 'none',
                        borderRadius: '6px',
                        boxShadow: '0 2px 8px rgba(184, 88, 69, 0.2)',
                    }}
                >
                    导入
                </Button>
            ),
        },
    ];

    return (
        <Modal
            title={
                <Space>
                    <Cloud size={20} color="#b85845" />
                    <span>云端Agent仓库</span>
                </Space>
            }
            open={visible}
            onCancel={onClose}
            footer={null}
            width={1000}
            styles={{
                body: { padding: '24px' }
            }}
        >
            <Space direction="vertical" style={{ width: '100%' }} size="large">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Text type="secondary">
                        从云端仓库选择并导入Agent配置
                    </Text>
                    <Button
                        icon={<RefreshCw size={14} />}
                        onClick={loadCloudAgents}
                        loading={loading}
                        style={{
                            borderRadius: '6px',
                            border: '1.5px solid rgba(184, 88, 69, 0.2)',
                            color: '#b85845',
                        }}
                    >
                        刷新列表
                    </Button>
                </div>

                <Table
                    columns={columns}
                    dataSource={cloudAgents}
                    loading={loading}
                    rowKey="id"
                    pagination={{
                        pageSize: 10,
                        showSizeChanger: false,
                        showTotal: (total) => `共 ${total} 个Agent`,
                    }}
                    style={{
                        background: 'white',
                        borderRadius: '8px',
                    }}
                />
            </Space>
        </Modal>
    );
};

export default CloudImportModal;
