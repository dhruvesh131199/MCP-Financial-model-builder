import { useEffect, useState } from "react";

/** User types percentage points (e.g. 10.5 = 10.5%); stored as decimal (0.105). */
export function decimalToPctText(decimal: number | null | undefined): string {
  if (decimal == null || Number.isNaN(decimal)) return "";
  const pct = decimal * 100;
  const rounded = Math.round(pct * 10000) / 10000;
  return String(rounded);
}

export function pctTextToDecimal(raw: string): number | null {
  const trimmed = raw.trim();
  if (!trimmed || trimmed === "-" || trimmed === "." || trimmed === "-.") return null;
  const n = Number(trimmed);
  if (Number.isNaN(n)) return null;
  return n / 100;
}

interface PercentInputProps {
  value: number | null | undefined;
  onChange: (decimal: number | null) => void;
  className?: string;
}

export default function PercentInput({ value, onChange, className = "" }: PercentInputProps) {
  const [text, setText] = useState(() => decimalToPctText(value));

  useEffect(() => {
    setText(decimalToPctText(value));
  }, [value]);

  return (
    <input
      type="text"
      inputMode="decimal"
      value={text}
      onChange={(e) => setText(e.target.value)}
      onBlur={() => {
        const parsed = pctTextToDecimal(text);
        onChange(parsed);
        setText(decimalToPctText(parsed));
      }}
      className={className}
    />
  );
}
