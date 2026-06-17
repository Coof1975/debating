import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import type { ChatMessage, ChatSession } from '../types'

export function useChatSession(meetingId: string, personaId: string | null) {
  const [session, setSession] = useState<ChatSession | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [loading, setLoading] = useState(false)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const cacheRef = useRef<Map<string, ChatMessage[]>>(new Map())

  const loadSession = useCallback(async () => {
    if (!personaId) {
      setSession(null)
      setMessages([])
      return
    }

    setLoading(true)
    setError(null)
    try {
      const created = await api.createChatSession(meetingId, personaId)
      setSession(created)
      const cached = cacheRef.current.get(created.id)
      if (cached) {
        setMessages(cached)
      } else {
        const history = await api.listChatMessages(meetingId, created.id)
        cacheRef.current.set(created.id, history)
        setMessages(history)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load chat session')
      setSession(null)
      setMessages([])
    } finally {
      setLoading(false)
    }
  }, [meetingId, personaId])

  useEffect(() => {
    loadSession()
  }, [loadSession])

  const sendMessage = useCallback(
    async (content: string) => {
      if (!session || !content.trim()) return
      setSending(true)
      setError(null)
      try {
        const result = await api.sendChatMessage(meetingId, session.id, content.trim())
        setMessages((prev) => {
          const next = [...prev, result.user_message, result.assistant_message]
          cacheRef.current.set(session.id, next)
          return next
        })
        setSession((prev) =>
          prev
            ? {
                ...prev,
                message_count: prev.message_count + 2,
                last_message_preview: result.assistant_message.content.slice(0, 120),
                updated_at: result.assistant_message.created_at,
              }
            : prev,
        )
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to send message')
      } finally {
        setSending(false)
      }
    },
    [meetingId, session],
  )

  return {
    session,
    messages,
    loading,
    sending,
    error,
    sendMessage,
    reload: loadSession,
  }
}
