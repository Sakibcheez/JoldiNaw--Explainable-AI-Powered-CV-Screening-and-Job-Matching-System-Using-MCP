import { useState, type FormEvent } from 'react'
import { MessageCircle, Send, Sparkles, X } from 'lucide-react'

export default function Chatbot() {
  const [open, setOpen] = useState(false)
  const [message, setMessage] = useState('')
  const [sent, setSent] = useState<string[]>([])

  function send(event: FormEvent) {
    event.preventDefault()
    const text = message.trim()
    if (!text) return
    setSent(messages => [...messages, text])
    setMessage('')
  }

  return <div className="chat-widget">
    {open && <section className="chat-panel" aria-label="JoldiNaw assistant">
      <div className="chat-heading"><span className="chat-avatar"><Sparkles size={17}/></span><div><strong>JoldiNaw assistant</strong><small>Interface preview</small></div><button className="chat-close" aria-label="Close chat" onClick={() => setOpen(false)}><X size={17}/></button></div>
      <div className="chat-messages" aria-live="polite">
        <p className="chat-bubble">Hi! I can help you explore the workspace. The AI service is not connected yet.</p>
        {sent.map((text, index) => <div key={`${index}-${text}`}><p className="chat-bubble chat-user">{text}</p><p className="chat-bubble">Thanks for the question. This chatbot preview is not connected to an AI service yet.</p></div>)}
      </div>
      <form className="chat-compose" onSubmit={send}><label className="sr-only" htmlFor="chat-message">Message the assistant</label><input id="chat-message" value={message} onChange={event => setMessage(event.target.value)} placeholder="Ask a question..." maxLength={1000}/><button className="primary" aria-label="Send message" disabled={!message.trim()}><Send size={16}/></button></form>
    </section>}
    <button className="chat-launcher" aria-label={open ? 'Close assistant' : 'Open assistant'} onClick={() => setOpen(value => !value)}>{open ? <X size={21}/> : <MessageCircle size={21}/>}</button>
  </div>
}
