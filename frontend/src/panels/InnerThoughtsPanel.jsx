import { useEffect, useRef, useState } from 'react'
import { Brain, Cpu } from 'lucide-react'

export function InnerThoughtsPanel({ thoughts, tickCountdown, tickCount, tickMode }) {
  const bottomRef = useRef(null)
  const [filter, setFilter] = useState('all') // all | thought | kernel

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [thoughts])

  const filtered = filter === 'all' ? thoughts : thoughts.filter(t => t.kind === filter)
  const countdownPct = tickCountdown != null ? Math.min((tickCountdown / 60) * 100, 100) : 0

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-4 py-2.5 border-b border-border shrink-0">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <Brain size={14} className="text-thought" />
            <span className="font-display text-sm font-semibold text-bright">Inner World</span>
          </div>
          <div className="flex items-center gap-1 text-xs font-body text-dim">
            <span className={tickMode === 'active' ? 'text-accent' : 'text-kernel'}>
              {tickMode === 'active' ? '● active' : '○ idle'}
            </span>
            <span className="text-border mx-1">|</span>
            <span>#{tickCount || 0}</span>
          </div>
        </div>

        {/* Tick countdown bar */}
        <div className="h-0.5 bg-muted rounded-full overflow-hidden">
          <div
            className="h-full bg-thought/50 transition-all duration-1000"
            style={{ width: `${100 - countdownPct}%` }}
          />
        </div>

        {/* Filter tabs */}
        <div className="flex gap-1 mt-2">
          {['all', 'thought', 'kernel'].map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`text-xs px-2 py-0.5 rounded font-body transition-colors capitalize
                ${filter === f
                  ? f === 'thought' ? 'bg-thought/20 text-thought'
                  : f === 'kernel' ? 'bg-kernel/20 text-kernel'
                  : 'bg-muted text-text'
                  : 'text-dim hover:text-ghost'
                }`}
            >
              {f === 'thought' ? '💭' : f === 'kernel' ? '⚙️' : '◈'} {f}
            </button>
          ))}
        </div>
      </div>

      {/* Thoughts feed */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2 font-body text-xs">
        {filtered.length === 0 && (
          <div className="text-dim text-center pt-8 opacity-50">
            <Brain size={24} className="mx-auto mb-2 opacity-50" />
            <div>Quiet mind...</div>
          </div>
        )}

        {filtered.map(t => (
          <ThoughtEntry key={t.id} thought={t} />
        ))}

        <div ref={bottomRef} />
      </div>
    </div>
  )
}

function ThoughtEntry({ thought }) {
  const isKernel = thought.kind === 'kernel'

  return (
    <div className={`rounded p-2.5 animate-slide-up border
      ${isKernel
        ? 'bg-kernel/5 border-kernel/20 kernel-glow'
        : 'bg-thought/5 border-thought/20 thought-glow'
      }`}
    >
      <div className="flex items-center gap-1.5 mb-1">
        {isKernel
          ? <Cpu size={10} className="text-kernel shrink-0" />
          : <Brain size={10} className="text-thought shrink-0" />
        }
        <span className={`uppercase tracking-widest text-[10px] font-display ${isKernel ? 'text-kernel' : 'text-thought'}`}>
          {isKernel ? 'kernel' : 'thought'}
        </span>
        <span className="text-dim ml-auto text-[10px]">
          {new Date(thought.timestamp || Date.now()).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </span>
      </div>
      <p className={`leading-relaxed ${isKernel ? 'text-ghost' : 'text-text'}`}>
        {thought.content}
      </p>
    </div>
  )
}
