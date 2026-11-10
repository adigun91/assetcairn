import { useDeferredValue, useEffect, useRef, useState } from 'react';
import { Activity, ArrowDownToLine, ArrowRight, Bell, BellRing, CalendarDays, Camera, Check, CheckCircle2, ChevronDown, ChevronRight,
  CircleAlert, Clock3, CreditCard, Download, Edit3, Filter, KeyRound, Laptop, LayoutDashboard, LoaderCircle, LogOut,
  Menu, Monitor, MoreHorizontal, Package, Plus, RefreshCw, Search, ShieldCheck, SlidersHorizontal, Trash2, Users, X } from 'lucide-react';

let csrfToken = '';
async function api(path, options = {}) {
  const response = await fetch(`/api${path}`, { credentials: 'same-origin', ...options,
    headers: { 'Content-Type': 'application/json', 'x-csrf-token': csrfToken, ...options.headers },
    ...(options.body ? { body: JSON.stringify(options.body) } : {}) });
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || 'Something went wrong');
  if (body.csrfToken) csrfToken = body.csrfToken;
  return body;
}

const categories = ['Hardware', 'Software', 'License', 'Subscription', 'Certificate', 'Other'];
const permissionNames = { 'assets:write': 'Manage assets', 'users:manage': 'Manage users', 'roles:manage': 'Manage roles', 'reminders:manage': 'Manage reminders' };
const dateLabel = value => value ? new Date(`${value}T00:00:00Z`).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC' }) : '-';
const moneyLabel = value => value === null || value === undefined || value === '' ? 'Not set' : new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(Number(value));
const today = () => new Date().toISOString().slice(0, 10);
const daysLeft = expiry => Math.round((Date.parse(`${expiry}T00:00:00Z`) - Date.parse(`${today()}T00:00:00Z`)) / 86400000);
const initials = name => name.split(' ').filter(Boolean).slice(0, 2).map(part => part[0]).join('').toUpperCase();
function assetStatus(asset) {
  if (asset.status === 'retired') return { text: 'Retired', tone: 'neutral' };
  const days = daysLeft(asset.expiry_date);
  if (days < 0) return { text: 'Expired', tone: 'danger' };
  if (days <= 5) return { text: days === 0 ? 'Expires today' : `${days} days left`, tone: 'danger' };
  if (days <= 30) return { text: `${days} days left`, tone: 'warning' };
  return { text: 'Active', tone: 'success' };
}
function AssetIcon({ category, size = 20 }) {
  const Icon = ({ Hardware: Laptop, Software: Monitor, License: KeyRound, Subscription: CreditCard, Certificate: ShieldCheck })[category] || Package;
  return <Icon size={size} strokeWidth={1.7} />;
}
function IconButton({ icon: Icon, label, ...props }) {
  return <button className="icon-button" title={label} aria-label={label} {...props}><Icon size={17} /></button>;
}
function Badge({ tone = 'neutral', children }) { return <span className={`badge ${tone}`}><span className="status-dot" />{children}</span>; }
function Field({ label, children, wide = false }) { return <label className={`field ${wide ? 'wide' : ''}`}><span>{label}</span>{children}</label>; }
function Avatar({ user, className = '' }) {
  return <span className={`avatar ${className}`} aria-label={`${user.name} profile picture`}>
    {user.avatar ? <img src={user.avatar} alt="" /> : initials(user.name)}
  </span>;
}
function Empty({ icon: Icon = Package, title, description, action }) {
  return <div className="empty-state"><div className="empty-icon"><Icon size={28} strokeWidth={1.4} /></div><h3>{title}</h3><p>{description}</p>{action}</div>;
}
function Modal({ title, subtitle, children, onClose, wide = false }) {
  const dialog = useRef();
  useEffect(() => { dialog.current.showModal(); }, []);
  return <dialog ref={dialog} className={`modal ${wide ? 'modal-wide' : ''}`} onCancel={onClose} onClick={event => { if (event.target === dialog.current) onClose(); }}>
    <div className="modal-head"><div><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div><IconButton icon={X} label="Close dialog" onClick={onClose} /></div>{children}
  </dialog>;
}

function Authentication({ session, onLogin }) {
  const [form, setForm] = useState({ name: '', email: '', password: '', setupToken: '' });
  const [busy, setBusy] = useState(false); const [error, setError] = useState('');
  const [visible, setVisible] = useState(false);
  const [mode, setMode] = useState(session.needsSetup ? 'create' : 'signin');
  const setup = mode === 'create' && session.needsSetup;
  async function submit(event) {
    event.preventDefault(); setBusy(true); setError('');
    try { const result = await api(setup ? '/auth/setup' : '/auth/login', { method: 'POST', body: form }); onLogin(result.user); }
    catch (failure) { setError(failure.message); } finally { setBusy(false); }
  }
  return <main className="auth-page">
    <div className="auth-brand"><span className="brand-mark"><Activity size={25} /></span><span>AssetCairn<span className="auth-brand-sub">IT ASSET LIFECYCLE</span></span></div>
    <div className="auth-content">
      <div className="auth-photo"><img src="https://images.unsplash.com/photo-1496181133206-80ce9b88a853?auto=format&fit=crop&w=1200&q=85" alt="Laptop and IT equipment" /><span className="photo-label"><Monitor size={15} /> Your assets. Accounted for.</span></div>
      <section className="auth-form"><div className="eyebrow">YOUR WORKSPACE, CONNECTED</div><h1>{setup ? 'A fresh start.' : mode === 'create' ? 'Workspace ready.' : 'Welcome back.'}</h1><p className="auth-subtitle">{setup ? 'Create your administrator account.' : mode === 'create' ? 'This installation already has a workspace.' : 'Sign in to your asset workspace.'}</p>
        <div className="auth-mode-switch" role="tablist" aria-label="Choose an authentication option">
          <button type="button" role="tab" aria-selected={mode === 'signin'} className={mode === 'signin' ? 'active' : ''} onClick={() => { setMode('signin'); setError(''); }}>Sign in</button>
          <button type="button" role="tab" aria-selected={mode === 'create'} className={mode === 'create' ? 'active' : ''} onClick={() => { setMode('create'); setError(''); }}>Create workspace</button>
        </div>
        {mode === 'create' && !session.needsSetup ? <div className="workspace-exists" role="status"><ShieldCheck size={19} /><div><strong>A workspace already exists here.</strong><p>Separate workspaces aren’t enabled on this installation. Ask the workspace administrator to add you as a user.</p></div></div> : <form onSubmit={submit} className="form-stack">
          {setup && <Field label="Full name"><input required minLength={2} maxLength={100} autoComplete="name" value={form.name} onChange={event => setForm({ ...form, name: event.target.value })} placeholder="Your full name" /></Field>}
          <Field label="Email address"><input type="email" required autoComplete="username" value={form.email} onChange={event => setForm({ ...form, email: event.target.value })} placeholder="you@company.com" />{setup && <small className="field-hint">Use your organization's email address. Personal email providers aren't accepted.</small>}</Field>
          <Field label="Password"><div className="password-input"><input type={visible ? 'text' : 'password'} required minLength={setup ? 12 : 1} maxLength={72} autoComplete={setup ? 'new-password' : 'current-password'} value={form.password} onChange={event => setForm({ ...form, password: event.target.value })} placeholder={setup ? 'At least 12 characters' : 'Your password'} /><button type="button" onClick={() => setVisible(!visible)}>{visible ? 'Hide' : 'Show'}</button></div></Field>
          {setup && session.setupTokenRequired && <Field label="Setup token"><input type="password" required autoComplete="off" value={form.setupToken} onChange={event => setForm({ ...form, setupToken: event.target.value })} /></Field>}
          {error && <div className="form-error" role="alert"><CircleAlert size={16} />{error}</div>}
          <button className="button primary auth-submit" disabled={busy}>{busy ? <LoaderCircle size={18} className="spin" /> : null}{setup ? 'Create workspace' : 'Sign in'}<ArrowRight size={18} /></button>
        </form>}
        <div className="auth-security"><ShieldCheck size={16} /> Private workspace. Secure access.</div>
      </section>
    </div><div className="auth-footer"><span>AssetCairn</span><span>IT assets, clearly tracked.</span><span>© 2026 Powered by autom8 Inc ®</span></div>
  </main>;
}

