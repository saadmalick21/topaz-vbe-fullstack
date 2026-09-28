import React, { useState } from 'react';
import { useDecisions } from '../DecisionContext.jsx';
import ConfirmBox from './ConfirmBox.jsx';

export function ErrorList({ errors }) {
  if (!errors || errors.length === 0) return null;
  return (
    <div className="error-list">
      <b>Please correct the following:</b>
      <ul>
        {errors.map((e, i) => (
          <li key={i}>{e}</li>
        ))}
      </ul>
    </div>
  );
}

export function WarningList({ warnings }) {
  if (!warnings || warnings.length === 0) return null;
  return (
    <div className="warning-list">
      <b>Warnings:</b>
      <ul>
        {warnings.map((w, i) => (
          <li key={i}>{w}</li>
        ))}
      </ul>
    </div>
  );
}

/* Save / Reset / Submit buttons wired to the decision context,
   with validation errors, warnings and the submit confirmation. */
export default function ActionButtons({ showSubmit = true, reviewLink = true }) {
  const {
    save,
    reset,
    submit,
    saving,
    errors,
    warnings,
    confirmation,
    submitted,
    savedAt,
  } = useDecisions();
  const [confirmReset, setConfirmReset] = useState(false);
  const [confirmSubmit, setConfirmSubmit] = useState(false);

  const doSave = async () => {
    await save();
  };

  return (
    <div>
      <ErrorList errors={errors} />
      <WarningList warnings={warnings} />
      {confirmation ? <div className="success-box">{confirmation}</div> : null}
      {savedAt && !confirmation ? (
        <div className="info-box">
          Draft saved at {new Date(savedAt).toLocaleString('en-GB')}. Use Review to check
          the full form, then Submit when the quarter's decisions are final.
        </div>
      ) : null}
      <div className="button-bar">
        <button onClick={doSave} disabled={saving || submitted}>
          {saving ? 'Saving…' : 'Save'}
        </button>{' '}
        <button onClick={() => setConfirmReset(true)} disabled={saving || submitted}>
          Reset to defaults
        </button>{' '}
        {showSubmit && !submitted ? (
          <button onClick={() => setConfirmSubmit(true)} disabled={saving}>
            Submit decisions
          </button>
        ) : null}{' '}
        {reviewLink ? <a href="#/review">Review decisions</a> : null}
      </div>

      <ConfirmBox
        open={confirmReset}
        message="Reset the whole decision form to the default values? Any unsaved changes will be lost."
        confirmLabel="Reset"
        onConfirm={async () => {
          setConfirmReset(false);
          await reset();
        }}
        onCancel={() => setConfirmReset(false)}
      />
      <ConfirmBox
        open={confirmSubmit}
        message="Submit these decisions for the current quarter? Once submitted, the form is LOCKED until the quarter is processed."
        confirmLabel="Submit"
        onConfirm={async () => {
          setConfirmSubmit(false);
          await submit();
        }}
        onCancel={() => setConfirmSubmit(false)}
      />
    </div>
  );
}
