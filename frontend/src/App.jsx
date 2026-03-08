import React, { useState, useRef, useEffect } from 'react';
import { Upload, Music, Settings, Activity, Play, Download, Loader2 } from 'lucide-react';
import './index.css';

function App() {
  const [file, setFile] = useState(null);
  const [targetBpm, setTargetBpm] = useState(88);
  const [quantize, setQuantize] = useState(true);

  const [isProcessing, setIsProcessing] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [resultUrl, setResultUrl] = useState(null);
  const [resultFileName, setResultFileName] = useState("");
  const [error, setError] = useState(null);
  const [metadata, setMetadata] = useState(null);
  const [detectedBpm, setDetectedBpm] = useState(null);
  const [isManualBpm, setIsManualBpm] = useState(false);
  const [customBpm, setCustomBpm] = useState("");

  const fileInputRef = useRef(null);

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile) {
      setFile(selectedFile);
      setResultUrl(null);
      setError(null);
      setMetadata(null);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
  };

  const handleDrop = (e) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      setFile(e.dataTransfer.files[0]);
      setResultUrl(null);
      setResultFileName("");
      setError(null);
      setMetadata(null);
      setDetectedBpm(null);
      setIsManualBpm(false);
      setCustomBpm("");
    }
  };

  useEffect(() => {
    if (file) {
      analyzeFile();
    }
  }, [file]);

  const analyzeFile = async () => {
    setIsAnalyzing(true);
    const formData = new FormData();
    formData.append('file', file);
    try {
      const response = await fetch('/api/analyze', {
        method: 'POST',
        body: formData,
      });
      if (response.ok) {
        const data = await response.json();
        setDetectedBpm(data.bpm);
        setCustomBpm(Math.round(data.bpm));
        setTargetBpm(Math.round(data.bpm));
      }
    } catch (err) {
      console.error("Analysis failed", err);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const activeInputBpm = isManualBpm ? parseFloat(customBpm) : detectedBpm;
  const liveFactor = activeInputBpm ? (targetBpm / activeInputBpm).toFixed(4) : null;

  const processAudio = async () => {
    if (!file) return;

    setIsProcessing(true);
    setError(null);
    setResultUrl(null);
    setMetadata(null);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('targetBpm', targetBpm);
    formData.append('quantize', quantize);
    if (isManualBpm && customBpm) {
      formData.append('inputBpm', customBpm);
    }

    try {
      const response = await fetch('/api/process-audio', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to process audio');
      }

      const data = await response.json();

      setMetadata({
        originalTempo: Math.round(data.original_tempo),
        stretchFactor: data.stretch_factor.toFixed(4),
        originalName: file.name
      });

      // Extremely strict sanitization: Keep only letters, numbers, and underscores
      let safeOriginalName = file.name.split('.').slice(0, -1).join('.');
      safeOriginalName = safeOriginalName.replace(/[^a-zA-Z0-9]/g, '_').substring(0, 40);
      const generatedFileName = `${safeOriginalName}_${targetBpm}bpm.wav`;

      // Target the direct backend path via proxy
      const downloadUrl = `/api/download/${data.job_id}/${encodeURIComponent(generatedFileName)}`;

      setResultUrl(downloadUrl);
      setResultFileName(generatedFileName);

      // Auto-trigger navigation to download the file directly, bypassing Safari's blob constraints completely
      setTimeout(() => {
        window.location.assign(downloadUrl);
      }, 300);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="app-container">
      <div className="background-glow"></div>

      <header className="header">
        <div className="hero">
          <div className="equalizer-container">
            {Array.from({ length: 40 }).map((_, i) => (
              <div key={i} className={`eq-bar bar-${(i % 5) + 1}`} style={{ animationDelay: `${i * 0.1}s` }}></div>
            ))}
          </div>
          <div className="hero-content">
            <h1 className="hero-title">
              <span className="title-bpm">BPM</span>
              <span className="title-shift">SHIFT</span>
            </h1>
            <p className="hero-subtitle">Intelligent Audio Retiming</p>
          </div>
        </div>
        <p className="app-description">
          Upload your audio file, set your desired BPM, and seamlessly quantize or retime your beats while preserving high-quality pristine audio.
        </p>
      </header>

      <main className="main-content">
        <div className="glass-panel uploader" onDragOver={handleDragOver} onDrop={handleDrop}>
          {!file ? (
            <div className="upload-prompt" onClick={() => fileInputRef.current?.click()}>
              <div className="upload-icon-wrapper">
                <Upload size={32} />
              </div>
              <p>Drag & drop your audio file here</p>
              <span className="upload-hint">or click to browse (MP3, WAV, FLAC)</span>
            </div>
          ) : (
            <div className="file-ready">
              <Music size={40} className="file-icon" />
              <div className="file-details">
                <h3>{file.name}</h3>
                <p>{(file.size / (1024 * 1024)).toFixed(2)} MB</p>
              </div>
              <button className="icon-button" onClick={() => setFile(null)} title="Remove file">
                &times;
              </button>
            </div>
          )}
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileChange}
            accept=".mp3,.wav,.flac,.ogg,.m4a"
            style={{ display: 'none' }}
          />
          {/* Show analyzing state right below uploader */}
          {isAnalyzing && (
            <div className="analyzing-state">
              <Loader2 className="spinner" size={24} />
              <p className="analyzing-text">Detecting Input BPM...</p>
            </div>
          )}
        </div>

        {file && !isAnalyzing && detectedBpm && (
          <>
            <div className="controls-grid">
              <div className="glass-panel control-card">
                <div className="card-header">
                  <Settings size={20} />
                  <h3>Target Tempo</h3>
                </div>
                <div className="bpm-display">
                  <span className="bpm-value">{targetBpm}</span>
                  <span className="bpm-label">BPM</span>
                  {liveFactor && (
                    <div className="live-factor">
                      Factor: {liveFactor}x
                    </div>
                  )}
                </div>
                <input
                  type="range"
                  min="40"
                  max="200"
                  value={targetBpm}
                  onChange={(e) => setTargetBpm(parseFloat(e.target.value))}
                  className="styled-slider"
                />
                <div className="detected-bpm-display">
                  Detected Input: {Math.round(detectedBpm)} BPM
                </div>

                <div className="manual-bpm-section">
                  <div className="toggle-container small-toggle">
                    <label className="switch">
                      <input
                        type="checkbox"
                        checked={isManualBpm}
                        onChange={(e) => setIsManualBpm(e.target.checked)}
                      />
                      <span className="slider round"></span>
                    </label>
                    <span className="toggle-title">Manual Input Override</span>
                  </div>

                  {isManualBpm && (
                    <div className="manual-bpm-input">
                      <label>Original BPM:</label>
                      <input
                        type="number"
                        value={customBpm}
                        onChange={(e) => setCustomBpm(e.target.value)}
                        className="bpm-input-field"
                        placeholder="e.g. 120"
                      />
                    </div>
                  )}
                </div>
              </div>

              <div className="glass-panel control-card">
                <div className="card-header">
                  <Activity size={20} />
                  <h3>Processing Mode</h3>
                </div>
                <div className="toggle-container">
                  <label className="switch">
                    <input
                      type="checkbox"
                      checked={quantize}
                      onChange={(e) => setQuantize(e.target.checked)}
                    />
                    <span className="slider round"></span>
                  </label>
                  <div className="toggle-labels">
                    <span className="toggle-title">Smart Quantize</span>
                    <span className="toggle-desc">Detects grid and warps beats accurately</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="action-area">
              <button
                className={`primary-button ${!file || isProcessing ? 'disabled' : ''}`}
                onClick={processAudio}
                disabled={!file || isProcessing}
              >
                {isProcessing ? (
                  <>
                    <Loader2 className="spinner" size={20} />
                    Processing Audio...
                  </>
                ) : (
                  <>
                    <Play size={20} fill="currentColor" />
                    Sculpt Audio
                  </>
                )}
              </button>
            </div>
          </>
        )}

        {error && (
          <div className="error-message">
            <p>{error}</p>
          </div>
        )}

        {resultUrl && (
          <div className="glass-panel result-panel fade-in">
            <h3 className="result-title">Ready to Download</h3>

            {metadata && (
              <div className="metadata-badges">
                <div className="badge">
                  <span className="badge-label">Input BPM</span>
                  <span className="badge-value">{metadata.originalTempo}</span>
                </div>
                <div className="badge">
                  <span className="badge-label">Target BPM</span>
                  <span className="badge-value">{targetBpm}</span>
                </div>
                <div className="badge">
                  <span className="badge-label">Factor</span>
                  <span className="badge-value">{metadata.stretchFactor}x</span>
                </div>
              </div>
            )}

            <button
              onClick={() => window.location.assign(resultUrl)}
              className="download-button"
            >
              <Download size={18} />
              Download Result
            </button>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
