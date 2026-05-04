'use client';

import { useCallback, useMemo, useRef, useState, type MouseEvent, type ReactNode } from 'react';
import {
  AlertTriangle,
  BarChart3,
  CheckCircle,
  ChevronDown,
  FileText,
  Files,
  FolderOpen,
  Loader2,
  RotateCcw,
  Upload,
  X,
  XCircle,
} from 'lucide-react';
import { AnimatePresence, motion } from 'framer-motion';
import { TranscriptionDocumentPreview } from '@/components/ui/transcription-document-preview';
import type {
  BatchExamResult,
  BatchSummary,
  BilanGlobal,
  FileProgress,
  GradeResult,
  GradesData,
  ProcessingStepProgress,
  SSEEvent,
  TranscriptionDocument,
} from './types';

type AppPhase = 'upload' | 'loading' | 'results' | 'error';
type ScoreStatus = 'success' | 'partial' | 'failed';
type ProcessingStepStatus = ProcessingStepProgress['status'];
type ExamStepKey = 'transcription' | 'transcription_document' | 'parsing' | 'grading' | 'complete';
type BatchStepKey = 'upload' | 'rubric' | 'copies' | 'complete';

type PreparedExamResult = {
  file: string;
  file_index: number;
  status: 'completed' | 'error';
  gradesData: GradesData;
  bilan: BilanGlobal | null;
  transcriptionDocument: TranscriptionDocument | null;
  error?: string;
};

const batchLoadingSteps: Array<{ key: BatchStepKey; label: string; completeAt: number }> = [
  { key: 'upload', label: 'Envoi des fichiers', completeAt: 5 },
  { key: 'rubric', label: 'Analyse du bareme', completeAt: 15 },
  { key: 'copies', label: 'Traitement des copies', completeAt: 99 },
  { key: 'complete', label: 'Resultats du batch', completeAt: 100 },
];

const examLoadingSteps: Array<{ key: ExamStepKey; label: string; hasDetailProgress?: boolean }> = [
  { key: 'transcription', label: 'Transcription OCR', hasDetailProgress: true },
  { key: 'transcription_document', label: 'Document transcrit' },
  { key: 'parsing', label: 'Extraction des reponses' },
  { key: 'grading', label: "Correction par l'IA", hasDetailProgress: true },
  { key: 'complete', label: 'Correction terminee' },
];

const emptyExamSteps = (): Record<ExamStepKey, ProcessingStepProgress> => ({
  transcription: { status: 'pending', progress: 0 },
  transcription_document: { status: 'pending', progress: 0 },
  parsing: { status: 'pending', progress: 0 },
  grading: { status: 'pending', progress: 0 },
  complete: { status: 'pending', progress: 0 },
});

const clampProgress = (value: number) => Math.max(0, Math.min(100, Math.round(value)));

const createInitialFileProgresses = (files: File[]) => {
  return files.reduce<Record<string, FileProgress>>((acc, file, index) => {
    const key = `${index}-${file.name}`;
    acc[key] = {
      file: file.name,
      file_index: index,
      status: 'queued',
      message: 'En attente de traitement',
      progress: 0,
      steps: emptyExamSteps(),
    };
    return acc;
  }, {});
};

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

function StatusIcon({ status }: { status: ScoreStatus }) {
  if (status === 'success') return <CheckCircle className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />;
  if (status === 'partial') return <AlertTriangle className="w-5 h-5 text-amber-600 dark:text-amber-400" />;
  return <XCircle className="w-5 h-5 text-rose-600 dark:text-rose-400" />;
}

