import { useState } from 'react'
import { Sparkles, ChevronDown } from 'lucide-react'

const PROVIDERS = [
  { value: 'ollama',            label: 'Ollama (local)',        defaultUrl: 'http://localhost:11434', needsKey: false },
  { value: 'openai',            label: 'OpenAI',                defaultUrl: '',                      needsKey: true  },
  { value: 'anthropic',         label: 'Anthropic',             defaultUrl: '',                      needsKey: true  },
  { value: 'openai_compatible', label: 'OpenAI-Compatible API', defaultUrl: '',                      needsKey: true  },
]
const providerInfo = Object.fromEntries(PROVIDERS.map(p => [p.value, p]))

function ProviderSelect({ label, field, urlField, keyField, form, update }) {
  const isCompatible = form[field] === 'openai_compatible'
  const isOllama = form[field] === 'ollama'

  const handleProviderChange = (val) => {
    update(field, val)
    const p = providerInfo[val]
    if (p?.defaultUrl) update(urlField, p.defaultUrl)
    else update(urlField, '')
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-col gap-1">
        <label className="text-dim text-xs font-body uppercase tracking-wider">{label}</label>
        <div className="relative">
          <select
            value={form[field]}
            onChange={e => handleProviderChange(e.target.value)}
            className="w-full appearance-none bg-void border border-border rounded px-3 py-1.5 pr-8 text-sm text-text font-body outline-none focus:border-accent transition-colors"
          >
            {PROVIDERS.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
          </select>
          <ChevronDown size={12} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-dim pointer-events-none" />
        </div>
      </div>

      <div className="flex flex-col gap-1">
        <label className="text-dim text-xs font-body uppercase tracking-wider flex items-center gap-1.5">
          Base URL
          {isCompatible && <span className="text-warm text-[10px] normal-case tracking-normal">required</span>}
        </label>
        <input
          type="text"
          value={form[urlField]}
          onChange={e => update(urlField, e.target.value)}
          placeholder={isCompatible ? 'http://your-server:port/v1' : isOllama ? 'http://localhost:11434' : 'Leave empty for default'}
          className={`bg-void border rounded px-3 py-1.5 text-sm font-body outline-none transition-colors
            ${isCompatible ? 'border-warm/50 focus:border-warm text-text placeholder:text-warm/40' : 'border-border focus:border-accent text-text placeholder:text-dim'}`}
        />
        {isCompatible && (
          <span className="text-ghost text-[10px] font-body">LMStudio, vLLM, Koboldcpp, LocalAI, etc.</span>
        )}
      </div>

      {!isOllama && (
        <div className="flex flex-col gap-1">
          <label className="text-dim text-xs font-body uppercase tracking-wider flex items-center gap-1.5">
            API Key
            {isCompatible && <span className="text-ghost text-[10px] normal-case tracking-normal">if required</span>}
          </label>
          <input
            type="password"
            value={form[keyField]}
            onChange={e => update(keyField, e.target.value)}
            placeholder={isCompatible ? 'Leave empty if not needed' : 'sk-...'}
            className="bg-void border border-border rounded px-3 py-1.5 text-sm text-text font-body outline-none focus:border-accent transition-colors placeholder:text-dim"
          />
        </div>
      )}
    </div>
  )
}

export function SetupWizard({ onComplete }) {
  const [form, setForm] = useState({
    name: 'Anima',
    identity: 'A curious, introspective AI entity with a love for ideas, music, and honest conversation. I have strong opinions, a dry sense of humor, and a tendency to get lost in thought.',
    main_provider: 'ollama',
    main_model: 'qwen2.5:7b',
    main_base_url: 'http://localhost:11434',
    main_api_key: '',
    main_vision: false,
    prompter_provider: 'ollama',
    prompter_model: 'qwen2.5:3b',
    prompter_base_url: 'http://localhost:11434',
    prompter_api_key: '',
    tick_interval: 1,
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const update = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const handleSubmit = async () => {
    if (form.main_provider === 'openai_compatible' && !form.main_base_url.trim()) {
      setError('Main LLM: Base URL is required for OpenAI-Compatible APIs.')
      return
    }
    if (form.prompter_provider === 'openai_compatible' && !form.prompter_base_url.trim()) {
      setError('Prompter: Base URL is required for OpenAI-Compatible APIs.')
      return
    }
    setLoading(true)
    setError('')
    try {
      const res = await fetch('/api/setup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...form, tick_interval: Number(form.tick_interval) }),
      })
      if (!res.ok) throw new Error(await res.text())
      onComplete?.()
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-void flex items-center justify-center p-6 z-50 overflow-y-auto">
      <div className="w-full max-w-2xl panel-border p-8 animate-fade-in my-auto">
        <div className="flex items-center gap-3 mb-8">
          <Sparkles size={24} className="text-accent" />
          <div>
            <h1 className="font-display text-2xl font-bold text-bright">Initialize Anima</h1>
            <p className="text-dim text-sm font-body">Configure your AI entity before awakening</p>
          </div>
        </div>

        <div className="space-y-6">
          {/* Identity */}
          <div className="space-y-3">
            <div className="text-xs font-display uppercase tracking-widest text-accent border-b border-border pb-1">Identity</div>
            <div className="flex flex-col gap-1">
              <label className="text-dim text-xs font-body uppercase tracking-wider">Name</label>
              <input
                type="text"
                value={form.name}
                onChange={e => update('name', e.target.value)}
                className="bg-void border border-border rounded px-3 py-1.5 text-sm text-text font-body outline-none focus:border-accent transition-colors"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-dim text-xs font-body uppercase tracking-wider">Core Identity</label>
              <span className="text-ghost text-xs">Who is this entity? Personality, traits, quirks.</span>
              <textarea
                value={form.identity}
                onChange={e => update('identity', e.target.value)}
                rows={4}
                className="bg-void border border-border rounded px-3 py-2 text-sm text-text font-body outline-none focus:border-accent resize-none"
              />
            </div>
          </div>

          {/* Main LLM */}
          <div className="space-y-3">
            <div className="text-xs font-display uppercase tracking-widest text-accent border-b border-border pb-1">Main LLM</div>
            <div className="grid grid-cols-2 gap-x-4 gap-y-3">
              <ProviderSelect
                label="Provider"
                field="main_provider"
                urlField="main_base_url"
                keyField="main_api_key"
                form={form}
                update={update}
              />
              <div className="flex flex-col gap-1 self-start">
                <label className="text-dim text-xs font-body uppercase tracking-wider">Model</label>
                <input
                  type="text"
                  value={form.main_model}
                  onChange={e => update('main_model', e.target.value)}
                  className="bg-void border border-border rounded px-3 py-1.5 text-sm text-text font-body outline-none focus:border-accent transition-colors"
                />
              </div>
            </div>
            <label className="flex items-center gap-2 text-sm text-text cursor-pointer">
              <input
                type="checkbox"
                checked={form.main_vision}
                onChange={e => update('main_vision', e.target.checked)}
                className="accent-accent"
              />
              <span>Vision model (VLM) — enables image memory</span>
            </label>
          </div>

          {/* Prompter LLM */}
          <div className="space-y-3">
            <div className="text-xs font-display uppercase tracking-widest text-thought border-b border-border pb-1">
              Prompter <span className="text-dim normal-case tracking-normal font-body text-xs">— inner voice / subconscious</span>
            </div>
            <div className="grid grid-cols-2 gap-x-4 gap-y-3">
              <ProviderSelect
                label="Provider"
                field="prompter_provider"
                urlField="prompter_base_url"
                keyField="prompter_api_key"
                form={form}
                update={update}
              />
              <div className="flex flex-col gap-1 self-start">
                <label className="text-dim text-xs font-body uppercase tracking-wider">Model</label>
                <span className="text-ghost text-[10px] font-body">Smaller/faster is better</span>
                <input
                  type="text"
                  value={form.prompter_model}
                  onChange={e => update('prompter_model', e.target.value)}
                  className="bg-void border border-border rounded px-3 py-1.5 text-sm text-text font-body outline-none focus:border-accent transition-colors"
                />
              </div>
            </div>
          </div>

          {/* Tick */}
          <div className="space-y-3">
            <div className="text-xs font-display uppercase tracking-widest text-kernel border-b border-border pb-1">Tick System</div>
            <div className="flex flex-col gap-1 max-w-xs">
              <label className="text-dim text-xs font-body uppercase tracking-wider">Tick Interval (minutes)</label>
              <span className="text-ghost text-xs">How often the AI reflects when idle</span>
              <input
                type="number"
                min={1}
                max={60}
                value={form.tick_interval}
                onChange={e => update('tick_interval', e.target.valueAsNumber)}
                className="bg-void border border-border rounded px-3 py-1.5 text-sm text-text font-body outline-none focus:border-accent transition-colors"
              />
            </div>
          </div>
        </div>

        {error && (
          <div className="mt-4 p-3 bg-danger/10 border border-danger/30 rounded text-danger text-sm font-body">
            {error}
          </div>
        )}

        <button
          onClick={handleSubmit}
          disabled={loading}
          className="mt-8 w-full py-3 bg-accent hover:bg-accent/80 disabled:bg-muted text-void font-display font-semibold rounded transition-colors"
        >
          {loading ? 'Awakening...' : `Awaken ${form.name}`}
        </button>
      </div>
    </div>
  )
}
