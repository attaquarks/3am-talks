import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Sparkles, ChevronRight, SkipForward, Wind } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';

interface Question {
  id: number;
  question: string;
  category: string;
  progress?: string;
}

interface Progress {
  answered: number;
  total: number;
}

export default function Questionnaire() {
  const navigate = useNavigate();
  const { toast } = useToast();

  const [question, setQuestion] = useState<Question | null>(null);
  const [answer, setAnswer] = useState('');
  const [progress, setProgress] = useState<Progress>({ answered: 0, total: 8 });
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // On mount — start the questionnaire
  useEffect(() => {
    const start = async () => {
      try {
        const res = await fetch('/api/questionnaire/start', { method: 'POST' });
        if (!res.ok) throw new Error('Failed to start questionnaire');
        const data = await res.json();

        if (data.completed) {
          // Already completed — go straight to dashboard
          navigate('/dashboard', { replace: true });
          return;
        }

        setQuestion(data.question ?? null);
        if (data.progress) setProgress(data.progress);
      } catch (e) {
        setError('Could not load your questions. Please try again.');
      } finally {
        setIsLoading(false);
      }
    };

    start();
  }, [navigate]);

  const submitAnswer = async () => {
    if (!answer.trim() || !question) return;
    setIsSubmitting(true);
    setError(null);

    try {
      const res = await fetch('/api/questionnaire/answer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question_id: question.id,
          response: answer.trim(),
          conversation_id: conversationId,
        }),
      });

      if (!res.ok) throw new Error('Failed to submit answer');

      const data = await res.json();

      // Track conversation_id for subsequent calls
      if (data.conversation_id && !conversationId) {
        setConversationId(data.conversation_id);
      }

      if (data.questionnaire?.completed) {
        toast({ title: 'All done! ✨', description: 'Ella now has a better understanding of you.' });
        navigate('/dashboard', { replace: true });
      } else if (data.questionnaire?.question) {
        setQuestion(data.questionnaire.question);
        const [ans, tot] = (data.questionnaire.question.progress ?? `${progress.answered + 1}/${progress.total}`).split('/');
        setProgress({ answered: parseInt(ans) - 1, total: parseInt(tot) });
        setAnswer('');
      }
    } catch (e) {
      setError('Could not submit your answer. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSkip = async () => {
    try {
      await fetch('/api/questionnaire/skip', { method: 'POST' });
    } catch (_) {
      // best-effort
    }
    navigate('/dashboard', { replace: true });
  };

  const progressPercent = progress.total > 0 ? (progress.answered / progress.total) * 100 : 0;

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gradient-to-br from-primary/10 via-background to-secondary/10 relative overflow-hidden px-4">

      {/* Background blobs */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <motion.div
          animate={{ scale: [1, 1.2, 1], opacity: [0.15, 0.25, 0.15] }}
          transition={{ duration: 8, repeat: Infinity }}
          className="absolute -top-40 -left-40 w-[600px] h-[600px] bg-primary/20 rounded-full blur-3xl"
        />
        <motion.div
          animate={{ scale: [1, 1.15, 1], opacity: [0.1, 0.2, 0.1] }}
          transition={{ duration: 10, repeat: Infinity, delay: 2 }}
          className="absolute -bottom-40 -right-40 w-[500px] h-[500px] bg-secondary/20 rounded-full blur-3xl"
        />
      </div>

      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="absolute top-0 left-0 right-0 flex items-center justify-between px-8 py-6 z-10"
      >
        <div className="flex items-center gap-3">
          <div className="relative w-9 h-9 flex items-center justify-center">
            <Wind className="absolute text-primary/50" size={28} strokeWidth={1.5} />
            <Sparkles className="absolute text-accent/60 -top-1 -right-1 animate-pulse" size={14} />
          </div>
          <span className="text-lg font-light tracking-[0.2em] uppercase">
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary via-secondary to-accent">Ella AI</span>
          </span>
        </div>

        <button
          onClick={handleSkip}
          className="flex items-center gap-2 text-[10px] font-black uppercase tracking-widest text-foreground/30 hover:text-primary transition-colors"
        >
          <SkipForward size={14} />
          Skip for now
        </button>
      </motion.div>

      {/* Card */}
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15 }}
        className="relative z-10 w-full max-w-2xl"
      >
        {/* Intro label */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.3 }}
          className="flex items-center gap-3 mb-6"
        >
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-card border border-primary/20 text-primary text-[10px] font-black uppercase tracking-widest shadow-lg shadow-primary/10">
            <Sparkles size={12} className="animate-pulse" />
            Personality Assessment
          </div>
        </motion.div>

        {/* Main card */}
        <div className="bg-card/80 backdrop-blur-2xl border border-border rounded-[2.5rem] p-10 md:p-14 shadow-2xl">

          {/* Progress bar */}
          <div className="mb-10">
            <div className="flex justify-between items-center mb-3">
              <span className="text-[10px] font-black uppercase tracking-widest text-foreground/40">
                Question {progress.answered + 1} of {progress.total}
              </span>
              <span className="text-[10px] font-black uppercase tracking-widest text-primary">
                {Math.round(progressPercent)}%
              </span>
            </div>
            <div className="w-full h-1.5 bg-border rounded-full overflow-hidden">
              <motion.div
                className="h-full bg-gradient-to-r from-primary to-secondary rounded-full"
                initial={{ width: 0 }}
                animate={{ width: `${progressPercent}%` }}
                transition={{ duration: 0.5, ease: 'easeOut' }}
              />
            </div>
          </div>

          {/* Content area */}
          {isLoading ? (
            <div className="flex flex-col items-center justify-center py-20 gap-4">
              <div className="w-12 h-12 rounded-full border-2 border-primary/20 border-t-primary animate-spin" />
              <p className="text-[10px] font-black uppercase tracking-widest text-foreground/30">Loading your questions…</p>
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center py-16 gap-4">
              <p className="text-sm text-destructive font-medium">{error}</p>
              <button
                onClick={() => window.location.reload()}
                className="px-6 py-3 rounded-2xl bg-primary text-primary-foreground text-xs font-black uppercase tracking-widest"
              >
                Try Again
              </button>
            </div>
          ) : (
            <AnimatePresence mode="wait">
              {question && (
                <motion.div
                  key={question.id}
                  initial={{ opacity: 0, x: 30 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -30 }}
                  transition={{ duration: 0.3 }}
                  className="space-y-8"
                >
                  {/* Question */}
                  <div>
                    <p className="text-[10px] font-black uppercase tracking-widest text-primary/60 mb-4">
                      {question.category}
                    </p>
                    <h2 className="text-2xl md:text-3xl font-black text-foreground leading-snug tracking-tight">
                      {question.question}
                    </h2>
                  </div>

                  {/* Answer input */}
                  <div className="relative">
                    <textarea
                      value={answer}
                      onChange={(e) => setAnswer(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) submitAnswer();
                      }}
                      placeholder="Take your time, share what feels right…"
                      rows={5}
                      disabled={isSubmitting}
                      className="w-full bg-background border border-border rounded-2xl p-5 text-foreground placeholder:text-foreground/30 focus:outline-none focus:ring-4 focus:ring-primary/20 resize-none transition-all text-base leading-relaxed"
                    />
                    <span className="absolute bottom-4 right-4 text-[9px] font-bold text-foreground/20 uppercase tracking-widest">
                      Ctrl+Enter to submit
                    </span>
                  </div>

                  {error && (
                    <p className="text-sm text-destructive font-medium">{error}</p>
                  )}

                  {/* Submit */}
                  <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={submitAnswer}
                    disabled={!answer.trim() || isSubmitting}
                    className="w-full py-5 rounded-[1.5rem] bg-primary text-primary-foreground font-black uppercase tracking-[0.2em] text-sm shadow-2xl shadow-primary/20 flex items-center justify-center gap-3 disabled:opacity-50 transition-all"
                  >
                    {isSubmitting ? (
                      <div className="w-5 h-5 rounded-full border-2 border-primary-foreground/30 border-t-primary-foreground animate-spin" />
                    ) : (
                      <>
                        <span>{progress.answered + 1 < progress.total ? 'Next Question' : 'Finish'}</span>
                        <ChevronRight size={18} className="group-hover:translate-x-0.5 transition-transform" />
                      </>
                    )}
                  </motion.button>
                </motion.div>
              )}
            </AnimatePresence>
          )}
        </div>

        {/* Footer note */}
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.6 }}
          className="text-center mt-8 text-[10px] font-bold uppercase tracking-[0.2em] text-foreground/20"
        >
          Your answers are private and used only to personalize your experience
        </motion.p>
      </motion.div>
    </div>
  );
}
