'use client';

import { useState, useCallback, useRef } from 'react';
import { ChevronDown, CheckCircle, AlertTriangle, XCircle, BarChart3, Upload, FileText, X, Loader2, RotateCcw } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { TranscriptionDocumentPreview } from '@/components/ui/transcription-document-preview';
import type { GradeResult, GradesData, BilanGlobal, SSEEvent, TranscriptionDocument } from './types';

type AppPhase = 'upload' | 'loading' | 'results' | 'error';
type ScoreStatus = 'success' | 'partial' | 'failed';

const questionIdCollator = new Intl.Collator(undefined, {
  numeric: true,
  sensitivity: 'base',
});

const compareQuestionIds = (a: string, b: string) => questionIdCollator.compare(a, b);

const getScoreStatus = (score: number, maxScore = 1): ScoreStatus => {
  const ratio = maxScore > 0 ? score / maxScore : 0;
  if (ratio >= 0.75) return 'success';
  if (ratio >= 0.5) return 'partial';
  return 'failed';
};

const statusColors: Record<ScoreStatus, string> = {
  success: 'bg-emerald-100 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-400 border-emerald-200 dark:border-emerald-800',
  partial: 'bg-amber-100 dark:bg-amber-950/40 text-amber-800 dark:text-amber-400 border-amber-200 dark:border-amber-800',
  failed: 'bg-rose-100 dark:bg-rose-950/40 text-rose-800 dark:text-rose-400 border-rose-200 dark:border-rose-800',
};

const StatusIcon = ({ status }: { status: ScoreStatus }) => {
  if (status === 'success') return <CheckCircle className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />;
  if (status === 'partial') return <AlertTriangle className="w-5 h-5 text-amber-600 dark:text-amber-400" />;
  return <XCircle className="w-5 h-5 text-rose-600 dark:text-rose-400" />;
};

// --- Toast ---
function Toast({ message, onClose }: { message: string; onClose: () => void }) {
  return (
    <motion.div initial={{ y: -40, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: -40, opacity: 0 }}
      className="fixed top-6 right-6 z-50 bg-rose-600 text-white px-5 py-3 rounded-xl shadow-2xl flex items-center gap-3 max-w-md">
      <span className="text-sm">{message}</span>
      <button onClick={onClose} className="hover:bg-white/20 rounded p-1"><X className="w-4 h-4" /></button>
    </motion.div>
  );
}

// --- File Drop Zone ---
function FileDropZone({ label, file, onFile, onRemove, icon }: {
  label: string; file: File | null; onFile: (f: File) => void; onRemove: () => void; icon: string;
}) {
  const [drag, setDrag] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault(); setDrag(false);
    const f = e.dataTransfer.files[0];
    if (f?.type === 'application/pdf') onFile(f);
  }, [onFile]);

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
      onDragLeave={() => setDrag(false)}
      onDrop={handleDrop}
      onClick={() => !file && inputRef.current?.click()}
      className={`relative border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-all duration-300
        ${file ? 'border-emerald-400 bg-emerald-50/50 dark:bg-emerald-950/20' : drag ? 'border-primary bg-primary/5 scale-[1.02]' : 'border-border hover:border-primary/50 hover:bg-muted/30'}`}
    >
      <input ref={inputRef} type="file" accept=".pdf" className="hidden"
        onChange={(e) => { const f = e.target.files?.[0]; if (f) onFile(f); }} />

      {file ? (
        <div className="flex items-center justify-center gap-4">
          <FileText className="w-10 h-10 text-emerald-600 dark:text-emerald-400" />
          <div className="text-left">
            <p className="font-bold text-foreground text-sm truncate max-w-[200px]">{file.name}</p>
            <p className="text-xs text-muted-foreground">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
          </div>
          <button onClick={(e) => { e.stopPropagation(); onRemove(); }}
            className="ml-2 p-2 rounded-full hover:bg-rose-100 dark:hover:bg-rose-950/40 transition">
            <X className="w-4 h-4 text-rose-500" />
          </button>
        </div>
      ) : (
        <>
          <div className="text-4xl mb-3">{icon}</div>
          <p className="font-bold text-foreground mb-1">{label}</p>
          <p className="text-sm text-muted-foreground">Glissez-déposez ou cliquez pour sélectionner</p>
          <p className="text-xs text-muted-foreground mt-2">PDF uniquement</p>
        </>
      )}
    </div>
  );
}

