import { useRef, useEffect } from 'react'
import { Zap, Wrench, AlertCircle } from 'lucide-react'

export function TickLog({ ticks, toolCalls, errors }) {
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [ticks, toolCalls, errors])

  // Merge and sort all events by timestamp
  const events = [
    ...ticks.map(t => ({ ...t, _type: 'tick' })),
    ...toolCalls.map(t => ({ ...t, _type: 'tool' })),
    ...errors.map(e => ({ ...e, _type: 'error' })),
  ].sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp)).slice(-80)

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-4 py-2.5 border-b border-border shrink-0">
        <div className="flex items-center gap-2">
          <Zap size={14} className="text-accent" />
          <span className="font-display text-sm font-semibold text-bright">System Log</span>
          <span className="text-dim text-xs font-body ml-auto">{events.length} events</span>
        </div>
      </div>

      {/* Log entries */}
      <div className="flex-1 overflow-y-auto p-2 space-y-0.5 font-body text-xs">
        {events.length === 0 && (
          <div className="text-dim text-center pt-6 opacity-50">Waiting for activity...</div>
        )}

        {events.map((event, i) => (
          <LogEntry key={i} event={event} />
        ))}

        <div ref={bottomRef} />
      </div>
    </div>
  )
}

function LogEntry({ event }) {
  const time = new Date(event.timestamp).toLocaleTimeString([], {
    hour: '2-digit', minute: '2-digit', second: '2-digit'
  })

  if (event._type === 'tick') {
    const modeColor = event.data?.mode === 'active' ? 'text-accent' : 'text-kernel'
    return (
      <div className="flex items-start gap-2 py-0.5 hover:bg-muted/30 px-1 rounded">
        <Zap size={10} className={`shrink-0 mt-0.5 ${modeColor}`} />
        <span className="text-dim shrink-0">{time}</span>
        <span className={modeColor}>tick #{event.data?.number}</span>
        <span className="text-dim">— {event.data?.mode}</span>
      </div>
    )
  }

  if (event._type === 'tool') {
    return (
      <div className="flex items-start gap-2 py-0.5 hover:bg-muted/30 px-1 rounded">
        <Wrench size={10} className="shrink-0 mt-0.5 text-warm" />
        <span className="text-dim shrink-0">{time}</span>
        <span className="text-warm">{event.data?.tool}</span>
        {event.data?.args && (
          <span className="text-dim truncate max-w-[160px]">
            {JSON.stringify(event.data.args).slice(0, 60)}
          </span>
        )}
      </div>
    )
  }

  if (event._type === 'error') {
    return (
      <div className="flex items-start gap-2 py-0.5 hover:bg-danger/5 px-1 rounded">
        <AlertCircle size={10} className="shrink-0 mt-0.5 text-danger" />
        <span className="text-dim shrink-0">{time}</span>
        <span className="text-danger truncate">{event.data?.message}</span>
        <span className="text-dim shrink-0">[{event.data?.source}]</span>
      </div>
    )
  }

  return null
}