function EmailSettings({ onSaved, defaultRecipient }) {
  const [form, setForm] = useState(null);
  const [password, setPassword] = useState('');
  const [replacePassword, setReplacePassword] = useState(false);
  const [recipient, setRecipient] = useState(defaultRecipient || '');
  const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  async function load() {
    setError('');
    try { setForm(await api('/reminders/email')); } catch (failure) { setError(failure.message); }
  }
  useEffect(() => { load(); }, []);
  function update(key, value) { setForm(current => ({ ...current, [key]: value })); setDirty(true); setMessage(''); }
  async function saveEmail(event) {
    event.preventDefault(); setBusy(true); setError(''); setMessage('');
    try {
      const body = { host: form.host, port: Number(form.port), security: form.security, username: form.username, from_email: form.from_email,
        ...((replacePassword || !form.has_password) ? { password } : {}) };
      await api('/reminders/email', { method: 'PUT', body });
      setPassword(''); setReplacePassword(false); setDirty(false);
      await load(); await onSaved(); setMessage('Email settings saved. Delivery not yet verified.');
    } catch (failure) { setError(failure.message); } finally { setBusy(false); }
  }
  async function testEmail(event) {
    event.preventDefault(); setBusy(true); setError(''); setMessage('');
    try { const result = await api('/reminders/test-email', { method: 'POST', body: { recipient } }); setMessage(result.message); }
    catch (failure) { setError(failure.message); } finally { setBusy(false); }
  }
  return <section className="management-section email-settings"><div className="management-toolbar"><h2><Bell size={18} />Email configuration</h2><span className="subtle-label">{form?.source === 'saved' ? 'Saved configuration' : 'Environment defaults'}</span></div>
    {!form ? <div className="modal-body">{error ? <div className="form-error" role="alert">{error}<button className="button secondary" onClick={load}>Retry</button></div> : <LoaderCircle className="spin" size={20} />}</div> : <>
      <form onSubmit={saveEmail}><fieldset disabled={busy} className="email-fieldset"><div className="form-grid">
        <Field label="SMTP server"><input required maxLength={253} placeholder="smtp.example.com" value={form.host} onChange={event => update('host', event.target.value)} /></Field>
        <Field label="Port"><input required type="number" min={1} max={65535} value={form.port} onChange={event => update('port', event.target.value)} /></Field>
        <Field label="Encryption"><select value={form.security} onChange={event => update('security', event.target.value)}><option value="starttls">STARTTLS</option><option value="ssl">SSL / TLS</option></select></Field>
        <Field label="Sender email"><input required type="email" maxLength={254} placeholder="assets@company.com" value={form.from_email} onChange={event => update('from_email', event.target.value)} /></Field>
        <Field label="SMTP username"><input autoComplete="off" maxLength={254} value={form.username} onChange={event => update('username', event.target.value)} /></Field>
        <Field label={form.has_password ? 'New SMTP password' : 'SMTP password'}><input type="password" autoComplete="new-password" maxLength={4096} disabled={form.has_password && !replacePassword} value={password} placeholder={form.has_password && !replacePassword ? 'Password saved' : 'Provider password or app password'} onChange={event => { setPassword(event.target.value); setDirty(true); setMessage(''); }} /></Field>
        {form.has_password && <label className="checkbox-row wide"><input type="checkbox" checked={replacePassword} onChange={event => { setReplacePassword(event.target.checked); setPassword(''); setDirty(true); setMessage(''); }} /><span>Replace saved password</span></label>}
      </div><div className="email-actions"><button className="button primary" disabled={busy}>{busy ? <LoaderCircle className="spin" size={16} /> : <Check size={16} />}Save email settings</button></div></fieldset></form>
      <form className="email-test" onSubmit={testEmail}><Field label="Test recipient"><input required type="email" maxLength={254} value={recipient} onChange={event => setRecipient(event.target.value)} /></Field><button className="button secondary" disabled={busy || dirty || !form.host || !form.from_email}><Bell size={16} />Send test email</button></form>
      {error && <div className="email-feedback form-error" role="alert">{error}</div>}{message && <div className="email-feedback" role="status">{message}</div>}
    </>}
  </section>;
}

