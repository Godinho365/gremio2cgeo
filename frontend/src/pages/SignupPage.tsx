import { IconEye, IconEyeOff } from "@tabler/icons-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { ORG_NAME } from "../branding";
import Brand from "../components/Brand";
import { MILITARY_RANKS, useSignup } from "../features/accounts/api";
import { cpfValid, maskCpf, maskPhone } from "../lib/masks";

export default function SignupPage() {
  const signup = useSignup();
  const { login } = useAuth();
  const navigate = useNavigate();

  const [form, setForm] = useState({
    full_name: "",
    nome_guerra: "",
    posto_graduacao: "",
    cpf: "",
    birth_date: "",
    email: "",
    email_confirm: "",
    phone: "",
    password: "",
    password_confirm: "",
  });
  const [showPwd, setShowPwd] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));

  const cpfTouched = form.cpf.length > 0;
  const cpfBad = cpfTouched && !cpfValid(form.cpf);
  const emailMismatch =
    form.email_confirm.length > 0 &&
    form.email.trim().toLowerCase() !== form.email_confirm.trim().toLowerCase();
  const pwdMismatch = form.password_confirm.length > 0 && form.password !== form.password_confirm;

  const today = new Date().toISOString().slice(0, 10);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!cpfValid(form.cpf)) {
      setError("CPF inválido.");
      return;
    }
    if (emailMismatch) {
      setError("Os e-mails não conferem.");
      return;
    }
    if (form.password !== form.password_confirm) {
      setError("As senhas não conferem.");
      return;
    }
    try {
      await signup.mutateAsync({
        full_name: form.full_name,
        nome_guerra: form.nome_guerra,
        posto_graduacao: form.posto_graduacao,
        cpf: form.cpf,
        birth_date: form.birth_date,
        email: form.email,
        email_confirm: form.email_confirm,
        phone: form.phone || undefined,
        password: form.password,
      });
      await login(form.email, form.password); // login por e-mail
      navigate("/", { replace: true });
    } catch (err) {
      const data = (err as { response?: { data?: { error?: { message?: string } } } }).response
        ?.data?.error;
      setError(data?.message ?? "Não foi possível concluir o cadastro.");
    }
  }

  return (
    <div className="page page-center">
      <div className="container container-tight py-4">
        <div className="text-center mb-4">
          <Brand title={ORG_NAME} size="lg" stacked />
          <div className="text-secondary mt-1">Criar conta</div>
        </div>
        <div className="card card-md">
          <div className="card-body">
            <h2 className="h2 text-center mb-4">Cadastre-se</h2>
            {error && <div className="alert alert-danger">{error}</div>}
            <form onSubmit={onSubmit}>
              <div className="mb-3">
                <label className="form-label required">Nome completo</label>
                <input
                  className="form-control"
                  value={form.full_name}
                  onChange={(e) => set("full_name", e.target.value)}
                  autoFocus
                  required
                />
              </div>
              <div className="row">
                <div className="col-6 mb-3">
                  <label className="form-label required">Posto / Graduação</label>
                  <select
                    className="form-select"
                    value={form.posto_graduacao}
                    onChange={(e) => set("posto_graduacao", e.target.value)}
                    required
                  >
                    <option value="">Selecione…</option>
                    {MILITARY_RANKS.map((g) => (
                      <optgroup key={g.group} label={g.group}>
                        {g.items.map((r) => (
                          <option key={r.value} value={r.value}>
                            {r.label} ({r.value})
                          </option>
                        ))}
                      </optgroup>
                    ))}
                  </select>
                </div>
                <div className="col-6 mb-3">
                  <label className="form-label required">Nome de guerra</label>
                  <input
                    className="form-control"
                    placeholder="Ex.: SILVA"
                    value={form.nome_guerra}
                    onChange={(e) => set("nome_guerra", e.target.value.toUpperCase())}
                    required
                  />
                </div>
              </div>
              <div className="row">
                <div className="col-7 mb-3">
                  <label className="form-label required">CPF</label>
                  <input
                    className={`form-control${cpfBad ? " is-invalid" : ""}`}
                    placeholder="000.000.000-00"
                    inputMode="numeric"
                    value={form.cpf}
                    onChange={(e) => set("cpf", maskCpf(e.target.value))}
                    required
                  />
                  {cpfBad && <div className="invalid-feedback d-block">CPF inválido.</div>}
                </div>
                <div className="col-5 mb-3">
                  <label className="form-label required">Nascimento</label>
                  <input
                    type="date"
                    className="form-control"
                    max={today}
                    value={form.birth_date}
                    onChange={(e) => set("birth_date", e.target.value)}
                    required
                  />
                </div>
              </div>
              <div className="mb-3">
                <label className="form-label required">E-mail</label>
                <input
                  type="email"
                  className="form-control"
                  value={form.email}
                  onChange={(e) => set("email", e.target.value)}
                  required
                />
              </div>
              <div className="mb-3">
                <label className="form-label required">Confirmar e-mail</label>
                <input
                  type="email"
                  className={`form-control${emailMismatch ? " is-invalid" : ""}`}
                  value={form.email_confirm}
                  onChange={(e) => set("email_confirm", e.target.value)}
                  onPaste={(e) => e.preventDefault()}
                  required
                />
                {emailMismatch && (
                  <div className="invalid-feedback d-block">Os e-mails não conferem.</div>
                )}
              </div>
              <div className="mb-3">
                <label className="form-label">Telefone</label>
                <input
                  className="form-control"
                  placeholder="(00) 00000-0000"
                  inputMode="tel"
                  value={form.phone}
                  onChange={(e) => set("phone", maskPhone(e.target.value))}
                />
              </div>
              <div className="row">
                <div className="col-6 mb-3">
                  <label className="form-label required">Senha</label>
                  <div className="input-icon">
                    <input
                      type={showPwd ? "text" : "password"}
                      className="form-control"
                      value={form.password}
                      onChange={(e) => set("password", e.target.value)}
                      minLength={8}
                      required
                    />
                    <button
                      type="button"
                      className="input-icon-addon border-0 bg-transparent p-0"
                      onClick={() => setShowPwd((s) => !s)}
                      style={{ cursor: "pointer", left: "auto", right: 8, pointerEvents: "auto" }}
                      title={showPwd ? "Ocultar" : "Mostrar"}
                      tabIndex={-1}
                    >
                      {showPwd ? <IconEyeOff size={16} /> : <IconEye size={16} />}
                    </button>
                  </div>
                </div>
                <div className="col-6 mb-3">
                  <label className="form-label required">Confirmar senha</label>
                  <input
                    type={showPwd ? "text" : "password"}
                    className={`form-control${pwdMismatch ? " is-invalid" : ""}`}
                    value={form.password_confirm}
                    onChange={(e) => set("password_confirm", e.target.value)}
                    onPaste={(e) => e.preventDefault()}
                    minLength={8}
                    required
                  />
                  {pwdMismatch && (
                    <div className="invalid-feedback d-block">As senhas não conferem.</div>
                  )}
                </div>
              </div>
              <div className="form-footer">
                <button
                  type="submit"
                  className="btn btn-primary w-100"
                  disabled={signup.isPending || cpfBad || emailMismatch || pwdMismatch}
                >
                  {signup.isPending ? "Cadastrando…" : "Criar conta"}
                </button>
              </div>
            </form>
          </div>
        </div>
        <div className="text-center text-secondary mt-3">
          Já tem conta? <Link to="/login">Entrar</Link>
        </div>
      </div>
    </div>
  );
}
