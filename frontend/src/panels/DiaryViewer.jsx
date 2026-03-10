import { useState, useEffect } from 'react'
import { BookOpen, ChevronLeft, ChevronRight } from 'lucide-react'

export function DiaryViewer({ memoryUpdates }) {
  const [entries, setEntries] = useState([])
  const [selectedDate, setSelectedDate] = useState(null)
  const [content, setContent] = useState(null)
  const [loading, setLoading] = useState(false)

  const loadEntries = async () => {
    try {
      const res = await fetch('/api/diary/list')
      const data = await res.json()
      setEntries(data.filter(e => e.type === 'file'))
      if (data.length > 0 && !selectedDate) {
        const latest = data.filter(e => e.type === 'file').at(-1)
        if (latest) selectEntry(latest.name.replace('.md', ''))
      }
    } catch {}
  }

  useEffect(() => { loadEntries() }, [])
  useEffect(() => { if (memoryUpdates > 0) loadEntries() }, [memoryUpdates])

  const selectEntry = async (date) => {
    setSelectedDate(date)
    setLoading(true)
    try {
      const res = await fetch(`/api/diary?date=${date}`)
      const data = await res.json()
      setContent(data.content)
    } catch {}
    setLoading(false)
  }

  const currentIndex = entries.findIndex(e => e.name.replace('.md', '') === selectedDate)

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-4 py-2.5 border-b border-border shrink-0">
        <div className="flex items-center gap-2 mb-2">
          <BookOpen size={14} className="text-kernel" />
          <span className="font-display text-sm font-semibold text-bright">Diary</span>
        </div>

        {/* Date navigator */}
        {entries.length > 0 && (
          <div className="flex items-center gap-2">
            <button
              onClick={() => currentIndex > 0 && selectEntry(entries[currentIndex - 1].name.replace('.md', ''))}
              disabled={currentIndex <= 0}
              className="text-dim hover:text-text disabled:opacity-30 transition-colors"
            >
              <ChevronLeft size={14} />
            </button>

            <div className="flex-1 overflow-x-auto flex gap-1">
              {entries.map(e => {
                const date = e.name.replace('.md', '')
                return (
                  <button
                    key={date}
                    onClick={() => selectEntry(date)}
                    className={`shrink-0 text-xs px-2 py-0.5 rounded font-body transition-colors
                      ${selectedDate === date ? 'bg-kernel/20 text-kernel' : 'text-dim hover:text-text'}`}
                  >
                    {date}
                  </button>
                )
              })}
            </div>

            <button
              onClick={() => currentIndex < entries.length - 1 && selectEntry(entries[currentIndex + 1].name.replace('.md', ''))}
              disabled={currentIndex >= entries.length - 1}
              className="text-dim hover:text-text disabled:opacity-30 transition-colors"
            >
              <ChevronRight size={14} />
            </button>
          </div>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {loading && (
          <div className="text-dim text-xs font-body animate-pulse">Reading...</div>
        )}
        {content && !loading && (
          <div className="font-body text-xs text-text leading-relaxed whitespace-pre-wrap">
            {content}
          </div>
        )}
        {!content && !loading && entries.length === 0 && (
          <div className="text-dim text-xs text-center pt-8 opacity-50 font-body">
            No diary entries yet
          </div>
        )}
      </div>
    </div>
  )
}
