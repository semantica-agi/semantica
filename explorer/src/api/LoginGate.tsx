/**
 * LDAP 登录页。后端 /api/auth/status 报告 ldap=true 时由 App 渲染，
 * 其余模式（X-API-Key / 匿名）保持原有行为、不经此组件。
 */
import { type FormEvent, useState } from "react";
import { login } from "./auth";
import type { AuthUser } from "./auth";

const fieldLabelStyle = {
  display: 'flex',
  flexDirection: 'column' as const,
  gap: 6,
  fontSize: 13,
  fontWeight: 600,
  color: '#33415c',
};

const fieldInputStyle = {
  padding: '10px 12px',
  borderRadius: 10,
  border: '1px solid rgba(21, 42, 84, 0.18)',
  fontSize: 14,
  color: '#152a54',
  outline: 'none',
  background: '#fbfcff',
};

export function LoginGate({ onAuthenticated }: { onAuthenticated: (user: AuthUser) => void }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const user = await login(username.trim(), password);
      onAuthenticated(user);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : '登录失败，请重试。');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background:
          'radial-gradient(1200px 600px at 50% -10%, rgba(54, 110, 244, 0.12), transparent), #f4f6fb',
        fontFamily: 'inherit',
      }}
    >
      <form
        onSubmit={handleSubmit}
        style={{
          width: 360,
          display: 'flex',
          flexDirection: 'column',
          gap: 14,
          padding: '36px 32px',
          borderRadius: 18,
          background: '#ffffff',
          boxShadow: '0 18px 50px rgba(21, 42, 84, 0.14)',
          border: '1px solid rgba(54, 110, 244, 0.16)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 4 }}>
          <img src="/favicon.png" alt="COWIN" width={40} height={40} style={{ borderRadius: 10 }} />
          <div>
            <div style={{ fontWeight: 700, fontSize: 18, color: '#152a54' }}>COWIN 知识图谱</div>
            <div style={{ fontSize: 12, color: '#64748b' }}>请使用域账号登录</div>
          </div>
        </div>
        <label style={fieldLabelStyle}>
          用户名
          <input
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            autoComplete="username"
            autoFocus
            disabled={busy}
            placeholder="例如 alice（域账号 sAMAccountName）"
            style={fieldInputStyle}
          />
        </label>
        <label style={fieldLabelStyle}>
          密码
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="current-password"
            disabled={busy}
            style={fieldInputStyle}
          />
        </label>
        {error ? (
          <div
            role="alert"
            style={{
              padding: '10px 12px',
              borderRadius: 10,
              background: 'rgba(220, 38, 38, 0.08)',
              border: '1px solid rgba(220, 38, 38, 0.25)',
              color: '#b91c1c',
              fontSize: 13,
            }}
          >
            {error}
          </div>
        ) : null}
        <button
          type="submit"
          disabled={busy || username.length === 0 || password.length === 0}
          style={{
            marginTop: 4,
            padding: '11px 14px',
            borderRadius: 10,
            border: 'none',
            background: busy || username.length === 0 || password.length === 0
              ? 'rgba(54, 110, 244, 0.45)'
              : 'rgb(54, 110, 244)',
            color: '#ffffff',
            fontWeight: 700,
            fontSize: 14,
            cursor: busy ? 'wait' : 'pointer',
          }}
        >
          {busy ? '登录中…' : '登录'}
        </button>
      </form>
    </div>
  );
}