function AssetForm({ asset, directory, onSave, onClose }) {
  const [credentials, setCredentials] = useState({ username: '', password: '', url: '' });
  const [form, setForm] = useState(asset ? { ...asset, owner_id: asset.owner_id || '', cost: asset.cost || 0 } : {
    name: '', tag: '', category: 'Hardware', vendor: '', registration_date: today(), expiry_date: '', renewal_date: '',
    owner_id: '', notification_email: '', cost: 0, asset_price: '', renewal_price: '',
    depreciation_acquisition_cost: '', depreciation_salvage_value: '', depreciation_useful_life_months: '',
    depreciation_method: '', depreciation_start_date: '', notes: '', status: 'active'
  });
  const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  const update = key => event => setForm({ ...form, [key]: event.target.value });
  const updateCategory = event => {
    const category = event.target.value;
    setForm({ ...form, category, ...(category === 'Hardware' ? {} : {
      depreciation_acquisition_cost: '', depreciation_salvage_value: '', depreciation_useful_life_months: '',
      depreciation_method: '', depreciation_start_date: ''
    }) });
  };
  async function submit(event) {
    event.preventDefault(); setBusy(true); setError('');
    const amount = value => value === '' || value === null || value === undefined ? null : Number(value);
    try { await onSave({ ...form, owner_id: form.owner_id ? Number(form.owner_id) : null, cost: Number(form.cost),
      asset_price: amount(form.asset_price), renewal_price: amount(form.renewal_price),
      depreciation_acquisition_cost: form.category === 'Hardware' ? amount(form.depreciation_acquisition_cost) : null,
      depreciation_salvage_value: form.category === 'Hardware' ? amount(form.depreciation_salvage_value) : null,
      depreciation_useful_life_months: form.category === 'Hardware' ? amount(form.depreciation_useful_life_months) : null,
      depreciation_method: form.category === 'Hardware' ? form.depreciation_method : '',
      depreciation_start_date: form.category === 'Hardware' ? (form.depreciation_start_date || null) : null,
      ...(!asset && Object.values(credentials).some(Boolean) ? { credentials } : {}) }); }
    catch (failure) { setError(failure.message); setBusy(false); }
  }
  return <Modal title={asset ? 'Edit asset' : 'Add an IT asset'} subtitle={asset ? asset.tag : 'Asset details and renewal dates'} onClose={onClose} wide>
    <form onSubmit={submit}><div className="form-grid">
      <Field label="Asset name" wide><input required minLength={2} maxLength={150} placeholder="e.g. Microsoft 365 Business" value={form.name} onChange={update('name')} autoFocus /></Field>
      <Field label="Asset tag"><input required maxLength={50} placeholder="e.g. SW-001" value={form.tag} onChange={update('tag')} /></Field>
      <Field label="Category"><select value={form.category} onChange={updateCategory}>{categories.map(category => <option key={category}>{category}</option>)}</select></Field>
      <Field label="Vendor"><input maxLength={100} placeholder="Vendor or provider" value={form.vendor} onChange={update('vendor')} /></Field>
      <Field label="Annual running cost (USD)"><input type="number" min={0} max={1000000000} step="0.01" value={form.cost} onChange={update('cost')} /></Field>
      <Field label="Asset price (USD)"><input type="number" min={0} max={1000000000} step="0.01" placeholder="Purchase price" value={form.asset_price ?? ''} onChange={update('asset_price')} /></Field>
      <Field label="Renewal price (USD)"><input type="number" min={0} max={1000000000} step="0.01" placeholder="Expected renewal price" value={form.renewal_price ?? ''} onChange={update('renewal_price')} /></Field>
      {form.category === 'Hardware' && <>
        <div className="form-divider wide"><SlidersHorizontal size={16} /><span>Hardware depreciation</span></div>
        <Field label="Acquisition cost (USD)"><input type="number" min={0} max={1000000000} step="0.01" placeholder="Original capitalized cost" value={form.depreciation_acquisition_cost ?? ''} onChange={update('depreciation_acquisition_cost')} /></Field>
        <Field label="Salvage value (USD)"><input type="number" min={0} max={1000000000} step="0.01" placeholder="Estimated residual value" value={form.depreciation_salvage_value ?? ''} onChange={update('depreciation_salvage_value')} /></Field>
        <Field label="Useful life (months)"><input type="number" min={1} max={1200} step="1" placeholder="e.g. 36" value={form.depreciation_useful_life_months ?? ''} onChange={update('depreciation_useful_life_months')} /></Field>
        <Field label="Depreciation method"><select value={form.depreciation_method || ''} onChange={update('depreciation_method')}><option value="">Select method</option><option value="straight_line">Straight-line</option><option value="double_declining_balance">Double-declining balance</option></select></Field>
        <Field label="Depreciation start date"><input type="date" value={form.depreciation_start_date || ''} onChange={update('depreciation_start_date')} /></Field>
      </>}
      <div className="form-divider wide"><KeyRound size={16} /><span>Login credentials</span></div>
      {!asset ? <>
        <Field label="Asset login username"><input maxLength={254} autoComplete="off" placeholder="Username or email address" value={credentials.username} onChange={event => setCredentials({ ...credentials, username: event.target.value })} /></Field>
        <Field label="Asset login password"><input type="password" maxLength={4096} autoComplete="new-password" value={credentials.password} onChange={event => setCredentials({ ...credentials, password: event.target.value })} /></Field>
        <Field label="Login URL" wide><input type="url" maxLength={1000} placeholder="https://service.example.com/login" value={credentials.url} onChange={event => setCredentials({ ...credentials, url: event.target.value })} /></Field>
      </> : <div className="wide"><span className="field-label">{asset.has_credentials ? 'Credentials saved' : 'No credentials saved'}</span><button type="button" className="button secondary" onClick={() => onClose('credentials')}><KeyRound size={16} />Manage login credentials</button></div>}
      <div className="form-divider wide"><CalendarDays size={16} /><span>Lifecycle dates</span></div>
      <Field label="Registration date"><input type="date" required value={form.registration_date} onChange={update('registration_date')} /></Field>
      <Field label="Expiry date"><input type="date" required min={form.registration_date} value={form.expiry_date} onChange={update('expiry_date')} /></Field>
      <Field label="Expected renewal date"><input type="date" required min={form.registration_date} value={form.renewal_date} onChange={update('renewal_date')} /></Field>
      <Field label="Lifecycle state"><select value={form.status} onChange={update('status')}><option value="active">Active</option><option value="retired">Retired</option></select></Field>
      <div className="form-divider wide"><Bell size={16} /><span>Ownership & notifications</span></div>
      <Field label="Assigned owner"><select value={form.owner_id} onChange={update('owner_id')}><option value="">Unassigned</option>{directory.map(user => <option key={user.id} value={user.id}>{user.name}</option>)}</select></Field>
      <Field label="Additional notification email"><input type="email" maxLength={254} placeholder="it@company.com" value={form.notification_email} onChange={update('notification_email')} /></Field>
      <Field label="Notes" wide><textarea rows={3} maxLength={2000} placeholder="Serial number, renewal reference, or other details" value={form.notes} onChange={update('notes')} /></Field>
      {error && <div className="form-error wide" role="alert"><CircleAlert size={16} />{error}</div>}
    </div><div className="modal-footer"><button type="button" className="button secondary" onClick={onClose}>Cancel</button><button className="button primary" disabled={busy}>{busy ? <LoaderCircle className="spin" size={16} /> : <Check size={16} />}{asset ? 'Save changes' : 'Add asset'}</button></div></form>
  </Modal>;
}

function UserForm({ user, roles, onSave, onClose }) {
  const [form, setForm] = useState({ name: user?.name || '', email: user?.email || '', role_id: user?.role_id || roles.find(role => role.name === 'Viewer')?.id || '', active: user?.active ?? true, password: '' });
  const [busy, setBusy] = useState(false); const [error, setError] = useState('');
  async function submit(event) {
    event.preventDefault(); setBusy(true); setError('');
    try { await onSave({ ...form, role_id: Number(form.role_id), ...(form.password ? {} : { password: undefined }) }); }
    catch (failure) { setError(failure.message); setBusy(false); }
  }
  return <Modal title={user ? 'Edit user' : 'Add a user'} subtitle="Workspace access" onClose={onClose}><form onSubmit={submit}><div className="form-stack modal-body">
    <Field label="Full name"><input required autoFocus minLength={2} maxLength={100} value={form.name} onChange={event => setForm({ ...form, name: event.target.value })} /></Field>
    <Field label="Email address"><input type="email" required value={form.email} onChange={event => setForm({ ...form, email: event.target.value })} /></Field>
    <Field label="Role"><select required value={form.role_id} onChange={event => setForm({ ...form, role_id: event.target.value })}>{roles.map(role => <option key={role.id} value={role.id}>{role.name}</option>)}</select></Field>
    <Field label={user ? 'New password (optional)' : 'Initial password'}><input type="password" required={!user} minLength={12} maxLength={72} autoComplete="new-password" placeholder="At least 12 characters" value={form.password} onChange={event => setForm({ ...form, password: event.target.value })} /></Field>
    {user && <label className="checkbox-row"><input type="checkbox" checked={form.active} onChange={event => setForm({ ...form, active: event.target.checked })} /><span>Active account</span></label>}
    {error && <div className="form-error" role="alert">{error}</div>}
  </div><div className="modal-footer"><button type="button" className="button secondary" onClick={onClose}>Cancel</button><button className="button primary" disabled={busy}>{busy ? <LoaderCircle className="spin" size={16} /> : <Check size={16} />}{user ? 'Save changes' : 'Create user'}</button></div></form></Modal>;
}

function RoleForm({ role, onSave, onClose }) {
  const [name, setName] = useState(role?.name || ''); const [permissions, setPermissions] = useState(role?.permissions || []);
  const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  async function submit(event) {
    event.preventDefault(); setBusy(true); setError('');
    try { await onSave({ name, permissions }); } catch (failure) { setError(failure.message); setBusy(false); }
  }
  return <Modal title={role ? 'Edit role' : 'Add a role'} subtitle="Workspace permissions" onClose={onClose}><form onSubmit={submit}><div className="modal-body form-stack">
    <Field label="Role name"><input required autoFocus minLength={2} maxLength={60} value={name} onChange={event => setName(event.target.value)} placeholder="e.g. IT Operations" /></Field>
    <span className="field-label">Permissions</span><div className="permission-list">
      {Object.entries(permissionNames).map(([permission, label]) => <label className="checkbox-row" key={permission}><input type="checkbox" checked={permissions.includes(permission)} onChange={event => setPermissions(event.target.checked ? [...permissions, permission] : permissions.filter(value => value !== permission))} /><span>{label}</span></label>)}
    </div>{error && <div className="form-error" role="alert">{error}</div>}
  </div><div className="modal-footer"><button type="button" className="button secondary" onClick={onClose}>Cancel</button><button className="button primary" disabled={busy}><Check size={16} />{role ? 'Save changes' : 'Create role'}</button></div></form></Modal>;
}

function PasswordForm({ onClose, onSave }) {
  const [form, setForm] = useState({ currentPassword: '', password: '' }); const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  async function submit(event) {
    event.preventDefault(); setBusy(true);
    try { await api('/auth/password', { method: 'POST', body: form }); onSave(); } catch (failure) { setError(failure.message); setBusy(false); }
  }
  return <Modal title="Change password" onClose={onClose}><form onSubmit={submit}><div className="modal-body form-stack"><Field label="Current password"><input type="password" required autoComplete="current-password" value={form.currentPassword} onChange={event => setForm({ ...form, currentPassword: event.target.value })} /></Field><Field label="New password"><input type="password" required minLength={12} maxLength={72} autoComplete="new-password" value={form.password} onChange={event => setForm({ ...form, password: event.target.value })} /></Field>{error && <div className="form-error" role="alert">{error}</div>}</div><div className="modal-footer"><button className="button primary" disabled={busy}><KeyRound size={16} />Update password</button></div></form></Modal>;
}

