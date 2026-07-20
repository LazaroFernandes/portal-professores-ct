export function Loading({ label = "Carregando dados…" }) {
  return <div className="state-card"><span className="spinner" aria-hidden="true" /><p>{label}</p></div>;
}

export function ErrorState({ error, retry }) {
  return <div className="state-card state-error"><strong>Não foi possível carregar</strong><p>{error?.message}</p>{retry && <button onClick={retry}>Tentar novamente</button>}</div>;
}

export function Empty({ title = "Nada por aqui", text = "Não há registros para os filtros selecionados." }) {
  return <div className="state-card"><strong>{title}</strong><p>{text}</p></div>;
}