// --- Loading View ---
function LoadingView({ progress, message }: { progress: number; message: string }) {
  const steps = [
    { key: 'upload', label: 'Envoi des fichiers', icon: '📤', threshold: 5 },
    { key: 'transcription', label: 'Transcription OCR', icon: '📝', threshold: 10 },
    { key: 'rubric', label: 'Analyse du barème', icon: '📋', threshold: 40 },
    { key: 'parsing', label: 'Extraction des réponses', icon: '🔍', threshold: 60 },
    { key: 'grading', label: 'Correction par l\'IA', icon: '🎓', threshold: 75 },
  ];

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-background/80 backdrop-blur-md">
      <motion.div initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}
        className="glass-card p-10 rounded-3xl max-w-lg w-full mx-4 text-center space-y-8">
        <div>
          <Loader2 className="w-12 h-12 text-primary mx-auto animate-spin" />
          <h2 className="text-2xl font-serif font-bold text-foreground mt-4">Analyse en cours...</h2>
          <p className="text-sm text-muted-foreground mt-2">{message}</p>
        </div>

        <div className="w-full bg-muted rounded-full h-3 overflow-hidden">
          <motion.div className="h-full bg-gradient-to-r from-primary to-secondary rounded-full"
            initial={{ width: 0 }} animate={{ width: `${progress}%` }} transition={{ duration: 0.5 }} />
        </div>

        <div className="space-y-3 text-left">
          {steps.map((s) => {
            const done = progress > s.threshold + 10;
            const active = progress >= s.threshold && !done;
            return (
              <div key={s.key} className={`flex items-center gap-3 py-2 px-3 rounded-lg transition-all ${active ? 'bg-primary/10' : ''}`}>
                <span className="text-lg">{s.icon}</span>
                <span className={`text-sm font-medium ${done ? 'text-emerald-600 dark:text-emerald-400' : active ? 'text-foreground' : 'text-muted-foreground'}`}>
                  {s.label}
                </span>
                {done && <CheckCircle className="w-4 h-4 text-emerald-500 ml-auto" />}
                {active && <Loader2 className="w-4 h-4 text-primary ml-auto animate-spin" />}
              </div>
            );
          })}
        </div>
      </motion.div>
    </div>
  );
}

// --- Bilan Global Card ---
function BilanCard({ bilan }: { bilan: BilanGlobal }) {
  const score = bilan.total_points;
  const max = bilan.total_max || 20;
  const pct = max > 0 ? (score / max) * 100 : 0;
  const status = getScoreStatus(pct, 100);
  const radius = 54;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (pct / 100) * circumference;
  const gaugeColor = status === 'success' ? '#10b981' : status === 'partial' ? '#f59e0b' : '#f43f5e';

  return (
    <motion.div initial={{ y: 30, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ delay: 0.1 }}
      className="glass-card p-8 rounded-3xl mb-10 overflow-hidden relative">
      <div className="absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-secondary/5 pointer-events-none" />
      <div className="relative flex flex-col md:flex-row items-center gap-8">
        {/* Gauge */}
        <div className="relative w-36 h-36 flex-shrink-0">
          <svg viewBox="0 0 120 120" className="w-full h-full -rotate-90">
            <circle cx="60" cy="60" r={radius} fill="none" stroke="currentColor" strokeWidth="8" className="text-muted/30" />
            <motion.circle cx="60" cy="60" r={radius} fill="none" stroke={gaugeColor} strokeWidth="8"
              strokeLinecap="round" strokeDasharray={circumference}
              initial={{ strokeDashoffset: circumference }} animate={{ strokeDashoffset: offset }}
              transition={{ duration: 1.5, ease: 'easeOut' }} />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-2xl font-black text-foreground">{Math.round(pct)}%</span>
          </div>
        </div>

        {/* Score Info */}
        <div className="text-center md:text-left flex-1">
          <p className="text-xs uppercase font-bold text-muted-foreground tracking-widest mb-2">Bilan Global</p>
          <p className="text-5xl font-serif font-black text-foreground">
            {bilan.note_sur_20}
          </p>
          <p className="text-sm text-muted-foreground mt-2 max-w-md">{bilan.message}</p>
          <div className={`mt-4 inline-block px-4 py-1.5 rounded-full text-sm font-bold border ${statusColors[status]}`}>
            {status === 'success' && '🏆 Excellent'}
            {status === 'partial' && '📊 Satisfaisant'}
            {status === 'failed' && '📉 Insuffisant'}
          </div>
        </div>

        {/* Details */}
        <div className="bg-card border border-border rounded-xl p-5 text-center min-w-[140px]">
          <p className="text-xs uppercase font-bold text-muted-foreground tracking-wider mb-1">Points bruts</p>
          <p className="text-2xl font-bold text-foreground">{score}<span className="text-sm text-muted-foreground font-normal"> / {max}</span></p>
        </div>
      </div>
    </motion.div>
  );
}

