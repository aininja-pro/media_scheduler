import React from 'react';

/**
 * Unmissable success/failure dialog for FMS submissions.
 *
 * The old pattern (a small status banner) let failures go unnoticed — users
 * saw an assignment stay green with no explanation. This modal blocks until
 * dismissed and shows the actual reason from the backend (auth problem,
 * booking conflict, FMS rejection, etc.).
 *
 * result: null | { success: boolean, title: string, message: string }
 */
const FmsResultModal = ({ result, onClose }) => {
  if (!result) return null;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md mx-4 rounded-lg bg-white shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className={`flex items-center gap-3 rounded-t-lg px-5 py-4 ${
          result.success ? 'bg-green-600' : 'bg-red-600'
        }`}>
          <span className="text-2xl text-white">{result.success ? '✓' : '✕'}</span>
          <h3 className="text-lg font-semibold text-white">
            {result.title || (result.success ? 'Sent to FMS' : 'Not sent to FMS')}
          </h3>
        </div>

        <div className="px-5 py-4">
          <p className="whitespace-pre-line text-sm text-gray-800">{result.message}</p>
        </div>

        <div className="flex justify-end border-t border-gray-200 px-5 py-3">
          <button
            onClick={onClose}
            className={`px-5 py-2 font-semibold text-white rounded-md transition-colors ${
              result.success ? 'bg-green-600 hover:bg-green-700' : 'bg-red-600 hover:bg-red-700'
            }`}
          >
            OK
          </button>
        </div>
      </div>
    </div>
  );
};

export default FmsResultModal;
