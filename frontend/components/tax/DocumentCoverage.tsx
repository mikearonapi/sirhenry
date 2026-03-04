"use client";
import { useState, useCallback, useRef } from "react";
import { CheckCircle, Circle, Upload, Loader2, AlertCircle, Check } from "lucide-react";
import { uploadFile } from "@/lib/api";
import type { TaxChecklist, TaxChecklistItem } from "@/types/api";
import { getErrorMessage } from "@/lib/errors";

const TAX_FORM_IDS = new Set([
  "import_w2", "import_1099_nec", "import_1099_div", "import_1099_b", "import_1099_int",
  "import_k1", "import_1099_r", "import_1099_g", "import_1099_k", "import_1098",
]);

interface Props {
  checklist: TaxChecklist;
  year: number;
  onUploadComplete: () => void;
}

type UploadStatus = "idle" | "uploading" | "success" | "error";

export default function DocumentCoverage({ checklist, year, onUploadComplete }: Props) {
  const [status, setStatus] = useState<UploadStatus>("idle");
  const [statusMessage, setStatusMessage] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const docItems = checklist.items.filter((i) => TAX_FORM_IDS.has(i.id));
  const docComplete = docItems.filter((i) => i.status === "complete").length;

  const handleFiles = useCallback(async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setStatus("uploading");
    setStatusMessage(`Uploading ${files.length} file(s)...`);

    let successCount = 0;
    let errorCount = 0;

    for (const file of Array.from(files)) {
      try {
        await uploadFile(file, "tax_document", { taxYear: year });
        successCount++;
      } catch (err: unknown) {
        errorCount++;
        console.error("Upload failed:", getErrorMessage(err));
      }
    }

    if (errorCount === 0) {
      setStatus("success");
      setStatusMessage(`${successCount} file(s) uploaded successfully`);
    } else {
      setStatus("error");
      setStatusMessage(`${successCount} uploaded, ${errorCount} failed`);
    }

    onUploadComplete();
    setTimeout(() => setStatus("idle"), 4000);
  }, [year, onUploadComplete]);

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    handleFiles(e.dataTransfer.files);
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
      {/* Left: Coverage checklist */}
      <div className="lg:col-span-2 bg-white rounded-xl border border-stone-100 shadow-sm p-5 print:shadow-none print:border-stone-200">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-stone-700">Document Coverage</h2>
          <span className="text-xs text-stone-400">{docComplete}/{docItems.length} types received</span>
        </div>
        <div className="space-y-1.5">
          {docItems.map((item) => (
            <CoverageRow key={item.id} item={item} />
          ))}
        </div>
      </div>

      {/* Right: Upload zone */}
      <div className="print:hidden">
        <div
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
          onClick={() => inputRef.current?.click()}
          className={`h-full min-h-[200px] border-2 border-dashed rounded-xl flex flex-col items-center justify-center gap-3 cursor-pointer transition-colors ${
            dragOver ? "border-[#16A34A] bg-green-50/50" : "border-stone-200 hover:border-stone-300 bg-white"
          }`}
        >
          {status === "uploading" ? (
            <>
              <Loader2 size={28} className="animate-spin text-[#16A34A]" />
              <p className="text-sm text-stone-500">{statusMessage}</p>
            </>
          ) : status === "success" ? (
            <>
              <Check size={28} className="text-green-500" />
              <p className="text-sm text-green-600">{statusMessage}</p>
            </>
          ) : status === "error" ? (
            <>
              <AlertCircle size={28} className="text-red-500" />
              <p className="text-sm text-red-600">{statusMessage}</p>
            </>
          ) : (
            <>
              <Upload size={28} className="text-stone-300" />
              <div className="text-center">
                <p className="text-sm font-medium text-stone-600">Drop tax documents here</p>
                <p className="text-xs text-stone-400 mt-1">PDF, JPG, PNG — W-2, 1099, K-1, 1098</p>
              </div>
            </>
          )}
          <input
            ref={inputRef}
            type="file"
            multiple
            accept=".pdf,.jpg,.jpeg,.png"
            className="hidden"
            onChange={(e) => handleFiles(e.target.files)}
          />
        </div>
      </div>
    </div>
  );
}

function CoverageRow({ item }: { item: TaxChecklistItem }) {
  const isComplete = item.status === "complete";
  const formLabel = item.label.replace("Import ", "").replace(" Documents", "");

  return (
    <div className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm ${
      isComplete ? "bg-green-50/50" : "bg-stone-50/30"
    }`}>
      {isComplete ? (
        <CheckCircle size={16} className="text-green-500 flex-shrink-0" />
      ) : (
        <Circle size={16} className="text-stone-300 flex-shrink-0" />
      )}
      <span className={`flex-1 font-medium ${isComplete ? "text-green-800" : "text-stone-600"}`}>
        {formLabel}
      </span>
      <span className="text-xs text-stone-400">{item.detail}</span>
    </div>
  );
}