function AssetCredentials({ asset, canWrite, onClose, onSaved }) {
  const [form, setForm] = useState(null);
  const [password, setPassword] = useState('');
  const [replacePassword, setReplacePassword] = useState(false);
  const [revealed, setRevealed] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [confirmRemoval, setConfirmRemoval] = useState(false);
  const endpoint = `/assets/${asset.id}/credentials`;
  useEffect(() => {
    let active = true;
    api(endpoint).then(data => { if (active) setForm({ username: data.username, url: data.url, hasPassword: Boolean(data.password) }); })
      .catch(failure => { if (active) setError(failure.message); });
    return () => { active = false; };
  }, [endpoint]);
  useEffect(() => { if (!revealed) return; const timer = setTimeout(() => setRevealed(''), 30000); return () => clearTimeout(timer); }, [revealed]);
  async function saveCredentials(event) {
    event.preventDefault(); setBusy(true); setError(''); setRevealed('');
    try { await api(endpoint, { method: 'PUT', body: { username: form.username, url: form.url,
      ...((replacePassword || !form.hasPassword) ? { password } : {}) } }); await onSaved('Asset credentials saved'); }
    catch (failure) { setError(failure.message); setBusy(false); }
  }
  async function toggleReveal() {
    if (revealed) { setRevealed(''); return; }
    setBusy(true); setError('');
    try { const data = await api(endpoint); setRevealed(data.password); }
    catch (failure) { setError(failure.message); } finally { setBusy(false); }
  }
  return <Modal title="Login credentials" subtitle={`${asset.name} / ${asset.tag}`} onClose={onClose}>
    <form onSubmit={saveCredentials}><div className="modal-body form-stack">
      {form ? <>
        <Field label="Asset login username"><input readOnly={!canWrite} maxLength={254} autoComplete="off" value={form.username} onChange={event => setForm({ ...form, username: event.target.value })} /></Field>
        <Field label="Login URL"><input readOnly={!canWrite} type="url" maxLength={1000} value={form.url} onChange={event => setForm({ ...form, url: event.target.value })} /></Field>
        {form.hasPassword && <Field label="Saved password"><div className="password-input"><input readOnly type={revealed ? 'text' : 'password'} value={revealed || '************'} autoComplete="off" /><button type="button" disabled={busy} onClick={toggleReveal}>{revealed ? 'Hide' : 'Show'}</button></div></Field>}
        {canWrite && <>
          {form.hasPassword && <label className="checkbox-row"><input type="checkbox" checked={replacePassword} onChange={event => { setReplacePassword(event.target.checked); setPassword(''); setRevealed(''); }} /><span>Replace password</span></label>}
          {(!form.hasPassword || replacePassword) && <Field label="New asset password"><input type="password" maxLength={4096} autoComplete="new-password" value={password} onChange={event => setPassword(event.target.value)} /></Field>}
          {asset.has_credentials && <label className="checkbox-row"><input type="checkbox" checked={confirmRemoval} onChange={event => setConfirmRemoval(event.target.checked)} /><span>Remove all saved login credentials</span></label>}
        </>}
      </> : !error && <LoaderCircle className="spin" size={20} />}
      {error && <div className="form-error" role="alert">{error}</div>}
    </div><div className="modal-footer"><button type="button" className="button secondary" onClick={onClose}>Close</button>
      {canWrite && (confirmRemoval ? <button type="button" className="button destructive" disabled={busy || !form} onClick={async () => { setBusy(true); setRevealed(''); try { await api(endpoint, { method: 'DELETE' }); await onSaved('Asset credentials removed'); } catch (failure) { setError(failure.message); setBusy(false); } }}><Trash2 size={16} />Remove credentials</button> : <button className="button primary" disabled={busy || !form}><Check size={16} />Save credentials</button>)}
    </div></form>
  </Modal>;
}

function AssetTable({ assets, canWrite, userId, onCredentials, onOpen, onEdit, onDelete, onAdd }) {
  if (!assets.length) return <Empty title="No assets found" description="Your asset register is ready for its first entry." action={canWrite && <button className="button primary" onClick={onAdd}><Plus size={17} />Add asset</button>} />;
  return <div className="table-scroll"><table className="asset-table"><thead><tr><th>Asset <ChevronDown size={12} /></th><th>Assigned to</th><th>Asset price</th><th>Renewal price</th><th>Login credentials</th><th>Registered</th><th>Expiry date</th><th>Expected renewal</th><th>Status</th><th><span className="sr-only">Actions</span></th></tr></thead><tbody>
    {assets.map(asset => { const status = assetStatus(asset); return <tr key={asset.id} className="asset-row" tabIndex={0} aria-label={`View details for ${asset.name}`} onClick={event => { if (!event.target.closest('button, a, input, select, textarea')) onOpen(asset); }} onKeyDown={event => { if (event.target === event.currentTarget && (event.key === 'Enter' || event.key === ' ')) { event.preventDefault(); onOpen(asset); } }}>
      <td><div className="asset-cell"><span className={`asset-icon category-${asset.category.toLowerCase()}`}><AssetIcon category={asset.category} /></span><div><button className="asset-name" aria-label={`View details for ${asset.name}`} onClick={event => { event.stopPropagation(); onOpen(asset); }}>{asset.name}</button><span className="asset-meta">{asset.tag}<span className="meta-dot">·</span>{asset.category}</span></div></div></td>
      <td>{asset.owner_name ? <div className="owner-cell"><span className="avatar small">{initials(asset.owner_name)}</span><span>{asset.owner_name}</span></div> : <span className="muted">Unassigned</span>}</td>
      <td className="date-cell">{moneyLabel(asset.asset_price)}</td><td className="date-cell">{moneyLabel(asset.renewal_price)}</td>
      <td><div className="owner-cell"><span className="muted">{asset.has_credentials ? 'Saved' : 'Not set'}</span>{(canWrite || asset.owner_id === userId) && <IconButton icon={KeyRound} label={`Login credentials for ${asset.name}`} onClick={() => onCredentials(asset)} />}</div></td>
      <td className="date-cell">{dateLabel(asset.registration_date)}</td><td className={`date-cell ${status.tone === 'danger' ? 'text-danger' : ''}`}>{dateLabel(asset.expiry_date)}</td><td className="date-cell muted">{dateLabel(asset.renewal_date)}</td>
      <td><Badge tone={status.tone}>{status.text}</Badge></td><td><div className="row-actions">{canWrite ? <><IconButton icon={Edit3} label={`Edit ${asset.name}`} onClick={() => onEdit(asset)} /><IconButton icon={Trash2} label={`Delete ${asset.name}`} onClick={() => onDelete(asset)} /></> : <IconButton icon={MoreHorizontal} label={`View ${asset.name}`} onClick={() => onEdit(asset)} />}</div></td>
    </tr>; })}
  </tbody></table></div>;
}

function exportAssets(assets) {
  const columns = ['name', 'tag', 'category', 'vendor', 'owner_name', 'asset_price', 'renewal_price', 'registration_date', 'expiry_date', 'renewal_date', 'status', 'notification_email', 'cost', 'notes'];
  const cell = value => { let text = String(value ?? ''); if (/^[=+\-@\t\r]/.test(text)) text = `'${text}`; return `"${text.replaceAll('"', '""')}"`; };
  const csv = [columns.map(cell).join(','), ...assets.map(asset => columns.map(column => cell(asset[column])).join(','))].join('\r\n');
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8;' }));
  const anchor = document.createElement('a'); anchor.href = url; anchor.download = `it-assets-${today()}.csv`; anchor.click(); URL.revokeObjectURL(url);
}

