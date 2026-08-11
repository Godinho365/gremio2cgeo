import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { homePath } from "../auth/roles";
import { ORG_NAME } from "../branding";
import Brand from "../components/Brand";

const SAVED_EMAIL = "login-email";

export default function LoginPage() {
  const { login, user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  // O e-mail fica guardado aqui; a senha fica com o gerenciador do navegador,
  // que a mantém cifrada pelo sistema — não é papel do app armazená-la.
  const saved = localStorage.getItem(SAVED_EMAIL) ?? "";
  const [username, setUsername] = useState(saved);
  const [remember, setRemember] = useState(!!saved);
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Sem destino guardado, cada perfil tem a sua porta de entrada (homePath).
  const from = (location.state as { from?: string })?.from;
  if (user) navigate(from ?? homePath(user), { replace: true });

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const logged = await login(username, password);
      if (remember) localStorage.setItem(SAVED_EMAIL, username.trim());
      else localStorage.removeItem(SAVED_EMAIL);
      navigate(from ?? homePath(logged), { replace: true });
    } catch {
      setError("Usuário ou senha inválidos.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="page page-center">
      <div className="container container-tight py-4">
        <div className="text-center mb-4">
          <Brand title={ORG_NAME} size="lg" stacked />
        </div>
        <div className="card card-md">
          <div className="card-body">
            <h2 className="h2 text-center mb-4">Entrar na sua conta</h2>
            {error && <div className="alert alert-danger">{error}</div>}
            {/* name/autoComplete corretos: é o que faz o navegador oferecer para
                guardar e depois preencher e-mail e senha. */}
            <form onSubmit={onSubmit} method="post" action="#">
              <div className="mb-3">
                <label className="form-label" htmlFor="login-email">
                  E-mail
                </label>
                <input
                  id="login-email"
                  name="username"
                  /* text, não email: contas antigas entram por nome de usuário
                     (demo, sgt_moreira) e type=email as barraria na validação. */
                  type="text"
                  inputMode="email"
                  autoComplete="username"
                  className="form-control"
                  placeholder="seu@email.com"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  autoFocus={!remember}
                />
              </div>
              <div className="mb-3">
                <label className="form-label" htmlFor="login-password">
                  Senha
                </label>
                <input
                  id="login-password"
                  name="password"
                  type="password"
                  autoComplete="current-password"
                  className="form-control"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoFocus={remember}
                />
              </div>
              <label className="form-check mb-3">
                <input
                  type="checkbox"
                  className="form-check-input"
                  checked={remember}
                  onChange={(e) => setRemember(e.target.checked)}
                />
                <span className="form-check-label">Lembrar meu e-mail neste aparelho</span>
              </label>
              <div className="form-footer">
                <button type="submit" className="btn btn-primary w-100" disabled={submitting}>
                  {submitting ? "Entrando…" : "Entrar"}
                </button>
              </div>
            </form>
          </div>
        </div>
        <div className="text-center text-secondary mt-3">
          Não tem conta? <Link to="/signup">Criar conta</Link>
        </div>
        <div className="text-center text-secondary mt-2 small">
          Acesso à agenda e aos serviços do grêmio
        </div>
      </div>
    </div>
  );
}
