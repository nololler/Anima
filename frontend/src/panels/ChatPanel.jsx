import { useEffect, useRef, useState } from 'react'
import { Send, Sparkles, Pencil, Check } from 'lucide-react'

export function ChatPanel({ messages, streamingMsg, onSend, personaName, username, onUsernameChange }) {
  const bottomRef = useRef(null)
  const [input, setInput] = useState('')
  const [editingName, setEditingName] = useState(false)
  const [nameInput, setNameInput] = useState(username || 'User')
  const nameRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingMsg])

  // Sync nameInput when username prop changes externally
  useEffect(() => {
    setNameInput(username || 'User')
  }, [username])

  const handleSend = () => {
    const text = input.trim()
    if (!text) return
    onSend(text)
    setInput('')
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const commitName = () => {
    const trimmed = nameInput.trim() || 'User'
    setNameInput(trimmed)
    onUsernameChange?.(trimmed)
    setEditingName(false)
  }

  const handleNameKeyDown = (e) => {
    if (e.key === 'Enter') commitName()
    if (e.key === 'Escape') { setNameInput(username || 'User'); setEditingName(false) }
  }

  const startEditing = () => {
    setEditingName(true)
    setTimeout(() => nameRef.current?.select(), 0)
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-4 py-2.5 border-b border-border flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-accent animate-pulse-soft" />
          <span className="font-display text-sm font-semibold text-bright">Conversation</span>
        </div>

        {/* Editable username */}
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-dim font-body">you are</span>
          {editingName ? (
            <div className="flex items-center gap-1">
              <input
                ref={nameRef}
                value={nameInput}
                onChange={e => setNameInput(e.target.value)}
                onKeyDown={handleNameKeyDown}
                onBlur={commitName}
                className="bg-void border border-accent/50 rounded px-2 py-0.5 text-xs text-text font-body outline-none w-28"
                maxLength={32}
              />
              <button onClick={commitName} className="text-accent hover:text-bright transition-colors">
                <Check size={12} />
              </button>
            </div>
          ) : (
            <button
              onClick={startEditing}
              className="flex items-center gap-1 text-xs text-accent hover:text-bright font-body transition-colors group"
            >
              <span>{username || 'User'}</span>
              <Pencil size={10} className="opacity-0 group-hover:opacity-100 transition-opacity" />
            </button>
          )}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3 font-body text-sm">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-dim gap-2 opacity-50">
            <Sparkles size={32} />
            <span className="font-display text-sm">{personaName} is waiting...</span>
          </div>
        )}

        {messages.map(msg => (
          <MessageBubble key={msg.id} msg={msg} personaName={personaName} username={username} />
        ))}

        {streamingMsg && (
          <div className="flex flex-col gap-1 animate-fade-in">
            <span className="text-xs text-dim uppercase tracking-wider font-display">{personaName}</span>
            <div className="max-w-[85%] px-3 py-2 rounded bg-panel border border-border text-text leading-relaxed">
              <span>{streamingMsg.content}</span>
              <span className="streaming-cursor" />
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="px-4 pb-4 pt-2 shrink-0">
        <div className="flex gap-2 items-end">
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Say something..."
            rows={1}
            className="flex-1 bg-surface border border-border rounded px-3 py-2 text-sm text-text font-body outline-none focus:border-accent resize-none transition-colors placeholder:text-dim"
            style={{ minHeight: '38px', maxHeight: '120px' }}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim()}
            className="p-2 bg-accent hover:bg-accent/80 disabled:bg-muted text-void rounded transition-colors shrink-0"
          >
            <Send size={15} />
          </button>
        </div>
      </div>
    </div>
  )
}

function MessageBubble({ msg, personaName, username }) {
  const isUser = msg.role === 'user'
  const isSystem = msg.role === 'system' || msg.role === 'tool'
  if (isSystem) return null

  return (
    <div className={`flex flex-col gap-1 animate-slide-up ${isUser ? 'items-end' : 'items-start'}`}>
      <div className="flex items-center gap-2">
        {msg.ai_initiated && (
          <span className="text-initiated text-xs font-body">✦ initiated</span>
        )}
        <span className="text-xs text-dim uppercase tracking-wider font-display">
          {isUser ? (username || 'You') : personaName}
        </span>
        {msg.culled && <span className="text-xs text-dim font-body">[culled]</span>}
      </div>
      <div className={`max-w-[85%] px-3 py-2 rounded text-sm leading-relaxed font-body
        ${isUser
          ? 'bg-accent/15 border border-accent/25 text-text'
          : 'bg-panel border border-border text-text'
        }
        ${msg.culled ? 'culled-message' : ''}
        ${msg.ai_initiated ? 'ai-initiated-message pl-3' : ''}`}
      >
        {msg.content}
      </div>
    </div>
  )
}
