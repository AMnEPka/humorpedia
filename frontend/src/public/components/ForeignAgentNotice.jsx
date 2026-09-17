const DEFAULT_NOTICES = [
  { marker: '*', text: 'признан в РФ иностранным агентом' },
];

export default function ForeignAgentNotice({ visible, notices }) {
  if (!visible) return null;

  const items = notices?.length ? notices : DEFAULT_NOTICES;

  return items.map(({ marker, text }) => (
    <p key={`${marker}-${text}`} className="foreign-agent-notice" role="note">
      <span aria-hidden="true">{marker}</span> — {text}.
    </p>
  ));
}

export function ForeignAgentMarker() {
  return (
    <sup
      className="foreign-agent-marker"
      title="признан в РФ иностранным агентом"
      aria-label="признан в РФ иностранным агентом"
    >
      *
    </sup>
  );
}