function Toast({ message, onClose }: { message: string; onClose: () => void }) {
  return (
    <motion.div
      initial={{ y: -40, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      exit={{ y: -40, opacity: 0 }}
      className="fixed top-6 right-6 z-50 bg-rose-600 text-white px-5 py-3 rounded-xl shadow-2xl flex items-center gap-3 max-w-md"
    >
      <span className="text-sm">{message}</span>
      <button onClick={onClose} className="hover:bg-white/20 rounded p-1 cursor-pointer" aria-label="Fermer">
        <X className="w-4 h-4" />
      </button>
    </motion.div>
  );
}

function FileDropZone({
  label,
  files,
  onFiles,
  onRemove,
  multiple = false,
  allowDirectory = false,
  icon,
}: {
  label: string;
  files: File[];
  onFiles: (files: File[]) => void;
  onRemove: (index?: number) => void;
  multiple?: boolean;
  allowDirectory?: boolean;
  icon: ReactNode;
}) {
  const [drag, setDrag] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const directoryInputRef = useRef<HTMLInputElement>(null);
  const hasFiles = files.length > 0;

  const acceptFiles = useCallback((fileList: FileList | File[]) => {
    const selected = Array.from(fileList).filter((f) => f.type === 'application/pdf' || f.name.toLowerCase().endsWith('.pdf'));
    if (selected.length > 0) onFiles(multiple ? selected : [selected[0]]);
  }, [multiple, onFiles]);

  const totalMb = files.reduce((sum, file) => sum + file.size, 0) / 1024 / 1024;

  const openFilePicker = (event: MouseEvent<HTMLDivElement>) => {
    const target = event.target as HTMLElement;
    if (target.closest('[data-dropzone-action]')) return;
    if (!hasFiles) inputRef.current?.click();
  };

  return (
    <div className="space-y-3">
      <input
        ref={inputRef}
        type="file"
        accept=".pdf"
        multiple={multiple}
        className="hidden"
        onChange={(e) => { if (e.target.files) acceptFiles(e.target.files); }}
      />
      {allowDirectory && (
        <input
          ref={(node) => {
            directoryInputRef.current = node;
            node?.setAttribute('webkitdirectory', '');
            node?.setAttribute('directory', '');
          }}
          type="file"
          accept=".pdf"
          multiple
          className="hidden"
          onChange={(e) => { if (e.target.files) acceptFiles(e.target.files); }}
        />
      )}

      <div
        onDragEnter={(e) => { e.preventDefault(); setDrag(true); }}
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); acceptFiles(e.dataTransfer.files); }}
        onClick={openFilePicker}
        className={`relative border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-all duration-200 ${
          hasFiles
            ? 'border-emerald-400 bg-emerald-50/70 dark:bg-emerald-950/20'
            : drag
              ? 'scale-[1.02] border-primary bg-primary/25 shadow-xl shadow-primary/15 ring-4 ring-primary/15 dark:bg-primary/25'
              : 'border-border hover:border-primary/50 hover:bg-muted/30'
        }`}
      >
        {hasFiles ? (
          <div className="space-y-4">
            <div className="flex items-center justify-center gap-4">
              <FileText className="w-10 h-10 text-emerald-600 dark:text-emerald-400" />
              <div className="text-left min-w-0">
                <p className="font-bold text-foreground text-sm truncate max-w-[260px]">
                  {multiple ? `${files.length} copie${files.length > 1 ? 's' : ''} en file` : files[0].name}
                </p>
                <p className="text-xs text-muted-foreground">{totalMb.toFixed(2)} MB</p>
              </div>
              <button
                data-dropzone-action
                onClick={(e) => { e.stopPropagation(); onRemove(); }}
                className="ml-2 p-2 rounded-full hover:bg-rose-100 dark:hover:bg-rose-950/40 transition-colors cursor-pointer"
                aria-label="Retirer les fichiers"
              >
                <X className="w-4 h-4 text-rose-500" />
              </button>
            </div>
            {multiple && (
              <div className="max-h-36 overflow-auto rounded-xl border border-border bg-background/70 text-left">
                {files.slice(0, 10).map((file, index) => (
                  <div key={`${file.name}-${index}`} className="flex items-center justify-between gap-3 px-3 py-2 text-sm border-b border-border last:border-b-0">
                    <span className="truncate text-foreground">{file.name}</span>
                    <button
                      data-dropzone-action
                      onClick={(e) => { e.stopPropagation(); onRemove(index); }}
                      className="p-1 rounded-md hover:bg-muted transition-colors cursor-pointer"
                      aria-label={`Retirer ${file.name}`}
                    >
                      <X className="w-3.5 h-3.5 text-muted-foreground" />
                    </button>
                  </div>
                ))}
                {files.length > 10 && <div className="px-3 py-2 text-xs text-muted-foreground">+{files.length - 10} autres fichiers</div>}
              </div>
            )}
          </div>
        ) : (
          <>
            <div className="mb-3 flex justify-center text-primary">{icon}</div>
            <p className="font-bold text-foreground mb-1">{label}</p>
            <p className="text-sm text-muted-foreground">Glissez-deposez ou cliquez pour selectionner</p>
            <p className="text-xs text-muted-foreground mt-2">PDF uniquement</p>
          </>
        )}
      </div>

      {allowDirectory && !hasFiles && (
        <button
          type="button"
          onClick={() => directoryInputRef.current?.click()}
          className="w-full inline-flex items-center justify-center gap-2 rounded-xl border border-border bg-card px-4 py-2.5 text-sm font-medium text-foreground hover:border-primary/50 hover:bg-primary/5 transition-colors cursor-pointer"
        >
          <FolderOpen className="w-4 h-4" />
          Selectionner un dossier
        </button>
      )}
    </div>
  );
}

