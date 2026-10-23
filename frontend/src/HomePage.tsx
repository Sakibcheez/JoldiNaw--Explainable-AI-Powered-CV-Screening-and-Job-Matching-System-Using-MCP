import { useState, type FormEvent } from 'react'
import { ArrowDown, ArrowRight, ArrowUpRight, Eye, EyeOff, FileCheck2, LockKeyhole, ScanLine, ShieldCheck, Sparkles, Users } from 'lucide-react'
import { api, setToken } from './api'
import { beginOidc } from './oidc'
import Chatbot from './Chatbot'

export default function HomePage({ onLogin }: { onLogin: () => void }) {
  const [mode, setMode] = useState<'login' | 'signup'>('login')
  const [role, setRole] = useState<'user' | 'recruiter'>('user')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [token, setTokenValue] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function submit(event: FormEvent) {
    event.preventDefault()
    setError('')
    setBusy(true)
    try {
      if (mode === 'signup') {
        await beginOidc(role)
        return
      }
      if (token.trim()) {
        setToken(token.trim())
      } else if (password) {
        const data = await api<{ access_token: string }>('/auth/demo', { method: 'POST', body: JSON.stringify({ password }) })
        setToken(data.access_token)
      } else {
        await beginOidc()
        return
      }
      await api('/me')
      onLogin()
    } catch (reason) {
      setToken('')
      setError(reason instanceof Error ? reason.message : String(reason))
    } finally {
      setBusy(false)
    }
  }

  function changeMode(next: 'login' | 'signup') {
    setMode(next)
    setError('')
  }

  return <main className="home-page">
    <nav className="home-nav">
      <a className="home-brand" href="/" aria-label="JoldiNaw home"><span><ScanLine size={23}/></span>JoldiNaw<span className="home-brand-dot">.</span></a>
      <div className="home-nav-links"><a href="#how-it-works">How it works</a><a href="#principles">Our principles</a></div>
      <a className="home-nav-cta" href="#account">Get started <ArrowUpRight size={16}/></a>
    </nav>

    <section className="home-hero">
      <div className="home-copy">
        <span className="home-kicker"><span className="pulse-dot"/> A MORE HUMAN WAY TO MATCH</span>
        <h1>Make every<br/><span>connection</span> count.</h1>
        <p>Bring job requirements and real experience into focus. Clear evidence, thoughtful decisions, and people at the center.</p>
        <a className="home-primary-link" href="#account">Start with clarity <ArrowDown size={16}/></a>
        <div className="home-trust"><ShieldCheck size={17}/><span>Transparent by design. Human judgment, always.</span></div>
      </div>
      <div className="home-visual" aria-label="Illustration showing a job requirement connected to supporting experience">
        <div className="visual-orbit orbit-one"/>
        <div className="visual-orbit orbit-two"/>
        <div className="visual-chip chip-top"><span className="chip-icon"><FileCheck2 size={18}/></span><span><small>REAL EXPERIENCE</small><strong>Evidence you can inspect</strong></span><span className="chip-status"/></div>
        <div className="visual-core"><div className="core-scan"><ScanLine size={39}/></div><span>THE RIGHT<br/>CONNECTION</span></div>
        <div className="visual-chip chip-bottom"><span className="chip-icon green"><Users size={18}/></span><span><small>HUMAN FIRST</small><strong>Decisions stay with you</strong></span><ShieldCheck size={17}/></div>
        <span className="visual-spark spark-one">+</span><span className="visual-spark spark-two">*</span>
      </div>
    </section>

    <section id="how-it-works" className="home-features">
      <div className="feature-intro"><span className="home-kicker">A CLEARER PROCESS</span><h2>Good matches start<br/>with good questions.</h2></div>
      <article className="feature-card"><span className="feature-number">01</span><span className="feature-icon"><ScanLine size={20}/></span><h3>Define what matters</h3><p>Turn a role into clear, reviewable requirements.</p></article>
      <article className="feature-card"><span className="feature-number">02</span><span className="feature-icon"><FileCheck2 size={20}/></span><h3>See the evidence</h3><p>Trace every connection to a source passage.</p></article>
      <article className="feature-card"><span className="feature-number">03</span><span className="feature-icon"><ShieldCheck size={20}/></span><h3>Keep people in control</h3><p>Tools support decisions; they never make them.</p></article>
    </section>

    <section id="principles" className="home-principles">
      <div><Sparkles size={20}/><strong>Evidence, not guesswork.</strong><span>Every insight points to its source.</span></div>
      <div><LockKeyhole size={20}/><strong>Private by default.</strong><span>Workspace membership is provider-managed.</span></div>
      <div><Users size={20}/><strong>People, not scores.</strong><span>No hiring probabilities or automated rejection.</span></div>
    </section>

    <section className="account-section" id="account">
      <div className="account-copy"><span className="home-kicker">YOUR NEXT STEP</span><h2>Thoughtful work<br/>starts here.</h2><p>Sign in with your organization, or create an account through its identity provider.</p><div className="account-proof"><ShieldCheck size={18}/><span>Your role and workspace access are assigned by your identity provider.</span></div></div>
      <form className="account-card" onSubmit={submit}>
        <div className="account-tabs" role="tablist" aria-label="Account access">
          <button type="button" role="tab" aria-selected={mode === 'login'} className={mode === 'login' ? 'selected' : ''} onClick={() => changeMode('login')}>Sign in</button>
          <button type="button" role="tab" aria-selected={mode === 'signup'} className={mode === 'signup' ? 'selected' : ''} onClick={() => changeMode('signup')}>Create account</button>
        </div>
        <span className="home-kicker">{mode === 'login' ? 'WELCOME BACK' : 'JOIN JOLDINAW'}</span>
        <h2>{mode === 'login' ? 'Your workspace awaits.' : 'Choose how you will use JoldiNaw.'}</h2>
        <p>{mode === 'login' ? 'Continue securely with your organization.' : 'Your identity provider confirms your account and role.'}</p>
        {mode === 'signup' && <fieldset className="role-options"><legend>Account type</legend><label className={role === 'user' ? 'role-choice active' : 'role-choice'}><input type="radio" name="account-role" value="user" checked={role === 'user'} onChange={() => setRole('user')}/><span><strong>User</strong><small>Personal account</small></span></label><label className={role === 'recruiter' ? 'role-choice active' : 'role-choice'}><input type="radio" name="account-role" value="recruiter" checked={role === 'recruiter'} onChange={() => setRole('recruiter')}/><span><strong>Recruiter</strong><small>Organization workspace</small></span></label><small className="role-note">The provider must provision this role; this choice cannot grant workspace access.</small></fieldset>}
        {mode === 'login' && import.meta.env.DEV && <label className="password-field">Local demo password<span className="password-control"><input aria-label="Local demo password" type={showPassword ? 'text' : 'password'} value={password} onChange={event => setPassword(event.target.value)} autoComplete="current-password" placeholder="Enter your demo password"/><button type="button" aria-label={showPassword ? 'Hide password' : 'Show password'} onClick={() => setShowPassword(value => !value)}>{showPassword ? <EyeOff size={17}/> : <Eye size={17}/>}</button></span></label>}
        {mode === 'login' && <details className="token-access"><summary>Use an organization access token</summary><label>OIDC access token<textarea aria-label="OIDC access token" value={token} onChange={event => setTokenValue(event.target.value)} rows={3}/></label></details>}
        {error && <div role="alert" className="error">{error}</div>}
        <button className="account-submit" disabled={busy}>{busy ? 'Connecting...' : mode === 'signup' ? 'Continue to create account' : 'Open workspace'}<ArrowRight size={17}/></button>
        <small className="account-footnote">{mode === 'signup' ? 'New accounts must be created and provisioned by your organization identity provider.' : 'Only upload synthetic or authorized CVs in a recruiter workspace.'}</small>
      </form>
    </section>
    <footer className="home-footer"><a className="home-brand" href="/"><span><ScanLine size={19}/></span>JoldiNaw<span className="home-brand-dot">.</span></a><span>Explainable matching. Human decisions.</span><span>(c) JoldiNaw</span></footer>
    <Chatbot/>
  </main>
}
