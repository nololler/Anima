import { useState } from 'react'
import { Zap, Database, Clock, Cpu, Circle, Settings } from 'lucide-react'

const MOOD_COLORS = {
  neutral: '#6b7a94', curious: '#7c9ef5', excited: '#f5c842',
  melancholic: '#b07cf5', calm: '#4a9e8a', anxious: '#e5956a',
  happy: '#7cf5a0', sad: '#5a7ab5', angry: '#e56a6a', content: '#9ef5c8',
}

export function StatusBar({ persona, tickStatus, banks, activeBank, connected, onBankSwitch, onCreateBank, onOpenSettings }) {
  const [showBanks, setShowBanks] = useState(false)
  const [newBankName, setNewBankName] = useState('')

  const moodColor = MOOD_COLORS[persona?.mood?.toLowerCase()] || '#6b7a94'
  const intensity = persona?.mood_intensity || 5

  const handleCreateBank = async () => {
    if (!newBankName.trim()) return
    await fetch('/api/bank/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ bank_name: newBankName.trim() }),
    })
    setNewBankName('')
    onCreateBank?.()
  }

  return (
    <div className="flex items-center justify-between px-4 h-9 bg-void border-b border-border font-body text-xs select-none shrink-0">
      {/* Left: Identity */}
      <div className="flex items-center gap-3">
        <span className="font-display font-semibold text-bright tracking-wide text-sm">
          {persona?.name || 'Anima'}
        </span>
        <span className="text-border">|</span>
        {/* Mood */}
        <div className="flex items-center gap-1.5">
          <Circle
            size={7}
            style={{ fill: moodColor, color: moodColor }}
            className="animate-pulse-soft"
          />
          <span style={{ color: moodColor }} className="capitalize">
            {persona?.mood || 'neutral'}
          </span>
          <span className="text-dim">{intensity}/10</span>
        </div>
      </div>

      {/* Center: Tick */}
      <div className="flex items-center gap-4 text-dim">
        <div className="flex items-center gap-1.5">
          <Zap size={11} className="text-accent" />
          <span>tick #{tickStatus?.tick_count || 0}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <Clock size={11} />
          <span>{tickStatus?.next_tick ? 'next in ...' : 'idle'}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <Cpu size={11} />
          <span>{persona?.bank || 'default'}</span>
        </div>
      </div>

      {/* Right: Bank switcher + connection */}
      <div className="flex items-center gap-3">
        {/* Bank switcher */}
        <div className="relative">
          <button
            onClick={() => setShowBanks(!showBanks)}
            className="flex items-center gap-1.5 text-dim hover:text-text transition-colors px-2 py-0.5 rounded hover:bg-muted"
          >
            <Database size={11} />
            <span>{activeBank || 'default'}</span>
          </button>

          {showBanks && (
            <div className="absolute right-0 top-full mt-1 w-48 bg-panel border border-border rounded shadow-xl z-50 p-1">
              <div className="text-dim text-xs px-2 py-1 font-display uppercase tracking-wider">Memory Banks</div>
              {banks?.map(bank => (
                <button
                  key={bank}
                  onClick={() => { onBankSwitch(bank); setShowBanks(false) }}
                  className={`w-full text-left px-2 py-1.5 rounded text-xs transition-colors
                    ${bank === activeBank ? 'text-accent bg-muted' : 'text-text hover:bg-muted'}`}
                >
                  {bank === activeBank ? '▶ ' : '  '}{bank}
                </button>
              ))}
              <div className="border-t border-border mt-1 pt-1">
                <div className="flex gap-1 px-1">
                  <input
                    value={newBankName}
                    onChange={e => setNewBankName(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && handleCreateBank()}
                    placeholder="new bank..."
                    className="flex-1 bg-void text-text text-xs px-1.5 py-1 rounded border border-border outline-none focus:border-accent"
                  />
                  <button
                    onClick={handleCreateBank}
                    className="text-accent hover:text-bright px-1.5 text-xs"
                  >+</button>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Connection status */}
        <div className="flex items-center gap-1.5">
          <Circle
            size={6}
            className={connected ? 'text-kernel' : 'text-danger'}
            style={{ fill: 'currentColor' }}
          />
          <span className={connected ? 'text-kernel' : 'text-danger'}>
            {connected ? 'live' : 'offline'}
          </span>
        </div>

        {/* Settings */}
        <button
          onClick={onOpenSettings}
          className="text-dim hover:text-text transition-colors p-1 rounded hover:bg-muted"
          title="Settings"
        >
          <Settings size={13} />
        </button>
      </div>
    </div>
  )
}