function LoadingStepRow({
  label,
  status,
  progress,
  completed,
  total,
  message,
}: {
  label: string;
  status: ProcessingStepStatus;
  progress: number;
  completed?: number;
  total?: number;
  message?: string;
}) {
  const isDone = status === 'done';
  const isActive = status === 'active';
  const isError = status === 'error';
  const displayProgress = clampProgress(progress);

  return (
    <div className={`rounded-lg px-3 py-2 transition-colors ${isActive ? 'bg-primary/10' : isError ? 'bg-rose-500/10' : ''}`}>
      <div className="flex items-center gap-3">
        <span className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-xs font-bold ${
          isDone
            ? 'border-emerald-500 bg-emerald-500 text-white'
            : isError
              ? 'border-rose-500 bg-rose-500 text-white'
              : isActive
                ? 'border-primary text-primary'
                : 'border-border text-muted-foreground'
        }`}>
          {isDone ? <CheckCircle className="h-3.5 w-3.5" /> : isError ? <XCircle className="h-3.5 w-3.5" /> : isActive ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : ''}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-3">
            <span className={`text-sm font-medium truncate ${isDone ? 'text-emerald-600 dark:text-emerald-400' : isActive ? 'text-foreground' : isError ? 'text-rose-600 dark:text-rose-400' : 'text-muted-foreground'}`}>
              {label}
            </span>
            <span className={`text-xs font-black ${isActive ? 'text-primary' : isDone ? 'text-emerald-600 dark:text-emerald-400' : 'text-muted-foreground'}`}>
              {displayProgress}%
            </span>
          </div>
          {(isActive || isDone || isError) && (
            <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-muted">
              <motion.div
                className={`h-full rounded-full ${isError ? 'bg-rose-500' : isDone ? 'bg-emerald-500' : 'bg-primary'}`}
                animate={{ width: `${displayProgress}%` }}
                transition={{ duration: 0.35 }}
              />
            </div>
          )}
          {typeof completed === 'number' && typeof total === 'number' && (
            <p className="mt-1 text-xs text-muted-foreground">{completed} / {total}</p>
          )}
          {message && isError && <p className="mt-1 text-xs text-rose-600 dark:text-rose-400">{message}</p>}
        </div>
      </div>
    </div>
  );
}

function getBatchStepStatus(step: BatchStepKey, progress: number): ProcessingStepStatus {
  if (step === 'upload') return progress > 5 ? 'done' : 'active';
  if (step === 'rubric') {
    if (progress >= 15) return 'done';
    return progress >= 10 ? 'active' : 'pending';
  }
  if (step === 'copies') {
    if (progress >= 100) return 'done';
    return progress >= 15 ? 'active' : 'pending';
  }
  if (step === 'complete') return progress >= 100 ? 'done' : 'pending';
  return 'pending';
}

function LoadingView({
  progress,
  message,
  fileProgresses,
  totalFiles,
}: {
  progress: number;
  message: string;
  fileProgresses: FileProgress[];
  totalFiles: number;
}) {
  const completedFiles = fileProgresses.filter((file) => file.status === 'exam_complete').length;

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-background/80 backdrop-blur-md">
      <motion.div
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        className="glass-card p-8 rounded-3xl max-w-5xl w-full mx-4 text-center space-y-7"
      >
        <div>
          <Loader2 className="w-12 h-12 text-primary mx-auto animate-spin" />
          <h2 className="text-2xl font-serif font-bold text-foreground mt-4">Analyse batch en cours...</h2>
          <p className="text-sm text-muted-foreground mt-2">{message}</p>
        </div>

        <div className="w-full bg-muted rounded-full h-3 overflow-hidden">
          <motion.div className="h-full bg-gradient-to-r from-primary to-secondary rounded-full" animate={{ width: `${progress}%` }} transition={{ duration: 0.5 }} />
        </div>

        <div className="grid gap-6 text-left lg:grid-cols-[300px_1fr]">
          <div className="bg-card border border-border rounded-xl p-4 space-y-3">
            <div>
              <p className="text-sm font-bold text-foreground">Progression globale</p>
              <p className="text-xs text-muted-foreground">{completedFiles} / {totalFiles} copie{totalFiles > 1 ? 's' : ''} terminee{totalFiles > 1 ? 's' : ''}</p>
            </div>
            <div className="space-y-2">
              {batchLoadingSteps.map((step) => {
                const status = getBatchStepStatus(step.key, progress);
                const stepProgress = status === 'done' ? 100 : status === 'active' ? clampProgress((progress / step.completeAt) * 100) : 0;
                return (
                  <LoadingStepRow
                    key={step.key}
                    label={step.label}
                    status={status}
                    progress={stepProgress}
                  />
                );
              })}
            </div>
          </div>

          <div className="grid gap-3 max-h-[430px] overflow-auto pr-1">
            {fileProgresses
              .slice()
              .sort((a, b) => a.file_index - b.file_index)
              .map((item) => {
                const steps = item.steps || emptyExamSteps();
                return (
                  <div key={`${item.file_index}-${item.file}`} className="bg-card border border-border rounded-xl p-4 space-y-3">
                    <div className="flex items-center justify-between gap-4">
                      <div className="min-w-0">
                        <p className="text-sm font-bold text-foreground truncate">{item.file}</p>
                        <p className="text-xs text-muted-foreground truncate">{item.message}</p>
                      </div>
                      <span className="text-sm font-black text-primary">{clampProgress(item.progress)}%</span>
                    </div>
                    <div className="space-y-2">
                      {examLoadingSteps.map((step) => {
                        const stepState = steps[step.key] || { status: 'pending', progress: 0 };
                        return (
                          <LoadingStepRow
                            key={step.key}
                            label={step.label}
                            status={stepState.status}
                            progress={stepState.progress}
                            completed={step.hasDetailProgress ? stepState.completed : undefined}
                            total={step.hasDetailProgress ? stepState.total : undefined}
                            message={stepState.message}
                          />
                        );
                      })}
                    </div>
                  </div>
                );
              })}
          </div>
        </div>
      </motion.div>
    </div>
  );
}

function updateFileProgressFromEvent(current: FileProgress | undefined, evt: SSEEvent): FileProgress {
  const steps: Record<string, ProcessingStepProgress> = {
    ...emptyExamSteps(),
    ...(current?.steps || {}),
  };

  const setStep = (key: ExamStepKey, patch: Partial<ProcessingStepProgress>) => {
    steps[key] = {
      ...steps[key],
      ...patch,
      progress: clampProgress(patch.progress ?? steps[key]?.progress ?? 0),
    };
  };

  if (evt.step === 'exam_started') {
    setStep('transcription', { status: 'active', progress: 0 });
  }

  if (evt.step === 'transcription') {
    setStep('transcription', { status: 'active', progress: 0, message: evt.message });
  }

  if (evt.step === 'transcription_progress') {
    setStep('transcription', {
      status: 'active',
      progress: evt.step_progress ?? 0,
      completed: evt.step_completed,
      total: evt.step_total,
      item: evt.item,
      message: evt.message,
    });
  }

  if (evt.step === 'transcription_done') {
    setStep('transcription', { status: 'done', progress: 100, message: evt.message });
  }

  if (evt.step === 'transcription_document') {
    setStep('transcription', { status: 'done', progress: 100 });
    setStep('transcription_document', { status: 'active', progress: 50, message: evt.message });
  }

  if (evt.step === 'parsing') {
    setStep('transcription_document', { status: 'done', progress: 100 });
    setStep('parsing', { status: 'active', progress: 50, message: evt.message });
  }

  if (evt.step === 'parsing_done') {
    setStep('parsing', { status: 'done', progress: 100, message: evt.message });
  }

  if (evt.step === 'grading') {
    setStep('parsing', { status: 'done', progress: 100 });
    setStep('grading', { status: 'active', progress: 0, message: evt.message });
  }

  if (evt.step === 'grading_progress') {
    setStep('grading', {
      status: 'active',
      progress: evt.step_progress ?? 0,
      completed: evt.step_completed,
      total: evt.step_total,
      item: evt.item,
      message: evt.message,
    });
  }

  if (evt.step === 'exam_complete') {
    for (const step of examLoadingSteps) setStep(step.key, { status: 'done', progress: 100 });
  }

  if (evt.step === 'exam_error') {
    const activeStep = examLoadingSteps.find((step) => steps[step.key]?.status === 'active')?.key || 'complete';
    setStep(activeStep, { status: 'error', progress: steps[activeStep]?.progress || 0, message: evt.error || evt.message });
  }

  return {
    file: evt.file || current?.file || '',
    file_index: evt.file_index ?? current?.file_index ?? 0,
    status: evt.step,
    message: evt.message,
    progress: clampProgress(evt.progress),
    stepProgress: evt.step_progress,
    completed: evt.step_completed,
    total: evt.step_total,
    error: typeof evt.error === 'string' ? evt.error : current?.error,
    steps,
  };
}

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
    <motion.div initial={{ y: 20, opacity: 0 }} animate={{ y: 0, opacity: 1 }} className="bg-card border border-border rounded-xl p-6 mb-8 overflow-hidden relative">
      <div className="relative flex flex-col md:flex-row items-center gap-8">
        <div className="relative w-32 h-32 flex-shrink-0">
          <svg viewBox="0 0 120 120" className="w-full h-full -rotate-90">
            <circle cx="60" cy="60" r={radius} fill="none" stroke="currentColor" strokeWidth="8" className="text-muted/30" />
            <motion.circle cx="60" cy="60" r={radius} fill="none" stroke={gaugeColor} strokeWidth="8" strokeLinecap="round" strokeDasharray={circumference} animate={{ strokeDashoffset: offset }} transition={{ duration: 1.2, ease: 'easeOut' }} />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-2xl font-black text-foreground">{Math.round(pct)}%</span>
          </div>
        </div>

        <div className="text-center md:text-left flex-1">
          <p className="text-xs uppercase font-bold text-muted-foreground tracking-widest mb-2">Bilan Global</p>
          <p className="text-5xl font-serif font-black text-foreground">{bilan.note_sur_20}</p>
          <p className="text-sm text-muted-foreground mt-2 max-w-md">{bilan.message}</p>
          <div className={`mt-4 inline-block px-4 py-1.5 rounded-full text-sm font-bold border ${statusColors[status]}`}>
            {status === 'success' && 'Excellent'}
            {status === 'partial' && 'Satisfaisant'}
            {status === 'failed' && 'Insuffisant'}
          </div>
        </div>

        <div className="bg-background border border-border rounded-xl p-5 text-center min-w-[140px]">
          <p className="text-xs uppercase font-bold text-muted-foreground tracking-wider mb-1">Points bruts</p>
          <p className="text-2xl font-bold text-foreground">{score}<span className="text-sm text-muted-foreground font-normal"> / {max}</span></p>
        </div>
      </div>
    </motion.div>
  );
}

function ExamDetail({ exam }: { exam: PreparedExamResult }) {
  const [expanded, setExpanded] = useState<string | null>(null);

  const exercises = useMemo(() => {
    return Object.entries(exam.gradesData).sort(([a], [b]) => compareQuestionIds(a, b)).reduce((acc, [key, value]) => {
      const ex = key.split('_')[0];
      if (!acc[ex]) acc[ex] = [];
      acc[ex].push({ id: key, ...value });
      return acc;
    }, {} as Record<string, Array<{ id: string } & GradeResult>>);
  }, [exam.gradesData]);

  if (exam.status === 'error') {
    return (
      <div className="bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-800 rounded-xl p-8 text-center">
        <XCircle className="w-10 h-10 text-rose-500 mx-auto mb-3" />
        <p className="font-bold text-rose-800 dark:text-rose-300 mb-2">Erreur sur cette copie</p>
        <p className="text-sm text-rose-600 dark:text-rose-400">{exam.error}</p>
      </div>
    );
  }

  if (!exam.bilan) return null;

  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <FileText className="w-5 h-5 text-primary" />
        <div className="min-w-0">
          <h1 className="text-2xl font-serif font-bold text-foreground truncate">{exam.file}</h1>
          <p className="text-sm text-muted-foreground">Detail de correction</p>
        </div>
      </div>

      <BilanCard bilan={exam.bilan} />
      <TranscriptionDocumentPreview document={exam.transcriptionDocument} />

      <div className="space-y-6">
        {Object.entries(exercises).sort(([a], [b]) => compareQuestionIds(a, b)).map(([exKey, questions], exIdx) => (
          <motion.div key={exKey} initial={{ y: 20, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ delay: exIdx * 0.05 }} className="bg-card border border-border rounded-xl overflow-hidden shadow-sm">
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
                    <button onClick={() => setExpanded(isOpen ? null : q.id)} className="w-full px-6 py-4 flex items-center justify-between hover:bg-muted/50 transition-colors text-left cursor-pointer">
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
                        <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.25 }} className="overflow-hidden">
                          <div className="px-6 py-6 bg-background border-t border-border space-y-5">
                            <div>
                              <h5 className="text-xs uppercase font-bold text-muted-foreground mb-2 tracking-wider">Reponse de l&apos;etudiant</h5>
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

function prepareBatchResults(batchResults: BatchExamResult[]): PreparedExamResult[] {
  return batchResults.map((item) => {
    const results = item.results || {};
    const gradesData: GradesData = {};
    for (const [key, value] of Object.entries(results)) {
      if (key !== 'BILAN_GLOBAL' && key !== 'TRANSCRIPTION_DOCUMENT') gradesData[key] = value as GradeResult;
    }
    return {
      file: item.file,
      file_index: item.file_index,
      status: item.status,
      error: item.error,
      gradesData,
      bilan: (results.BILAN_GLOBAL as BilanGlobal | undefined) || null,
      transcriptionDocument: (results.TRANSCRIPTION_DOCUMENT as TranscriptionDocument | undefined) || null,
    };
  });
}

function BatchResultsView({
  exams,
  summary,
  onReset,
}: {
  exams: PreparedExamResult[];
  summary: BatchSummary | null;
  onReset: () => void;
}) {
  const [activeIndex, setActiveIndex] = useState(exams[0]?.file_index ?? 0);
  const activeExam = exams.find((exam) => exam.file_index === activeIndex) || exams[0];

  return (
    <div className="container mx-auto py-10 px-4 max-w-7xl">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 gap-4">
        <div className="flex items-center gap-3">
          <BarChart3 className="w-5 h-5 text-primary" />
          <div>
            <h1 className="text-3xl font-serif font-bold text-foreground">Resultats du batch</h1>
            {summary && (
              <p className="text-sm text-muted-foreground mt-1">
                {summary.completed}/{summary.total_files} copies traitees - moyenne {summary.average_note_sur_20}
              </p>
            )}
          </div>
        </div>
        <button onClick={onReset} className="flex items-center gap-2 px-5 py-2.5 bg-primary text-primary-foreground rounded-xl font-medium hover:opacity-90 transition-opacity cursor-pointer">
          <RotateCcw className="w-4 h-4" /> Nouvelle analyse
        </button>
      </div>

      <div className="grid lg:grid-cols-[320px_1fr] gap-6 items-start">
        <aside className="bg-card border border-border rounded-xl overflow-hidden lg:sticky lg:top-6">
          <div className="px-5 py-4 border-b border-border bg-muted">
            <div className="flex items-center gap-2 font-bold text-foreground">
              <Files className="w-4 h-4 text-primary" />
              Copies
            </div>
          </div>
          <div className="divide-y divide-border max-h-[720px] overflow-auto">
            {exams.map((exam) => {
              const selected = exam.file_index === activeExam.file_index;
              const note = exam.bilan?.note_sur_20 || 'Erreur';
              const status = exam.status === 'completed' && exam.bilan
                ? getScoreStatus(exam.bilan.total_points, exam.bilan.total_max)
                : 'failed';
              return (
                <button
                  key={`${exam.file_index}-${exam.file}`}
                  onClick={() => setActiveIndex(exam.file_index)}
                  className={`w-full p-4 text-left transition-colors cursor-pointer ${selected ? 'bg-primary/10' : 'hover:bg-muted/50'}`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="font-bold text-sm text-foreground truncate">{exam.file}</p>
                      <p className="text-xs text-muted-foreground mt-1">{exam.status === 'completed' ? 'Correction terminee' : exam.error}</p>
                    </div>
                    <span className={`px-2.5 py-1 rounded-lg text-xs font-bold border ${statusColors[status]}`}>{note}</span>
                  </div>
                </button>
              );
            })}
          </div>
        </aside>

        <main className="min-w-0">
          {activeExam && <ExamDetail exam={activeExam} />}
        </main>
      </div>
    </div>
  );
}

export default function GradesPage() {
  const [phase, setPhase] = useState<AppPhase>('upload');
  const [hwFiles, setHwFiles] = useState<File[]>([]);
  const [rubricFile, setRubricFile] = useState<File | null>(null);
  const [progress, setProgress] = useState(0);
  const [statusMsg, setStatusMsg] = useState('');
  const [fileProgresses, setFileProgresses] = useState<Record<string, FileProgress>>({});
  const [batchExams, setBatchExams] = useState<PreparedExamResult[]>([]);
  const [batchSummary, setBatchSummary] = useState<BatchSummary | null>(null);
  const [errorMsg, setErrorMsg] = useState('');
  const [toast, setToast] = useState('');

  const canAnalyze = hwFiles.length > 0 && rubricFile;

  const mergeStudentFiles = useCallback((files: File[]) => {
    setHwFiles((current) => {
      const seen = new Set(current.map((file) => `${file.name}:${file.size}`));
      const next = [...current];
      for (const file of files) {
        const key = `${file.name}:${file.size}`;
        if (!seen.has(key)) {
          seen.add(key);
          next.push(file);
        }
      }
      return next;
    });
  }, []);

  const removeStudentFile = (index?: number) => {
    if (typeof index === 'number') {
      setHwFiles((current) => current.filter((_, i) => i !== index));
    } else {
      setHwFiles([]);
    }
  };

  const handleAnalyze = async () => {
    if (!rubricFile || hwFiles.length === 0) return;

    setPhase('loading');
    setProgress(2);
    setStatusMsg('Envoi des fichiers...');
    setFileProgresses(createInitialFileProgresses(hwFiles));

    const formData = new FormData();
    for (const file of hwFiles) formData.append('handwritten_work', file);
    formData.append('rubric', rubricFile);

    try {
      const res = await fetch('/api/analyze', { method: 'POST', body: formData });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: 'Erreur inconnue' }));
        throw new Error(err.error || `HTTP ${res.status}`);
      }

      if (!res.body) throw new Error('Pas de reponse du serveur');

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
          const evt: SSEEvent = JSON.parse(line.slice(6));
          setProgress(evt.progress);
          setStatusMsg(evt.message);

          if (typeof evt.file_index === 'number' && evt.file) {
            const key = `${evt.file_index}-${evt.file}`;
            setFileProgresses((current) => ({
              ...current,
              [key]: updateFileProgressFromEvent(current[key], evt),
            }));
          }

          if (evt.step === 'error') throw new Error(evt.message);

          if (evt.step === 'complete' && evt.results) {
            const batchResults = (evt.results.BATCH_RESULTS as BatchExamResult[] | undefined) || [];
            const summary = (evt.results.BILAN_BATCH as BatchSummary | undefined) || null;
            setBatchExams(prepareBatchResults(batchResults));
            setBatchSummary(summary);
            setPhase('results');
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
    setHwFiles([]);
    setRubricFile(null);
    setBatchExams([]);
    setBatchSummary(null);
    setProgress(0);
    setStatusMsg('');
    setFileProgresses({});
    setErrorMsg('');
  };

  if (phase === 'results') {
    return <BatchResultsView exams={batchExams} summary={batchSummary} onReset={handleReset} />;
  }

  return (
    <>
      <AnimatePresence>{toast && <Toast message={toast} onClose={() => setToast('')} />}</AnimatePresence>
      {phase === 'loading' && <LoadingView progress={progress} message={statusMsg} fileProgresses={Object.values(fileProgresses)} totalFiles={hwFiles.length} />}

      <div className="min-h-screen flex items-center justify-center py-16 px-4">
        <motion.div initial={{ y: 30, opacity: 0 }} animate={{ y: 0, opacity: 1 }} className="w-full max-w-2xl">
          <div className="text-center mb-10">
            <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-primary/10 text-primary text-sm font-semibold mb-4">
              <Upload className="w-4 h-4" /> Correction IA
            </div>
            <h1 className="text-4xl font-serif font-bold text-foreground">Analyser des examens</h1>
            <p className="text-muted-foreground mt-3 max-w-md mx-auto">
              Deposez plusieurs copies manuscrites et un seul bareme. Sallahli traite le batch en parallele.
            </p>
          </div>

          {phase === 'error' && (
            <motion.div initial={{ scale: 0.95, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} className="mb-8 bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-800 rounded-2xl p-6 text-center">
              <XCircle className="w-10 h-10 text-rose-500 mx-auto mb-3" />
              <p className="font-bold text-rose-800 dark:text-rose-300 mb-2">Erreur lors de l&apos;analyse</p>
              <p className="text-sm text-rose-600 dark:text-rose-400 mb-4">{errorMsg}</p>
              <button onClick={handleReset} className="px-5 py-2 bg-rose-600 text-white rounded-xl font-medium hover:bg-rose-700 transition-colors cursor-pointer">
                <RotateCcw className="w-4 h-4 inline mr-2" />Reessayer
              </button>
            </motion.div>
          )}

          <div className="space-y-5 mb-8">
            <FileDropZone
              label="Copies manuscrites"
              icon={<Files className="w-10 h-10" />}
              files={hwFiles}
              multiple
              allowDirectory
              onFiles={(files) => {
                const pdfs = files.filter((f) => f.type === 'application/pdf' || f.name.toLowerCase().endsWith('.pdf'));
                if (pdfs.length !== files.length) setToast('Seuls les fichiers PDF sont acceptes.');
                mergeStudentFiles(pdfs);
              }}
              onRemove={removeStudentFile}
            />
            <FileDropZone
              label="Bareme / Corrige"
              icon={<FileText className="w-10 h-10" />}
              files={rubricFile ? [rubricFile] : []}
              onFiles={(files) => {
                const file = files[0];
                if (!file || (!file.type.includes('pdf') && !file.name.toLowerCase().endsWith('.pdf'))) {
                  setToast('Seuls les fichiers PDF sont acceptes.');
                  return;
                }
                setRubricFile(file);
              }}
              onRemove={() => setRubricFile(null)}
            />
          </div>

          {hwFiles.length > 0 && (
            <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-border bg-card px-4 py-2 text-sm font-medium text-foreground">
              <Files className="w-4 h-4 text-primary" />
              {hwFiles.length} copie{hwFiles.length > 1 ? 's' : ''} en attente
            </div>
          )}

          <motion.button
            onClick={handleAnalyze}
            disabled={!canAnalyze || phase === 'loading'}
            whileHover={canAnalyze ? { scale: 1.01 } : {}}
            whileTap={canAnalyze ? { scale: 0.99 } : {}}
            className={`w-full py-4 rounded-2xl font-bold text-lg transition-all duration-300 ${
              canAnalyze
                ? 'bg-gradient-to-r from-[hsl(var(--cta))] to-[hsl(var(--secondary))] text-white shadow-lg hover:shadow-xl cursor-pointer'
                : 'bg-muted text-muted-foreground cursor-not-allowed'
            }`}
          >
            {phase === 'loading' ? (
              <span className="flex items-center justify-center gap-2"><Loader2 className="w-5 h-5 animate-spin" />Analyse en cours...</span>
            ) : (
              'Analyser le batch'
            )}
          </motion.button>

          {!canAnalyze && phase === 'upload' && (
            <p className="text-center text-sm text-muted-foreground mt-3">
              Veuillez deposer au moins une copie et un bareme PDF pour commencer.
            </p>
          )}
        </motion.div>
      </div>
    </>
  );
}
