import { useState, useEffect, useCallback } from 'react'
import { Folder, FileText, ChevronRight, ChevronDown, RefreshCw } from 'lucide-react'

export function MemoryBrowser({ memoryUpdates }) {
  const [tree, setTree] = useState([])
  const [selectedPath, setSelectedPath] = useState(null)
  const [fileContent, setFileContent] = useState(null)
  const [loading, setLoading] = useState(false)
  const [expandedFolders, setExpandedFolders] = useState(new Set(['static', 'people', 'days']))

  const loadTree = useCallback(async () => {
    try {
      const res = await fetch('/api/memory/list')
      setTree(await res.json())
    } catch {}
  }, [])

  useEffect(() => { loadTree() }, [loadTree])

  // Reload when memory updates
  useEffect(() => {
    if (memoryUpdates > 0) loadTree()
  }, [memoryUpdates, loadTree])

  const loadFile = async (path) => {
    setSelectedPath(path)
    setLoading(true)
    try {
      const res = await fetch(`/api/memory/read?path=${encodeURIComponent(path)}`)
      if (res.ok) {
        const data = await res.json()
        setFileContent(data.content)
      }
    } catch {}
    setLoading(false)
  }

  const toggleFolder = (name) => {
    setExpandedFolders(prev => {
      const next = new Set(prev)
      if (next.has(name)) next.delete(name)
      else next.add(name)
      return next
    })
  }

  const folders = tree.filter(e => e.type === 'folder')
  const rootFiles = tree.filter(e => e.type === 'file')

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-4 py-2.5 border-b border-border flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <Folder size={14} className="text-warm" />
          <span className="font-display text-sm font-semibold text-bright">Memory Bank</span>
        </div>
        <button onClick={loadTree} className="text-dim hover:text-text transition-colors">
          <RefreshCw size={12} />
        </button>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Tree */}
        <div className="w-36 border-r border-border overflow-y-auto p-2 shrink-0">
          {/* Root files */}
          {rootFiles.map(f => (
            <FileEntry
              key={f.path}
              entry={f}
              selected={selectedPath === f.path}
              onClick={() => loadFile(f.path)}
            />
          ))}

          {/* Folders */}
          {folders.map(folder => (
            <FolderEntry
              key={folder.path}
              folder={folder}
              expanded={expandedFolders.has(folder.name)}
              onToggle={() => toggleFolder(folder.name)}
              selectedPath={selectedPath}
              onSelectFile={loadFile}
            />
          ))}
        </div>

        {/* File viewer */}
        <div className="flex-1 overflow-y-auto p-3">
          {selectedPath && (
            <div className="text-xs text-dim font-body mb-2 pb-2 border-b border-border truncate">
              {selectedPath}
            </div>
          )}
          {loading && (
            <div className="text-dim text-xs font-body animate-pulse">Loading...</div>
          )}
          {fileContent && !loading && (
            <pre className="text-xs font-body text-text leading-relaxed whitespace-pre-wrap break-words">
              {fileContent}
            </pre>
          )}
          {!selectedPath && !loading && (
            <div className="text-dim text-xs font-body opacity-50 text-center pt-8">
              Select a file to read
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function FileEntry({ entry, selected, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center gap-1.5 px-1.5 py-1 rounded text-xs font-body text-left transition-colors
        ${selected ? 'bg-accent/15 text-accent' : 'text-ghost hover:text-text hover:bg-muted'}`}
    >
      <FileText size={10} className="shrink-0" />
      <span className="truncate">{entry.name}</span>
    </button>
  )
}

function FolderEntry({ folder, expanded, onToggle, selectedPath, onSelectFile }) {
  const [children, setChildren] = useState([])
  const [loaded, setLoaded] = useState(false)

  const handleToggle = async () => {
    onToggle()
    if (!loaded) {
      try {
        const res = await fetch(`/api/memory/list?folder=${encodeURIComponent(folder.path)}`)
        setChildren(await res.json())
        setLoaded(true)
      } catch {}
    }
  }

  const FOLDER_COLORS = {
    static: 'text-accent', people: 'text-warm', days: 'text-thought',
    diary: 'text-kernel', images: 'text-dim',
  }
  const color = FOLDER_COLORS[folder.name] || 'text-ghost'

  return (
    <div>
      <button
        onClick={handleToggle}
        className="w-full flex items-center gap-1 px-1 py-1 rounded text-xs font-body text-left transition-colors hover:bg-muted"
      >
        {expanded ? <ChevronDown size={10} className="shrink-0 text-dim" /> : <ChevronRight size={10} className="shrink-0 text-dim" />}
        <Folder size={10} className={`shrink-0 ${color}`} />
        <span className={`truncate ${color}`}>{folder.name}</span>
      </button>

      {expanded && (
        <div className="ml-3 border-l border-border/50 pl-1 space-y-0.5">
          {children.filter(c => c.type === 'file').map(f => (
            <FileEntry
              key={f.path}
              entry={f}
              selected={selectedPath === f.path}
              onClick={() => onSelectFile(f.path)}
            />
          ))}
          {children.length === 0 && loaded && (
            <div className="text-dim text-[10px] px-1 py-0.5 font-body">empty</div>
          )}
        </div>
      )}
    </div>
  )
}
