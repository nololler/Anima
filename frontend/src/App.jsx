import { useState, useCallback, useRef } from 'react'
import './index.css'
import { useWebSocket } from './hooks/useWebSocket'
import { useDragResize } from './hooks/useDragResize'
import { StatusBar } from './components/StatusBar'
import { SetupWizard } from './components/SetupWizard'
import { SettingsPanel } from './components/SettingsPanel'
import { ChatPanel } from './panels/ChatPanel'
import { InnerThoughtsPanel } from './panels/InnerThoughtsPanel'
import { MemoryBrowser } from './panels/MemoryBrowser'
import { DiaryViewer } from './panels/DiaryViewer'
import { TickLog } from './panels/TickLog'

// ── Drag handle ───────────────────────────────────────────────────────────────
function DragHandle({ onMouseDown, direction = 'horizontal' }) {
  const isH = direction === 'horizontal'
  return (
    <div
      onMouseDown={onMouseDown}
      className="group shrink-0 flex items-center justify-center hover:bg-accent/10 transition-colors"
      style={{
        width: isH ? '6px' : '100%',
        height: isH ? '100%' : '6px',
        cursor: isH ? 'col-resize' : 'row-resize',
        flexShrink: 0,
      }}
    >
      <div
        className="bg-border group-hover:bg-accent/50 transition-colors rounded-full"
        style={{
          width: isH ? '1px' : '28px',
          height: isH ? '28px' : '1px',
        }}
      />
    </div>
  )
}

