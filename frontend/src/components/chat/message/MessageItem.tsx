// 单条消息项组件
import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ConversationMessage, TaskRoundData } from '../../../types/conversation';
import { getCurrentUserDisplayName } from '../../../config/user';
import ReasoningDisplay from './ReasoningDisplay';
import SmartMarkdown from './SmartMarkdown';
import GlassCodeBlock from './GlassCodeBlock';
import ToolCallDisplay from './ToolCallDisplay';
import NodeExecutionInfo from './NodeExecutionInfo';
import StaticTaskBlock from './StaticTaskBlock';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { useT } from '../../../i18n/hooks';

interface MessageItemProps {
  message: ConversationMessage;
  showTyping?: boolean;
  toolResults?: Record<string, string>;
  taskRoundDataMap?: Record<string, TaskRoundData>;
  nodeInfo?: {
    nodeName: string;
    level: number;
    outputEnabled?: string;
    mcpServers?: string[];
    status: 'running' | 'completed' | 'pending';
  };
  reasoningContent?: string;
  isGraphMode?: boolean;
  isFirstMessageInRound?: boolean;
  renderingMode: 'chat' | 'agent' | 'graph_run';
  conversationId?: string;
}

/**
 * 单条消息项组件
 * 渲染用户或助手的单条消息
 */
