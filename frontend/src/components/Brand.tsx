import logo from "../logo_gremio.png";

type Size = "sm" | "md" | "lg";

const LOGO_PX: Record<Size, number> = { sm: 30, md: 40, lg: 72 };

interface Props {
  title?: string;
  subtitle?: string;
  size?: Size;
  /** Empilha logo e texto (telas de login/cadastro). */
  stacked?: boolean;
  /** Só o emblema, sem texto (rail recolhido). */
  iconOnly?: boolean;
  /** Chapa branca atrás do emblema — ajuda a leitura sobre fundo colorido. */
  plate?: boolean;
  className?: string;
}

/** Emblema do grêmio + nome. O texto varia por perfil — ver `brandFor`. */
export default function Brand({
  title,
  subtitle,
  size = "md",
  stacked = false,
  iconOnly = false,
  plate = false,
  className = "",
}: Props) {
  const px = LOGO_PX[size];
  const img = (
    <img
      src={logo}
      alt={title ?? "Grêmio do 2º CGEO"}
      width={px}
      height={px}
      className="flex-shrink-0"
      style={{
        objectFit: "contain",
        ...(plate
          ? {
              background: "var(--sheet)",
              borderRadius: "50%",
              padding: 2,
              boxShadow: "0 0 0 1px var(--graticule)",
            }
          : {}),
      }}
    />
  );

  if (iconOnly) return <span className={`d-inline-flex ${className}`}>{img}</span>;

  const text = (
    <span className="lh-sm" style={{ minWidth: 0 }}>
      <span
        className="d-block fw-semibold"
        style={{
          fontFamily: "var(--font-display)",
          fontSize: size === "lg" ? "var(--text-2xl)" : "var(--text-lg)",
          letterSpacing: "var(--track-display)",
          color: "var(--ink)",
        }}
      >
        {title}
      </span>
      {subtitle && (
        <span className="d-block" style={{ fontSize: "var(--text-xs)", color: "var(--ink-muted)" }}>
          {subtitle}
        </span>
      )}
    </span>
  );

  if (stacked) {
    return (
      <span className={`d-inline-flex flex-column align-items-center gap-2 ${className}`}>
        {img}
        <span className="text-center">{text}</span>
      </span>
    );
  }

  return (
    <span className={`d-inline-flex align-items-center gap-2 ${className}`}>
      {img}
      {text}
    </span>
  );
}
