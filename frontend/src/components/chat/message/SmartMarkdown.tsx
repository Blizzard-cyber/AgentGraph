// 智能Markdown渲染器组件
import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import GlassCodeBlock from './GlassCodeBlock';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { useT } from '../../../i18n/hooks';

interface SmartMarkdownProps {
  content: string;
  isStreaming?: boolean;
  conversationId?: string;
}

/**
 * 智能Markdown渲染器
 * 支持流式输出时的代码块实时渲染
 */
const SmartMarkdown: React.FC<SmartMarkdownProps> = ({
  content,
  isStreaming = false,
  conversationId
}) => {
  // 思考框展开状态映射
  const [thinkingStates, setThinkingStates] = useState<Record<number, boolean>>({});

  // 切换思考框展开状态
  const toggleThinking = (index: number) => {
    setThinkingStates(prev => ({
      ...prev,
      [index]: !prev[index]
    }));
  };

  const t = useT();
  // 处理思考标签的函数
  const parseThinkingContent = (text: string) => {
    const thinkRegex = /<think>([\s\S]*?)<\/think>/g;
    const parts = [];
    let lastIndex = 0;
    let match;

    while ((match = thinkRegex.exec(text)) !== null) {
      // 添加思考标签前的文本
      if (match.index > lastIndex) {
        parts.push({
          type: 'text',
          content: text.slice(lastIndex, match.index)
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
    if (lastIndex < text.length) {
      parts.push({
        type: 'text',
        content: text.slice(lastIndex)
      });
    }

    return parts;
  };
  // 解析内容中的代码块状态
  const parseCodeBlocks = (text: string) => {
    const codeBlocks: { type: string; content: string; isComplete: boolean; startIndex: number; endIndex: number }[] = [];
    const lines = text.split('\n');
    let currentBlock: { type: string; content: string; startIndex: number } | null = null;
    let currentLineIndex = 0;

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const currentPos = currentLineIndex;
      currentLineIndex += line.length + 1; // +1 for newline

      if (line.startsWith('```')) {
        if (currentBlock) {
          // 结束当前代码块
          codeBlocks.push({
            type: currentBlock.type,
            content: currentBlock.content,
            isComplete: true,
            startIndex: currentBlock.startIndex,
            endIndex: currentPos + line.length
          });
          currentBlock = null;
        } else {
          // 开始新代码块
          const type = line.slice(3).trim() || 'text';
          currentBlock = {
            type,
            content: '',
            startIndex: currentPos
          };
        }
      } else if (currentBlock) {
        // 添加到当前代码块
        currentBlock.content += (currentBlock.content ? '\n' : '') + line;
      }
    }

    // 如果有未完成的代码块（流式输出中）
    if (currentBlock) {
      codeBlocks.push({
        type: currentBlock.type,
        content: currentBlock.content,
        isComplete: false,
        startIndex: currentBlock.startIndex,
        endIndex: text.length
      });
    }

    return codeBlocks;
  };

  const parsed = parseCodeBlocks(content);
  const tail = parsed.length > 0 ? parsed[parsed.length - 1] : null;
  const hasIncompleteTail = isStreaming && tail && !tail.isComplete;

  // 渲染代码块的通用组件配置
  const codeComponent = ({ node, ...codeProps }: any) => {
    const { children: codeChildren, className: codeClassName, ...restProps } = codeProps;
    const match = /language-(\w+)/.exec(codeClassName || '');
    const lang = match ? match[1] : '';
    const inline = !match;
    return !inline ? (
      <GlassCodeBlock language={lang} isStreaming={false} conversationId={conversationId}>
        {String(codeChildren).replace(/\n$/, '')}
      </GlassCodeBlock>
    ) : (
      <code style={{
        background: 'rgba(24, 144, 255, 0.08)',
        padding: '2px 6px',
        borderRadius: '3px',
        fontSize: '0.9em',
        fontFamily: "'SF Mono', monospace",
        color: '#1890ff'
      }} {...restProps}>
        {codeChildren}
      </code>
    );
  };

  if (hasIncompleteTail) {
    const before = content.slice(0, tail.startIndex);
    const language = tail.type || 'text';
    const codeText = tail.content || '';

    return (
      <div style={{
        fontFamily: "Cambria, Georgia, 'Times New Roman', serif, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', serif",
        fontSize: 'inherit'
      }}>
        {before && (() => {
          const contentParts = parseThinkingContent(before);
          return contentParts.map((part, index) => {
            if (part.type === 'thinking') {
              const isExpanded = thinkingStates[index] || false;
              return (
                <div key={index} style={{
                  margin: '16px 0',
                  border: '1px solid rgba(24, 144, 255, 0.15)',
                  borderRadius: '8px',
                  overflow: 'hidden'
                }}>
                  {/* 思考框头部 */}
                  <div
                    style={{
                      padding: '8px 16px',
                      background: 'rgba(24, 144, 255, 0.06)',
                      borderBottom: isExpanded ? '1px solid rgba(24, 144, 255, 0.15)' : 'none',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      transition: 'all 0.2s ease'
                    }}
                    onClick={() => toggleThinking(index)}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = 'rgba(24, 144, 255, 0.08)';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = 'rgba(24, 144, 255, 0.06)';
                    }}
                  >
                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px'
                    }}>
                      {isExpanded ? (
                        <ChevronDown size={14} style={{ color: 'rgba(64, 169, 255, 0.8)' }} />
                      ) : (
                        <ChevronRight size={14} style={{ color: 'rgba(64, 169, 255, 0.8)' }} />
                      )}
                      <span style={{
                        fontSize: '12px',
                        fontWeight: 600,
                        color: 'rgba(64, 169, 255, 0.8)',
                        textTransform: 'uppercase',
                        letterSpacing: '0.5px'
                      }}>
                        💭 {t('common.thinkingProcess')}
                      </span>
                      <span style={{
                        fontSize: '11px',
                        color: 'rgba(45, 45, 45, 0.5)',
                        background: 'rgba(24, 144, 255, 0.1)',
                        padding: '2px 6px',
                        borderRadius: '10px'
                      }}>
                        {part.content.split('\n').length} {t('common.lines')}
                      </span>
                    </div>
                  </div>

                  {/* 思考框内容 */}
                  {isExpanded && (
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
                  remarkPlugins={[remarkGfm, remarkMath]}
                  rehypePlugins={[rehypeKatex]}
                  components={{ code: codeComponent }}
                >
                  {part.content}
                </ReactMarkdown>
              );
            }
          });
        })()}
        <GlassCodeBlock language={language} isStreaming={true} conversationId={conversationId}>
          {codeText}
        </GlassCodeBlock>
      </div>
    );
  }

  return (
    <div style={{
      fontFamily: "Cambria, Georgia, 'Times New Roman', serif, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', serif",
      fontSize: 'inherit'
    }}>
      {(() => {
        const contentParts = parseThinkingContent(content);
        return contentParts.map((part, index) => {
          if (part.type === 'thinking') {
            const isExpanded = thinkingStates[index] || false;
            return (
              <div key={index} style={{
                margin: '16px 0',
                border: '1px solid rgba(24, 144, 255, 0.15)',
                borderRadius: '8px',
                overflow: 'hidden'
              }}>
                {/* 思考框头部 */}
                <div
                  style={{
                    padding: '8px 16px',
                    background: 'rgba(24, 144, 255, 0.06)',
                    borderBottom: isExpanded ? '1px solid rgba(24, 144, 255, 0.15)' : 'none',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    transition: 'all 0.2s ease'
                  }}
                  onClick={() => toggleThinking(index)}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = 'rgba(24, 144, 255, 0.08)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = 'rgba(24, 144, 255, 0.06)';
                  }}
                >
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px'
                  }}>
                    {isExpanded ? (
                      <ChevronDown size={14} style={{ color: 'rgba(64, 169, 255, 0.8)' }} />
                    ) : (
                      <ChevronRight size={14} style={{ color: 'rgba(64, 169, 255, 0.8)' }} />
                    )}
                    <span style={{
                      fontSize: '12px',
                      fontWeight: 600,
                      color: 'rgba(64, 169, 255, 0.8)',
                      textTransform: 'uppercase',
                      letterSpacing: '0.5px'
                    }}>
                      💭 {t('common.thinkingProcess')}
                    </span>
                    <span style={{
                      fontSize: '11px',
                      color: 'rgba(45, 45, 45, 0.5)',
                      background: 'rgba(24, 144, 255, 0.1)',
                      padding: '2px 6px',
                      borderRadius: '10px'
                    }}>
                      {part.content.split('\n').length} {t('common.lines')}
                    </span>
                  </div>
                </div>

                {/* 思考框内容 */}
                {isExpanded && (
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
                remarkPlugins={[remarkGfm, remarkMath]}
                rehypePlugins={[rehypeKatex]}
                components={{ code: codeComponent }}
              >
                {part.content}
              </ReactMarkdown>
            );
          }
        });
      })()}
    </div>
  );
};

export default SmartMarkdown;
