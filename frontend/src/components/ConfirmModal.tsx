"use client";

type ConfirmModalProps = {
  open: boolean;
  title?: string;
  description?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  onCancel: () => void;
  onConfirm: () => void;
};

export function ConfirmModal({
  open,
  title = "确认操作",
  description = "此操作无法撤销，确认继续吗？",
  confirmLabel = "确认",
  cancelLabel = "取消",
  onCancel,
  onConfirm,
}: ConfirmModalProps) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* backdrop */}
      <div
        className="absolute inset-0 bg-slate-900/20 backdrop-blur-[2px]"
        onClick={onCancel}
      />
      {/* dialog */}
      <div className="relative w-[min(90vw,22rem)] rounded-[1.5rem] border border-slate-200/80 bg-white/98 px-7 py-6 shadow-[0_32px_80px_rgba(0,0,0,0.12)] backdrop-blur-xl">
        <h2 className="mb-1.5 text-[1.05rem] font-semibold text-slate-800">{title}</h2>
        <p className="text-sm leading-6 text-slate-500">{description}</p>
        <div className="mt-6 flex items-center justify-end gap-2.5">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-full border border-slate-200 bg-white px-5 py-2 text-sm font-medium text-slate-600 transition hover:border-slate-300 hover:text-slate-900"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className="rounded-full bg-red-500 px-5 py-2 text-sm font-medium text-white transition hover:bg-red-600"
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
