import { useState, useEffect } from 'react'
import { Settings, X, Save, RefreshCw } from 'lucide-react'

const PROVIDERS = ['ollama', 'openai', 'anthropic', 'openai_compatible']

export function SettingsPanel({ onClose, onSaved }) {
  const [form, setForm] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)

  useEffect(() => {
    Promise.all([
      fetch('/api/config').then(r => r.json()),
      fetch('/api/memory/read?path=static/self.md').then(r => r.json()).catch(() => ({ content: '' })),
    ]).then(([cfg, selfFile]) => {
      setForm({
        name: cfg.anima?.name || 'Anima',
        identity: selfFile.content || '',
        main_provider: cfg.main_llm?.provider || 'ollama',
        main_model: cfg.main_llm?.model || '',
        main_base_url: cfg.main_llm?.base_url || 'http://localhost:11434',
        main_api_key: cfg.main_llm?.api_key || '',
        main_vision: cfg.main_llm?.vision || false,
        prompter_provider: cfg.prompter_llm?.provider || 'ollama',
        prompter_model: cfg.prompter_llm?.model || '',
        prompter_base_url: cfg.prompter_llm?.base_url || 'http://localhost:11434',
        prompter_api_key: cfg.prompter_llm?.api_key || '',
        tick_interval: cfg.tick?.interval_minutes || 1,
      })
      setLoading(false)
    }).catch(e => {
      setError('Failed to load config: ' + e.message)
      setLoading(false)
    })
  }, [])

  const update = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const handleSave = async () => {
    setSaving(true)
    setError('')
    setSuccess(false)
    try {
      const res = await fetch('/api/setup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...form, tick_interval: Number(form.tick_interval) }),
      })
      if (!res.ok) throw new Error(await res.text())
      setSuccess(true)
      onSaved?.()
      setTimeout(() => setSuccess(false), 3000)
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  const Field = ({ label, field, type = 'text', hint }) => (
    <div className="flex flex-col gap-1">
      <label className="text-dim text-xs font-body uppercase tracking-wider">{label}</label>
      {hint && <span className="text-ghost text-xs -mt-0.5">{hint}</span>}
      <input
        type={type}
        value={form?.[field] ?? ''}
        onChange={e => update(field, type === 'number' ? e.target.valueAsNumber : e.target.value)}
        className="bg-void border border-border rounded px-3 py-1.5 text-sm text-text font-body outline-none focus:border-accent transition-colors"
      />
    </div>
  )

  const Select = ({ label, field }) => (
    <div className="flex flex-col gap-1">
      <label className="text-dim text-xs font-body uppercase tracking-wider">{label}</label>
      <select
        value={form?.[field] ?? ''}
        onChange={e => update(field, e.target.value)}
        className="bg-void border border-border rounded px-3 py-1.5 text-sm text-text font-body outline-none focus:border-accent"
      >
        {PROVIDERS.map(p => <option key={p} value={p}>{p}</option>)}
      </select>
    </div>
  )

  return (
    <div className="fixed inset-0 bg-void/80 backdrop-blur-sm flex items-center justify-center p-6 z-50">
      <div className="w-full max-w-2xl panel-border flex flex-col max-h-[90vh] animate-fade-in">
        <div className="flex items-center justify-between px-6 py-4 border-b border-border shrink-0">
          <div className="flex items-center gap-2">
            <Settings size={16} className="text-accent" />
            <span className="font-display font-semibold text-bright">Settings</span>
          </div>
          <button onClick={onClose} className="text-dim hover:text-text transition-colors">
            <X size={16} />
          </button>
        </div>

        <div className="overflow-y-auto flex-1 px-6 py-4">
          {loading && (
            <div className="text-dim text-sm font-body animate-pulse text-center py-8">Loading config...</div>
          )}

          {!loading && form && (
            <div className="space-y-6">
              <div className="space-y-3">
                <div className="text-xs font-display uppercase tracking-widest text-accent border-b border-border pb-1">Identity</div>
                <Field label="Name" field="name" />
                <div className="flex flex-col gap-1">
                  <label className="text-dim text-xs font-body uppercase tracking-wider">Core Identity (self.md)</label>
                  <span className="text-ghost text-xs">The AI's identity file. Changes take effect on next message.</span>
                  <textarea
                    value={form.identity}
                    onChange={e => update('identity', e.target.value)}
                    rows={5}
                    className="bg-void border border-border rounded px-3 py-2 text-sm text-text font-body outline-none focus:border-accent resize-none"
                  />
                </div>
              </div>

              <div className="space-y-3">
                <div className="text-xs font-display uppercase tracking-widest text-accent border-b border-border pb-1">Main LLM</div>
                <div className="grid grid-cols-2 gap-3">
                  <Select label="Provider" field="main_provider" />
                  <Field label="Model" field="main_model" />
                  <Field label="Base URL" field="main_base_url" />
                  <Field label="API Key" field="main_api_key" type="password" hint="Leave empty for Ollama" />
                </div>
                <label className="flex items-center gap-2 text-sm text-text cursor-pointer">
                  <input
                    type="checkbox"
                    checked={form.main_vision}
                    onChange={e => update('main_vision', e.target.checked)}
                    className="accent-accent"
                  />
                  <span>Vision model (VLM)</span>
                </label>
              </div>

              <div className="space-y-3">
                <div className="text-xs font-display uppercase tracking-widest text-thought border-b border-border pb-1">Prompter (Inner Voice)</div>
                <div className="grid grid-cols-2 gap-3">
                  <Select label="Provider" field="prompter_provider" />
                  <Field label="Model" field="prompter_model" hint="Smaller is better" />
                  <Field label="Base URL" field="prompter_base_url" />
                  <Field label="API Key" field="prompter_api_key" type="password" />
                </div>
              </div>

              <div className="space-y-3">
                <div className="text-xs font-display uppercase tracking-widest text-kernel border-b border-border pb-1">Tick System</div>
                <Field label="Tick Interval (minutes)" field="tick_interval" type="number" hint="How often the AI thinks when idle" />
              </div>
            </div>
          )}
        </div>

        <div className="px-6 py-4 border-t border-border shrink-0 flex items-center gap-3">
          {error && <span className="text-danger text-xs font-body flex-1">{error}</span>}
          {success && <span className="text-kernel text-xs font-body flex-1">✓ Saved</span>}
          {!error && !success && <span className="flex-1" />}
          <button onClick={onClose} className="px-4 py-1.5 text-sm text-dim hover:text-text font-body transition-colors">
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving || loading}
            className="flex items-center gap-2 px-4 py-1.5 bg-accent hover:bg-accent/80 disabled:bg-muted text-void text-sm font-display font-semibold rounded transition-colors"
          >
            {saving ? <RefreshCw size={13} className="animate-spin" /> : <Save size={13} />}
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}
