import { useEffect, useState } from "react";

/** Plain $M / count input. Local text state so partial entries like "-" are typable. */
export function numberToText(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "";
  return String(value);
}

export function textToNumber(raw: string): number | null {
  const trimmed = raw.trim();
  if (!trimmed || trimmed === "-" || trimmed === "." || trimmed === "-.") return null;
  const n = Number(trimmed);
  return Number.isNaN(n) ? null : n;
}

interface NumberInputProps {
  value: number | null | undefined;
  onChange: (value: number | null) => void;
  className?: string;
}

export default function NumberInput({ value, onChange, className = "" }: NumberInputProps) {
  const [text, setText] = useState(() => numberToText(value));

  useEffect(() => {
    setText(numberToText(value));
  }, [value]);

  return (
    <input
      type="text"
      inputMode="text"
      value={text}
      onChange={(e) => setText(e.target.value)}
      onBlur={() => {
        const parsed = textToNumber(text);
        onChange(parsed);
        setText(numberToText(parsed));
      }}
      className={className}
    />
  );
}
