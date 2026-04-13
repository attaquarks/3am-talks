import React, { useState } from 'react';
import { MessageCircle, X, Sparkles, Send, Loader2 } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const QuickSupport: React.FC = () => {
    const [isOpen, setIsOpen] = useState(false);
    const [input, setInput] = useState('');
    const [message, setMessage] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(false);

    const handleSeekSupport = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!input.trim() || isLoading) return;

        setIsLoading(true);
        const userMessage = input;
        setInput('');

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: userMessage,
                    conversation_id: null,
                    conversation_history: []
                }),
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData?.message || 'Quick support request failed');
            }
            const data = await response.json();

            const aiResponse = data?.response || data?.content || "I'm here for you. Take a deep breath.";
            setMessage(aiResponse);
        } catch (err) {
            console.error('Quick support error:', err);
            setMessage("I'm having trouble connecting right now, but please know you're not alone. Try taking five deep breaths.");
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="fixed bottom-8 right-8 z-50">
            <AnimatePresence>
                {isOpen ? (
                    <motion.div
                        initial={{ opacity: 0, scale: 0.9, y: 20 }}
                        animate={{ opacity: 1, scale: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.9, y: 20 }}
                        className="bg-white/40 backdrop-blur-xl border border-white/40 w-80 md:w-96 rounded-[2.5rem] p-8 shadow-2xl origin-bottom-right"
                    >
                        <div className="flex justify-between items-center mb-6">
                            <div className="flex items-center gap-3">
                                <div className="w-10 h-10 rounded-2xl bg-primary flex items-center justify-center text-primary-foreground shadow-lg shadow-primary/20">
                                    <Sparkles size={20} />
                                </div>
                                <div>
                                    <h3 className="font-bold text-foreground text-sm">ELLA Instant Peace</h3>
                                    <div className="flex items-center gap-1">
                                        <span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" />
                                        <span className="text-[10px] text-muted-foreground font-bold uppercase tracking-wider">Always Online</span>
                                    </div>
                                </div>
                            </div>
                            <button
                                onClick={() => setIsOpen(false)}
                                className="p-2 hover:bg-muted/50 rounded-xl transition-colors text-muted-foreground"
                            >
                                <X size={20} />
                            </button>
                        </div>

                        <div className="mb-6 h-32 overflow-y-auto pr-2 scrollbar-thin">
                            {message ? (
                                <motion.div
                                    initial={{ opacity: 0 }}
                                    animate={{ opacity: 1 }}
                                    className="bg-white/60 p-5 rounded-2xl text-foreground/70 text-sm italic leading-relaxed shadow-sm border border-white/50"
                                >
                                    "{message}"
                                </motion.div>
                            ) : (
                                <p className="text-muted-foreground text-sm leading-relaxed">
                                    Feeling overwhelmed? Tell me how you're feeling right now, and I'll help you find a moment of peace.
                                </p>
                            )}
                        </div>

                        <form onSubmit={handleSeekSupport} className="relative">
                            <input
                                type="text"
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                placeholder="Ex: I feel anxious..."
                                className="w-full bg-white/50 border border-border/60 rounded-2xl px-5 py-4 text-sm focus:outline-none focus:ring-4 focus:ring-primary/10 transition-all pr-14 placeholder:text-muted-foreground/30"
                            />
                            <button
                                disabled={isLoading}
                                type="submit"
                                className="absolute right-2 top-2 p-3 bg-primary text-primary-foreground rounded-xl transition-all hover:bg-primary/90 disabled:opacity-50 shadow-md shadow-primary/10"
                            >
                                {isLoading ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
                            </button>
                        </form>
                    </motion.div>
                ) : (
                    <motion.button
                        whileHover={{ scale: 1.05 }}
                        whileTap={{ scale: 0.95 }}
                        onClick={() => setIsOpen(true)}
                        className="flex items-center gap-4 bg-white/40 backdrop-blur-md border border-white/40 pl-6 pr-4 py-4 rounded-full shadow-xl transition-all group"
                    >
                        <span className="text-sm font-bold text-foreground tracking-tight">Need immediate peace?</span>
                        <div className="w-12 h-12 bg-primary text-primary-foreground rounded-full flex items-center justify-center shadow-lg shadow-primary/10 group-hover:rotate-12 transition-transform">
                            <MessageCircle size={24} />
                        </div>
                    </motion.button>
                )}
            </AnimatePresence>
        </div>
    );
};

export default QuickSupport;