const MessageItem: React.FC<MessageItemProps> = ({
  message,
  showTyping = false,
  toolResults = {},
  taskRoundDataMap = {},
  nodeInfo,
  reasoningContent,
  isGraphMode = false,
  isFirstMessageInRound = false,
  renderingMode,
  conversationId
}) => {
  const isUser = message.role === 'user';
  const isSystem = message.role === 'system';

  // 思考框展开状态
  const [thinkingExpanded, setThinkingExpanded] = useState(false);

  const t = useT();

  // 处理思考标签的函数
  const parseThinkingContent = (content: string) => {
    const thinkRegex = /<think>([\s\S]*?)<\/think>/g;
    const parts = [];
    let lastIndex = 0;
    let match;

    while ((match = thinkRegex.exec(content)) !== null) {
      // 添加思考标签前的文本
      if (match.index > lastIndex) {
        parts.push({
          type: 'text',
          content: content.slice(lastIndex, match.index)
        });
      }

      // 添加思考内容
      parts.push({
        type: 'thinking',
        content: match[1].trim()
      });

      lastIndex = match.index + match[0].length;
    }

    // 添加剩余的文本
    if (lastIndex < content.length) {
      parts.push({
        type: 'text',
        content: content.slice(lastIndex)
      });
    }

    return parts;
  };
  const isTool = message.role === 'tool';

  // 优先使用消息自带的reasoning_content，其次使用流式传入的reasoningContent
  const effectiveReasoningContent = (message as any).reasoning_content || reasoningContent;

  // 基础过滤：不显示系统消息和工具结果消息
  if (isSystem || isTool) {
    return null;
  }

  // Graph执行模式下的特殊处理：如果是用户消息且没有节点信息，则不显示
  if (renderingMode === 'graph_run' && isUser && !nodeInfo) {
    return null;
  }

  return (
    <div style={{
      marginBottom: '24px',
      color: '#2d2d2d',
      lineHeight: '1.7',
      fontSize: '16px',
      letterSpacing: '0.3px',
      fontFamily: "Cambria, Georgia, 'Times New Roman', serif, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', serif"
    }}>
      {/* 呼吸灯指示器 - 改为墨点效果 */}
      {isFirstMessageInRound && renderingMode !== 'graph_run' && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          marginBottom: '10px',
          gap: '8px'
        }}>
          <div style={{
            width: '8px',
            height: '8px',
            borderRadius: '50%',
            background: isUser ? '#a0826d' : '#b85845',
            boxShadow: isUser
              ? '0 0 0 0 rgba(160, 130, 109, 0.4)'
              : '0 0 0 0 rgba(184, 88, 69, 0.4)',
            animation: 'inkDotPulse 2s ease-in-out infinite'
          }} />
          <span style={{
            fontSize: '13px',
            fontWeight: 500,
            color: 'rgba(45, 45, 45, 0.65)',
            letterSpacing: '0.3px'
          }}>
            {isUser ? getCurrentUserDisplayName() : (renderingMode === 'agent' ? 'Agent' : 'Assistant')}
          </span>
        </div>
      )}

      {/* Graph执行模式的节点信息 */}
      {nodeInfo && (
        <NodeExecutionInfo {...nodeInfo} />
      )}

      {/* Graph执行模式下用户消息：只有start节点显示消息内容，其他节点不显示 */}
      {!(renderingMode === 'graph' && isUser && nodeInfo?.nodeName !== 'start') && (
        <div style={isUser ? {
          background: 'rgba(212, 196, 176, 0.15)',
          border: '1px solid rgba(139, 115, 85, 0.2)',
          borderRadius: '8px',
          padding: '14px 16px',
          boxShadow: '0 1px 3px rgba(139, 115, 85, 0.06), inset 0 1px 0 rgba(255, 255, 255, 0.6)',
          maxHeight: '30rem',
          overflow: 'auto',
          scrollbarWidth: 'thin',
          scrollbarColor: 'rgba(139, 115, 85, 0.3) rgba(139, 115, 85, 0.08)'
        } : {}} className={isUser ? 'user-message-scrollbar' : ''}>
          <div>
            {/* AI思考过程优先显示 */}
            {effectiveReasoningContent && (
              <ReasoningDisplay content={effectiveReasoningContent} />
            )}

            {/* 主要消息内容 */}
            {message.content && (
              <div style={{
                color: '#2d2d2d',
                lineHeight: '1.7',
                fontSize: '16px',
                letterSpacing: '0.3px',
                fontFamily: "Cambria, Georgia, 'Times New Roman', serif, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', serif"
              }}>
                <div>
                  {showTyping ? (
                    <div>
                      {/* 流式消息使用 SmartMarkdown 渲染，支持代码块 */}
                      <SmartMarkdown
                        content={message.content}
                        isStreaming={true}
                        conversationId={conversationId}
                      />
                    </div>
                  ) : (
                    // 解析并渲染包含思考标签的内容
                    (() => {
                      const contentParts = parseThinkingContent(message.content);
                      return contentParts.map((part, index) => {
                        if (part.type === 'thinking') {
                          return (
                            <div key={index} style={{
                              margin: '16px 0',
                              border: '1px solid rgba(139, 115, 85, 0.15)',
                              borderRadius: '8px',
                              overflow: 'hidden'
                            }}>
                              {/* 思考框头部 */}
                              <div
                                style={{
                                  padding: '8px 16px',
                                  background: 'rgba(139, 115, 85, 0.06)',
                                  borderBottom: thinkingExpanded ? '1px solid rgba(139, 115, 85, 0.15)' : 'none',
                                  cursor: 'pointer',
                                  display: 'flex',
                                  alignItems: 'center',
                                  justifyContent: 'space-between',
                                  transition: 'all 0.2s ease'
                                }}
                                onClick={() => setThinkingExpanded(!thinkingExpanded)}
                                onMouseEnter={(e) => {
                                  e.currentTarget.style.background = 'rgba(139, 115, 85, 0.08)';
                                }}
                                onMouseLeave={(e) => {
                                  e.currentTarget.style.background = 'rgba(139, 115, 85, 0.06)';
                                }}
                              >
                                <div style={{
                                  display: 'flex',
                                  alignItems: 'center',
                                  gap: '8px'
                                }}>
                                  {thinkingExpanded ? (
                                    <ChevronDown size={14} style={{ color: 'rgba(160, 130, 109, 0.8)' }} />
                                  ) : (
                                    <ChevronRight size={14} style={{ color: 'rgba(160, 130, 109, 0.8)' }} />
                                  )}
                                  <span style={{
                                    fontSize: '12px',
                                    fontWeight: 600,
                                    color: 'rgba(160, 130, 109, 0.8)',
                                    textTransform: 'uppercase',
                                    letterSpacing: '0.5px'
                                  }}>
                                    💭 {t('common.thinkingProcess')}
                                  </span>
                                  <span style={{
                                    fontSize: '11px',
                                    color: 'rgba(45, 45, 45, 0.5)',
                                    background: 'rgba(139, 115, 85, 0.1)',
                                    padding: '2px 6px',
                                    borderRadius: '10px'
                                  }}>
                                    {part.content.split('\n').length} {t('common.lines')}
                                  </span>
                                </div>
                              </div>

                              {/* 思考框内容 */}
                              {thinkingExpanded && (
                                <div style={{
                                  padding: '12px 16px',
                                  background: 'rgba(255, 255, 255, 0.5)',
                                  fontSize: '14px',
                                  color: 'rgba(45, 45, 45, 0.75)',
                                  lineHeight: '1.6',
                                  fontStyle: 'italic'
                                }}>
                                  <div style={{
                                    whiteSpace: 'pre-wrap',
                                    wordBreak: 'break-word'
                                  }}>
                                    {part.content}
                                  </div>
                                </div>
                              )}
                            </div>
                          );
                        } else {
                          return (
                            <ReactMarkdown
                              key={index}
                              remarkPlugins={[remarkGfm]}
                              components={{
                                code({ node, ...codeProps }) {
                                  const { children: codeChildren, className: codeClassName, ...restProps } = codeProps;
                                  const match = /language-(\w+)/.exec(codeClassName || '');
                                  const language = match ? match[1] : '';
                                  const inline = !match;

                                  return !inline ? (
                                    <GlassCodeBlock
                                      language={language}
                                      conversationId={conversationId}
                                    >
                                      {String(codeChildren).replace(/\n$/, '')}
                                    </GlassCodeBlock>
                                  ) : (
                                    <code style={{
                                      background: 'rgba(139, 115, 85, 0.08)',
                                      padding: '2px 6px',
                                      borderRadius: '3px',
                                      fontSize: '0.9em',
                                      fontFamily: "'SF Mono', monospace",
                                      color: '#b85845'
                                    }} {...restProps}>
                                      {codeChildren}
                                    </code>
                                  );
                                }
                              }}
                            >
                              {part.content}
                            </ReactMarkdown>
                          );
                        }
                      });
                    })()
                  )}
                </div>
              </div>
            )}

            {/* 工具调用 */}
            {message.tool_calls && message.tool_calls.length > 0 && (
              <div style={{ marginTop: '12px' }}>
                {message.tool_calls.map((toolCall, index) => (
                  <React.Fragment key={toolCall.id || index}>
                    <ToolCallDisplay
                      toolCall={toolCall}
                      result={toolCall.id ? toolResults[toolCall.id] : undefined}
                      conversationId={conversationId}
                    />
                    {/* 在工具调用下方显示对应的 Task */}
                    {toolCall.id && taskRoundDataMap[toolCall.id] && (
                      <StaticTaskBlock
                        taskData={{
                          task_id: taskRoundDataMap[toolCall.id].task_id,
                          agent_name: taskRoundDataMap[toolCall.id].agent_name,
                          rounds: [taskRoundDataMap[toolCall.id].round]
                        }}
                        toolCallId={toolCall.id}
                        toolResults={toolResults}
                        conversationId={conversationId}
                      />
                    )}
                  </React.Fragment>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
export default MessageItem;
