import { useRef, useState, type KeyboardEvent } from "react";

export interface ChipInputProps {
  values: string[];
  onChange: (values: string[]) => void;
  placeholder?: string;
  maxItems?: number;
  disabled?: boolean;
  error?: boolean;
  normalize?: (raw: string) => string | null;
  validate?: (value: string) => string | null;
  inputClassName?: string;
}

import { chipFieldClass } from "../utils/hubFormValidation";

export default function ChipInput({
  values,
  onChange,
  placeholder = "Type ticker and press enter",
  maxItems,
  disabled = false,
  error = false,
  normalize,
  validate,
  inputClassName = "",
}: ChipInputProps) {
  const [draft, setDraft] = useState("");
  const [hint, setHint] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  function commitRaw(raw: string) {
    const trimmed = raw.trim();
    if (!trimmed) return;
    if (maxItems != null && values.length >= maxItems) {
      setHint(`Maximum ${maxItems} items`);
      return;
    }
    const normalized = normalize ? normalize(trimmed) : trimmed;
    if (!normalized) {
      setHint("Invalid value");
      return;
    }
    if (validate) {
      const err = validate(normalized);
      if (err) {
        setHint(err);
        return;
      }
    }
    if (values.includes(normalized)) {
      setHint("Already added");
      setDraft("");
      return;
    }
    onChange([...values, normalized]);
    setDraft("");
    setHint(null);
  }

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      commitRaw(draft);
      return;
    }
    if (e.key === "Backspace" && !draft && values.length > 0) {
      onChange(values.slice(0, -1));
      setHint(null);
    }
  }

  return (
    <div className="space-y-1">
      <div
        className={chipFieldClass(error, disabled)}
        onClick={() => inputRef.current?.focus()}
      >
        {values.map((value) => (
          <span
            key={value}
            className="inline-flex items-center gap-1 rounded-full bg-indigo-100 px-2 py-0.5 text-xs font-medium text-indigo-900"
          >
            {value}
            {!disabled && (
              <button
                type="button"
                aria-label={`Remove ${value}`}
                className="text-indigo-600 hover:text-indigo-900"
                onClick={(e) => {
                  e.stopPropagation();
                  onChange(values.filter((v) => v !== value));
                  setHint(null);
                }}
              >
                ×
              </button>
            )}
          </span>
        ))}
        <input
          ref={inputRef}
          type="text"
          value={draft}
          disabled={disabled}
          onChange={(e) => {
            setDraft(e.target.value);
            setHint(null);
          }}
          onKeyDown={handleKeyDown}
          onBlur={() => {
            if (draft.includes(",")) {
              draft.split(",").forEach((part) => commitRaw(part));
            }
          }}
          placeholder={placeholder}
          className={`min-w-[120px] flex-1 border-0 bg-transparent px-1 py-1 text-sm outline-none ${inputClassName}`}
        />
      </div>
      {hint && <p className="text-xs text-amber-700">{hint}</p>}
    </div>
  );
}
