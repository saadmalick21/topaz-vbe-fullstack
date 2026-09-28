import React, { useState, useEffect } from 'react';

/* Labeled form inputs in the old-school style. */

export function NumField({
  label,
  value,
  onChange,
  min,
  max,
  step = 'any',
  width = 90,
  suffix,
  disabled,
  integers,
}) {
  const [text, setText] = useState(value === null || value === undefined ? '' : String(value));

  useEffect(() => {
    setText(value === null || value === undefined ? '' : String(value));
  }, [value]);

  const commit = () => {
    const t = text.trim();
    if (t === '') {
      setText(value === null || value === undefined ? '' : String(value));
      return;
    }
    const n = Number(t);
    if (!isNaN(n)) {
      onChange(integers ? Math.round(n) : n);
    } else {
      setText(value === null || value === undefined ? '' : String(value));
    }
  };

  return (
    <div className="form-row">
      <label className="field-label">
        {label}
        {suffix ? ' (' + suffix + ')' : ''}
      </label>
      <input
        type="number"
        style={{ width }}
        value={text}
        min={min}
        max={max}
        step={integers ? 1 : step}
        disabled={disabled}
        onChange={(e) => setText(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === 'Enter') commit();
        }}
      />
    </div>
  );
}

export function TextField({
  label,
  value,
  onChange,
  width = 200,
  suffix,
  disabled,
  password,
}) {
  const [text, setText] = useState(value === null || value === undefined ? '' : String(value));

  useEffect(() => {
    setText(value === null || value === undefined ? '' : String(value));
  }, [value]);

  return (
    <div className="form-row">
      <label className="field-label">
        {label}
        {suffix ? ' (' + suffix + ')' : ''}
      </label>
      <input
        type={password ? 'password' : 'text'}
        style={{ width }}
        value={text}
        disabled={disabled}
        onChange={(e) => {
          setText(e.target.value);
          onChange(e.target.value);
        }}
      />
    </div>
  );
}

export function CheckField({ label, value, onChange, disabled, note }) {
  return (
    <div className="check-row">
      <label>
        <input
          type="checkbox"
          checked={!!value}
          disabled={disabled}
          onChange={(e) => onChange(e.target.checked)}
        />{' '}
        {label}
      </label>
      {note ? <span className="note"> — {note}</span> : null}
    </div>
  );
}

export function SelectField({ label, value, onChange, options, disabled }) {
  return (
    <div className="form-row">
      <label className="field-label">{label}</label>
      <select
        value={value === null || value === undefined ? '' : value}
        disabled={disabled}
        onChange={(e) => onChange(Number(e.target.value))}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  );
}

/* Compact numeric input for use inside table cells. */
export function CellInput({ value, onChange, width = 64, disabled, integers }) {
  const [text, setText] = useState(value === null || value === undefined ? '' : String(value));

  useEffect(() => {
    setText(value === null || value === undefined ? '' : String(value));
  }, [value]);

  const commit = () => {
    const t = text.trim();
    if (t === '') {
      setText(value === null || value === undefined ? '' : String(value));
      return;
    }
    const n = Number(t);
    if (!isNaN(n)) {
      onChange(integers ? Math.round(n) : n);
    } else {
      setText(value === null || value === undefined ? '' : String(value));
    }
  };

  return (
    <input
      type="number"
      step={integers ? 1 : 'any'}
      style={{ width }}
      value={text}
      disabled={disabled}
      onChange={(e) => setText(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === 'Enter') commit();
      }}
    />
  );
}

/* Compact checkbox for use inside table cells. */
export function CellCheck({ value, onChange, disabled }) {
  return (
    <input
      type="checkbox"
      checked={!!value}
      disabled={disabled}
      onChange={(e) => onChange(e.target.checked)}
    />
  );
}
