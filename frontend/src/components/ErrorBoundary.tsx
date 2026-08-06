import { IconAlertTriangle } from "@tabler/icons-react";
import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

/** Evita que um erro de render derrube o app inteiro (tela branca). */
export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Ponto de integração para um serviço de observabilidade (Sentry etc.).
    console.error("ErrorBoundary capturou:", error, info.componentStack);
  }

  private reset = () => this.setState({ error: null });

  render() {
    if (this.state.error) {
      return (
        <div className="empty">
          <div className="empty-icon text-danger">
            <IconAlertTriangle size={48} />
          </div>
          <p className="empty-title">Algo deu errado</p>
          <p className="empty-subtitle text-secondary">
            Ocorreu um erro ao exibir esta tela. Tente novamente.
          </p>
          <div className="empty-action d-flex gap-2">
            <button className="btn btn-primary" onClick={this.reset}>
              Tentar novamente
            </button>
            <button className="btn btn-link" onClick={() => window.location.reload()}>
              Recarregar página
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
