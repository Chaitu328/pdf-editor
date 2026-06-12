import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  FileText, Upload, Download, ZoomIn, ZoomOut, ChevronLeft, ChevronRight, RotateCcw, Edit3, Check, X, AlertCircle, Loader2, Eye, Layers
} from "lucide-react";
import * as pdfjsLib from "pdfjs-dist";

pdfjsLib.GlobalWorkerOptions.workerSrc = `https://cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjsLib.version}/pdf.worker.min.mjs`;

const GATEWAY_API =
  window.location.port === "5173" || window.location.hostname === "localhost"
    ? "http://localhost:3000"
    : "";

async function uploadAndAnalyze(selectedFile) {
  const formData = new FormData();
  formData.append("file", selectedFile);
  const res = await fetch(`${GATEWAY_API}/api/pdf/analyze`, {
    method: "POST",
    body: formData,
  });
  const body = await res.json();
  if (!res.ok) {
    throw new Error(body?.error || body?.detail || `Server error ${res.status}`);
  }
  if (body?.success && body?.data) return body.data;
  if (body?.file_path) return body;
  throw new Error(body?.error || "Unexpected response from server");
}

export default function App() {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [loadingMsg, setLoadingMsg] = useState("");
  const [ocrData, setOcrData] = useState(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [zoom, setZoom] = useState(1.2);
  const [edits, setEdits] = useState({});
  const [activeId, setActiveId] = useState(null);
  const [saving, setSaving] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [canvasReady, setCanvasReady] = useState(false);
  const [showAllFields, setShowAllFields] = useState(false);

  const fileInputRef = useRef(null);
  const canvasRef = useRef(null);
  const pdfDocRef = useRef(null);

  const handleReset = () => {
    setFile(null);
    setOcrData(null);
    setEdits({});
    setCurrentPage(1);
    setZoom(1.2);
    setActiveId(null);
    setError(null);
    setCanvasReady(false);
    setShowAllFields(true);
    pdfDocRef.current = null;
  };

  const handleDragOver = (e) => { e.preventDefault(); setDragging(true); };
  const handleDragLeave = () => setDragging(false);
  const handleDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) processFile(f);
  };
  const handleFileChange = (e) => {
    const f = e.target.files[0];
    if (f) processFile(f);
  };

  const processFile = async (selectedFile) => {
    setLoading(true);
    setError(null);
    setFile(selectedFile);
    setOcrData(null);
    setEdits({});
    setCurrentPage(1);
    setCanvasReady(false);

    try {
      setLoadingMsg("Uploading document...");
      const data = await uploadAndAnalyze(selectedFile);
      setLoadingMsg("Processing OCR results...");
      setOcrData(data);
    } catch (err) {
      console.error("[OCR Error]", err);
      setError(err.message);
      setFile(null);
    } finally {
      setLoading(false);
      setLoadingMsg("");
    }
  };

  const pageMetadata = ocrData?.pages?.find((p) => p.page === currentPage);
  const totalPages = ocrData?.total_pages || 1;

  useEffect(() => {
    if (!ocrData || !file) return;
    let cancelled = false;
    setCanvasReady(false);

    const renderPage = async () => {
      try {
        if (!pdfDocRef.current) {
          const fileUrl = `${GATEWAY_API}/api/pdf/download?path=${encodeURIComponent(ocrData.file_path)}`;
          const loadingTask = pdfjsLib.getDocument({ url: fileUrl, withCredentials: false });
          pdfDocRef.current = await loadingTask.promise;
        }
        if (cancelled) return;
        const page = await pdfDocRef.current.getPage(currentPage);
        if (cancelled) return;
        const viewport = page.getViewport({ scale: zoom });
        const canvas = canvasRef.current;
        if (!canvas) return;
        const ctx = canvas.getContext("2d");
        canvas.width = viewport.width;
        canvas.height = viewport.height;
        await page.render({ canvasContext: ctx, viewport }).promise;
        if (!cancelled) setCanvasReady(true);
      } catch (err) {
        if (!cancelled) console.error("[PDF Render Error]", err);
      }
    };
    renderPage();
    return () => { cancelled = true; };
  }, [ocrData, currentPage, zoom, file]);

  useEffect(() => {
    pdfDocRef.current = null;
  }, [zoom]);

  const scaleX = zoom;
  const scaleY = zoom;
  const displayWidth = pageMetadata ? pageMetadata.width * zoom : 0;
  const displayHeight = pageMetadata ? pageMetadata.height * zoom : 0;

  const handleInputChange = useCallback((textId, value) => {
    setEdits((prev) => ({ ...prev, [textId]: value }));
  }, []);

  const handleDownload = async () => {
    if (!ocrData) return;
    setSaving(true);
    try {
      const editList = [];
      ocrData.pages.forEach((p) => {
        p.texts.forEach((t) => {
          const editedVal = edits[t.id];
          if (editedVal !== undefined && editedVal !== t.text) {
            editList.push({
              type: "replace_text",
              page: p.page,
              bbox: t.bbox,
              new_text: editedVal,
              fontsize: 12,
            });
          }
        });
      });

      if (editList.length === 0) {
        alert("No edits were made. Edit some text first and then export.");
        return;
      }

      const applyRes = await fetch(`${GATEWAY_API}/api/pdf/apply-edits`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          file_path: ocrData.file_path,
          edits: editList,
        }),
      });

      const applyBody = await applyRes.json();
      if (!applyRes.ok) {
        throw new Error(applyBody?.error || applyBody?.detail || "Apply edits failed");
      }

      const outputPath = applyBody?.data?.output_path || applyBody?.output_path || applyBody?.data?.data?.output_path;
      if (!outputPath) {
        throw new Error("No output path returned from server.");
      }

      const downloadUrl = `${GATEWAY_API}/api/pdf/download?path=${encodeURIComponent(outputPath)}`;
      const fileRes = await fetch(downloadUrl);
      if (!fileRes.ok) {
        throw new Error(`Download failed: ${fileRes.status}`);
      }

      const blob = await fileRes.blob();
      const link = document.createElement("a");
      link.href = window.URL.createObjectURL(blob);
      link.download = `edited_${file?.name || "document.pdf"}`;
      document.body.appendChild(link);
      link.click();
      window.URL.revokeObjectURL(link.href);
      link.remove();
    } catch (err) {
      alert(`Export failed: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  const editCount = Object.keys(edits).filter((id) => edits[id] !== undefined).length;

  return (
    <div className="app-shell">
      <link
        rel="stylesheet"
        href="https://fonts.googleapis.com/css2?family=Noto+Sans+Telugu:wght@400;600&family=Inter:wght@400;500;600;700&display=swap"
      />
      <header className="app-header">
        <div className="header-brand">
          <div className="brand-icon"><FileText size={22} /></div>
          <div>
            <h1 className="brand-title">PDF OCR Editor</h1>
            <p className="brand-sub">Telugu &amp; English · Direct Vector Replacement</p>
          </div>
        </div>

        {file && ocrData && (
          <div className="header-controls">
            <div className="zoom-control">
              <button className="icon-btn" onClick={() => setZoom((z) => Math.max(0.5, +(z - 0.15).toFixed(2)))}><ZoomOut size={15} /></button>
              <span className="zoom-label">{Math.round(zoom * 100)}%</span>
              <button className="icon-btn" onClick={() => setZoom((z) => Math.min(3.0, +(z + 0.15).toFixed(2)))}><ZoomIn size={15} /></button>
            </div>

            {totalPages > 1 && (
              <div className="page-nav">
                <button className="icon-btn" disabled={currentPage <= 1} onClick={() => setCurrentPage((p) => p - 1)}><ChevronLeft size={15} /></button>
                <span className="page-label">{currentPage} / {totalPages}</span>
                <button className="icon-btn" disabled={currentPage >= totalPages} onClick={() => setCurrentPage((p) => p + 1)}><ChevronRight size={15} /></button>
              </div>
            )}

            <button className="icon-btn sidebar-toggle" onClick={() => setSidebarOpen((s) => !s)}><Layers size={15} /></button>
            <button className={`icon-btn toggle-fields-btn ${showAllFields ? "active-toggle" : ""}`} onClick={() => setShowAllFields((s) => !s)}><Eye size={15} /></button>
            <button className="btn btn-ghost" onClick={handleReset}><RotateCcw size={14} /> Reset</button>
            <button className="btn btn-primary" onClick={handleDownload} disabled={saving}>
              {saving ? <Loader2 size={14} className="spin" /> : <Download size={14} />}
              {saving ? "Exporting…" : `Export PDF${editCount > 0 ? ` (${editCount})` : ""}`}
            </button>
          </div>
        )}
      </header>

      <main className="app-body">
        {!file && !loading && (
          <div className="upload-screen">
            <div className="upload-card" onDragOver={handleDragOver} onDragLeave={handleDragLeave} onDrop={handleDrop}>
              <div className="upload-icon-wrap"><Upload size={40} /></div>
              <h2 className="upload-heading">Upload your document</h2>
              <p className="upload-hint">Drag &amp; drop a PDF/Image here or browse. Supports Telugu + English.</p>

              {error && <div className="error-banner"><AlertCircle size={16} /><span>{error}</span></div>}

              <input
                id="automation-file-input"
                type="file"
                ref={fileInputRef}
                onChange={handleFileChange}
                accept="application/pdf,image/png,image/jpeg,image/jpg"
                style={{ display: "block", margin: "10px auto", opacity: 0.8 }}
              />
              <button className="btn btn-primary btn-large" onClick={() => fileInputRef.current.click()}>Choose Document</button>
            </div>
          </div>
        )}

        {loading && (
          <div className="loading-screen">
            <div className="loader-ring" />
            <h3 className="loading-title">Analyzing Document</h3>
            <p className="loading-sub">{loadingMsg || "Running OCR pipeline…"}</p>
          </div>
        )}

        {file && ocrData && pageMetadata && (
          <div className="editor-layout">
            <div className="canvas-scroll-area">
              <div className="canvas-wrapper" style={{ width: `${displayWidth}px`, height: `${displayHeight}px` }}>
                <canvas ref={canvasRef} className="pdf-canvas" style={{ width: `${displayWidth}px`, height: `${displayHeight}px` }} />
                <div className="overlay-layer">
                  {pageMetadata.texts.map((t) => {
                    const [x1, y1, x2, y2] = t.bbox;
                    const value = edits[t.id] ?? t.text;
                    const isTelugu = /[\u0C00-\u0C7F]/.test(value);
                    const isActive = activeId === t.id;
                    const isEdited = edits[t.id] !== undefined && edits[t.id] !== t.text;
                    const computedFontSize = Math.max(7, (y2 - y1) * scaleY * 0.72);

                    return (
                      <input
                        key={t.id}
                        id={t.id}
                        type="text"
                        value={value}
                        onChange={(e) => handleInputChange(t.id, e.target.value)}
                        onFocus={() => setActiveId(t.id)}
                        onBlur={() => setActiveId(null)}
                        className={`text-overlay ${isActive ? "active" : ""} ${isEdited ? "edited" : ""} ${showAllFields ? "show-all" : ""}`}
                        style={{
                          left: `${x1 * scaleX}px`,
                          top: `${y1 * scaleY}px`,
                          width: `${(x2 - x1) * scaleX}px`,
                          height: `${(y2 - y1) * scaleY}px`,
                          fontSize: `${computedFontSize}px`,
                          fontFamily: isTelugu ? "'Noto Sans Telugu', sans-serif" : "'Inter', sans-serif",
                        }}
                        title={`Original: ${t.text}`}
                      />
                    );
                  })}
                </div>
              </div>
            </div>

            {sidebarOpen && (
              <aside className="sidebar">
                <div className="sidebar-header">
                  <Edit3 size={16} /><span>Text Blocks — Page {currentPage}</span>
                  <span className="sidebar-count">{pageMetadata.texts.length}</span>
                </div>
                <div className="sidebar-list">
                  {pageMetadata.texts.map((t) => {
                    const value = edits[t.id] ?? t.text;
                    const isEdited = edits[t.id] !== undefined && edits[t.id] !== t.text;
                    const isTelugu = /[\u0C00-\u0C7F]/.test(value);

                    return (
                      <div key={t.id} className={`sidebar-item ${activeId === t.id ? "active" : ""} ${isEdited ? "edited" : ""}`} onClick={() => document.getElementById(t.id)?.focus()}>
                        <div className="sidebar-item-meta">
                          <span className="conf-badge">{(t.confidence * 100).toFixed(0)}%</span>
                          {isEdited && <Check size={12} className="edited-check" />}
                        </div>
                        <textarea
                          className="sidebar-textarea"
                          value={value}
                          onChange={(e) => handleInputChange(t.id, e.target.value)}
                          onFocus={() => setActiveId(t.id)}
                          onBlur={() => setActiveId(null)}
                          rows={2}
                          style={{ fontFamily: isTelugu ? "'Noto Sans Telugu', sans-serif" : "'Inter', sans-serif" }}
                        />
                        {isEdited && (
                          <button
                            className="revert-btn"
                            onClick={(e) => {
                              e.stopPropagation();
                              setEdits((prev) => {
                                const next = { ...prev };
                                delete next[t.id];
                                return next;
                              });
                            }}
                          >
                            <X size={11} /> Revert
                          </button>
                        )}
                      </div>
                    );
                  })}
                </div>
              </aside>
            )}
          </div>
        )}
      </main>

      <footer className="app-footer">
        <span>{file ? `📄 ${file.name}` : "Ready — upload a PDF to start"}</span>
        <span className="status-dot-wrap">
          <span className={`status-dot ${ocrData ? "online" : "idle"}`} />
          {ocrData ? `OCR ready · ${ocrData.total_pages} page(s)` : "No document loaded"}
        </span>
      </footer>
    </div>
  );
}