// --- Results View (exercises + questions) ---
function ResultsView({
  data,
  bilan,
  transcriptionDocument,
  onReset,
}: {
  data: GradesData;
  bilan: BilanGlobal;
  transcriptionDocument?: TranscriptionDocument | null;
  onReset: () => void;
}) {
  const [expanded, setExpanded] = useState<string | null>(null);

  const exercises = Object.entries(data).sort(([a], [b]) => compareQuestionIds(a, b)).reduce((acc, [key, value]) => {
    const ex = key.split('_')[0];
    if (!acc[ex]) acc[ex] = [];
    acc[ex].push({ id: key, ...value });
    return acc;
  }, {} as Record<string, Array<{ id: string } & GradeResult>>);

  const counts = { success: 0, partial: 0, failed: 0 };
  Object.values(data).forEach((item) => {
    const s = getScoreStatus(item.ai_evaluation?.score_final || 0, item.max_score || 1);
    counts[s]++;
  });

  return (
    <div className="container mx-auto py-12 px-4 max-w-6xl">
      <motion.div initial={{ y: 20, opacity: 0 }} animate={{ y: 0, opacity: 1 }}
        className="flex flex-col md:flex-row justify-between items-start md:items-center mb-8">
        <div className="flex items-center gap-3">
          <BarChart3 className="w-5 h-5 text-primary" />
          <h1 className="text-3xl font-serif font-bold text-foreground">Résultats de l&apos;analyse</h1>
        </div>
        <button onClick={onReset}
          className="mt-4 md:mt-0 flex items-center gap-2 px-5 py-2.5 bg-primary text-primary-foreground rounded-xl font-medium hover:opacity-90 transition">
          <RotateCcw className="w-4 h-4" /> Nouvelle analyse
        </button>
      </motion.div>

      <BilanCard bilan={bilan} />
      <TranscriptionDocumentPreview document={transcriptionDocument} />

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4 mb-10">
        {[
          { label: 'Réussis', count: counts.success, color: 'text-emerald-600 dark:text-emerald-400' },
          { label: 'Partiels', count: counts.partial, color: 'text-amber-600 dark:text-amber-400' },
          { label: 'Échoués', count: counts.failed, color: 'text-rose-600 dark:text-rose-400' },
        ].map((s) => (
          <motion.div key={s.label} initial={{ y: 20, opacity: 0 }} animate={{ y: 0, opacity: 1 }}
            className="bg-card border border-border rounded-xl p-5 text-center">
            <div className={`text-3xl font-bold ${s.color}`}>{s.count}</div>
            <p className="text-sm text-muted-foreground mt-1 uppercase tracking-wider font-medium">{s.label}</p>
          </motion.div>
        ))}
      </div>

      {/* Exercises */}
      <div className="space-y-6">
        {Object.entries(exercises).sort(([a], [b]) => compareQuestionIds(a, b)).map(([exKey, questions], exIdx) => (
          <motion.div key={exKey} initial={{ y: 20, opacity: 0 }} animate={{ y: 0, opacity: 1 }}
            transition={{ delay: exIdx * 0.08 }}
            className="bg-card border border-border rounded-xl overflow-hidden shadow-sm">
            <div className="bg-muted px-6 py-4 border-b border-border flex items-center justify-between">
              <div>
                <h2 className="text-lg font-serif font-bold text-foreground">{exKey}</h2>
                <p className="text-sm text-muted-foreground mt-0.5">{questions.length} question{questions.length !== 1 ? 's' : ''}</p>
              </div>
              {(() => {
                const s = questions.reduce((a, q) => a + (q.ai_evaluation?.score_final || 0), 0);
                const m = questions.reduce((a, q) => a + (q.max_score || 1), 0);
                const st = getScoreStatus(s, m);
                return <span className={`px-4 py-2 rounded-lg text-sm font-bold border ${statusColors[st]}`}>{s.toFixed(2)} / {m} pts</span>;
              })()}
            </div>

            <div className="divide-y divide-border">
              {questions.slice().sort((a, b) => compareQuestionIds(a.id, b.id)).map((q) => {
                const st = getScoreStatus(q.ai_evaluation?.score_final || 0, q.max_score || 1);
                const isOpen = expanded === q.id;
                return (
                  <div key={q.id}>
                    <button onClick={() => setExpanded(isOpen ? null : q.id)}
                      className="w-full px-6 py-4 flex items-center justify-between hover:bg-muted/50 transition-colors text-left">
                      <div className="flex items-center gap-4 flex-1 min-w-0">
                        <StatusIcon status={st} />
                        <div className="min-w-0">
                          <h4 className="font-bold text-foreground uppercase tracking-widest text-sm">{q.id}</h4>
                          <p className="text-sm text-muted-foreground mt-0.5 line-clamp-1">{q.ai_evaluation?.justification}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3 flex-shrink-0 ml-4">
                        <span className={`px-3 py-1 rounded-full text-sm font-bold border ${statusColors[st]}`}>
                          {(q.ai_evaluation?.score_final || 0).toFixed(2)}/{q.max_score || 1}
                        </span>
                        <ChevronDown className={`w-5 h-5 text-muted-foreground transition-transform ${isOpen ? 'rotate-180' : ''}`} />
                      </div>
                    </button>

                    <AnimatePresence>
                      {isOpen && (
                        <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.25 }}
                          className="overflow-hidden">
                          <div className="px-6 py-6 bg-background border-t border-border space-y-5">
                            <div>
                              <h5 className="text-xs uppercase font-bold text-muted-foreground mb-2 tracking-wider">Réponse de l&apos;étudiant</h5>
                              <div className="bg-card border border-border rounded-lg p-4">
                                <p className="text-foreground font-mono text-sm whitespace-pre-wrap">{q.student_answer}</p>
                              </div>
                            </div>
                            <div>
                              <h5 className="text-xs uppercase font-bold text-muted-foreground mb-2 tracking-wider">Raisonnement de l&apos;IA</h5>
                              <div className={`rounded-lg p-4 border ${statusColors[st]}`}>
                                <p className="text-sm whitespace-pre-wrap">{q.ai_evaluation?.raisonnement}</p>
                              </div>
                            </div>
                            <div className="grid md:grid-cols-2 gap-4">
                              <div className="bg-card border border-border rounded-lg p-4">
                                <div className="text-xs uppercase font-bold text-muted-foreground mb-1 tracking-wider">Score</div>
                                <div className="text-2xl font-bold text-foreground">
                                  {(q.ai_evaluation?.score_final || 0).toFixed(2)} <span className="text-sm text-muted-foreground font-normal">/ {q.max_score || 1}</span>
                                </div>
                              </div>
                              <div className={`rounded-lg p-4 border ${statusColors[st]}`}>
                                <div className="text-xs uppercase font-bold opacity-80 mb-1 tracking-wider">Statut</div>
                                <div className="text-lg font-bold">
                                  {st === 'success' && '✓ Réussi'}{st === 'partial' && '⚠ Partiel'}{st === 'failed' && '✗ Échoué'}
                                </div>
                              </div>
                            </div>
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                );
              })}
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  );
}

// ============ MAIN PAGE ============
export default function GradesPage() {
  const [phase, setPhase] = useState<AppPhase>('upload');
  const [hwFile, setHwFile] = useState<File | null>(null);
  const [rubricFile, setRubricFile] = useState<File | null>(null);
  const [progress, setProgress] = useState(0);
  const [statusMsg, setStatusMsg] = useState('');
  const [gradesData, setGradesData] = useState<GradesData | null>(null);
  const [bilan, setBilan] = useState<BilanGlobal | null>(null);
  const [transcriptionDocument, setTranscriptionDocument] = useState<TranscriptionDocument | null>(null);
  const [errorMsg, setErrorMsg] = useState('');
  const [toast, setToast] = useState('');

  const canAnalyze = hwFile && rubricFile;

  const handleAnalyze = async () => {
    if (!hwFile || !rubricFile) return;

    setPhase('loading');
    setProgress(2);
    setStatusMsg('Envoi des fichiers...');

    const formData = new FormData();
    formData.append('handwritten_work', hwFile);
    formData.append('rubric', rubricFile);

    try {
      const res = await fetch('/api/analyze', { method: 'POST', body: formData });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: 'Erreur inconnue' }));
        throw new Error(err.error || `HTTP ${res.status}`);
      }

      if (!res.body) throw new Error('Pas de réponse du serveur');

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const evt: SSEEvent = JSON.parse(line.slice(6));
            setProgress(evt.progress);
            setStatusMsg(evt.message);

            if (evt.step === 'error') {
              throw new Error(evt.message);
            }

            if (evt.step === 'complete' && evt.results) {
              const results = evt.results as Record<string, unknown>;
              const bilanData = results['BILAN_GLOBAL'] as BilanGlobal;
              const transcriptionDocumentData = results['TRANSCRIPTION_DOCUMENT'] as TranscriptionDocument | undefined;
              const questionsData: GradesData = {};

              for (const [k, v] of Object.entries(results)) {
                if (k !== 'BILAN_GLOBAL' && k !== 'TRANSCRIPTION_DOCUMENT') questionsData[k] = v as GradeResult;
              }

              setBilan(bilanData);
              setTranscriptionDocument(transcriptionDocumentData || null);
              setGradesData(questionsData);
              setPhase('results');
            }
          } catch (parseErr) {
            if (parseErr instanceof Error && parseErr.message !== line) {
              throw parseErr;
            }
          }
        }
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Erreur inconnue';
      setErrorMsg(msg);
      setPhase('error');
    }
  };

  const handleReset = () => {
    setPhase('upload');
    setHwFile(null);
    setRubricFile(null);
    setGradesData(null);
    setBilan(null);
    setTranscriptionDocument(null);
    setProgress(0);
    setStatusMsg('');
    setErrorMsg('');
  };

  // --- Results Phase ---
  if (phase === 'results' && gradesData && bilan) {
    return <ResultsView data={gradesData} bilan={bilan} transcriptionDocument={transcriptionDocument} onReset={handleReset} />;
  }

  return (
    <>
      <AnimatePresence>{toast && <Toast message={toast} onClose={() => setToast('')} />}</AnimatePresence>
      {phase === 'loading' && <LoadingView progress={progress} message={statusMsg} />}

      <div className="min-h-screen flex items-center justify-center py-16 px-4">
        <motion.div initial={{ y: 30, opacity: 0 }} animate={{ y: 0, opacity: 1 }}
          className="w-full max-w-2xl">

          {/* Header */}
          <div className="text-center mb-10">
            <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-primary/10 text-primary text-sm font-semibold mb-4">
              <Upload className="w-4 h-4" /> Correction IA
            </div>
            <h1 className="text-4xl font-serif font-bold text-foreground">Analyser un examen</h1>
            <p className="text-muted-foreground mt-3 max-w-md mx-auto">
              Déposez la copie manuscrite et le barème. Notre IA se charge du reste.
            </p>
          </div>

          {/* Error state */}
          {phase === 'error' && (
            <motion.div initial={{ scale: 0.95, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}
              className="mb-8 bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-800 rounded-2xl p-6 text-center">
              <XCircle className="w-10 h-10 text-rose-500 mx-auto mb-3" />
              <p className="font-bold text-rose-800 dark:text-rose-300 mb-2">Erreur lors de l&apos;analyse</p>
              <p className="text-sm text-rose-600 dark:text-rose-400 mb-4">{errorMsg}</p>
              <button onClick={handleReset}
                className="px-5 py-2 bg-rose-600 text-white rounded-xl font-medium hover:bg-rose-700 transition">
                <RotateCcw className="w-4 h-4 inline mr-2" />Réessayer
              </button>
            </motion.div>
          )}

          {/* Upload Zones */}
          <div className="space-y-5 mb-8">
            <FileDropZone label="Copie manuscrite" icon="✍️" file={hwFile}
              onFile={(f) => { if (f.type !== 'application/pdf') { setToast('Seuls les fichiers PDF sont acceptés.'); return; } setHwFile(f); }}
              onRemove={() => setHwFile(null)} />
            <FileDropZone label="Barème / Corrigé" icon="📋" file={rubricFile}
              onFile={(f) => { if (f.type !== 'application/pdf') { setToast('Seuls les fichiers PDF sont acceptés.'); return; } setRubricFile(f); }}
              onRemove={() => setRubricFile(null)} />
          </div>

          {/* Analyze Button */}
          <motion.button
            onClick={handleAnalyze}
            disabled={!canAnalyze || phase === 'loading'}
            whileHover={canAnalyze ? { scale: 1.02 } : {}}
            whileTap={canAnalyze ? { scale: 0.98 } : {}}
            className={`w-full py-4 rounded-2xl font-bold text-lg transition-all duration-300 ${
              canAnalyze
                ? 'bg-gradient-to-r from-[hsl(var(--cta))] to-[hsl(var(--secondary))] text-white shadow-lg hover:shadow-xl cursor-pointer'
                : 'bg-muted text-muted-foreground cursor-not-allowed'
            }`}
          >
            {phase === 'loading' ? (
              <span className="flex items-center justify-center gap-2"><Loader2 className="w-5 h-5 animate-spin" />Analyse en cours...</span>
            ) : (
              'Analyser'
            )}
          </motion.button>

          {!canAnalyze && phase === 'upload' && (
            <p className="text-center text-sm text-muted-foreground mt-3">
              Veuillez déposer les deux fichiers PDF pour commencer.
            </p>
          )}
        </motion.div>
      </div>
    </>
  );
}
