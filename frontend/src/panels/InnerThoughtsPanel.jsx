import { useEffect, useRef, useState } from 'react'
import { Brain, Cpu, Eye } from 'lucide-react'

const STATE_COLORS = {
  active: 'text-accent',
  idle:   'text-kernel',
  sleep:  'text-dim',
}
const STATE_LABELS = {
  active: '● active',
  idle:   '○ idle',
  sleep:  '◌ sleep',
}

export function InnerThoughtsPanel({ thoughts, tickCountdown, tickCount, tickMode }) {
  const bottomRef = useRef(null)
  const [filter, setFilter] = useState('all') // all | think | thought | kernel

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [thoughts])

  const filtered = filter === 'all' ? thoughts : thoughts.filter(t => t.kind === filter)

  // Countdown progress — 60s base tick
  const maxSeconds = 60
  const elapsed = maxSeconds - (tickCountdown ?? maxSeconds)
  const pct = Math.min((elapsed / maxSeconds) * 100, 100)

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-4 py-2.5 border-b border-border shrink-0">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <Brain size={14} className="text-thought" />
            <span className="font-display text-sm font-semibold text-bright">Inner World</span>
          </div>
          <div className="flex items-center gap-1 text-xs font-body">
            <span className={STATE_COLORS[tickMode] || 'text-dim'}>
              {STATE_LABELS[tickMode] || tickMode}
            </span>
            <span className="text-border mx-1">|</span>
            <span className="text-dim">#{tickCount || 0}</span>
          </div>
        </div>

        {/* Tick countdown bar */}
        <div className="h-0.5 bg-muted rounded-full overflow-hidden">
          <div
            className="h-full transition-all duration-1000 rounded-full"
            style={{
              width: `${pct}%`,
              background: tickMode === 'sleep'
                ? 'rgba(74,83,102,0.5)'
                : tickMode === 'active'
                ? 'rgba(124,158,245,0.6)'
                : 'rgba(176,124,245,0.5)',
            }}
          />
        </div>

        {/* Filter tabs */}
        <div className="flex gap-1 mt-2">
          {[
            { id: 'all',    label: '◈ all' },
            { id: 'think',  label: '💭 think' },
            { id: 'thought',label: '✦ thought' },
            { id: 'kernel', label: '⚙ kernel' },
          ].map(f => (
            <button
              key={f.id}
              onClick={() => setFilter(f.id)}
              className={`text-xs px-2 py-0.5 rounded font-body transition-colors
                ${filter === f.id
                  ? f.id === 'think'   ? 'bg-accent/20 text-accent'
                  : f.id === 'thought' ? 'bg-thought/20 text-thought'
                  : f.id === 'kernel'  ? 'bg-kernel/20 text-kernel'
                  : 'bg-muted text-text'
                  : 'text-dim hover:text-ghost'}`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* Feed */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2 font-body text-xs">
        {filtered.length === 0 && (
          <div className="text-dim text-center pt-8 opacity-50">
            <Brain size={24} className="mx-auto mb-2 opacity-50" />
            <div>{tickMode === 'sleep' ? 'Sleeping...' : 'Quiet mind...'}</div>
          </div>
        )}
        {filtered.map(t => <ThoughtEntry key={t.id} thought={t} />)}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}

function ThoughtEntry({ thought }) {
  const { kind, content, timestamp } = thought
  const [expanded, setExpanded] = useState(true)

  // think blocks can be long — make them collapsible
  const isThink = kind === 'think'
  const isKernel = kind === 'kernel'
  const isThought = kind === 'thought'

  const style = isThink
    ? { bg: 'bg-accent/5 border-accent/20', icon: <Eye size={10} className="text-accent shrink-0" />, label: 'thinking', labelColor: 'text-accent' }
    : isKernel
    ? { bg: 'bg-kernel/5 border-kernel/20', icon: <Cpu size={10} className="text-kernel shrink-0" />, label: 'kernel', labelColor: 'text-kernel' }
    : { bg: 'bg-thought/5 border-thought/20', icon: <Brain size={10} className="text-thought shrink-0" />, label: 'thought', labelColor: 'text-thought' }

  return (
    <div className={`rounded p-2.5 animate-slide-up border ${style.bg}`}>
      <div className="flex items-center gap-1.5 mb-1">
        {style.icon}
        <span className={`uppercase tracking-widest text-[10px] font-display ${style.labelColor}`}>
          {style.label}
        </span>
        {isThink && (
          <button
            onClick={() => setExpanded(v => !v)}
            className="ml-1 text-dim hover:text-text transition-colors"
          >
            {expanded ? <ChevronDown size={9} /> : <ChevronRight size={9} />}
          </button>
        )}
        <span className="text-dim ml-auto text-[10px]">
          {new Date(timestamp || Date.now()).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </span>
      </div>

      {(!isThink || expanded) && (
        <p className={`leading-relaxed whitespace-pre-wrap ${isKernel ? 'text-ghost' : 'text-text'}`}>
          {content}
        </p>
      )}
      {isThink && !expanded && (
        <p className="text-dim text-[11px] italic">
          {content.slice(0, 80)}{content.length > 80 ? '...' : ''}
        </p>
      )}
    </div>
  )
}

// Need these for the think block chevrons
function ChevronDown({ size, className }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <polyline points="6 9 12 15 18 9" />
    </svg>
  )
}
function ChevronRight({ size, className }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <polyline points="9 18 15 12 9 6" />
    </svg>
  )
}
