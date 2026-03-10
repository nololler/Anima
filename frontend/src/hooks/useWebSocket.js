import { useEffect, useRef, useCallback, useState } from 'react'

export function useWebSocket(onMessage) {
  const ws = useRef(null)
  const [connected, setConnected] = useState(false)
  const onMessageRef = useRef(onMessage)
  const reconnectTimer = useRef(null)
  const mounted = useRef(true)
  onMessageRef.current = onMessage

  const connect = useCallback(() => {
    if (!mounted.current) return
    // Close any existing connection first
    if (ws.current && ws.current.readyState < 2) {
      ws.current.onclose = null  // prevent reconnect loop
      ws.current.close()
    }

    const url = `ws://${window.location.hostname}:8000/ws`
    const socket = new WebSocket(url)
    ws.current = socket

    socket.onopen = () => {
      if (mounted.current) setConnected(true)
    }

    socket.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        onMessageRef.current(data)
      } catch {}
    }

    socket.onclose = () => {
      if (!mounted.current) return
      setConnected(false)
      reconnectTimer.current = setTimeout(connect, 2500)
    }

    socket.onerror = () => {
      socket.close()
    }
  }, [])

  useEffect(() => {
    mounted.current = true
    connect()
    return () => {
      mounted.current = false
      clearTimeout(reconnectTimer.current)
      if (ws.current) {
        ws.current.onclose = null
        ws.current.close()
      }
    }
  }, [connect])

  const send = useCallback((data) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(data))
    }
  }, [])

  return { connected, send }
}