export default function App() {
  const [setupComplete, setSetupComplete] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const [persona, setPersona] = useState({ name: 'Anima', mood: 'neutral', mood_intensity: 5, bank: 'default' })
  const [tickStatus, setTickStatus] = useState({ tick_count: 0 })
  const [banks, setBanks] = useState(['default'])
  const [activeBank, setActiveBank] = useState('default')
  const [messages, setMessages] = useState([])
  const [streamingMsg, setStreamingMsg] = useState(null)
  const [thoughts, setThoughts] = useState([])
  const [tickMode, setTickMode] = useState('idle')
  const [tickCountdown, setTickCountdown] = useState(60)
  const [ticks, setTicks] = useState([])
  const [toolCalls, setToolCalls] = useState([])
  const [errors, setErrors] = useState([])
  const [memoryUpdates, setMemoryUpdates] = useState(0)

  // Username — persisted to localStorage
  const [username, setUsername] = useState(() => localStorage.getItem('anima_username') || 'User')

  const handleUsernameChange = (name) => {
    setUsername(name)
    localStorage.setItem('anima_username', name)
  }

  const seenMsgIds = useRef(new Set())
  const seenThoughtIds = useRef(new Set())

  // Column widths: center col and right col (chat takes remaining flex space)
  const { sizes: colSizes, onMouseDown: colDrag } = useDragResize([310, 270], 'horizontal', 160)
  // Center column row heights: bottom panel height (top takes flex:1)
  const { sizes: centerRows, onMouseDown: centerRowDrag } = useDragResize([190], 'vertical', 120)
  // Right column row heights: bottom panel height (top takes flex:1)
  const { sizes: rightRows, onMouseDown: rightRowDrag } = useDragResize([190], 'vertical', 120)

  const handleWsMessage = useCallback((event) => {
    const { type, data, timestamp } = event
    switch (type) {
      case 'init':
        setSetupComplete(data.setup_complete === true)
        if (data.persona) setPersona(data.persona)
        if (data.tick_status) setTickStatus(data.tick_status)
        if (data.banks) setBanks(data.banks)
        if (data.persona?.bank) setActiveBank(data.persona.bank)
        if (data.messages) {
          setMessages(data.messages)
          data.messages.forEach(m => seenMsgIds.current.add(m.id))
        }
        break
      case 'setup_complete':
        setSetupComplete(true)
        setPersona(p => ({ ...p, name: data.name }))
        break
      case 'chat_message':
        if (seenMsgIds.current.has(data.id)) break
        seenMsgIds.current.add(data.id)
        setMessages(prev => [...prev, { ...data, timestamp }])
        break
      case 'chat_stream':
        setStreamingMsg(prev => ({
          id: data.id,
          content: (prev?.id === data.id ? prev.content : '') + data.chunk,
        }))
        break
      case 'chat_stream_end':
        setStreamingMsg(prev => (prev?.id === data.id ? null : prev))
        break
      case 'inner_thought':
        if (seenThoughtIds.current.has(data.id)) break
        seenThoughtIds.current.add(data.id)
        setThoughts(prev => [...prev.slice(-199), { ...data, timestamp }])
        break
      case 'tick':
        setTickMode(data.mode)
        setTickStatus(prev => ({ ...prev, tick_count: data.number }))
        setTicks(prev => {
          if (prev.some(t => t.data?.number === data.number)) return prev
          return [...prev.slice(-99), { data, timestamp }]
        })
        break
      case 'tick_countdown': setTickCountdown(data.seconds); break
      case 'mood_update':
        setPersona(prev => ({ ...prev, mood: data.mood, mood_intensity: data.intensity }))
        break
      case 'memory_update': setMemoryUpdates(n => n + 1); break
      case 'context_cull':
        setMessages(prev => prev.map(m =>
          data.message_ids.includes(m.id) ? { ...m, culled: true } : m
        ))
        break
      case 'bank_switch':
        setActiveBank(data.new_bank)
        setPersona(prev => ({ ...prev, bank: data.new_bank }))
        setMessages([]); setThoughts([])
        seenMsgIds.current.clear(); seenThoughtIds.current.clear()
        break
      case 'tool_call':
        setToolCalls(prev => [...prev.slice(-199), { data, timestamp }])
        break
      case 'error':
        setErrors(prev => [...prev.slice(-49), { data, timestamp }])
        break
    }
  }, [])

  const { connected, send } = useWebSocket(handleWsMessage)

  const handleSend = (text) => send({ type: 'chat', content: text, user_id: 'user', username })

  const handleBankSwitch = async (bankName) => {
    if (bankName === activeBank) return
    try {
      await fetch('/api/bank/switch', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ bank_name: bankName }),
      })
    } catch {}
  }

  const handleCreateBank = async () => {
    try {
      const res = await fetch('/api/banks')
      const data = await res.json()
      setBanks(data.banks)
    } catch {}
  }

  const [centerW, rightW] = colSizes
  const [centerBottomH] = centerRows
  const [rightBottomH] = rightRows

  return (
    <div className="h-screen flex flex-col bg-void overflow-hidden">
      {!setupComplete && <SetupWizard onComplete={() => setSetupComplete(true)} />}
      {showSettings && (
        <SettingsPanel onClose={() => setShowSettings(false)} onSaved={() => setShowSettings(false)} />
      )}

      <StatusBar
        persona={persona} tickStatus={tickStatus} banks={banks}
        activeBank={activeBank} connected={connected}
        onBankSwitch={handleBankSwitch} onCreateBank={handleCreateBank}
        onOpenSettings={() => setShowSettings(true)}
      />

      {/* ── Main layout ─────────────────────────────────────────────── */}
      <div className="flex-1 flex overflow-hidden p-2 gap-0 min-h-0">

        {/* Chat — takes all remaining horizontal space */}
        <div className="flex-1 min-w-0 panel-border overflow-hidden mr-0">
          <ChatPanel
            messages={messages} streamingMsg={streamingMsg}
            onSend={handleSend} personaName={persona.name}
            username={username} onUsernameChange={handleUsernameChange}
          />
        </div>

        <DragHandle onMouseDown={(e) => colDrag(0, e)} direction="horizontal" />

        {/* Center column */}
        <div className="flex flex-col min-h-0 shrink-0" style={{ width: centerW }}>
          {/* Inner Thoughts — grows to fill */}
          <div className="flex-1 min-h-0 panel-border overflow-hidden">
            <InnerThoughtsPanel
              thoughts={thoughts} tickCountdown={tickCountdown}
              tickCount={tickStatus.tick_count} tickMode={tickMode}
            />
          </div>

          <DragHandle onMouseDown={(e) => centerRowDrag(0, e)} direction="vertical" />

          {/* Tick Log — fixed height, resizable upward */}
          <div className="panel-border overflow-hidden shrink-0" style={{ height: centerBottomH }}>
            <TickLog ticks={ticks} toolCalls={toolCalls} errors={errors} />
          </div>
        </div>

        <DragHandle onMouseDown={(e) => colDrag(1, e)} direction="horizontal" />

        {/* Right column */}
        <div className="flex flex-col min-h-0 shrink-0" style={{ width: rightW }}>
          {/* Memory Browser — grows to fill */}
          <div className="flex-1 min-h-0 panel-border overflow-hidden">
            <MemoryBrowser memoryUpdates={memoryUpdates} />
          </div>

          <DragHandle onMouseDown={(e) => rightRowDrag(0, e)} direction="vertical" />

          {/* Diary — fixed height, resizable upward */}
          <div className="panel-border overflow-hidden shrink-0" style={{ height: rightBottomH }}>
            <DiaryViewer memoryUpdates={memoryUpdates} />
          </div>
        </div>

      </div>
    </div>
  )
}
