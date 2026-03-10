import { useState, useCallback, useRef, useEffect } from 'react'

/**
 * useDragResize
 * Manages an array of pixel sizes for resizable panels.
 * The drag handle at index `i` resizes panel[i] and panel[i+1].
 * Set a size to null to mark it as "flex: 1" (takes remaining space) — those won't be resized.
 */
export function useDragResize(initialSizes, direction = 'horizontal', minSize = 140) {
  const [sizes, setSizes] = useState(initialSizes)
  const dragging = useRef(null)

  const onMouseDown = useCallback((handleIndex, e) => {
    e.preventDefault()
    const pos = direction === 'horizontal' ? e.clientX : e.clientY
    dragging.current = {
      handleIndex,
      startPos: pos,
      startSizes: [...sizes],
    }
    document.body.style.cursor = direction === 'horizontal' ? 'col-resize' : 'row-resize'
    document.body.style.userSelect = 'none'
  }, [sizes, direction])

  useEffect(() => {
    const onMove = (e) => {
      if (!dragging.current) return
      const { handleIndex, startPos, startSizes } = dragging.current
      const pos = direction === 'horizontal' ? e.clientX : e.clientY
      const delta = pos - startPos

      setSizes(prev => {
        const next = [...prev]
        // Find the two panels adjacent to this handle
        // Handle i sits between panel i and panel i+1
        const left = handleIndex
        const right = handleIndex + 1

        if (next[left] == null || next[right] == null) return prev // can't resize flex panels

        const newLeft = Math.max(minSize, startSizes[left] + delta)
        const newRight = Math.max(minSize, startSizes[right] - delta)
        next[left] = newLeft
        next[right] = newRight
        return next
      })
    }

    const onUp = () => {
      dragging.current = null
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }

    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
    return () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
  }, [direction, minSize])

  return { sizes, onMouseDown }
}
