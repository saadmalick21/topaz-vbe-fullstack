import React from 'react';

export default function ConfirmBox({ open, message, confirmLabel, onConfirm, onCancel }) {
  if (!open) return null;
  return (
    <>
      <div className="confirm-overlay" onClick={onCancel} />
      <div className="confirm-box">
        <p>{message}</p>
        <button onClick={onConfirm}>{confirmLabel || 'Confirm'}</button>{' '}
        <button onClick={onCancel}>Cancel</button>
      </div>
    </>
  );
}
