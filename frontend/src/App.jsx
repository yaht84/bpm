import React, { useState, useRef, useEffect } from 'react';
import { Upload, Music, Settings, Activity, Play, Download, Loader2 } from 'lucide-react';
import './index.css';

function App() {
  const [file, setFile] = useState(null);
  const [targetBpm, setTargetBpm] = useState(88);
  const [quantize, setQuantize] = useState(true);
  
  const [isProcessing, setIsProcessing] = useState(false);
  const [resultUrl, setResultUrl] = useState(null);
  const [error, setError] = useState(null);
  const [metadata, setMetadata] = useState(null);

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
      setError(null);
      setMetadata(null);
    }
  };

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

    try {
      const response = await fetch('http://localhost:8000/process-audio', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to process audio');
      }

      // Read headers for metadata
      const origTempo = response.headers.get('X-Original-Tempo');
      const stretchFactor = response.headers.get('X-Stretch-Factor');
      
      if (origTempo && stretchFactor) {
        setMetadata({
          originalTempo: origTempo,
          stretchFactor: stretchFactor,
        });
      }

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      setResultUrl(url);
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
        <div className="logo">
          <Activity size={28} className="icon-pulse" />
          <h1>TempoSculpt</h1>
        </div>
        <p className="subtitle">Professional Audio Quantization & Retiming</p>
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
        </div>

        <div className="controls-grid">
          <div className="glass-panel control-card">
            <div className="card-header">
              <Settings size={20} />
              <h3>Target Tempo</h3>
            </div>
            <div className="bpm-display">
              <span className="bpm-value">{targetBpm}</span>
              <span className="bpm-label">BPM</span>
            </div>
            <input 
              type="range" 
              min="40" 
              max="200" 
              value={targetBpm} 
              onChange={(e) => setTargetBpm(e.target.value)}
              className="styled-slider"
            />
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
                  <span className="badge-label">Original</span>
                  <span className="badge-value">{metadata.originalTempo} BPM</span>
                </div>
                <div className="badge">
                  <span className="badge-label">Target</span>
                  <span className="badge-value">{targetBpm} BPM</span>
                </div>
                <div className="badge">
                  <span className="badge-label">Stretch</span>
                  <span className="badge-value">{metadata.stretchFactor}x</span>
                </div>
              </div>
            )}

            <div className="audio-player-wrapper">
              <audio controls src={resultUrl} className="custom-audio-player"></audio>
            </div>
            
            <a href={resultUrl} download={`molded_${targetBpm}bpm.wav`} className="download-button">
              <Download size={18} />
              Download Result
            </a>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