export default function App() {
  const [session, setSession] = useState(null); const [user, setUser] = useState(null);
  const [page, setPage] = useState('overview'); const [assets, setAssets] = useState([]); const [directory, setDirectory] = useState([]);
  const [selectedAssetId, setSelectedAssetId] = useState(null); const [assetListPage, setAssetListPage] = useState('assets');
  const [users, setUsers] = useState([]); const [roles, setRoles] = useState([]); const [roleOptions, setRoleOptions] = useState([]);
  const [reminders, setReminders] = useState(null); const [loading, setLoading] = useState(true); const [error, setError] = useState('');
  const [query, setQuery] = useState(''); const deferredQuery = useDeferredValue(query); const [category, setCategory] = useState('All categories');
  const [statusFilter, setStatusFilter] = useState('all'); const [modal, setModal] = useState(null); const [toast, setToast] = useState('');
  const [mobileOpen, setMobileOpen] = useState(false); const [sending, setSending] = useState(false); const [pageNumber, setPageNumber] = useState(1);
  const can = permission => user?.permissions.includes(permission);
  async function refresh(currentUser = user) {
    const permitted = permission => currentUser?.permissions.includes(permission);
    setError('');
    const [assetData, ownerData, userData, roleData, reminderData, options] = await Promise.all([
      api('/assets'), api('/directory'), permitted('users:manage') ? api('/users') : [],
      permitted('roles:manage') ? api('/roles') : [], permitted('reminders:manage') ? api('/reminders') : null,
      permitted('users:manage') ? api('/role-options') : []
    ]);
    setAssets(assetData); setDirectory(ownerData); setUsers(userData); setRoles(roleData); setReminders(reminderData); setRoleOptions(options);
  }
  useEffect(() => { let active = true; api('/auth/session').then(result => { if (active) { setSession(result); setUser(result.user); } }).catch(failure => { if (active) setError(failure.message); }).finally(() => { if (active) setLoading(false); }); return () => { active = false; }; }, []);
  useEffect(() => { if (user) { setLoading(true); refresh(user).catch(failure => setError(failure.message)).finally(() => setLoading(false)); } }, [user]);
  useEffect(() => { if (!toast) return; const timeout = setTimeout(() => setToast(''), 5000); return () => clearTimeout(timeout); }, [toast]);
  useEffect(() => { setPageNumber(1); }, [deferredQuery, category, statusFilter, page]);
  function navigate(next) { setPage(next); setQuery(''); setStatusFilter('all'); setCategory('All categories'); setMobileOpen(false); }
  function openAsset(asset) { setSelectedAssetId(asset.id); setAssetListPage(page === 'overview' ? 'overview' : 'assets'); setPage('asset-detail'); }
  async function save(path, method, body, message) {
    await api(path, { method, body }); setModal(null); setToast(message);
    await refresh();
    const next = await api('/auth/session'); setUser(next.user); setSession(next);
  }
  async function signOut() {
    try { await api('/auth/logout', { method: 'POST' }); const result = await api('/auth/session'); setSession(result); setUser(null); navigate('overview'); }
    catch (failure) { setError(failure.message); }
  }
  const activeAssets = assets.filter(asset => asset.status === 'active');
  const due = activeAssets.filter(asset => daysLeft(asset.expiry_date) >= 0 && daysLeft(asset.expiry_date) <= 30);
  const expired = activeAssets.filter(asset => daysLeft(asset.expiry_date) < 0);
  const healthy = activeAssets.filter(asset => daysLeft(asset.expiry_date) > 30);
  const filtered = assets.filter(asset => {
    const matchesQuery = `${asset.name} ${asset.tag} ${asset.vendor} ${asset.owner_name || ''}`.toLowerCase().includes(deferredQuery.toLowerCase());
    const matchesCategory = category === 'All categories' || asset.category === category;
    const remaining = daysLeft(asset.expiry_date);
    const matchesStatus = statusFilter === 'all' || (statusFilter === 'due' && asset.status === 'active' && remaining >= 0 && remaining <= 30)
      || (statusFilter === 'expired' && asset.status === 'active' && remaining < 0) || (statusFilter === 'active' && asset.status === 'active' && remaining > 30) || (statusFilter === 'retired' && asset.status === 'retired');
    return matchesQuery && matchesCategory && matchesStatus;
  });
  const pageSize = page === 'overview' ? 6 : 10;
  const maxPage = Math.max(1, Math.ceil(filtered.length / pageSize));
  const currentPage = Math.min(pageNumber, maxPage);
  const visibleAssets = filtered.slice((currentPage - 1) * pageSize, currentPage * pageSize);
  const selectedAsset = assets.find(asset => asset.id === selectedAssetId) || null;
  const navigation = [{ id: 'overview', label: 'Overview', icon: LayoutDashboard }, { id: 'assets', label: 'Asset register', icon: Package },
    ...(can('users:manage') ? [{ id: 'users', label: 'Users', icon: Users }] : []), ...(can('roles:manage') ? [{ id: 'roles', label: 'Roles & access', icon: ShieldCheck }] : []),
    ...(can('reminders:manage') ? [{ id: 'reminders', label: 'Reminders', icon: Bell }] : []), { id: 'profile', label: 'My profile', icon: Users }];
  const titles = { overview: ['Asset overview', 'A clear view of every asset, from registration to renewal.'], assets: ['Asset register', 'Your hardware, software, and subscriptions in one place.'], users: ['Workspace users', 'The people behind your assets.'], roles: ['Roles & access', 'The right access, for the right people.'], reminders: ['Renewal reminders', 'Stay ahead of the next expiry.'], profile: ['My profile', 'Manage your profile photo and account details.'] };

  if (!session && loading) return <div className="loading-page"><Activity size={36} /><span>Opening workspace...</span></div>;
  if (!session) return <div className="loading-page"><CircleAlert size={30} /><p>{error || 'Unable to connect to the server'}</p><button className="button primary" onClick={() => location.reload()}><RefreshCw size={16} />Retry</button></div>;
  if (!user) return <Authentication session={session} onLogin={setUser} />;

  return <div className="app-shell">
    {mobileOpen && <div className="nav-backdrop" onClick={() => setMobileOpen(false)} />}
    <aside className={`sidebar ${mobileOpen ? 'open' : ''}`}>
      <a className="brand" href="#" onClick={event => { event.preventDefault(); navigate('overview'); }}><span className="brand-mark"><Activity size={23} /></span><span>AssetCairn<small>IT ASSET LIFECYCLE</small></span></a>
      <div className="workspace-chip"><span className="workspace-symbol"><Monitor size={18} /></span><div>IT workspace<small>Asset management</small></div><ChevronDown size={14} /></div>
      <span className="nav-label">WORKSPACE</span><nav>{navigation.map(item => <button className={`nav-item ${page === item.id || (page === 'asset-detail' && item.id === 'assets') ? 'selected' : ''}`} key={item.id} onClick={() => navigate(item.id)}><item.icon size={19} strokeWidth={1.7} /><span>{item.label}</span>{item.id === 'assets' && assets.length > 0 && <span className="nav-count">{assets.length}</span>}</button>)}</nav>
      <div className="sidebar-bottom"><div className="sidebar-status"><span className="live-dot" />Workspace connected</div><div className="account"><Avatar user={user} /><div><strong>{user.name}</strong><small>{user.role}</small></div><IconButton icon={LogOut} label="Sign out" onClick={signOut} /></div></div>
    </aside>
    <div className="main-shell"><header className="topbar"><div className="breadcrumb"><IconButton icon={Menu} label="Open navigation" onClick={() => setMobileOpen(true)} className="icon-button mobile-menu" /><span>Workspace</span><ChevronRight size={14} /><strong>{page === 'asset-detail' ? 'Asset details' : page === 'profile' ? 'My profile' : navigation.find(item => item.id === page)?.label}</strong></div><div className="topbar-right"><span className="current-date"><CalendarDays size={15} />{new Date().toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}</span><span className="topbar-divider" /><IconButton icon={KeyRound} label="Change password" onClick={() => setModal({ type: 'password' })} /><button type="button" className="profile-trigger" aria-label="Open profile" title="My profile" onClick={() => navigate('profile')}><Avatar user={user} className="topbar-avatar" /></button></div></header>
      <main className="main-content"><div className="page-heading"><div><div className="eyebrow">{page === 'overview' ? 'THE BIG PICTURE' : 'IT WORKSPACE'}</div><h1>{page === 'asset-detail' ? selectedAsset?.name || 'Asset details' : titles[page][0]}</h1><p>{page === 'asset-detail' ? `${selectedAsset?.tag || ''} · Complete asset record` : titles[page][1]}</p></div><div className="heading-actions">
        {['overview', 'assets'].includes(page) && <><button className="button secondary" onClick={() => exportAssets(filtered)}><Download size={16} /><span>Export</span></button>{can('assets:write') && <button className="button primary" onClick={() => setModal({ type: 'asset' })}><Plus size={17} />Add asset</button>}</>}
        {page === 'asset-detail' && <><button className="button secondary" onClick={() => { setPage(assetListPage); setSelectedAssetId(null); }}><ArrowRight className="back-arrow" size={16} />Back to register</button>{can('assets:write') && selectedAsset && <button className="button primary" onClick={() => setModal({ type: 'asset', item: selectedAsset })}><Edit3 size={16} />Edit asset</button>}</>}
        {page === 'users' && <button className="button primary" onClick={() => setModal({ type: 'user' })}><Plus size={17} />Add user</button>}
        {page === 'roles' && <button className="button primary" onClick={() => setModal({ type: 'role' })}><Plus size={17} />Add role</button>}
      </div></div>
      {error && <div className="error-banner" role="alert"><CircleAlert size={18} /><span>{error}</span><button className="button secondary" onClick={() => refresh().catch(failure => setError(failure.message))}><RefreshCw size={15} />Retry</button><IconButton icon={X} label="Dismiss error" onClick={() => setError('')} /></div>}
      {page === 'profile' && <ProfilePage user={user} onSaved={updated => { setUser(updated); setSession(current => ({ ...current, user: updated })); setToast('Profile photo updated'); }} />}
      {page === 'asset-detail' && selectedAsset && <section className="asset-detail-page">
        <div className="asset-detail-summary"><span className={`asset-icon category-${selectedAsset.category.toLowerCase()}`}><AssetIcon category={selectedAsset.category} size={25} /></span><div><span className="eyebrow">ASSET RECORD</span><h2>{selectedAsset.name}</h2><div className="detail-summary-meta"><span>{selectedAsset.tag}</span><span>{selectedAsset.category}</span>{selectedAsset.vendor && <span>{selectedAsset.vendor}</span>}</div></div><Badge tone={assetStatus(selectedAsset).tone}>{assetStatus(selectedAsset).text}</Badge></div>
        <section className="detail-section"><div className="section-heading"><h2>Asset information</h2></div><dl className="asset-detail-grid">
          <div><dt>Asset name</dt><dd>{selectedAsset.name}</dd></div><div><dt>Asset tag</dt><dd>{selectedAsset.tag}</dd></div>
          <div><dt>Category</dt><dd>{selectedAsset.category}</dd></div><div><dt>Vendor</dt><dd>{selectedAsset.vendor || 'Not specified'}</dd></div>
          <div><dt>Annual running cost</dt><dd>{moneyLabel(selectedAsset.cost || 0)}</dd></div>
          <div><dt>Asset price</dt><dd>{moneyLabel(selectedAsset.asset_price)}</dd></div><div><dt>Renewal price</dt><dd>{moneyLabel(selectedAsset.renewal_price)}</dd></div>
          <div><dt>Status</dt><dd><Badge tone={assetStatus(selectedAsset).tone}>{assetStatus(selectedAsset).text}</Badge></dd></div>
          <div><dt>Registration date</dt><dd>{dateLabel(selectedAsset.registration_date)}</dd></div><div><dt>Expiry date</dt><dd>{dateLabel(selectedAsset.expiry_date)}</dd></div>
          <div><dt>Expected renewal date</dt><dd>{dateLabel(selectedAsset.renewal_date)}</dd></div><div><dt>Days until expiry</dt><dd>{daysLeft(selectedAsset.expiry_date) < 0 ? `Expired ${Math.abs(daysLeft(selectedAsset.expiry_date))} days ago` : `${daysLeft(selectedAsset.expiry_date)} days`}</dd></div>
          <div><dt>Created</dt><dd>{selectedAsset.created_at ? new Date(selectedAsset.created_at).toLocaleString('en-GB') : 'Not available'}</dd></div>
        </dl></section>
        {selectedAsset.category === 'Hardware' && <section className="detail-section"><div className="section-heading"><h2>Hardware depreciation</h2><span className="number-chip">{selectedAsset.depreciation_method ? 'Configured' : 'Not configured'}</span></div>
          {selectedAsset.depreciation_method ? <dl className="asset-detail-grid">
            <div><dt>Acquisition cost</dt><dd>{moneyLabel(selectedAsset.depreciation_acquisition_cost)}</dd></div><div><dt>Salvage value</dt><dd>{moneyLabel(selectedAsset.depreciation_salvage_value)}</dd></div>
            <div><dt>Useful life</dt><dd>{selectedAsset.depreciation_useful_life_months} months</dd></div><div><dt>Method</dt><dd>{selectedAsset.depreciation_method === 'double_declining_balance' ? 'Double-declining balance' : 'Straight-line'}</dd></div>
            <div><dt>Depreciation start date</dt><dd>{dateLabel(selectedAsset.depreciation_start_date)}</dd></div>
          </dl> : <p className="detail-note">Depreciation details have not been entered for this hardware asset.</p>}
        </section>}
        <section className="detail-section"><div className="section-heading"><h2>Assignment & notifications</h2></div><dl className="asset-detail-grid">
          <div><dt>Assigned owner</dt><dd>{selectedAsset.owner_name || 'Unassigned'}</dd></div><div><dt>Owner email</dt><dd>{selectedAsset.owner_email || 'Not available'}</dd></div>
          <div><dt>Additional notification email</dt><dd>{selectedAsset.notification_email || 'Not set'}</dd></div>
        </dl></section>
        <section className="detail-section"><div className="section-heading"><h2>Login credentials</h2><span className="number-chip">{selectedAsset.has_credentials ? 'Saved securely' : 'Not set'}</span></div><p className="detail-note">Passwords are encrypted and are never shown on this detail page.</p>{(can('assets:write') || selectedAsset.owner_id === user.id) && <button className="button secondary" onClick={() => setModal({ type: 'credentials', item: selectedAsset })}><KeyRound size={16} />{selectedAsset.has_credentials ? 'View login credentials' : 'Manage login credentials'}</button>}</section>
        <section className="detail-section"><div className="section-heading"><h2>Notes</h2></div><p className="asset-notes">{selectedAsset.notes || 'No notes added.'}</p></section>
      </section>}
      {page === 'overview' && <>
        <div className="metrics">
          {[{ label: 'Total assets', value: assets.length, icon: Package, tone: 'green', caption: `${activeAssets.length} currently in service`, filter: 'all' },
            { label: 'Expiring soon', value: due.length, icon: Clock3, tone: 'amber', caption: 'Within the next 30 days', filter: 'due' },
            { label: 'Expired assets', value: expired.length, icon: CircleAlert, tone: 'red', caption: 'Past their expiry date', filter: 'expired' },
            { label: 'Healthy lifecycle', value: healthy.length, icon: ShieldCheck, tone: 'blue', caption: 'More than 30 days remaining', filter: 'active' }].map(metric => <button className={`metric metric-${metric.tone}`} key={metric.label} onClick={() => setStatusFilter(metric.filter)}><div className="metric-top"><span>{metric.label}</span><metric.icon size={19} strokeWidth={1.7} /></div><strong>{metric.value.toString().padStart(2, '0')}</strong><div className="metric-caption"><span className="status-dot" />{metric.caption}</div></button>)}
        </div>
        <div className="overview-middle"><section className="renewal-summary"><div className="section-heading"><div className="section-icon"><BellRing size={18} /></div><h2>On the renewal radar</h2><button className="text-button" onClick={() => { navigate('assets'); setStatusFilter('due'); }}>View assets<ArrowRight size={14} /></button></div>
          <div className="renewal-buckets">{[{ days: 30, min: 16, label: '30 days', tone: 'quiet' }, { days: 15, min: 11, label: '15 days', tone: 'quiet' }, { days: 10, min: 6, label: '10 days', tone: 'warning' }, { days: 5, min: 0, label: '5 days', tone: 'danger' }].map(bucket => <div key={bucket.days} className={`renewal-bucket ${bucket.tone}`}><span><span className="status-dot" />{bucket.label}</span><strong>{due.filter(asset => { const remaining = daysLeft(asset.expiry_date); return remaining >= bucket.min && remaining <= bucket.days; }).length}</strong><small>assets to renew</small></div>)}</div>
        </section><section className="portfolio-summary"><div className="section-heading"><h2>Asset mix</h2><span className="subtle-label">{assets.length} total</span></div><div className="mix-bar">{categories.map((item, index) => { const count = assets.filter(asset => asset.category === item).length; return count > 0 ? <span key={item} title={`${item}: ${count}`} className={`mix-${index}`} style={{ flex: count }} /> : null; })}{!assets.length && <span className="mix-empty" />}</div><div className="mix-legend">{categories.filter(item => assets.some(asset => asset.category === item)).map((item, index) => <span key={item}><span className={`legend-dot mix-${categories.indexOf(item)}`} />{item}<strong>{assets.filter(asset => asset.category === item).length}</strong></span>)}{!assets.length && <span className="muted">No assets registered yet</span>}</div></section></div>
        {reminders && <div className={`reminder-banner ${reminders.configured && reminders.enabled ? 'ready' : ''}`}><span className="banner-icon"><Bell size={18} /></span><div><strong>{!reminders.configured ? 'Email delivery is not connected' : reminders.enabled ? 'Your renewal reminders are on' : 'Renewal reminders are paused'}</strong><span>{!reminders.configured ? 'SMTP configuration pending' : '30, 15, 10 & 5 days before expiry'}</span></div><button className="text-button" onClick={() => navigate('reminders')}>Reminder settings<ArrowRight size={15} /></button></div>}
      </>}
      {['overview', 'assets'].includes(page) && <section className="asset-section"><div className="section-heading asset-section-title"><h2>{page === 'overview' ? 'Your asset register' : 'All IT assets'}<span className="number-chip">{assets.length}</span></h2>{page === 'overview' && <button className="text-button" onClick={() => navigate('assets')}>View all<ArrowRight size={14} /></button>}</div>
        <div className="table-toolbar"><div className="filter-tabs">{[['all', 'All assets'], ['due', 'Expiring soon'], ['expired', 'Expired'], ['retired', 'Retired']].map(([value, label]) => <button key={value} className={statusFilter === value ? 'active' : ''} onClick={() => setStatusFilter(value)}>{label}{value === 'due' && due.length > 0 && <span>{due.length}</span>}</button>)}</div><div className="table-tools"><div className="search-field"><Search size={16} /><input aria-label="Search assets" placeholder="Search assets..." value={query} onChange={event => setQuery(event.target.value)} />{query && <IconButton icon={X} label="Clear search" onClick={() => setQuery('')} />}</div><div className="category-filter"><Filter size={15} /><select aria-label="Filter by category" value={category} onChange={event => setCategory(event.target.value)}><option>All categories</option>{categories.map(item => <option key={item}>{item}</option>)}</select></div></div></div>
        {loading ? <div className="table-loading"><LoaderCircle size={23} className="spin" />Loading assets...</div> : <AssetTable assets={visibleAssets} canWrite={can('assets:write')} userId={user.id} onCredentials={asset => setModal({ type: 'credentials', item: asset })} onOpen={openAsset} onEdit={asset => setModal({ type: 'asset', item: asset })} onDelete={asset => setModal({ type: 'delete-asset', item: asset })} onAdd={() => setModal({ type: 'asset' })} />}
        <div className="table-footer"><span>{filtered.length ? `Showing ${(currentPage - 1) * pageSize + 1}-${Math.min(currentPage * pageSize, filtered.length)} of ${filtered.length} assets` : '0 assets'}<span className="footer-dot">·</span>All dates in UTC</span><div className="pagination"><button className="button secondary compact" disabled={currentPage <= 1} onClick={() => setPageNumber(currentPage - 1)}>Previous</button><span>{currentPage} / {maxPage}</span><button className="button secondary compact" disabled={currentPage >= maxPage} onClick={() => setPageNumber(currentPage + 1)}>Next</button></div></div>
      </section>}
      {page === 'users' && <section className="management-section"><div className="management-toolbar"><h2>Members <span className="number-chip">{users.length}</span></h2><div className="search-field"><Search size={16} /><input aria-label="Search users" placeholder="Search users..." value={query} onChange={event => setQuery(event.target.value)} /></div></div><div className="table-scroll"><table className="users-table"><thead><tr><th>Name</th><th>Email address</th><th>Role</th><th>Status</th><th>Actions</th></tr></thead><tbody>{users.filter(member => `${member.name} ${member.email}`.toLowerCase().includes(deferredQuery.toLowerCase())).map(member => <tr key={member.id}><td><div className="owner-cell"><Avatar user={member} /><strong>{member.name}</strong>{member.id === user.id && <span className="you-label">You</span>}</div></td><td>{member.email}</td><td><span className="role-label"><ShieldCheck size={14} />{member.role}</span></td><td><Badge tone={member.active ? 'success' : 'neutral'}>{member.active ? 'Active' : 'Inactive'}</Badge></td><td><IconButton icon={Edit3} label={`Edit ${member.name}`} onClick={() => setModal({ type: 'user', item: member })} /></td></tr>)}</tbody></table></div></section>}
      {page === 'roles' && <section className="roles-section">{roles.map(role => <article className="role-card" key={role.id}><div className="role-card-head"><span className={`role-icon ${role.system ? 'built-in' : ''}`}><ShieldCheck size={22} strokeWidth={1.5} /></span><div><h2>{role.name}</h2><span>{role.system ? 'Built-in role' : 'Custom role'}</span></div>{!role.system && <div className="row-actions"><IconButton icon={Edit3} label={`Edit ${role.name}`} onClick={() => setModal({ type: 'role', item: role })} /><IconButton icon={Trash2} label={`Delete ${role.name}`} onClick={() => setModal({ type: 'delete-role', item: role })} /></div>}</div><div className="role-permissions"><div><Check size={15} />View assets</div>{Object.entries(permissionNames).map(([permission, label]) => <div key={permission} className={role.permissions.includes(permission) ? '' : 'permission-off'}>{role.permissions.includes(permission) ? <Check size={15} /> : <X size={15} />}{label}</div>)}</div><div className="role-card-footer"><Users size={14} />{users.filter(member => member.role_id === role.id).length} assigned users{role.system && <span><KeyRound size={13} />Protected</span>}</div></article>)}</section>}
      {page === 'reminders' && reminders && <>
        <EmailSettings defaultRecipient={user.email} onSaved={() => refresh()} />
        <section className="reminder-settings"><div className="settings-title"><span className="settings-icon"><BellRing size={24} strokeWidth={1.5} /></span><div><h2>Automatic expiry reminders</h2><p>{reminders.schedule}</p></div><label className="toggle"><input type="checkbox" aria-label="Enable automatic reminders" checked={reminders.enabled} onChange={event => save('/reminders', 'PUT', { enabled: event.target.checked }, event.target.checked ? 'Reminders enabled' : 'Reminders paused').catch(failure => setError(failure.message))} /><span /></label></div>
          <div className="schedule-line">{[30, 15, 10, 5].map((days, index) => <div className="schedule-stop" key={days}><span className={index === 3 ? 'urgent' : ''}><Bell size={17} /></span><strong>{days} days</strong><small>before expiry</small></div>)}<div className="schedule-stop"><span className="expiry-stop"><CalendarDays size={17} /></span><strong>Expiry</strong><small>Renewal due</small></div></div>
          <div className="smtp-line"><div><span className={`live-dot ${reminders.configured ? '' : 'pending'}`} /><strong>{reminders.configured ? 'SMTP connected' : 'SMTP not configured'}</strong><span>{reminders.configured ? 'Ready for email delivery' : 'Server email credentials required'}</span></div><button className="button secondary" disabled={!reminders.configured || !reminders.enabled || sending} onClick={async () => { setSending(true); try { const result = await api('/reminders/run', { method: 'POST' }); setToast(result.skipped ? `Reminder check skipped: ${result.skipped}` : `${result.sent} sent, ${result.failed} failed${result.skippedRecipients ? `, ${result.skippedRecipients} assets without recipients` : ''}`); await refresh(); } catch (failure) { setError(failure.message); } finally { setSending(false); } }}>{sending ? <LoaderCircle size={16} className="spin" /> : <RefreshCw size={16} />}Check reminders now</button></div>
        </section><section className="management-section"><div className="management-toolbar"><h2>Delivery history <span className="number-chip">{reminders.deliveries.length}</span></h2><span className="subtle-label">Latest 200 deliveries</span></div>{!reminders.deliveries.length ? <Empty icon={Bell} title="No deliveries yet" description="Reminder deliveries will appear here." /> : <div className="table-scroll"><table className="delivery-table"><thead><tr><th>Asset</th><th>Recipient</th><th>Reminder</th><th>Status</th><th>Last attempt</th></tr></thead><tbody>{reminders.deliveries.map(delivery => <tr key={delivery.id}><td><strong>{delivery.asset_name}</strong><small className="cell-subtitle">{delivery.asset_tag}</small></td><td>{delivery.recipient}</td><td>{delivery.threshold} days before expiry</td><td><Badge tone={delivery.state === 'sent' ? 'success' : 'danger'}>{delivery.state === 'sent' ? 'Sent' : 'Failed'}</Badge>{delivery.error && <small className="cell-subtitle text-danger">{delivery.error}</small>}</td><td>{new Date(delivery.attempted_at).toLocaleString('en-GB', { timeZone: 'UTC' })}</td></tr>)}</tbody></table></div>}</section>
      </>}
      <footer className="main-footer"><span>AssetCairn<span className="footer-dot">/</span>IT asset lifecycle</span><span><ShieldCheck size={13} />{user.role} access</span><span className="copyright">© 2026 Powered by autom8 Inc ®</span></footer>
      </main>
    </div>
    {toast && <div className="toast" role="status"><CheckCircle2 size={19} /><span>{toast}</span><IconButton icon={X} label="Dismiss notification" onClick={() => setToast('')} /></div>}
    {modal?.type === 'asset' && <AssetForm asset={modal.item} directory={directory} onClose={next => setModal(next === 'credentials' && modal.item ? { type: 'credentials', item: modal.item } : null)} onSave={body => save(modal.item ? `/assets/${modal.item.id}` : '/assets', modal.item ? 'PUT' : 'POST', body, modal.item ? 'Asset updated' : 'Asset added')} />}
    {modal?.type === 'credentials' && <AssetCredentials asset={modal.item} canWrite={can('assets:write')} onClose={() => setModal(null)} onSaved={async message => { setModal(null); setToast(message); await refresh(); }} />}
    {modal?.type === 'user' && <UserForm user={modal.item} roles={roleOptions} onClose={() => setModal(null)} onSave={body => save(modal.item ? `/users/${modal.item.id}` : '/users', modal.item ? 'PUT' : 'POST', body, modal.item ? 'User updated' : 'User created')} />}
    {modal?.type === 'role' && <RoleForm role={modal.item} onClose={() => setModal(null)} onSave={body => save(modal.item ? `/roles/${modal.item.id}` : '/roles', modal.item ? 'PUT' : 'POST', body, modal.item ? 'Role updated' : 'Role created')} />}
    {modal?.type === 'password' && <PasswordForm onClose={() => setModal(null)} onSave={() => { setModal(null); setToast('Password updated'); }} />}
    {modal?.type === 'detail' && <Modal title={modal.item.name} subtitle={modal.item.tag} onClose={() => setModal(null)}><dl className="asset-details">{[['Category', modal.item.category], ['Vendor', modal.item.vendor || '-'], ['Owner', modal.item.owner_name || 'Unassigned'], ['Registration', dateLabel(modal.item.registration_date)], ['Expiry', dateLabel(modal.item.expiry_date)], ['Expected renewal', dateLabel(modal.item.renewal_date)], ['Notification email', modal.item.notification_email || '-'], ['Notes', modal.item.notes || '-']].map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl></Modal>}
    {['delete-asset', 'delete-role'].includes(modal?.type) && <ConfirmDelete name={modal.item.name} onClose={() => setModal(null)} onConfirm={() => save(modal.type === 'delete-asset' ? `/assets/${modal.item.id}` : `/roles/${modal.item.id}`, 'DELETE', undefined, modal.type === 'delete-asset' ? 'Asset deleted' : 'Role deleted')} />}
  </div>;
}

function ConfirmDelete({ name, onConfirm, onClose }) {
  const [busy, setBusy] = useState(false); const [error, setError] = useState('');
  return <Modal title="Confirm deletion" onClose={onClose}><div className="modal-body"><p className="delete-message">Delete <strong>{name}</strong>? This action cannot be undone.</p>{error && <div className="form-error" role="alert">{error}</div>}</div><div className="modal-footer"><button className="button secondary" onClick={onClose}>Cancel</button><button className="button destructive" disabled={busy} onClick={async () => { setBusy(true); try { await onConfirm(); } catch (failure) { setError(failure.message); setBusy(false); } }}><Trash2 size={16} />Delete</button></div></Modal>;
}

function ProfilePage({ user, onSaved }) {
  const [avatar, setAvatar] = useState(user.avatar || '');
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const fileInput = useRef();
  function chooseAvatar(event) {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) { setError('Choose a JPEG, PNG, or WebP image.'); return; }
    if (file.size > 5 * 1024 * 1024) { setError('Image must be smaller than 5 MB.'); return; }
    const reader = new FileReader();
    reader.onload = () => { setAvatar(String(reader.result)); setDirty(true); setError(''); };
    reader.onerror = () => setError('Could not read the selected image.');
    reader.readAsDataURL(file);
  }
  async function saveAvatar(event) {
    event.preventDefault(); setBusy(true); setError('');
    try { onSaved(await api('/profile', { method: 'PUT', body: { avatar } })); }
    catch (failure) { setError(failure.message); } finally { setBusy(false); }
  }
  return <section className="profile-page"><div className="profile-card"><form onSubmit={saveAvatar}>
    <div className="profile-avatar-section"><Avatar user={{ ...user, avatar }} className="profile-avatar-large" /><div><h2>Profile photo</h2><p>Choose an image to personalize your account.</p><div className="profile-avatar-actions"><input ref={fileInput} className="sr-only" type="file" accept="image/jpeg,image/png,image/webp" onChange={chooseAvatar} /><button type="button" className="button secondary" onClick={() => fileInput.current?.click()}><Camera size={16} />Choose photo</button>{avatar && <button type="button" className="text-button" onClick={() => { setAvatar(''); setDirty(true); setError(''); }}>Remove photo</button>}</div></div></div>
    <div className="profile-fields"><Field label="Full name"><input readOnly value={user.name} /></Field><Field label="Email address"><input readOnly type="email" value={user.email} /><span className="profile-field-note">Email address cannot be changed here.</span></Field><Field label="Role"><input readOnly value={user.role} /></Field></div>
    {error && <div className="form-error profile-error" role="alert"><CircleAlert size={16} />{error}</div>}
    <div className="profile-actions"><span className="subtle-label">JPEG, PNG, or WebP · Max 5 MB</span><button className="button primary" disabled={!dirty || busy}>{busy ? <LoaderCircle className="spin" size={16} /> : <Check size={16} />}Save profile photo</button></div>
  </form></div></section>;
}